import json
from pathlib import Path
import sys
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from phone_current_app import AppProbe


class CurrentAppTest(unittest.TestCase):
    def setUp(self):
        self.probe = AppProbe({'host': '127.0.0.1', 'port': 0, 'token': 'test-report-secret'})
        self.url = f'http://127.0.0.1:{self.probe.server.server_port}'
        self.headers = {'Authorization': 'Bearer test-report-secret'}

    def tearDown(self):
        self.probe.server.shutdown()
        self.probe.server.server_close()

    def test_authenticated_native_report_matches_query(self):
        def trigger():
            with urllib.request.urlopen(urllib.request.Request(self.url + '/request', headers=self.headers)) as response:
                nonce = json.load(response)['request_id']
            body = {'request_id': nonce, 'app_name': 'Calculator'}
            req = urllib.request.Request(self.url + '/report', data=json.dumps(body).encode(), headers=self.headers)
            with urllib.request.urlopen(req) as response:
                self.assertTrue(json.load(response)['accepted'])
        result = self.probe.query(trigger)
        self.assertEqual(result['app_name'], 'Calculator')
        self.assertIsNone(result['bundle_id'])
        self.assertFalse(result['cached'])
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.url + '/request')
        self.assertEqual(error.exception.code, 401)

    def test_missing_report_never_returns_previous_app(self):
        self.probe.query(lambda: self.probe.accept({'request_id': self.probe.pending,
                              'app_name': 'Settings', 'bundle_id': 'com.apple.Preferences'}))
        result = self.probe.query(lambda: None, timeout=0)
        self.assertFalse(result['available'])
        self.assertIsNone(result['app_name'])

    def test_late_report_from_an_old_query_cannot_complete_new_query(self):
        def trigger():
            self.assertFalse(self.probe.accept({'request_id': 'old-query', 'app_name': 'Old',
                                               'bundle_id': 'com.example.old'}))
        self.assertFalse(self.probe.query(trigger, timeout=0)['available'])


if __name__ == '__main__':
    unittest.main()
