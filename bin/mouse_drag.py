#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

if not term.get_dec_mode(term.DecPrivateMode.MOUSE_REPORT_DRAG, timeout=1).is_supported():
    print("This terminal does not support MOUSE_ALL_MOTION tracking!")
else:
    print("Click and drag the mouse (press 'q' to quit):")
    with term.cbreak(), term.dec_modes_enabled(
            term.DecPrivateMode.MOUSE_REPORT_DRAG,
            term.DecPrivateMode.MOUSE_EXTENDED_SGR):
        while True:
            event = term.inkey()

            if event == 'q':
                break

            if event.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
                mouse = event.mode_values
                if mouse.is_motion:
                    print(f"Dragging at (y={mouse.y}, x={mouse.x})")
