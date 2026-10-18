"""Authenticated broker transport, without loading the MCP schema runtime."""

import json
import logging
import os
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / ".runtime/phone-broker.json"
logging.getLogger("httpx").setLevel(logging.WARNING)
_client = httpx.Client(timeout=httpx.Timeout(90, connect=5), trust_env=False)


def broker_state():
    import psutil

    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text("utf-8"))
        if psutil.pid_exists(state["pid"]):
            process = psutil.Process(state["pid"])
            if str(ROOT / "tools/phone_broker.py") in process.cmdline():
                return state
    raise RuntimeError("Phone service is stopped. Run phone-service.cmd on the connected Windows computer first")


def request(action, **args):
    bridge_config = os.environ.get("PHONE_BRIDGE_CONFIG")
    if bridge_config:
        state = json.loads(Path(bridge_config).read_text("utf-8"))
        url = state["url"]
    else:
        state = broker_state()
        url = f'http://127.0.0.1:{state["port"]}/'
    try:
        response = _client.post(url, headers={"Authorization": "Bearer " + state["token"]},
                              json={"action": action, "args": args})
    except httpx.TransportError as error:
        if bridge_config:
            if action == "status":
                return {"device_online": False, "mirror_connected": False,
                        "reason": "Windows phone bridge is offline; the computer and ESP32 must remain on"}
            raise RuntimeError("Windows phone bridge is offline; no phone action was confirmed") from error
        raise
    result = response.json()
    if response.status_code != 200:
        raise RuntimeError(result["error"])
    return result


def request_with_lease(action, owner, lease_token=None, **args):
    own_lease = lease_token is None
    if own_lease:
        lease_token = request('acquire', owner=owner)['lease_token']
    try:
        return request(action, lease_token=lease_token, **args)
    finally:
        if own_lease:
            request('release', lease_token=lease_token)
