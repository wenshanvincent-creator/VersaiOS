"""Regressions that could replay input, leak text, or hide already executed actions."""
import sys
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from phone_actions import ActionBatch
import phone_broker
import phone_client


class ActionsTest(unittest.TestCase):
    def broker(self):
        phone = phone_broker.Phone.__new__(phone_broker.Phone)
        phone.lock = threading.RLock()
        phone.owner, phone.lease, phone.expires = 'test', 'test-token', time.monotonic() + 30
        phone.connected = Mock(return_value=True)
        phone.video, phone.pointer = Mock(), Mock()
        return phone

    def test_invalid_later_action_prevents_all_input(self):
        broker = self.broker()
        for bad in ({'action': 'type_text', 'text': '\n'}, {'action': []},
                    {'action': 'macro', 'name': {}}, {'action': 'click', 'unknown': 1},
                    {'action': 'scroll', 'direction': 'sideways'},
                    {'action': 'scroll', 'direction': 'down', 'steps': True},
                    {'action': 'scroll', 'direction': 'down', 'steps': 25}):
            with self.subTest(bad=bad), patch('phone_broker.PhoneController') as controller:
                with self.assertRaises(ValueError):
                    broker.handle('run_actions', {'lease_token': 'test-token',
                                  'actions': [{'action': 'click'}, bad]})
                controller.assert_not_called()

    def test_list_scroll_uses_wheel_and_keeps_swipe_gestures(self):
        phone = Mock()
        result = ActionBatch([{'action': 'scroll', 'direction': 'down'},
                              {'action': 'scroll', 'direction': 'up', 'steps': 2},
                              {'action': 'swipe', 'dx': 0, 'dy': -120}]).run(phone, Mock())
        self.assertTrue(result['ok'])
        self.assertEqual([c.args[0] for c in phone.send.call_args_list],
                         ['SCROLL:4', 'SCROLL:-2', 'DRAG:0,-120'])

    def test_scroll_broker_validates_before_serial_and_requires_lease(self):
        broker = self.broker()
        with patch('phone_broker.PhoneController') as controller:
            with self.assertRaises(ValueError):
                broker.handle('scroll', {'lease_token': 'test-token', 'direction': 'down', 'steps': 0})
            with self.assertRaises(RuntimeError):
                broker.handle('scroll', {'lease_token': 'wrong', 'direction': 'down'})
            controller.assert_not_called()
            result = broker.handle('scroll', {'lease_token': 'test-token', 'direction': 'down', 'steps': 3})
            controller.return_value.__enter__.return_value.send.assert_called_once_with('SCROLL:3')
            self.assertFalse(result['visual_result_verified'])

    def test_partial_batch_stops_without_replaying_or_echoing_text(self):
        phone = Mock()
        phone.send.side_effect = [None, RuntimeError('keyboard disconnected')]
        result = ActionBatch([{'action': 'click'}, {'action': 'type_text', 'text': 'private'},
                              {'action': 'long_press'}]).run(phone, Mock())
        self.assertEqual(result['completed_count'], 1)
        self.assertEqual(result['failed_action_index'], 1)
        self.assertEqual(phone.send.call_count, 2)
        self.assertNotIn('private', str(result))
        self.assertFalse(result['retry_automatically'])

    def test_screenshot_failure_preserves_executed_batch(self):
        broker = self.broker()
        broker.video.snapshot.side_effect = RuntimeError('stream stopped')
        with patch('phone_broker.PhoneController') as controller:
            result = broker.handle('run_actions', {'lease_token': 'test-token',
                                   'actions': [{'action': 'click'}]})
        controller.return_value.__enter__.return_value.send.assert_called_once_with('TAP')
        self.assertEqual(result['completed_count'], 1)
        self.assertEqual(result['screen_error'], 'stream stopped')

    def test_open_failure_does_not_hide_unlock_attempt(self):
        broker = self.broker()
        with patch('phone_broker.PhoneController'), patch('phone_broker.time.sleep'), \
             patch('phone_broker.phone_unlocking.unlock', return_value={'attempt_sent': True}) as unlock, \
             patch('phone_broker.phone_keyboard.open_app', side_effect=RuntimeError('disconnected')):
            result = broker.handle('unlock_and_open_app', {'lease_token': 'test-token', 'name': 'Calculator'})
        unlock.assert_called_once()
        self.assertTrue(result['attempt_sent'])
        self.assertEqual(result['failed_stage'], 'open_app')
        self.assertFalse(result['retry_automatically'])

    def test_temporary_lease_released_on_failure_and_existing_lease_reused(self):
        with patch('phone_client.request', side_effect=[{'lease_token': 'temporary'}, RuntimeError('failed'), {}]) as request:
            with self.assertRaisesRegex(RuntimeError, 'failed'):
                phone_client.request_with_lease('run_actions', 'test', actions=[])
            self.assertEqual([c.args[0] for c in request.call_args_list], ['acquire', 'run_actions', 'release'])
        with patch('phone_client.request', return_value={'ok': True}) as request:
            phone_client.request_with_lease('run_actions', 'test', 'existing', actions=[])
            request.assert_called_once_with('run_actions', lease_token='existing', actions=[])


if __name__ == '__main__':
    unittest.main()
