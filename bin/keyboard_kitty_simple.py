#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

print("Press and hold keys to see raw kitty keystrokes and their names (press 'q' to quit)")
# disambiguate=True, report_events=True, report_alternates=True, report_all_keys=True
with term.enable_kitty_keyboard(report_events=True):
    with term.cbreak():
        while True:
            key = term.inkey()

            kind = ("pressed" if key.pressed
                    else "repeated" if key.repeated
                    else "released" if key.released
                    else "???")
            if key.pressed and key.value == 'q':
                break
            print(f"Key name={key.name} kind={kind} value={key.value}, sequence={key!r}")
