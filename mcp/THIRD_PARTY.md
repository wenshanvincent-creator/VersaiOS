# Third-party sources

- VersaiOS: https://github.com/zhaodashuaibi/VersaiOS at `5619a233a124df80b01477239d2bc60797c41998`. Original README declares MIT. `firmware/VersaiOS/VersaiOS.ino` derives from its `hardware/esp32_ble_mouse/VersaiOS.ino`; keep this attribution with redistributions. The original upstream tree is preserved in this fork.
- ESP32-BLE-Combo: https://github.com/blackketter/ESP32-BLE-Combo at `b25c1cb9dbff64374d2fd4ad307a184506eb9232`, building on T-vK's ESP32 BLE keyboard/mouse projects. Library source is not vendored here; follow its upstream notices when obtaining it.
- uxplay-windows: https://github.com/leapbtw/uxplay-windows, release `2.0.0.1736`. Downloaded separately from its official release; not redistributed in this extension. Preserve licenses bundled with the distribution.
- UxPlay Bluetooth beacon: https://github.com/FDH2/UxPlay at `4e95a9ec013c52d8555d88dbc55abe346e94d56e`. The separately downloaded beacon Python files carry `LGPL-2.1-or-later` headers, copyright F. Duncanh. `setup_receiver.py` downloads unmodified files with recorded hashes; they stay in the ignored local runtime directory.
- Python/Arduino packages retain their upstream licenses; dependency source and build artifacts are not included in this extension.

The extension's MIT license covers its original code, not a relicensing of upstream code or external dependencies.
