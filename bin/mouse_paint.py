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

            if inp.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
                # process mouse event buttons
                mouse = inp.mode_values
                color_offset = {'SCROLL_UP': 1, 'SCROLL_DOWN': -1}.get(mouse.button, 0)
                color_idx = (color_idx + color_offset) % num_colors
                block_fill = term.color(color_idx)('█')
                char = {'LEFT': block_fill, 'RIGHT': ' '}.get(mouse.button, '')

                # update draw text
                text = make_header() + term.move_yx(mouse.y, mouse.x) + char
