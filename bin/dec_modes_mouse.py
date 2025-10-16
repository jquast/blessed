#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

print("Click anywhere (or press 'q' to quit):")

with term.cbreak(), term.mouse_enabled():
    while True:
        inp = term.inkey()

        if inp.lower() == 'q':
            break

        if inp.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
            mouse = inp.mode_values
            # Filter out release events by checking if button name ends with _RELEASED
            if not mouse.button.endswith('_RELEASED'):
                print(f"Clicked at (y={mouse.y}, x={mouse.x}) with button {mouse.button}")
