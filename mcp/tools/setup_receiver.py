"""Download the pinned receiver and discovery sources; do not execute downloaded software."""
import hashlib
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELEASE = 'https://github.com/leapbtw/uxplay-windows/releases/download/2.0.0.1736/uxplay-windows.zip'
BEACON = 'https://raw.githubusercontent.com/FDH2/UxPlay/4e95a9ec013c52d8555d88dbc55abe346e94d56e/Bluetooth_LE_beacon/'
FILES = [
    (RELEASE, '.runtime/uxplay-windows.zip', '9d3a51c15fc9db857351195e7eb7bbb21700d9ae25d936a54bcf8536b62cca18'),
    (BEACON + 'uxplay-beacon.py', '.runtime/beacon/uxplay-beacon.py', 'ccb2f00316148d091f2921c0ac07547e2c455c43cb0d2daf851437aced2e9d68'),
    (BEACON + 'uxplay_beacon_module_winrt.py', '.runtime/beacon/uxplay_beacon_module_winrt.py', '79e0e84e3994cf209345dbd7fa71971c67689873bc1f18816a773be65ea1a9ca'),
]


def main():
    for url, name, digest in FILES:
        target = ROOT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise RuntimeError('Checksum mismatch: ' + name)
            target.write_bytes(data)
        print('Verified ' + name)
    destination = ROOT / '.runtime/uxplay-windows'
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(ROOT / '.runtime/uxplay-windows.zip') as archive:
        for member in archive.infolist():
            resolved = (destination / member.filename).resolve()
            if not resolved.is_relative_to(destination.resolve()):
                raise RuntimeError('Archive path outside receiver directory')
        archive.extractall(destination)
    if not (destination / 'uxplay-windows.exe').is_file():
        raise RuntimeError('Expected receiver executable at .runtime/uxplay-windows/uxplay-windows.exe')
    print('Receiver prepared. Install/enable Bonjour and configure phone_macros.json before starting.')


if __name__ == '__main__':
    main()
