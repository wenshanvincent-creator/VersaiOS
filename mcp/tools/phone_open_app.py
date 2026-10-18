"""Open an installed app through the same exclusive phone service as MCP."""

import argparse
import json

from phone_client import request


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name', nargs='+')
    args = parser.parse_args()
    name = ' '.join(args.name)
    lease = request('acquire', owner='local open-app: ' + name[:60])['lease_token']
    try:
        print(json.dumps(request('open_app', lease_token=lease, name=name)))
    finally:
        request('release', lease_token=lease)
