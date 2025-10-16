#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

print("Paste some text (press 'q' to quit)...")

with term.bracketed_paste():
    with term.cbreak():
        while True:
            ks = term.inkey()

            if ks.name == 'BRACKETED_PASTE':
                print(f"Pasted: {term.reverse(repr(ks.text))}")
            elif ks == 'q':
                print("Goodbye!")
                break
            elif ks:
                print(f"Regular key: {ks!r}")
