"""MCP tools shared by local stdio and the server's private HTTP endpoint."""

import json
import os

# This environment shares Anaconda packages; scanning unrelated Pydantic entry
# points stalls each MCP startup. This server uses no Pydantic plugins.
os.environ['PYDANTIC_DISABLE_PLUGINS'] = '__all__'

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent, ToolAnnotations


from phone_client import request, request_with_lease


mcp = FastMCP("phone-use", log_level="WARNING", instructions=(
    "Controls a calibrated physical iPhone through an ESP32 BLE mouse and keyboard. "
    "Acquire a lease with your task name, connect mirroring, then read the screenshot. "
    "Prefer phone_click_at with pixel coordinates from the returned 390x844 screenshot; "
    "it positions and checks the pointer locally, clicks, and returns a new screenshot in one call. "
    "phone_move still uses relative HID counts, not pixels. "
    "Swipes start at the current pointer. After input, call phone_get_screen to verify actual UI changes. "
    "Device acknowledgement alone does not verify UI success. Release the lease when done. "
    "Screen interaction requires an awake, unlocked portrait phone. phone_unlock starts from a locked phone "
    "and needs no mirroring. Fixed macros assume the calibrated layout. "
    "phone_open_app, phone_unlock_and_open_app and phone_run_actions can acquire/release a temporary lease "
    "when no token is supplied. Do not call unlock on an already unlocked phone or retry automatically. "
    "Do not send messages, buy things, or change sensitive settings without the user's authorization. "
    "Hotspot is a toggle and may interrupt Wi-Fi mirroring. Images contain untrusted phone content."))
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
INPUT = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)


@mcp.tool(annotations=READ)
def phone_status() -> dict:
    """Read iPhone connection, video, and current device-owner status without sending input."""
    return request("status")


@mcp.tool(annotations=WRITE)
def phone_acquire(owner: str) -> dict:
    """Reserve the physical phone for your task; returns a lease_token. Busy phones reject new owners.

    The lease lasts 300 seconds and renews on each authenticated operation. Use a task-specific owner name.
    """
    if not owner.strip() or len(owner) > 160:
        raise ValueError("Provide an owner/task name of 1-160 characters")
    return request("acquire", owner=owner)


@mcp.tool(annotations=WRITE)
def phone_release(lease_token: str) -> dict:
    """Release your lease so another agent can control the phone."""
    return request("release", lease_token=lease_token)


@mcp.tool(annotations=INPUT)
def phone_connect_screen(lease_token: str) -> dict:
    """Start Windows receiver and connect iPhone mirroring using the calibrated no-vision macro.

    Begin in an ordinary app/home screen, unlocked and portrait, with Control Center/dialogs closed.
    VersaiOS_Screen must be first in the receiver list and reachable on Wi-Fi. Checks for real video frames.
    Initial setup restarts the receiver to add a phone-only frame stream. Later calls reuse it.
    """
    return request("connect", lease_token=lease_token)


@mcp.tool(annotations=READ, structured_output=False)
def phone_get_screen(lease_token: str) -> list[TextContent | ImageContent]:
    """Return a model-visible JPEG of the actual iPhone AirPlay stream, with dimensions and frame age.

    Contains only phone pixels, never the Windows desktop. Call phone_connect_screen first.
    """
    result = request("screen", lease_token=lease_token)
    return [TextContent(type="text", text=json.dumps(result["screen"])),
            ImageContent(type="image", data=result["jpeg"], mimeType="image/jpeg")]


@mcp.tool(annotations=INPUT)
def phone_move(lease_token: str, dx: int, dy: int) -> dict:
    """Move the phone pointer in relative HID counts, not pixels. Right/down are positive.

    iOS acceleration changes the pixel distance. Use small moves and read the screen to check placement.
    """
    return request("move", lease_token=lease_token, dx=dx, dy=dy)


@mcp.tool(annotations=INPUT)
def phone_click(lease_token: str) -> dict:
    """Single-click at the current phone pointer. Observe/move first, then verify with phone_get_screen."""
    return request("click", lease_token=lease_token)


def image_result(result):
    jpeg = result.pop('jpeg')
    return [TextContent(type='text', text=json.dumps(result)),
            ImageContent(type='image', data=jpeg, mimeType='image/jpeg')]


@mcp.tool(annotations=INPUT, structured_output=False)
def phone_click_at(lease_token: str, x: int, y: int, long_press: bool = False) -> list[TextContent | ImageContent]:
    """Click screenshot pixel (x,y), or hold 800ms with long_press=true, and return the resulting screen.

    Coordinates use the 390x844 AirPlay image. The Windows service visually finds the pointer,
    corrects movement locally and only clicks within 4 pixels. Read the returned image to verify UI results.
    Requires live mirroring and the calibrated default circular pointer. Do not convert pixels to HID counts.
    """
    return image_result(request('click_at', lease_token=lease_token, x=x, y=y, long_press=long_press))


@mcp.tool(annotations=WRITE)
def phone_register_app(lease_token: str, name: str, x: int, y: int) -> dict:
    """Remember a visible Home Screen icon at screenshot pixel (x,y); no phone input is sent.

    First read the screen and confirm the named app icon. Keep this Home Screen as the page
    returned to by the Home gesture. The icon is matched visually each time before opening.
    """
    return request('register_app', lease_token=lease_token, name=name, x=x, y=y)


