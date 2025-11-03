#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

print("Press and hold keys to see raw kitty keystrokes and their names (press 'q' to quit)")
with term.enable_kitty_keyboard(report_events=True):
    with term.cbreak():
        while True:
            key = term.inkey()

            if key.pressed:
                print(f"Key {key.name} pressed, value={key.value}, sequence={key!r}")
                if key == 'q':
                    break
            elif key.repeated:
                print(f"Key repeating, sequence={key!r}")
            elif key.released:
                print(f"Key released, sequence={key!r}")
