#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

print("Press and hold keys to see raw kitty keystrokes and their names (press 'q' to quit)")
with term.enable_kitty_keyboard(report_events=True, report_all_keys=True, report_alternates=True):
    print("kitty keyboard state:", term.get_kitty_keyboard_state())
    with term.raw():
        while True:
            key = term.inkey()

            kind = ("pressed" if key.pressed
                    else "repeated" if key.repeated
                    else "released")
            if key.pressed and key.value == 'q':
                break
            print(
                f"name={
                    key.key_name} value={
                    key.key_value} kind={kind}, sequence={
                    key!r}",
                end="\r\n")
