#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

if not term.does_mouse(report_drag=True):
    print("This terminal does not support mouse drag tracking!")
else:
    print("Click and drag the mouse (press 'q' to quit):")
    with term.cbreak(), term.mouse_enabled(report_drag=True):
        while True:
            event = term.inkey()

            if event == 'q':
                break

            if event.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
                mouse = event.mode_values
                if mouse.is_motion:
                    print(f"Dragging at (y={mouse.y}, x={mouse.x})")
