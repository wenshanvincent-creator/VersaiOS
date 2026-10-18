"""Remember explicitly registered Home Screen icons and find them before opening."""

import base64
import json
from pathlib import Path


CATALOG = Path(__file__).resolve().parent.parent / '.runtime/phone-apps.json'


def catalog():
    return json.loads(CATALOG.read_text('utf-8')) if CATALOG.exists() else {}


def register(name, x, y, frame):
    import cv2
    if not name.strip() or len(name) > 60:
        raise ValueError('Provide an app name of 1-60 characters')
    height, width = frame.shape[:2]
    if not (24 <= x < width - 24 and 24 <= y < height - 24):
        raise ValueError('App icon must fit inside the screenshot')
    icon = frame[y-22:y+22, x-22:x+22]
    ok, png = cv2.imencode('.png', cv2.cvtColor(icon, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError('Could not save the app icon')
    apps = catalog()
    apps[name.casefold()] = {'name': name, 'icon': base64.b64encode(png).decode('ascii')}
    CATALOG.write_text(json.dumps(apps, ensure_ascii=False, indent=2), 'utf-8')
    return {'registered': name, 'apps': [a['name'] for a in apps.values()]}


def find(name, frame):
    import cv2
    import numpy as np
    app = catalog().get(name.casefold())
    if app is None:
        raise ValueError('App is not registered; use phone_register_app on the Home Screen first')
    icon = cv2.imdecode(np.frombuffer(base64.b64decode(app['icon']), np.uint8), cv2.IMREAD_COLOR)
    image = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    matches = cv2.matchTemplate(image, icon, cv2.TM_CCOEFF_NORMED)
    _, confidence, _, point = cv2.minMaxLoc(matches)
    if confidence < .92:
        raise RuntimeError('Registered app icon is not visible on this Home Screen; no icon was clicked')
    return point[0] + 22, point[1] + 22, round(confidence, 3)
