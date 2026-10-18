"""Run calibrated iPhone mouse macros without screenshots or a vision model."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import psutil

from phone_control import PhoneController
from start_receiver import ensure_receiver


ROOT = Path(__file__).resolve().parent.parent
PROFILE = json.loads((Path(__file__).with_name("phone_macros.json")).read_text("utf-8"))


def receiver_process():
    pid_file = ROOT / ".runtime/windows-receiver.pid"
    pid = int(pid_file.read_text("utf-8-sig"))
    process = psutil.Process(pid)
    expected = ROOT / ".runtime/uxplay-windows/uxplay-windows.exe"
    if Path(process.exe()) != expected:
        raise RuntimeError("Receiver PID belongs to another application; start the receiver first")
    return process


def mirror_connected(receiver):
    return any(c.status == psutil.CONN_ESTABLISHED and c.laddr.port == 7100
               and c.raddr for c in receiver.net_connections(kind="tcp"))


def run_steps(phone, name, commands, profile=None):
    if profile is None:
        profile = json.loads((Path(__file__).with_name("phone_macros.json")).read_text("utf-8"))
    for step in profile["macros"][name]:
        if "call" in step:
            run_steps(phone, step["call"], commands, profile)
            continue
        if "move" in step:
            command = "REL:" + ",".join(map(str, step["move"]))
        elif "drag" in step:
            command = "DRAG:" + ",".join(map(str, step["drag"]))
        else:
            command = step["press"]
        phone.send(command)
        commands.append(command)
        time.sleep(step["wait"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=list(PROFILE["macros"]) + ["status"])
    args = parser.parse_args()
    result = {"action": args.action, "started_at": datetime.now(timezone.utc).isoformat(),
              "vision_used": False, "commands": []}
    exit_code = 0
    try:
        receiver = ensure_receiver() if args.action == "mirror-connect" else (
            receiver_process() if args.action == "status" else None)
        if args.action == "status":
            result["mirror_connected"] = mirror_connected(receiver)
        elif args.action == "mirror-connect" and mirror_connected(receiver):
            result.update(mirror_connected=True, result="already_connected")
        else:
            with PhoneController() as phone:
                run_steps(phone, args.action, result["commands"])
                if args.action == "mirror-connect":
                    deadline = time.monotonic() + 12
                    while not mirror_connected(receiver) and time.monotonic() < deadline:
                        time.sleep(0.5)
                    if not mirror_connected(receiver):
                        raise RuntimeError("No AirPlay video connection after fixed device-selection steps")
                    result["mirror_connected"] = True
                    time.sleep(1.0)
                    run_steps(phone, "close-controls", result["commands"])
                    result["result"] = "connected"
                else:
                    result["result"] = "input_sequence_acknowledged"
                    if args.action == "hotspot-toggle":
                        result["hotspot_state"] = "not_observed; toggled, not an idempotent enable command"
    except (OSError, ValueError, RuntimeError, psutil.Error) as error:
        result.update(result="failed", error=str(error))
        exit_code = 1
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / ".runtime/macros"
    output.mkdir(parents=True, exist_ok=True)
    (output / "last-result.json").write_text(json.dumps(result, indent=2), "utf-8")
    print(json.dumps(result))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
