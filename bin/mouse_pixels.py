#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

if not term.does_mouse(report_pixels=True):
    print("This terminal does not support pixel coordinate mouse tracking!")
else:
    print("Click anywhere to display *Pixel* coordinates (press 'q' to quit):")
    with term.cbreak(), term.mouse_enabled(report_pixels=True):
        while True:
            event = term.inkey()

            if event == 'q':
                break

            if event.mode == term.DecPrivateMode.MOUSE_SGR_PIXELS:
                mouse_event = event.mode_values
                # x and y are now in pixels instead of cells
                print(f"Pixel position: (y={mouse_event.y}, x={mouse_event.x})")
