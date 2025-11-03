#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

if not term.does_mouse():
    print("This example won't work on your terminal!")
else:
    print("Click anywhere! ^C to quit")
    with term.cbreak(), term.mouse_enabled():
        while True:
            inp = term.inkey()
            if inp.name and inp.name.startswith('MOUSE_'):
                print(f"button {inp.name} at (y={inp.y}, x={inp.x})")