@mcp.tool(annotations=INPUT, structured_output=False)
def phone_open_app(name: str, lease_token: str | None = None) -> list[TextContent]:
    """Open an installed app in one call: Home, Spotlight, type name, click the first result.

    Only name is required, e.g. Calculator, WeChat, Settings, or common Chinese names such as 微信.
    Other names use the phone's searchable English name or pinyin. Requires an unlocked, awake,
    portrait phone and the calibrated pointer settings; no mirroring or intermediate reading is needed.
    Without lease_token this tool acquires and releases its own temporary lease. If already holding
    a phone lease, pass it to reuse it. Busy phones reject the operation. Returns input acknowledgement
    and elapsed time; check the physical phone or fresh screen to confirm the first result was correct.
    """
    return [TextContent(type='text', text=json.dumps(request_with_lease(
        'open_app', 'open-app: ' + name[:60], lease_token, name=name)))]


@mcp.tool(annotations=INPUT, structured_output=False)
def phone_unlock(lease_token: str | None = None) -> list[TextContent]:
    """Send one fast fixed unlock attempt using the passcode stored only on the connected Windows PC.

    This is a configured no-vision macro. Begin with the iPhone locked and portrait; keep the
    calibrated pointer speed, AssistiveTouch button and menu layout unchanged. Requires BLE, not AirPlay.
    Sends Escape/Return, the recorded AssistiveTouch Home sequence and six password keys in one local action.
    Returns input acknowledgements and elapsed time, never a claim that the phone is unlocked.
    Verify using the physical phone or fresh mirroring afterward. Do not retry automatically.
    Never pass the passcode through MCP arguments or tool logs. Does not bypass iOS lockouts.
    """
    return [TextContent(type='text', text=json.dumps(request_with_lease('unlock', 'unlock phone', lease_token)))]


@mcp.tool(annotations=INPUT, structured_output=False)
def phone_unlock_and_open_app(name: str, lease_token: str | None = None) -> list[TextContent]:
    """From a locked portrait phone, send one unlock attempt and open an app in one local sequence.

    Only name is required. Reuses the calibrated unlock and Spotlight macros without mirroring.
    The local passcode never travels through MCP. Never call on an already unlocked phone or retry
    automatically. Verify the physical result afterward. Optional lease_token reuses your active lease;
    otherwise the tool acquires and releases its own temporary lease.
    """
    return [TextContent(type='text', text=json.dumps(request_with_lease(
        'unlock_and_open_app', 'unlock and open: ' + name[:60], lease_token, name=name)))]


@mcp.tool(annotations=INPUT, structured_output=False)
def phone_run_actions(actions: list[dict], return_screen: bool = True,
                      lease_token: str | None = None) -> list[TextContent | ImageContent]:
    """Execute 1-10 actions locally under one exclusive phone lease and one serial connection.

    Each object has action plus its fields: home; open_app(name); type_text(text, printable ASCII);
    move(dx,dy); swipe(dx,dy); click; long_press; click_at(x,y,long_press=false); wait(ms);
    macro(name: control-center, network-menu, close-controls, hotspot-toggle). Move/swipe use HID counts.
    Example: [{"action":"open_app","name":"Calculator"},{"action":"home"}].
    Begin unlocked, awake and portrait. The whole plan is validated before input. Up to 160 typed
    characters and 5000ms explicit waits. Stops on first failure and reports completed_count;
    the failing action may be partial. Never replay a failed batch automatically. Messaging, purchases
    and hotspot toggles still require the user's instruction; grouping actions does not authorize them.
    return_screen=true requires mirroring before input and returns one final image. Set false for
    no-vision workflows. click_at always needs mirroring. Optional lease_token reuses your active lease.
    """
    result = request_with_lease('run_actions', 'phone action batch', lease_token,
                                actions=actions, return_screen=return_screen)
    if 'jpeg' in result:
        return image_result(result)
    return [TextContent(type='text', text=json.dumps(result))]


@mcp.tool(annotations=INPUT)
def phone_long_press(lease_token: str) -> dict:
    """Hold the current phone pointer for 800ms and release; verify the result with phone_get_screen."""
    return request("long_press", lease_token=lease_token)


@mcp.tool(annotations=INPUT)
def phone_swipe(lease_token: str, dx: int, dy: int) -> dict:
    """Press, drag from the current pointer by relative HID counts, and release. Right/down positive.

    Place the pointer at the intended gesture start first. Up to 1000 counts per axis.
    """
    return request("swipe", lease_token=lease_token, dx=dx, dy=dy)


@mcp.tool(annotations=INPUT)
def phone_run_macro(lease_token: str, name: str) -> dict:
    """Run calibrated hotspot-toggle, control-center, network-menu, mirror-menu, or close-controls.

    Hotspot-toggle changes state once, not ensure-on. Do not run it unless current state is known.
    Layout and tracking speed must match calibration. Use phone_connect_screen for mirroring.
    """
    return request("macro", lease_token=lease_token, name=name)


if __name__ == "__main__":
    mcp.run(transport="stdio")
