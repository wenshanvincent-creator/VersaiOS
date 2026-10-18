"""Compact output must retain failures and distinguish acknowledgement from UI proof."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import phone_mcp


class ResponseTest(unittest.TestCase):
    def test_success_omits_traces_but_preserves_evidence(self):
        original = {'ok': True, 'completed_count': 3, 'results': [{'action': 'home'}],
                    'commands': ['KEY:8,11'], 'device_acknowledged': True,
                    'visual_result_verified': False, 'elapsed_ms': 900}
        result = json.loads(phone_mcp.text_result(original)[0].text)
        self.assertNotIn('results', result)
        self.assertNotIn('commands', result)
        self.assertEqual(result['completed_count'], 3)
        self.assertFalse(result['visual_result_verified'])
        self.assertIn('results', original)

    def test_failures_keep_partial_progress_and_observation_errors(self):
        for failure in ({'ok': False, 'error': 'disconnected', 'retry_automatically': False},
                        {'ok': True, 'screen_error': 'stream stopped', 'retry_automatically': False}):
            original = {**failure, 'completed_count': 1, 'results': [{'action': 'click'}]}
            self.assertEqual(json.loads(phone_mcp.text_result(original)[0].text), original)

    def test_batch_default_does_not_request_screen(self):
        with patch('phone_mcp.request_with_lease', return_value={'ok': True}) as request:
            phone_mcp.phone_run_actions([{'action': 'home'}])
        self.assertFalse(request.call_args.kwargs['return_screen'])


if __name__ == '__main__':
    unittest.main()
