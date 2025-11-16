#!/usr/bin/env python
# std imports
import sys
import math
import time
import timeit
import colorsys
import contextlib

# local
import blessed


def scale_255(val): return int(round(val * 255))


def rgb_at_xy(term, x, y, t):
    h, w = term.height, term.width
    hue = 4.0 + (
        math.sin(x / 16.0)
        + math.sin(y / 32.0)
        + math.sin(math.sqrt(
            (x - w / 2.0) * (x - w / 2.0) +
            (y - h / 2.0) * (y - h / 2.0)
        ) / 8.0 + t * 3)
    ) + math.sin(math.sqrt(x * x + y * y) / 8.0)
    saturation = y / h
    lightness = x / w
    return tuple(map(scale_255, colorsys.hsv_to_rgb(hue / 8.0, saturation, lightness)))


def screen_plasma(term, plasma_fn, t):
    result = ''
    for y in range(term.height - 1):
        for x in range(term.width):
            result += term.on_color_rgb(*plasma_fn(term, x, y, t)) + ' '
    return result


@contextlib.contextmanager
def elapsed_timer():
    """Timer pattern, from https://stackoverflow.com/a/30024601."""
    start = timeit.default_timer()

    def elapser():
        return timeit.default_timer() - start

    # pylint: disable=unnecessary-lambda
    yield lambda: elapser()


def show_please_wait(term):
    txt_wait = 'please wait ...'
    outp = term.move_yx(term.height - 1, 0) + term.clear_eol + term.center(txt_wait)
    print(outp, end='')
    sys.stdout.flush()


def show_paused(term):
    txt_paused = 'paused'
    outp = term.move_yx(term.height - 1, int(term.width / 2 - len(txt_paused) / 2))
    outp += txt_paused
    print(outp, end='')
    sys.stdout.flush()


def next_algo(algo, forward):
    algos = tuple(sorted(blessed.color.COLOR_DISTANCE_ALGORITHMS))
    next_index = algos.index(algo) + (1 if forward else -1)
    if next_index == len(algos):
        next_index = 0
    return algos[next_index]


def next_color(color, forward):
    colorspaces = (4, 8, 16, 256, 1 << 24)
    next_index = colorspaces.index(color) + (1 if forward else -1)
    if next_index == len(colorspaces):
        next_index = 0
    return colorspaces[next_index]


def status(term, elapsed):
    left_txt = (f'{term.number_of_colors} colors - '
                f'{term.color_distance_algorithm} - ?: help ')
    right_txt = f'fps: {1 / elapsed:2.2f}'
    return ('\n' + term.normal +
            term.white_on_blue + term.clear_eol + left_txt +
            term.rjust(right_txt, term.width - len(left_txt)))


def main(term):
    with term.cbreak(), term.hidden_cursor(), term.fullscreen():
        pause, dirty = False, True
        t = time.time()
        while True:
            if dirty or not pause:
                if not pause:
                    t = time.time()
                with elapsed_timer() as elapsed:
                    outp = term.home + screen_plasma(term, rgb_at_xy, t)
                outp += status(term, elapsed())
                # Use synchronized output to reduce tearing and improve smoothness
                with term.dec_modes_enabled(term.DecPrivateMode.SYNCHRONIZED_OUTPUT):
                    print(outp, end='')
                    sys.stdout.flush()
                dirty = False
            if pause:
                show_paused(term)

            inp = term.inkey(timeout=None if pause else 0.01)
            if inp == '?':
                assert False, "don't panic"
            elif inp == '\x0c':
                dirty = True

            if inp in ('[', ']'):
                term.color_distance_algorithm = next_algo(
                    term.color_distance_algorithm, inp == '[')
                show_please_wait(term)
                dirty = True
            if inp == ' ':
                pause = not pause

            if inp.code in (term.KEY_TAB, term.KEY_BTAB):
                term.number_of_colors = next_color(
                    term.number_of_colors, inp.code == term.KEY_TAB)
                show_please_wait(term)
                dirty = True


if __name__ == "__main__":
    exit(main(blessed.Terminal()))
