"""Run the local unlock script through the shared phone lease."""

from phone_client import request


if __name__ == '__main__':
    lease = request('acquire', owner='local phone-unlock script')['lease_token']
    try:
        result = request('unlock', lease_token=lease)
        print({key:value for key,value in result.items() if key != 'jpeg'})
    finally:
        request('release', lease_token=lease)
