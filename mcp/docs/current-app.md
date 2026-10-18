# Optional native foreground-app identity

`phone_get_current_app(lease_token=None)` invokes a background iOS Shortcut using AssistiveTouch mouse Button 4 and waits for a fresh, correlated report. It returns the app's native Name without screenshots. It does not infer the app from the most recent launch command. The phone must be awake/unlocked, paired over BLE, and able to reach the Windows PC over the LAN. Locking, leaving Wi-Fi, or a missing report returns `available:false`; that alone does not identify the phone's state.

Create `.runtime/phone-current-app.json` **locally**, containing `host` (the PC's WLAN IPv4), `port` (8768), a fresh random `token`, and `ready:false`. Generate the token with Python `secrets.token_urlsafe(32)`. Keep this file out of Git and server deployments. Allow inbound reports only for the intended program, WLAN interface/address, port and local subnet. This is a separate report-only listener: the phone-control broker stays authenticated on loopback. Changing WLAN address requires updating this file, both Shortcut URLs and the firewall rule, then restarting the broker.

Create a Shortcut named **Phone Current App**, in this order:

1. **Get Contents of URL**: GET `http://<PC-WLAN-IPv4>:8768/request`. Add header `Authorization: Bearer <locally generated report token>`.
2. **Get Dictionary Value**: get `request_id` from the previous response.
3. **Get Current App**.
4. **Get Contents of URL**: POST `http://<PC-WLAN-IPv4>:8768/report`, with the same Authorization header and JSON body. Bind `request_id` to step 2's **Dictionary Value** magic variable. Bind `app_name` to step 3's **Current App** magic variable, using its **Name** property. Do not type variable names as literal text. `bundle_id` is optional; omit it if not available.

In iPhone AssistiveTouch → Devices → the paired mouse → Customize Additional Buttons, register Button 4 and select this Shortcut. The firmware command is `BUTTON:8` (button mask 8, not button number 8). The authenticated local broker provides an installation helper; while the phone is waiting for a device button, run the following from the `mcp` directory:

```python
import sys
sys.path.insert(0, "tools")
from phone_client import request

lease = request("acquire", owner="Configure current-app shortcut")["lease_token"]
try:
    request("current_app_setup", lease_token=lease, press_button=True)
finally:
    request("release", lease_token=lease)
```

After the Shortcut and button binding are complete, change local `ready` to `true`. Allow the Shortcut's first network access to this PC when prompted. A normal query starts the report listener before triggering the button. No cached result is returned when the current request times out; late reports from older requests cannot complete a newer query.

The report credential is stored locally and in the phone's Shortcut. Do not publish the configured Shortcut or report file. Source templates in this repository contain no actual credential, server address or device screenshot. The Linux adapter only forwards the tool call; it needs no report listener, passcode or local token file.

Observed on the calibrated iPhone 13: native reports identified Settings, Calculator and Settings, without an AirPlay connection. First use took 4645ms; subsequent local queries took 357–857ms. Optional bundle ID was not reported. These measurements exclude model/client latency, and reboot/Wi-Fi-return recovery has not been accepted on a clean installation.

Apple's action documentation: [Get Current App in Shortcuts](https://support.apple.com/en-au/121131).
