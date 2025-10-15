#!/usr/bin/env python
from blessed import Terminal

term = Terminal()

if not term.does_mouse(report_motion=True):
    print("This terminal does not support mouse motion tracking!")
else:
    with term.cbreak(), term.fullscreen(), term.mouse_enabled(report_motion=True):
        # header row displays mouse data
        quit_msg = "Press ^C to quit!"
        xoff = len(quit_msg) + 3
        print(term.home + term.reverse(term.ljust(quit_msg)) + term.clear_eos)

        while True:
            inp = term.inkey(timeout=1)

            if inp == 'q':
                break

            if inp.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
                mouse = inp.mode_values

                # Display mouse data in header row, move the blinking cursor
                # position, and conditionally draw a block character when LMB is
                # held, and erase when Middle or RMB is used.
                maybe_char = ('█' if mouse.button == 0 and not mouse.is_release else
                              ' ' if mouse.button < 3 and not mouse.is_release else
                              '')
                text = (term.move_yx(0, xoff) +
                        term.reverse(term.ljust(repr(mouse), term.width - xoff)) +
                        term.move_yx(mouse.y, mouse.x) +
                        maybe_char)

                print(text, end='', flush=True)
