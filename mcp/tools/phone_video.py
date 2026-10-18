"""Receive only the AirPlay RGB stream; never capture the Windows desktop."""

import io
import threading
import time

from PIL import Image
import pywintypes
import win32file
import win32pipe


WIDTH, HEIGHT = 390, 844
STRIDE = (WIDTH * 3 + 3) & ~3
PIPE_NAME = r"\\.\pipe\PhoneUseFrames"
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000


def video_converter():
    # Qt splits arguments on spaces; tabs preserve one GStreamer pipeline argument.
    location = PIPE_NAME.replace("\\", "\\\\")
    return (f'videoconvert ! videoscale ! video/x-raw,format=RGB,width={WIDTH},height={HEIGHT},'
            'pixel-aspect-ratio=1/1 ! tee name=phone_frames ! queue leaky=downstream max-size-buffers=2 '
            f'! filesink location="{location}" sync=false buffer-mode=unbuffered '
            'phone_frames. ! queue ! videoconvert')


class PhoneVideo:
    def __init__(self):
        self.condition = threading.Condition()
        self.frame = None
        self.frame_id = 0
        self.received_at = 0.0
        self.connected = False
        self.error = None
        self.ready = threading.Event()
        threading.Thread(target=self._read, daemon=True).start()
        if not self.ready.wait(3):
            raise RuntimeError("Phone video pipe did not start")
        if self.error:
            raise RuntimeError(self.error)

    def _read(self):
        try:
            pipe = win32pipe.CreateNamedPipe(
                PIPE_NAME, win32pipe.PIPE_ACCESS_INBOUND | FILE_FLAG_FIRST_PIPE_INSTANCE,
                win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_WAIT, 1, 0, 4 * 1024 * 1024, 0, None)
        except pywintypes.error as error:
            self.error = str(error)
            self.ready.set()
            return
        self.ready.set()
        while True:
            try:
                try:
                    win32pipe.ConnectNamedPipe(pipe, None)
                except pywintypes.error as error:
                    if error.winerror != 535:  # Client connected before ConnectNamedPipe.
                        raise
                with self.condition:
                    self.connected = True
                    self.frame = None
                pending = bytearray()
                size = STRIDE * HEIGHT
                while True:
                    _, data = win32file.ReadFile(pipe, 1024 * 1024)
                    pending.extend(data)
                    while len(pending) >= size:
                        frame = bytes(pending[:size])
                        del pending[:size]
                        with self.condition:
                            self.frame = frame
                            self.frame_id += 1
                            self.received_at = time.monotonic()
                            self.condition.notify_all()
            except pywintypes.error as error:
                if error.winerror not in (109, 232):
                    self.error = str(error)
                    return
            finally:
                with self.condition:
                    self.connected = False
                    self.frame = None
                win32pipe.DisconnectNamedPipe(pipe)

    def snapshot(self, timeout=5, after_frame=None):
        deadline = time.monotonic() + timeout
        with self.condition:
            while (self.frame is None or (after_frame is not None and self.frame_id <= after_frame)) and time.monotonic() < deadline:
                self.condition.wait(deadline - time.monotonic())
            if self.frame is None or (after_frame is not None and self.frame_id <= after_frame):
                raise RuntimeError("No phone video frame; connect mirroring first. " + (self.error or ""))
            age = time.monotonic() - self.received_at
            if age > 10:
                raise RuntimeError(f"Phone video frame is stale ({age:.1f}s); reconnect mirroring")
            frame, frame_id = self.frame, self.frame_id
        picture = Image.frombytes("RGB", (WIDTH, HEIGHT), frame, "raw", "RGB", STRIDE)
        image = io.BytesIO()
        picture.save(image, "JPEG", quality=90)
        return image.getvalue(), {"width": WIDTH, "height": HEIGHT, "frame_id": frame_id,
                                  "age_ms": round(age * 1000), "source": "iPhone AirPlay RGB stream"}
