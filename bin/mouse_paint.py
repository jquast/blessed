#!/usr/bin/env python
from blessed import Terminal

term = Terminal()

if not term.does_mouse(report_motion=True):
    print("This terminal does not support mouse motion tracking!")
else:
    # Track current color for painting
    color_idx = 7
    num_colors = min(256, term.number_of_colors)
    header = "Scroll wheel changes color=[{0}], LMB paints, RMB erases, ^C to quit"
    def make_header(): return term.home + term.center(header.format(term.color(color_idx)('█')))

    with term.cbreak(), term.fullscreen(), term.mouse_enabled(report_motion=True):
        text = make_header()
        while True:
            print(text, end='', flush=True)
            inp = term.inkey()
            print(inp.name)
            term.inkey(0.01)

            if inp.name and inp.name.startswith('MOUSE_'):
                # process mouse event buttons using magic methods
                if inp.is_mouse_scroll_up():
                    color_idx = (color_idx + 1) % num_colors
                elif inp.is_mouse_scroll_down():
                    color_idx = (color_idx - 1) % num_colors

                block_fill = term.color(color_idx)('█')
                char = (block_fill if inp.name.startswith('MOUSE_LEFT')
                        else ' ' if inp.name.startswith('MOUSE_RIGHT')
                        else '')

                # update draw text using mouse_yx
                text = make_header() + term.move_yx(*inp.mouse_yx) + char
