"""A healthy static stream must not wait for a second frame after connection."""
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import phone_broker


class MirrorConnectionTest(unittest.TestCase):
    def broker(self):
        phone = phone_broker.Phone.__new__(phone_broker.Phone)
        phone.lock = threading.RLock()
        phone.owner, phone.lease, phone.expires = 'test', 'test-token', time.monotonic()+30
        phone.receiver = Mock()
        phone.receiver.is_running.return_value = True
        phone.video = Mock(frame_id=12)
        return phone

    def test_connected_static_stream_reuses_frame_without_input(self):
        phone = self.broker()
        def snapshot(timeout, after_frame=None):
            if after_frame is not None:
                raise RuntimeError('Static screen has no newer frame')
            return b'', {'frame_id': 12}
        phone.video.snapshot.side_effect = snapshot
        with patch('phone_broker.PhoneController') as controller, \
             patch('phone_broker.mirror_connected', return_value=True):
            result = phone.handle('connect', {'lease_token': 'test-token'})
        controller.assert_not_called()
        self.assertEqual(result['commands'], [])
        self.assertEqual(result['screen']['frame_id'], 12)

    def test_new_connection_accepts_new_frame_received_during_sequence(self):
        phone = self.broker()
        macros = []
        def run_steps(controller, name, commands):
            macros.append(name)
            phone.video.frame_id = 13
        def snapshot(timeout, after_frame=None):
            if after_frame != 12:
                raise RuntimeError('No second frame after the UI became static')
            return b'', {'frame_id': 13}
        phone.video.snapshot.side_effect = snapshot
        with patch('phone_broker.PhoneController'), patch('phone_broker.phone_keyboard.home'), \
             patch('phone_broker.mirror_connected', side_effect=[False, True, True]), \
             patch('phone_broker.run_steps', side_effect=run_steps), patch('phone_broker.time.sleep'):
            result = phone.handle('connect', {'lease_token': 'test-token'})
        self.assertEqual(macros, ['mirror-connect', 'mirror-close'])
        self.assertEqual(result['screen']['frame_id'], 13)


if __name__ == '__main__':
    unittest.main()
