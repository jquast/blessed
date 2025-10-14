#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()
print('Press Ctrl+x or F10 to exit! Press F1 for help')
with term.cbreak():
    while True:
        key = term.inkey()

        # Check for specific character with modifier
        if key.is_ctrl('x') or key.is_f10():
            print(f"Exit by key named {key.name}")
            break

        # Check for function key
        elif key.is_f1():
            print("* don't panic")

        # Check for arrow key with modifier
        elif key.is_shift_left():
            print("You have been eaten by a grue")
