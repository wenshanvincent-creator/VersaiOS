"""Start the shared phone service outside any MCP client's process/job tree."""

import json
from pathlib import Path
import subprocess
import sys
import time

import psutil
import win32api
import win32event


ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / ".runtime/phone-broker.json"
BROKER = ROOT / "tools/phone_broker.py"


def running_service():
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text("utf-8"))
        if psutil.pid_exists(state["pid"]) and str(BROKER) in psutil.Process(state["pid"]).cmdline():
            return state
    return None


def main():
    mutex = win32event.CreateMutex(None, False, r"Local\PhoneUseBrokerStartup")
    if win32event.WaitForSingleObject(mutex, 20000) != win32event.WAIT_OBJECT_0:
        win32api.CloseHandle(mutex)
        raise RuntimeError("Phone service startup is busy")
    try:
        state = running_service()
        if state:
            return {"running": True, "pid": state["pid"], "started": False}
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with (ROOT / ".runtime/phone-broker.log").open("ab") as log:
            process = subprocess.Popen([sys.executable, str(BROKER)], cwd=ROOT,
                                       stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            state = running_service()
            if state:
                return {"running": True, "pid": state["pid"], "started": True}
            if process.poll() is not None:
                raise RuntimeError("Phone service exited; see .runtime/phone-broker.log")
            time.sleep(0.25)
        raise RuntimeError("Phone service did not become ready within 20 seconds")
    finally:
        win32event.ReleaseMutex(mutex)
        win32api.CloseHandle(mutex)


if __name__ == "__main__":
    print(json.dumps(main()))
