"""Local visual pointer positioning in the 390x844 AirPlay image."""

import io
import math
import time

from PIL import Image
from phone_video import WIDTH, HEIGHT


def moved_circles(before, after, min_change=.35, neutral=True):
    """Find cursor-sized circles whose pixels actually changed after mouse input."""
    import cv2
    import numpy as np
    # On the light lock-screen wallpaper the translucent cursor changes pixels
    # by only about 20 levels; 24 misses the actual cursor in captured frames.
    changed = cv2.absdiff(before, after).max(axis=2) > 12
    if changed.mean() > .3:
        raise RuntimeError('Phone UI changed during pointer positioning; no click was sent')
    gray = cv2.cvtColor(after, cv2.COLOR_RGB2GRAY)
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 14,
                               param1=60, param2=14, minRadius=8, maxRadius=12)
    found = []
    if circles is not None:
        yy, xx = np.ogrid[:gray.shape[0], :gray.shape[1]]
        for x, y, radius in circles[0]:
            disk = (xx - x) ** 2 + (yy - y) ** 2 < radius ** 2
            center = after[(xx - x) ** 2 + (yy - y) ** 2 < 6 ** 2]
            # The blue AirPlay status pill also has moving, cursor-sized ends.
            # The configured pointer is neutral, even when it overlaps an icon.
            color = center.mean(axis=0)
            if changed[disk].mean() > min_change and (not neutral or color.max()-color.min() < 45):
                found.append((float(x), float(y)))
    return found


class PixelPointer:
    def __init__(self, video):
        self.video = video
        self.gain = 1.7

    def frame(self, after_frame=None):
        import numpy as np
        jpeg, info = self.video.snapshot(after_frame=after_frame)
        return np.array(Image.open(io.BytesIO(jpeg)).convert('RGB')), info

    def move(self, phone, dx, dy, commands):
        command = f'FINE:{dx},{dy}'
        previous = self.video.frame_id
        phone.send(command)
        commands.append(command)
        self.video.snapshot(after_frame=previous)
        time.sleep(.4)

    def locate(self, phone, commands):
        # Fixed macros leave the cursor partly outside the bottom edge. Bring it
        # to a known corner, then fully into the image before fitting its circle.
        previous = self.video.frame_id
        phone.send('REL:-1200,-2400')
        commands.append('REL:-1200,-2400')
        self.video.snapshot(after_frame=previous)
        time.sleep(.4)
        before, _ = self.frame()
        self.move(phone, 160, 160, commands)
        after, _ = self.frame()
        points = [p for p in moved_circles(before, after) if 12 < p[0] < WIDTH - 12 and 12 < p[1] < HEIGHT - 12]
        if len(points) != 1:
            from pathlib import Path
            diagnostic = Path(__file__).resolve().parent.parent / '.runtime'
            Image.fromarray(before).save(diagnostic / 'pointer-before.png')
            Image.fromarray(after).save(diagnostic / 'pointer-after.png')
            raise RuntimeError('Cannot uniquely locate the phone pointer; no click was sent')
        point = points[0]
        self.gain = (point[0] + point[1]) / 320
        return after, point

    def position(self, phone, x, y, commands):
        if not (isinstance(x, int) and isinstance(y, int) and
                12 <= x < WIDTH - 12 and 12 <= y < HEIGHT - 10):
            raise ValueError(f'Pixel target must be inside x=12..{WIDTH-13}, y=12..{HEIGHT-11}')
        before, point = self.locate(phone, commands)
        for _ in range(7):
            error = (x - point[0], y - point[1])
            if math.hypot(*error) <= 4:
                return {'x': point[0], 'y': point[1], 'target_x': x, 'target_y': y,
                        'error_px': round(math.hypot(*error), 2)}
            dx, dy = [max(-400, min(400, round(e / self.gain * .85))) for e in error]
            if dx == dy == 0:
                raise RuntimeError('Pointer cannot reach the requested pixel; no click was sent')
            predicted = (point[0] + dx * self.gain, point[1] + dy * self.gain)
            self.move(phone, dx, dy, commands)
            after, _ = self.frame()
            # Final corrections move only a few pixels, changing a thin crescent.
            candidates = moved_circles(before, after, min_change=.1)
            if not candidates:
                # When iOS absorbs the pointer into a blue action icon, accept
                # its center only when it is already within the target tolerance.
                candidates = [p for p in moved_circles(before, after, min_change=.1, neutral=False)
                              if math.dist(p, (x, y)) <= 4]
            candidates = [p for p in candidates if math.dist(p, predicted) < max(55, math.hypot(dx, dy) * .75)]
            if len(candidates) != 1:
                from pathlib import Path
                diagnostic = Path(__file__).resolve().parent.parent / '.runtime'
                Image.fromarray(before).save(diagnostic / 'pointer-before.png')
                Image.fromarray(after).save(diagnostic / 'pointer-after.png')
                raise RuntimeError(f'Pointer position became ambiguous: expected {predicted}, observed {candidates}; no click was sent')
            moved = math.dist(point, candidates[0])
            counts = math.hypot(dx, dy)
            if moved > 3 and counts:
                self.gain = moved / counts
            point, before = candidates[0], after
        raise RuntimeError('Pointer did not reach the target within 4 pixels; no click was sent')
