#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

if not term.get_dec_mode(term.DecPrivateMode.MOUSE_ALL_MOTION, timeout=0.1).is_supported():
    print("This terminal does not support MOUSE_ALL_MOTION tracking!")
else:
    print("Click anywhere to display *Pixel* coordinates (press 'q' to quit):")
    with term.cbreak(), term.dec_modes_enabled(
            term.DecPrivateMode.MOUSE_REPORT_CLICK,
            term.DecPrivateMode.MOUSE_EXTENDED_SGR,
            term.DecPrivateMode.MOUSE_SGR_PIXELS):
        while True:
            event = term.inkey()

            if event == 'q':
                break

            if event.mode == term.DecPrivateMode.MOUSE_SGR_PIXELS:
                mouse_event = event.mode_values
                # x and y are now in pixels instead of cells
                print(f"Pixel position: (y={mouse_event.y}, x={mouse_event.x})")
