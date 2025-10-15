#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

print("Switch focus to/from this terminal window, Ctrl+C to stop.")

with term.focus_events():
    with term.cbreak():
        while True:
            inp = term.inkey()
            if inp.mode == term.DecPrivateMode.FOCUS_IN_OUT_EVENTS:
                status = "gained" if inp.mode_values.gained else "lost"
                print(f"Focus {status}")
