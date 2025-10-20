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

            if event.name and event.name.startswith('MOUSE_'):
                print(f"Pixel position: (y={event.y}, x={event.x})")
