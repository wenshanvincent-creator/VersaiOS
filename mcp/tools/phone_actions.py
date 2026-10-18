"""Validate an entire bounded action batch before any phone input, then stop on first failure."""

import time

import phone_keyboard
from phone_macro import run_steps
from phone_video import WIDTH, HEIGHT
from phone_scrolling import scroll_command


FIELDS = {
    'home': set(), 'open_app': {'name'}, 'type_text': {'text'},
    'move': {'dx', 'dy'}, 'swipe': {'dx', 'dy'}, 'click': set(),
    'long_press': set(), 'click_at': {'x', 'y'}, 'wait': {'ms'}, 'macro': {'name'},
    'key': {'usage'},
    'scroll': {'direction'},
}
MACROS = {'control-center', 'network-menu', 'close-controls', 'hotspot-toggle'}


class ActionBatch:
    def __init__(self, actions):
        if not isinstance(actions, list) or not 1 <= len(actions) <= 10:
            raise ValueError('Provide 1-10 actions per batch')
        self.steps = []
        characters, waiting = 0, 0
        for index, raw in enumerate(actions):
            if not isinstance(raw, dict) or not isinstance(raw.get('action'), str) or raw['action'] not in FIELDS:
                raise ValueError(f'Unknown action at index {index}')
            step = dict(raw)
            action = step['action']
            required = FIELDS[action] | {'action'}
            allowed = required | ({'long_press'} if action == 'click_at' else
                                  {'modifiers'} if action == 'key' else
                                  {'steps'} if action == 'scroll' else set())
            if not required <= step.keys() or step.keys() - allowed:
                raise ValueError(f'Incorrect fields for action {index}: {action}')
            if action in ('open_app', 'type_text'):
                field = 'name' if action == 'open_app' else 'text'
                if not isinstance(step[field], str):
                    raise ValueError(f'{field} must be a string at action {index}')
                if action == 'open_app':
                    step[field] = phone_keyboard.app_search_name(step[field])
                else:
                    phone_keyboard.validate_text(step[field])
                characters += len(step[field])
            elif action in ('move', 'swipe'):
                limit = 1000 if action == 'swipe' else 4000
                if any(type(step[k]) is not int or abs(step[k]) > limit for k in ('dx', 'dy')):
                    raise ValueError(f'{action} counts must be integers within +/-{limit}')
            elif action == 'click_at':
                if not (type(step['x']) is type(step['y']) is int and
                        12 <= step['x'] < WIDTH-12 and 12 <= step['y'] < HEIGHT-10):
                    raise ValueError('click_at coordinates must be inside the calibrated screenshot')
                if 'long_press' in step and type(step['long_press']) is not bool:
                    raise ValueError('long_press must be a boolean')
            elif action == 'wait':
                if type(step['ms']) is not int or not 0 <= step['ms'] <= 2000:
                    raise ValueError('Each wait must be 0-2000ms')
                waiting += step['ms']
            elif action == 'key':
                if type(step['usage']) is not int or not 1 <= step['usage'] <= 0x65:
                    raise ValueError('Key usage must be an integer 1-101')
                if type(step.get('modifiers', 0)) is not int or not 0 <= step.get('modifiers', 0) <= 255:
                    raise ValueError('Key modifiers must be an integer 0-255')
            elif action == 'scroll':
                scroll_command(step['direction'], step.get('steps', 4))
            elif action == 'macro' and (not isinstance(step['name'], str) or step['name'] not in MACROS):
                raise ValueError('Unsupported batch macro')
            self.steps.append(step)
        # Keep normal batches inside the existing 90-second broker transport timeout.
        if characters > 160 or waiting > 5000:
            raise ValueError('A batch allows at most 160 typed characters and 5000ms of explicit waits')
        self.needs_screen = any(step['action'] == 'click_at' for step in self.steps)

    def run(self, phone, pointer):
        results = []
        for index, step in enumerate(self.steps):
            action = step['action']
            started = time.monotonic()
            try:
                if action == 'home':
                    phone_keyboard.home(phone)
                elif action == 'open_app':
                    phone_keyboard.open_app(phone, step['name'])
                elif action == 'type_text':
                    phone_keyboard.text(phone, step['text'])
                elif action == 'key':
                    phone_keyboard.key(phone, step['usage'], step.get('modifiers', 0))
                elif action == 'scroll':
                    phone.send(scroll_command(step['direction'], step.get('steps', 4)))
                elif action in ('move', 'swipe'):
                    phone.send(f"{'REL' if action == 'move' else 'DRAG'}:{step['dx']},{step['dy']}")
                elif action in ('click', 'long_press'):
                    phone.send('TAP' if action == 'click' else 'LONG')
                elif action == 'click_at':
                    pointer.position(phone, step['x'], step['y'], [])
                    phone.send('LONG' if step.get('long_press', False) else 'TAP')
                elif action == 'wait':
                    time.sleep(step['ms']/1000)
                elif action == 'macro':
                    run_steps(phone, step['name'], [])
            except (OSError, RuntimeError, ValueError) as error:
                return {'ok': False, 'completed_count': len(results), 'results': results,
                        'failed_action_index': index, 'failed_action': action, 'error': str(error),
                        'retry_automatically': False,
                        'note': 'The failing action may have partially executed; later actions were not sent'}
            results.append({'index': index, 'action': action,
                            'elapsed_ms': round((time.monotonic()-started)*1000)})
        return {'ok': True, 'completed_count': len(results), 'results': results,
                'device_acknowledged': True, 'visual_result_verified': False}
