#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

if not term.get_dec_mode(term.DecPrivateMode.MOUSE_EXTENDED_SGR, timeout=1).is_supported():
    print('This example wont work on your terminal!')
else:
    print("Click anywhere! Press 'q' to quit")
    with term.cbreak(), term.dec_modes_enabled(
            term.DecPrivateMode.MOUSE_REPORT_CLICK,
            term.DecPrivateMode.MOUSE_EXTENDED_SGR):
        while True:
            inp = term.inkey()
            if inp .lower() == 'q':
                break
            if inp.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
                mouse_event = inp.mode_values
                if not mouse_event.is_release and mouse_event.button:
                    y, x = (mouse_event.y, mouse_event.x)
                    print(f"button clicked at (y={y}, x={x})")
