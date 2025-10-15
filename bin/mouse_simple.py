#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

if not term.does_mouse():
    print('This example won\'t work on your terminal!')
else:
    print("Click anywhere! Press 'q' to quit")
    with term.cbreak(), term.mouse_enabled():
        while True:
            inp = term.inkey()
            if inp.lower() == 'q':
                break
            if inp.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
                mouse_event = inp.mode_values
                if not mouse_event.is_release and mouse_event.button:
                    y, x = (mouse_event.y, mouse_event.x)
                    print(f"button clicked at (y={y}, x={x})")
