"""
Utility to show X11 colors in 24-bit and downconverted to 256, 16, and 8 colors.

The time to generate the table is displayed to give an indication of how long each algorithm takes
compared to the others.
"""
# std imports
import sys
import timeit
import colorsys

# local
import blessed
from blessed.color import COLOR_DISTANCE_ALGORITHMS
from blessed.colorspace import X11_COLORNAMES_TO_RGB


def sort_colors():
    """Sort colors by HSV value and remove duplicates."""
    colors = {}
    for color_name, rgb_color in X11_COLORNAMES_TO_RGB.items():
        if rgb_color not in colors:
            colors[rgb_color] = color_name

    return sorted(colors.items(),
                  key=lambda rgb: colorsys.rgb_to_hsv(*rgb[0]),
                  reverse=True)


ALGORITHMS = tuple(sorted(COLOR_DISTANCE_ALGORITHMS))
SORTED_COLORS = sort_colors()


def draw_chart(term):
    """Draw a chart of each color downconverted with selected distance algorithm."""
    sys.stdout.write(term.home)
    width = term.width
    line = ''
    line_len = 0

    start = timeit.default_timer()
    for color in SORTED_COLORS:

        chart = ''
        for noc in (1 << 24, 256, 16, 8):
            term.number_of_colors = noc
            chart += getattr(term, color[1])('█')

        if line_len + 5 > width:
            line += '\n'
            line_len = 0

        line += ' %s' % chart
        line_len += 5

    elapsed = round((timeit.default_timer() - start) * 1000)
    print(line)

    left_text = '[] to select, q to quit'
    center_text = f'{term.color_distance_algorithm}'
    right_text = f'{elapsed:d} ms\n'

    sys.stdout.write(term.clear_eos + left_text +
                     term.center(center_text, term.width -
                                 term.length(left_text) - term.length(right_text)) +
                     right_text)


def color_chart(term):
    """Main color chart application."""
    term = blessed.Terminal()
    algo_idx = 0
    dirty = True
    with term.cbreak(), term.hidden_cursor(), term.fullscreen():
        while True:
            if dirty:
                draw_chart(term)
            inp = term.inkey()
            dirty = True
            if inp in '[]':
                algo_idx += 1 if inp == ']' else -1
                algo_idx %= len(ALGORITHMS)
                term.color_distance_algorithm = ALGORITHMS[algo_idx]
            elif inp == '\x0c':
                pass
            elif inp in 'qQ':
                break
            else:
                dirty = False


if __name__ == '__main__':
    color_chart(blessed.Terminal())
