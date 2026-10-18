"""Start the configured Windows AirPlay receiver and Wi-Fi-specific BLE beacon."""

import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

import psutil


ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".runtime"
EXE = RUNTIME / "uxplay-windows/uxplay-windows.exe"
BLE_FILE = Path(os.environ["USERPROFILE"]) / "AppData/Roaming/leapbtw/uxplay-windows/uxplay_status.ble"


def ensure_receiver(video_converter=None, restart=False):
    profile = json.loads((ROOT / "tools/phone_macros.json").read_text("utf-8"))
    addresses = psutil.net_if_addrs()[profile["network_interface"]]
    wifi_ip = next(address.address for address in addresses if address.family == socket.AF_INET)
    running = [p for p in psutil.process_iter(["name", "exe"])
               if p.info["name"] == "uxplay-windows.exe" and p.info["exe"]
               and Path(p.info["exe"]) == EXE]
    if len(running) > 1:
        raise RuntimeError("Multiple receiver instances are running; close the duplicate first")
    if running and restart:
        old_receiver = running.pop()
        for child in reversed(old_receiver.children(recursive=True)):
            if child.name() == "uxplay-bluetooth-beacon.exe":
                child.terminate()
        old_receiver.terminate()
        old_receiver.wait(5)
    if running:
        receiver = running[0]
    else:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\leapbtw\uxplay-windows") as key:
            winreg.SetValueEx(key, "renderer_mode", 0, winreg.REG_SZ, "d3d11")
        BLE_FILE.parent.mkdir(parents=True, exist_ok=True)
        arguments = f'-n {profile["receiver_name"]} -nh -p 7100 -as 0 -avdec -vsync no -s 390x844'
        if video_converter:
            arguments += " -vc " + video_converter.replace(" ", "\t")
        (BLE_FILE.parent / "arguments.txt").write_text(arguments, "utf-8")
        env = dict(os.environ, GST_DEBUG="2", GST_DEBUG_NO_COLOR="1",
                   GST_DEBUG_FILE=str(RUNTIME / "gstreamer-receiver.log"),
                   GST_REGISTRY=str(RUNTIME / "windows-gst-registry.bin"))
        started = subprocess.Popen([str(EXE)], cwd=EXE.parent, env=env)
        receiver = psutil.Process(started.pid)
    (RUNTIME / "windows-receiver.pid").write_text(str(receiver.pid), "utf-8")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if BLE_FILE.exists():
            data = BLE_FILE.read_bytes()
            if len(data) >= 6 and struct.unpack_from("<I", data, 2)[0] == receiver.pid:
                break
        time.sleep(0.25)
    else:
        raise RuntimeError("Receiver did not publish its AirPlay discovery information")

    beacon_script = RUNTIME / "beacon/uxplay-beacon.py"
    beacon_pid_file = RUNTIME / "beacon.pid"
    own_beacon = None
    if beacon_pid_file.exists():
        beacon_pid = int(beacon_pid_file.read_text("utf-8-sig"))
        if psutil.pid_exists(beacon_pid):
            candidate = psutil.Process(beacon_pid)
            if str(beacon_script) in candidate.cmdline():
                own_beacon = candidate
    if own_beacon and wifi_ip not in own_beacon.cmdline():
        for child in reversed(own_beacon.children(recursive=True)):
            child.terminate()
        own_beacon.terminate()
        own_beacon.wait(3)
        own_beacon = None
    for child in reversed(receiver.children(recursive=True)):
        if child.name() == "uxplay-bluetooth-beacon.exe":
            child.terminate()
    if own_beacon is None:
        with (RUNTIME / "beacon.log").open("wb") as out, (RUNTIME / "beacon.err").open("wb") as err:
            beacon = subprocess.Popen(
                [sys.executable, "-u", str(beacon_script), "--path", str(BLE_FILE), "--ipv4", wifi_ip],
                cwd=ROOT, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
        beacon_pid_file.write_text(str(beacon.pid), "utf-8")
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            if beacon.poll() is not None:
                raise RuntimeError("BLE discovery exited; see .runtime/beacon.err and beacon.log")
            if "Publisher status change to: STARTED" in (RUNTIME / "beacon.log").read_text("utf-8"):
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("BLE discovery did not enter STARTED; see .runtime/beacon.log")
    # Discovery is published above. The mirror macro spends several seconds opening
    # Control Center and its receiver list before selection, so discovery can run
    # during those gestures instead of adding another fixed startup sleep.
    return receiver


if __name__ == "__main__":
    receiver = ensure_receiver()
    print(json.dumps({"receiver_pid": receiver.pid, "receiver_running": True}))
