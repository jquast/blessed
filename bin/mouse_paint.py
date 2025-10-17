#!/usr/bin/env python
from blessed import Terminal

term = Terminal()

if not term.does_mouse(report_motion=True):
    print("This terminal does not support mouse motion tracking!")
else:
    # Track current color for painting
    color_idx = 7
    num_colors = min(256, term.number_of_colors)
    header = "Mouse wheel sets color=[{0}], LEFT button paints, RIGHT erases, ^C:quit"

    def make_header():
        return term.home + term.center(header.format(term.color(color_idx)('█')))
    text = make_header()

    with term.cbreak(), term.fullscreen(), term.mouse_enabled(report_motion=True):
        while True:
            print(text, end='', flush=True)
            inp = term.inkey()

            if inp.name and inp.name.startswith('MOUSE_'):
                # process scroll wheel changes color
                _offset = (1 if inp.name == 'MOUSE_SCROLL_UP' else
                           -1 if inp.name == 'MOUSE_SCROLL_DOWN' else 0)
                color_idx = (color_idx + _offset) % num_colors

                # and left mouse paints, right erases
                char = (term.color(color_idx)('█')
                        if inp.name.startswith('MOUSE_LEFT')
                        else ' ' if inp.name.startswith('MOUSE_RIGHT')
                        else '')

                # update draw text using mouse_yx
                text = make_header() + term.move_yx(*inp.mouse_yx) + char
