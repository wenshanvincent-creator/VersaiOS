"""One fixed unlock attempt, without waiting for AirPlay or image recognition."""

import time
from pathlib import Path

import phone_keyboard
from phone_macro import run_steps


def unlock(phone):
    if not Path(__file__).with_name('phone_unlock_private.py').is_file():
        raise RuntimeError('Configure tools/phone_unlock_private.py locally before unlocking')
    from phone_unlock_private import PASSCODE

    if not (PASSCODE.isascii() and PASSCODE.isdigit() and len(PASSCODE) == 6):
        raise ValueError('Local unlock configuration must contain a six-digit numeric passcode')
    phone_keyboard.key(phone, 0x29)  # Escape, then Return: physical wake verified on iPhone 13 / iOS 26.
    time.sleep(.1)
    phone_keyboard.key(phone, 0x28)
    time.sleep(.15)
    commands = []
    run_steps(phone, 'unlock-menu', commands)
    run_steps(phone, 'unlock-home-action', commands)
    for digit in PASSCODE:
        phone_keyboard.text(phone, digit)
    return {'attempt_sent': True, 'passcode_keys_sent': True, 'device_acknowledged': True,
            'unlock_verified': False, 'method': 'fixed AssistiveTouch Home macro and keyboard',
            'verification': 'Check the physical phone or reconnect mirroring; do not repeat automatically'}
