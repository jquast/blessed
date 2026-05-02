#!/usr/bin/env python
"""Classic game of tennis."""

# std imports
from math import floor

# local
from blessed import Terminal


def roundxy(x, y):
    return int(floor(x)), int(floor(y))


term = Terminal()

x, y, xs, ys = 2, 2, 0.4, 0.3
with term.cbreak(), term.hidden_cursor():
    # clear the screen
    print(term.home + term.black_on_olivedrab4 + term.clear)

    # loop every 20ms
    while term.inkey(timeout=0.02) != 'q':
        # erase,
        txt_erase = term.move_xy(*roundxy(x, y)) + ' '

        # bounce,
        if x >= (term.width - 1) or x <= 0:
            xs *= -1
        if y >= term.height or y <= 0:
            ys *= -1

        # move,
        x, y = x + xs, y + ys

        # draw !
        txt_ball = term.move_xy(*roundxy(x, y)) + '█'
        print(txt_erase + txt_ball, end='', flush=True)
