#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()
with term.cbreak():
    key = term.inkey()
    print(f"You pressed: {key!r}")
