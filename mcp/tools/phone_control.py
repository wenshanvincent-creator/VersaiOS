"""Send one BLE mouse action; the acknowledgement is not screen verification."""

import argparse
import json
from pathlib import Path
import time

import serial


def device_port():
    root = Path(__file__).resolve().parent.parent
    return json.loads((root / 'firmware/sources.json').read_text('utf-8'))['device_identified']['port']


def exchange(connection, command, acknowledgement):
    connection.write((command + "\n").encode("utf-8"))
    received = bytearray()
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        received.extend(connection.read(connection.in_waiting or 1))
        reply = received.decode("utf-8", errors="replace")
        if acknowledgement in reply:
            return reply.strip()
    if command.startswith('KEY:'):
        raise RuntimeError('No device acknowledgement for keyboard input')
    raise RuntimeError(f"No device acknowledgement for {command!r}: {reply!r}")


class PhoneController:
    def __init__(self):
        self.connection = serial.Serial(baudrate=115200, timeout=0.1)
        self.connection.port = device_port()
        # Keep reset lines deasserted when opening the CH343 bridge.
        self.connection.dtr = False
        self.connection.rts = False

    def __enter__(self):
        self.connection.open()
        self.connection.reset_input_buffer()
        exchange(self.connection, "REL:0,0", "纯相对移动")
        return self

    def __exit__(self, *_):
        self.connection.close()

    def send(self, command):
        acknowledgements = {
            "REL": "纯相对移动", "TAP": "原地点击完成",
            "LONG": "长按完成", "DRAG": "拖动完成",
            "FINE": "精细移动完成",
            "KEY": "按键完成",
        }
        return exchange(self.connection, command, acknowledgements[command.split(":")[0]])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    move = actions.add_parser("move")
    move.add_argument("dx", type=int)
    move.add_argument("dy", type=int)
    actions.add_parser("tap")
    actions.add_parser("long-press")
    drag = actions.add_parser("drag")
    drag.add_argument("dx", type=int)
    drag.add_argument("dy", type=int)
    args = parser.parse_args()

    if args.action == "tap":
        command = "TAP"
    elif args.action == "long-press":
        command = "LONG"
    else:
        command = f"{'DRAG' if args.action == 'drag' else 'REL'}:{args.dx},{args.dy}"
    with PhoneController() as phone:
        reply = phone.send(command)
        print(json.dumps({"command": command, "device_acknowledgement": reply}))


if __name__ == "__main__":
    main()
