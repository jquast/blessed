#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

print("Click anywhere (or press 'q' to quit):")

with term.cbreak(), term.mouse_enabled():
    while True:
        inp = term.inkey()

        if inp.lower() == 'q':
            break

        if inp.name and inp.name.startswith('MOUSE_'):
            # Filter out release events by checking if name ends with _RELEASED
            if not inp.name.endswith('_RELEASED'):
                print(f"Clicked at (y={inp.y}, x={inp.x}) with button {inp.name}")
