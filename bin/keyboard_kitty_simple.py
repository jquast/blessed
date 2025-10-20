#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

print("Press and hold keys to see events (press 'q' to quit)")
with term.enable_kitty_keyboard(report_events=True):
    with term.cbreak():
        while True:
            key = term.inkey()

            if key.pressed:
                print(f"Key {key!r} pressed")
                if key == 'q':
                    break
            elif key.repeated:
                print(f"Key {key!r} repeating")
            elif key.released:
                print(f"Key {key!r} released")
