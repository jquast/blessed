#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()
with term.cbreak():
    key = term.inkey()

    if key.is_sequence:
        print(f"Special key: {key.name} ({key!r})")
    else:
        print(f"Regular character: {key}")
