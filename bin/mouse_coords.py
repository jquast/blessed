#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

if not term.does_mouse():
    print("This example won't work on your terminal!")
else:
    with term.cbreak(), term.fullscreen(), term.mouse_enabled(report_drag=True):
        print("Click to move cursor! ^C to quit")
        while True:
            inp = term.inkey()
            if inp.name and inp.name.startswith('MOUSE_'):
                print(term.move_yx(*inp.mouse_yx), end='', flush=True)
