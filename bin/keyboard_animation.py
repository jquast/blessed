#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()
print("Cross animation, press any key to stop: ", end="", flush=True)
with term.cbreak(), term.hidden_cursor():
    cross = '|'

    while True:
        key = term.inkey(timeout=0.1)
        if key:
            print(f'STOP by {key!r}')
            break

        cross = {'|': '-', '-': '|'}[cross]
        print(f'{cross}\b', end='', flush=True)
