# iPhone MCP for VersaiOS

Windows + ESP32-S3 BLE keyboard/mouse + iPhone, exposed as MCP tools. Agents share one exclusive phone lease. Screenshots come from the decoded AirPlay stream, never from the Windows desktop. The extension does not call a separate vision model; the calling agent reads the returned JPEG.

中文：此扩展把手机投屏、读屏、点击、长按、滑动、固定解锁、搜索打开 App 和批量操作封装成 MCP。支持本机 agent，也可通过私有 SSH 桥接接入服务器；电脑和 ESP32 必须保持在线。固定宏目前按 iPhone 13 / iOS 26 校准，其他布局需重新录制。

## One-call workflows

### List scrolling

`phone_scroll(direction="down", steps=4)` sends native BLE mouse-wheel reports. It does not hold a mouse button or move the pointer. Put the pointer over the intended list first. `steps` is 1–24 wheel ticks, not pixels. On the calibrated iPhone, `down` reveals later rows and `up` reveals earlier rows; keep its scrolling-direction setting unchanged and verify polarity on other devices.

The ESP32 sketch now accepts `SCROLL:signed_ticks`; flash the updated **application firmware** before using this tool. The HID descriptor is unchanged from the composite keyboard/mouse version. `phone_swipe` remains a held-pointer gesture for other interactions, rather than serving as the default list-scrolling method.

Physical acceptance on 2026-10-18: Settings and AssistiveTouch lists scrolled in both directions, the pointer stayed in place, and no list items or toggles were clicked. Four ticks moved the observed list about 93 image pixels; this is an observation, not a fixed pixels-per-tick contract. The previous Control Center drag macro did **not** open Control Center during this session; automatic mirroring remains calibration-dependent and can require manual connection. This release does not claim to fix that macro.

### Fast app identity and concise results

`phone_get_current_app()` returns native iOS Shortcuts metadata without an AirPlay image or a last-opened-app guess. It is optional and requires one-time local configuration; see [native app identity setup](docs/current-app.md). A live cloud MCP query returned Calculator with 357ms local device time and 1052ms server-side MCP round trip; model/client latency is excluded.

`phone_run_actions` now defaults to `return_screen=False`. Request `True` when visual verification is needed, then inspect that returned image instead of requesting the same screen again. Successful responses omit serial/step traces but retain acknowledgement, verification state, completion count and total timing. Failure responses preserve partial progress and errors. These changes reduce payloads and unnecessary follow-up calls; no end-to-end model latency improvement is claimed.

```python
phone_open_app(name="Calculator")               # phone already unlocked
phone_unlock_and_open_app(name="Calculator")    # phone initially locked
phone_run_actions(actions=[
    {"action": "open_app", "name": "Calculator"},
    {"action": "home"},
    {"action": "open_app", "name": "Settings"}
], return_screen=False)
```

These tools acquire/release a temporary lease automatically. Pass your existing `lease_token` when a longer task already owns the phone. They reject requests while another agent owns it. Unlock sends **one attempt** using a passcode stored on the connected PC; it never accepts a passcode as an MCP argument. Start locked and portrait. Never retry unlock or a partially executed batch automatically.

## Setup on Windows

Tested hardware: ESP32-S3 N16R8, CH343 USB bridge, iPhone 13 / iOS 26. Python 3.11+ and Arduino ESP32 core **2.0.17**. Run commands from this `mcp` directory.

