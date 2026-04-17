#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()
with term.cbreak():
    #print('\033=')
    key = term.inkey()
    extra = term.flushinp()
    print(f"You pressed: {key!r} ({str(key)!r}) extra={str(extra)!r}")
    #print('\033>')
    key = term.inkey()
    extra = term.flushinp()
    print(f"You pressed: {key!r} ({str(key)!r}) extra={str(extra)!r}")
