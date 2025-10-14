#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

print("Click anywhere (or press 'q' to quit):")
with term.cbreak(), term.dec_modes_enabled(
        term.DecPrivateMode.MOUSE_REPORT_CLICK,
        term.DecPrivateMode.MOUSE_EXTENDED_SGR, timeout=1):

    while True:
        inp = term.inkey()
        if inp.lower() == 'q':
            break
        if inp.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
            mouse_event = inp.mode_values
            if not mouse_event.is_release:
                print(
                    f"Clicked at (y={
                        mouse_event.y}, x={
                        mouse_event.x}) with button {
                        mouse_event.button}")