1. Create the Python environment:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements-mcp.txt
   ```

2. Install [ESP32-BLE-Combo](https://github.com/blackketter/ESP32-BLE-Combo) at commit `b25c1cb9dbff64374d2fd4ad307a184506eb9232`. Compile/upload `firmware/VersaiOS/VersaiOS.ino` with that library and ESP32 core 2.0.17; board/FQBN is recorded in `firmware/sources.json`. This composite keyboard/mouse sketch is separate from the original mouse-only sketch. When upgrading from mouse-only firmware, forget the old Bluetooth device and pair it again. Set the serial port in `firmware/sources.json` (`COM6` is only an example).

3. Enable iPhone **Settings → Accessibility → Touch → AssistiveTouch**. Pair `VersaiOS Mouse` in Settings → Bluetooth. Disable pointer animations and keep tracking speed fixed. To retain the phone's software keyboard while BLE keyboard is connected, enable **Show Onscreen Keyboard** in AssistiveTouch ([Apple instructions](https://support.apple.com/en-au/111775)).

4. For screenshots, download the pinned receiver and discovery scripts:

   ```powershell
   .\.venv\Scripts\python.exe tools/setup_receiver.py
   ```

   This only downloads/checks/extracts; it does not launch downloaded programs. It uses the official [uxplay-windows 2.0.0.1736 release](https://github.com/leapbtw/uxplay-windows/releases/tag/2.0.0.1736) and [UxPlay beacon source](https://github.com/FDH2/UxPlay/tree/4e95a9ec013c52d8555d88dbc55abe346e94d56e/Bluetooth_LE_beacon), with SHA-256 checks. Install/enable Bonjour as described by the receiver project. Keep PC and phone on the same Wi-Fi. In `tools/phone_macros.json`, change `network_interface` to your Windows Wi-Fi adapter name and choose `receiver_name`. The first receiver row must match this name for the fixed connection macro.

5. Review/calibrate `tools/phone_macros.json` before sending fixed macros. The included values are an **iPhone 13 example**, not universal coordinates. The unlock recording assumes the floating AssistiveTouch button at screenshot `(39,423)` and menu Home at `(158,499)`, portrait 390×844. Ordinary app launching assumes the first Spotlight result is the requested app. Use the phone's searchable English name/pinyin; common Chinese aliases are mapped in `phone_keyboard.py`.

6. Optionally copy `tools/phone_unlock_private.example.py` to `tools/phone_unlock_private.py` and enter your own six-digit passcode **locally**. That destination is ignored by Git. Leave it absent if unlock is not needed. Do not upload it to a server, connector, issue, or chat log.

7. Run `phone-service.cmd` from a normal Windows terminal. The independent broker listens only on loopback, authenticates requests, and stays separate from MCP client process lifetimes. Adapt `mcp.example.json` with absolute paths and add it to your MCP client. Start a new session/refresh tools after changes. The broker must be running before a client calls tools.

## Tools and units

| Tools | Behavior |
| --- | --- |
| `phone_status` | Connection and lease state; no input |
| `phone_acquire(owner)`, `phone_release(token)` | Shared exclusive lease, renewed for 300 seconds per operation |
| `phone_connect_screen(token)` | Start receiver and fixed mirroring macro; require actual new video frames |
| `phone_get_screen(token)` | Phone JPEG with dimensions, frame ID and age |
| `phone_move(token,dx,dy)` | Relative HID counts; right/down positive |
| `phone_click(token)`, `phone_long_press(token)` | Current pointer; hold 800ms for long press |
| `phone_swipe(token,dx,dy)` | Press/drag/release from current pointer; HID counts |
| `phone_scroll(direction,steps=4,lease_token=None)` | Wheel-only list scrolling; up/down navigation on the calibrated device |
| `phone_get_current_app(lease_token=None)` | Fresh native foreground-app Name, optional local Shortcut setup |
| `phone_click_at(token,x,y,long_press=False)` | Experimental local visual positioning in screenshot pixels; return image |
| `phone_register_app(token,name,x,y)` | Store a Home Screen icon template locally; no input |
| `phone_run_macro(token,name)` | Calibrated Control Center/network/hotspot macros |
| `phone_open_app(name,lease_token=None)` | Home → Spotlight → type name → first-result click |
| `phone_unlock(lease_token=None)` | One fixed unlock attempt |
| `phone_unlock_and_open_app(name,lease_token=None)` | Unlock and launch under one serial connection |
| `phone_run_actions(actions,return_screen=False,lease_token=None)` | Entire validated plan runs locally under one serial connection |

For visual tasks: status → acquire → connect_screen → get_screen → input → inspect one resulting image → release. `phone_click_at` and image-returning batches already supply that image. For a single fixed task, tools with optional leases manage their own lease without extra acquire/release calls. Once sufficient outcome evidence is available, answer briefly instead of adding diagnostics. Each agent uses its own lease. Do not run the old non-leasing `phone.cmd` CLI while an MCP task owns the phone.

Batch actions use `action` plus these fields: `home`; `open_app(name)`; `type_text(text)` (printable ASCII); `move(dx,dy)`; `swipe(dx,dy)`; `scroll(direction,steps=4)`; `key(usage,modifiers=0)`; `click`; `long_press`; `click_at(x,y,long_press=false)`; `wait(ms)`; `macro(name)`. Available batch macros: `control-center`, `network-menu`, `close-controls`, `hotspot-toggle`. Maximum 10 actions, 160 typed characters, 2000ms per wait / 5000ms total explicit waits. The full plan is validated before any input. Execution stops at the first failure; `completed_count` covers only completed actions, and the failing action may be partial. Never replay a failed batch automatically.

`return_screen=True` requires mirroring before input. It returns one final fresh image; if that image is unavailable after execution, the result preserves completed actions and adds `screen_error`. `return_screen=False` needs no mirroring unless a `click_at` action is present. Mouse counts are **not pixels**. Hotspot is a **toggle**, may break mirroring, and cannot be called an idempotent enable operation. Batching does not authorize messages, purchases or other actions on its own.

## Private cloud connection

The Linux adapter needs only `tools/phone_mcp.py`, `tools/phone_client.py`, `tools/phone_remote_server.py` and `requirements-server.txt`. Keep all firmware access, passcodes, frame capture and calibration on Windows.

Use an authenticated private SSH reverse forward from a server loopback port to the current Windows broker port (read `.runtime/phone-broker.json` locally). On Linux, set `PHONE_BRIDGE_CONFIG` to a private JSON file containing `{"url":"http://127.0.0.1:18765/","token":"<broker token>"}`. The broker token must be transferred over the private connection, not as a public URL or command-line argument. A bridge supervisor must update this file/reconnect whenever the broker restarts and changes port/token. Keep file permissions restricted to the service account.

For HTTP MCP, set `PHONE_MCP_TOKEN_FILE` to a private server-side Bearer token file and run `phone_remote_server.py` using the server virtual environment; it listens only on `127.0.0.1:8766/mcp`. Route a private authenticated tunnel/connector to it. For stdio MCP, run `phone_mcp.py` with `PHONE_BRIDGE_CONFIG` set. The original private deployment scripts are deliberately excluded because they depend on one person's server/account configuration. This public package provides the adapter, not a preconfigured hosted endpoint. Windows must stay powered on and connected for either mode.

## Verification and limits

2026-10-18, existing calibrated iPhone 13 / iOS 26 / ESP32-S3 N16R8:

- `phone_run_actions`: a real MCP call completed Calculator → Home → Settings in **9497ms**; device owner confirmed Settings on the physical phone. Show Onscreen Keyboard was enabled.
- `phone_unlock_and_open_app("Calculator")`: one local broker call completed in **9657ms**; owner confirmed physical unlock and Calculator, with phone face down to avoid Face ID.
- Focused regression tests cover wheel-vs-drag routing, wheel input validation and leases, batch preflight/partial progress, final-image failures, compact result evidence, and request-correlated native app metadata. Physical observations and software checks are separate evidence.
- Earlier fixed unlock/open-app macros were physically confirmed. Experimental pixel clicking passed selected static targets, not general menus/animations. Do not claim broad pixel-click reliability or other iPhone layouts based on this release.

The numbers above measure local device execution, **not full cloud round-trip latency**. Batch grouping removes repeated network/model turns; it does not accelerate iOS animations or each BLE report. The tools return input acknowledgements, not proof of UI success. A locked/black physical display may leave the last AirPlay image frozen; check the actual device or an appropriate fresh UI transition. No unlock retries or iOS lockout bypasses are implemented.

The release package was checked separately from the private installation; it is not a clean-machine hardware acceptance test. Run focused software checks on Windows with `.venv/Scripts/python.exe -m unittest discover -s tests -v`.

## Attribution

Built on [VersaiOS](https://github.com/zhaodashuaibi/VersaiOS), commit `5619a233a124df80b01477239d2bc60797c41998`. The original README and GUI remain intact. Firmware provenance is in `firmware/sources.json`; the extension uses the composite library rather than replacing upstream's mouse-only sketch. See [THIRD_PARTY.md](THIRD_PARTY.md). New original MCP code is under [MIT](LICENSE); third-party projects retain their own notices and licenses.
