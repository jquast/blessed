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
            mouse_event = inp.mode_values
            if not mouse_event.is_release:
                print(f"Clicked at (y={mouse_event.y}, x={mouse_event.x}) "
                      f"with button {mouse_event.button}")
