#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

if not term.does_mouse(report_pixels=True):
    print("This terminal does not support pixel coordinate mouse tracking!")
else:
    print("Click to display Pixel coordinates, ^C to quit:")
    with term.cbreak(), term.mouse_enabled(report_pixels=True):
        while True:
            event = term.inkey()

            if event.mode == term.DecPrivateMode.MOUSE_SGR_PIXELS:
                mouse = event.mode_values
                print(f"Pixel position: (y={mouse.y}, x={mouse.x})")
