#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

if not term.does_mouse(report_drag=True):
    print("This example won't work on your terminal!")
else:
    with term.cbreak(), term.mouse_enabled(report_drag=True):
        while True:
            inp = term.inkey()
            if inp.name and inp.name.endswith('_MOTION'):
                print(f"Drag event at ({inp.y}, {inp.x})")
