"""Receive request-correlated native Shortcuts app metadata, never screenshots."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
import time

CONFIG = Path(__file__).resolve().parents[1] / '.runtime/phone-current-app.json'


class AppProbe:
    def __init__(self, config):
        self.token = config['token']
        self.condition = threading.Condition()
        self.pending = None
        self.result = None
        self.server = ThreadingHTTPServer((config['host'], config['port']), ReportHandler)
        self.server.probe = self
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def query(self, trigger, timeout=6):
        started = time.monotonic()
        with self.condition:
            self.pending, self.result = secrets.token_urlsafe(18), None
        try:
            trigger()
            with self.condition:
                if not self.condition.wait_for(lambda: self.result is not None, timeout):
                    return {'available': False, 'app_name': None, 'bundle_id': None,
                            'reason': 'No fresh native app report; check the shortcut, button binding and Wi-Fi',
                            'source': 'iOS Shortcuts Get Current App', 'cached': False,
                            'elapsed_ms': round((time.monotonic()-started)*1000)}
                return {**self.result, 'available': bool(self.result['app_name']),
                        'source': 'iOS Shortcuts Get Current App', 'cached': False,
                        'elapsed_ms': round((time.monotonic()-started)*1000)}
        finally:
            with self.condition:
                self.pending = self.result = None

    def accept(self, value):
        required = {'request_id', 'app_name'}
        if not isinstance(value, dict) or not required <= value.keys() or value.keys()-required-{'bundle_id'}:
            raise ValueError('Expected request_id and app_name; bundle_id is optional')
        if not all(isinstance(v, str) for v in value.values()):
            raise ValueError('Report values must be strings')
        bundle_id = value.get('bundle_id', '')
        if len(value['app_name']) > 160 or len(bundle_id) > 255:
            raise ValueError('App metadata is too long')
        if bundle_id and not re.fullmatch(r'[A-Za-z0-9._-]+', bundle_id):
            raise ValueError('Invalid bundle identifier')
        with self.condition:
            if self.pending is None or not secrets.compare_digest(value['request_id'].encode('utf-8'), self.pending.encode('ascii')):
                return False
            self.result = {'app_name': value['app_name'] or None, 'bundle_id': bundle_id or None}
            self.condition.notify_all()
        return True


class ReportHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, value):
        data = json.dumps(value).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def authorized(self, suffix):
        expected = ('Bearer ' + self.server.probe.token).encode('ascii')
        return self.path == suffix and secrets.compare_digest(
            self.headers.get('Authorization', '').encode('utf-8'), expected)

    def do_GET(self):
        if not self.authorized('/request'):
            self.reply(401, {'error': 'Unauthorized'})
            return
        with self.server.probe.condition:
            request_id = self.server.probe.pending
        self.reply(200 if request_id else 409, {'request_id': request_id})

    def do_POST(self):
        if not self.authorized('/report'):
            self.reply(401, {'error': 'Unauthorized'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 2048:
                raise ValueError('Report body must be 1-2048 bytes')
            accepted = self.server.probe.accept(json.loads(self.rfile.read(length)))
            self.reply(200 if accepted else 409, {'accepted': accepted})
        except (ValueError, UnicodeError) as error:
            self.reply(400, {'error': str(error)})
