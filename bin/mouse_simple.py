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
            if inp.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
                mouse = inp.mode_values
                print(f"button {mouse.button} at (y={mouse.y}, x={mouse.x})")
