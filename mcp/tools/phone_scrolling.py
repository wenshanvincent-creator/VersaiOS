"""List scrolling uses wheel reports; DRAG remains reserved for pointer gestures."""


def scroll_command(direction, steps=4):
    if direction not in ('up', 'down'):
        raise ValueError('Scroll direction must be up or down')
    if type(steps) is not int or not 1 <= steps <= 24:
        raise ValueError('Scroll steps must be an integer 1-24')
    # Calibrated on this iPhone: positive wheel ticks reveal later rows.
    # Expose viewport navigation, not the raw mouse-wheel sign.
    return f'SCROLL:{steps if direction == "down" else -steps}'
