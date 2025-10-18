#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

print("Switch focus to/from this terminal window, 'q' to stop.")

with term.focus_events():
    with term.cbreak():
        while True:
            inp = term.inkey()
            if inp.name == 'FOCUS_IN':
                print("Focus gained")
            elif inp.name == 'FOCUS_OUT':
                print("Focus lost")
            elif inp == 'q':
                break
