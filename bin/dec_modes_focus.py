#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

print("Switch focus to/from this terminal window (press 'q' to quit)...")

with term.dec_modes_enabled(term.DecPrivateMode.FOCUS_IN_OUT_EVENTS):
    with term.cbreak():
        while True:
            ks = term.inkey()

            if ks.mode == term.DecPrivateMode.FOCUS_IN_OUT_EVENTS:
                event = ks.mode_values
                status = "gained" if event.gained else "lost"
                print(f"Focus {status}")
            elif ks == 'q':
                print("Goodbye!")
                break
