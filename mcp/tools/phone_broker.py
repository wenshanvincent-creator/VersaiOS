"""Single local owner for the phone, serial input, and AirPlay frame pipe."""

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time

import psutil

from phone_control import PhoneController, device_port
from phone_coordinates import PixelPointer
import phone_apps
import phone_unlocking
import phone_keyboard
from phone_actions import ActionBatch
from phone_macro import mirror_connected, receiver_process, run_steps
from phone_video import PhoneVideo, video_converter
from start_receiver import ensure_receiver


ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / ".runtime/phone-broker.json"


class Phone:
    def __init__(self):
        self.lock = threading.RLock()
        self.video = PhoneVideo()
        self.pointer = PixelPointer(self.video)
        self.owner = None
        self.lease = None
        self.expires = 0
        self.receiver = None

    def connected(self):
        try:
            return mirror_connected(receiver_process())
        except (OSError, ValueError, RuntimeError, psutil.Error):
            return False

    def handle(self, action, args):
        with self.lock:
            if self.expires < time.monotonic():
                self.owner = self.lease = None
            if action == "status":
                return {"device": "iPhone 13 / iOS 26", "port": device_port(), "mirror_connected": self.connected(),
                        "video_pipe_connected": self.video.connected, "video_frame_id": self.video.frame_id,
                        "owner": self.owner, "lease_seconds_remaining": max(0, round(self.expires - time.monotonic()))
                        if self.owner else 0}
            if action == "acquire":
                if self.owner:
                    raise RuntimeError(f"Phone is in use by {self.owner}; wait for release or lease expiry")
                self.owner, self.lease = args["owner"], secrets.token_urlsafe(24)
                self.expires = time.monotonic() + 300
                return {"lease_token": self.lease, "owner": self.owner, "lease_seconds": 300}
            if not self.lease or not secrets.compare_digest(args.get("lease_token", ""), self.lease):
                raise RuntimeError("Acquire the phone first and pass your lease_token")
            self.expires = time.monotonic() + 300
            if action == "release":
                self.owner = self.lease = None
                return {"released": True}
            if action == "connect":
                if self.receiver is None or not self.receiver.is_running():
                    self.receiver = ensure_receiver(video_converter=video_converter(), restart=True)
                commands = []
                if not mirror_connected(self.receiver):
                    with PhoneController() as phone:
                        phone_keyboard.home(phone)
                        commands.append('KEY:8,11')
                        run_steps(phone, "mirror-connect", commands)
                        deadline = time.monotonic() + 12
                        while not mirror_connected(self.receiver) and time.monotonic() < deadline:
                            time.sleep(0.5)
                        if not mirror_connected(self.receiver):
                            raise RuntimeError("No AirPlay video connection after fixed mirror-connect steps")
                        time.sleep(1)
                        run_steps(phone, "close-controls", commands)
                _, screen = self.video.snapshot(10, after_frame=self.video.frame_id)
                return {"mirror_connected": True, "screen": screen, "commands": commands}
            if action == "screen":
                if not self.connected():
                    raise RuntimeError("No AirPlay connection; call phone_connect_screen first")
                picture, screen = self.video.snapshot()
                return {"screen": screen, "jpeg": base64.b64encode(picture).decode("ascii")}
            if action == "click_at":
                if not self.connected():
                    raise RuntimeError('Pixel clicking needs live mirroring; call phone_connect_screen first')
                started = time.monotonic()
                commands = []
                with PhoneController() as phone:
                    position = self.pointer.position(phone, args['x'], args['y'], commands)
                    command = 'LONG' if args.get('long_press', False) else 'TAP'
                    previous = self.video.frame_id
                    phone.send(command)
                    commands.append(command)
                time.sleep(1.2)  # Allow the app-opening animation to reach the AirPlay stream.
                picture, screen = self.video.snapshot(after_frame=previous)
                return {'pointer': position, 'commands': commands, 'device_acknowledged': True,
                        'visual_result_verified': False, 'elapsed_ms': round((time.monotonic()-started)*1000),
                        'screen': screen, 'jpeg': base64.b64encode(picture).decode('ascii')}
            if action == 'register_app':
                if not self.connected():
                    raise RuntimeError('App registration needs live mirroring')
                frame, _ = self.pointer.frame()
                return phone_apps.register(args['name'], args['x'], args['y'], frame)
            if action == 'open_app':
                started = time.monotonic()
                with PhoneController() as phone:
                    search_name = phone_keyboard.open_app(phone, args['name'])
                return {'app_name': args['name'], 'app_search': search_name,
                        'method': 'Home, Spotlight, type name, fixed first-result click',
                        'device_acknowledged': True, 'visual_result_verified': False,
                        'elapsed_ms': round((time.monotonic()-started)*1000)}
            if action == 'unlock':
                started = time.monotonic()
                with PhoneController() as phone:
                    result = phone_unlocking.unlock(phone)
                return {**result, 'elapsed_ms': round((time.monotonic()-started)*1000)}
            if action == 'unlock_and_open_app':
                name = phone_keyboard.app_search_name(args['name'])
                started = time.monotonic()
                result, stage = {}, 'unlock'
                with PhoneController() as phone:
                    try:
                        result = phone_unlocking.unlock(phone)
                        stage = 'open_app'
                        time.sleep(.35)
                        phone_keyboard.open_app(phone, name)
                    except (OSError, RuntimeError) as error:
                        return {**result, 'ok': False, 'failed_stage': stage, 'error': str(error),
                                'unlock_attempt_may_be_partial': True, 'retry_automatically': False,
                                'elapsed_ms': round((time.monotonic()-started)*1000)}
                return {**result, 'ok': True, 'app_name': args['name'], 'app_search': name,
                        'retry_automatically': False,
                        'visual_result_verified': False,
                        'elapsed_ms': round((time.monotonic()-started)*1000)}
            if action == 'run_actions':
                batch = ActionBatch(args['actions'])
                return_screen = args.get('return_screen', True)
                if type(return_screen) is not bool:
                    raise ValueError('return_screen must be a boolean')
                if (return_screen or batch.needs_screen) and not self.connected():
                    raise RuntimeError('Connect mirroring first, or use return_screen=false with no click_at actions; no input was sent')
                started = time.monotonic()
                with PhoneController() as phone:
                    result = batch.run(phone, self.pointer)
                result['elapsed_ms'] = round((time.monotonic()-started)*1000)
                if return_screen:
                    # An unavailable final image must not hide an already executed batch.
                    try:
                        previous = self.video.frame_id
                        picture, screen = self.video.snapshot(2, after_frame=previous)
                        result.update(screen=screen, jpeg=base64.b64encode(picture).decode('ascii'))
                    except RuntimeError as error:
                        result['screen_error'] = str(error)
                        result['retry_automatically'] = False
                return result
            commands = []
            with PhoneController() as phone:
                if action == "macro":
                    name = args["name"]
                    if name not in ("hotspot-toggle", "control-center", "network-menu", "mirror-menu", "close-controls"):
                        raise ValueError("Unknown macro; use phone_connect_screen for mirroring")
                    run_steps(phone, name, commands)
                else:
                    if action in ("move", "swipe"):
                        limit = 1000 if action == "swipe" else 4000
                        dx, dy = args["dx"], args["dy"]
                        if not all(isinstance(v, int) and abs(v) <= limit for v in (dx, dy)):
                            raise ValueError(f"dx and dy must be integers within +/-{limit} HID counts")
                        command = f"{'DRAG' if action == 'swipe' else 'REL'}:{dx},{dy}"
                    elif action in ("click", "long_press"):
                        command = "TAP" if action == "click" else "LONG"
                    else:
                        raise ValueError("Unknown phone action")
                    phone.send(command)
                    commands.append(command)
            return {"commands": commands, "device_acknowledged": True, "visual_result_verified": False}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + self.server.token):
            self.send_error(401)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 16384:
                raise ValueError("Request too large")
            request = json.loads(self.rfile.read(length))
            result = self.server.phone.handle(request["action"], request.get("args", {}))
            status = 200
        except (KeyError, OSError, ValueError, RuntimeError, psutil.Error) as error:
            status, result = 409, {"error": str(error)}
        data = json.dumps(result).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.token = secrets.token_urlsafe(32)
    server.phone = Phone()
    state = {"pid": os.getpid(), "port": server.server_port, "token": server.token}
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state), "utf-8")
    temporary.replace(STATE_FILE)
    server.serve_forever()
