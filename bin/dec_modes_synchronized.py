#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

fill = "█" * term.height * term.width
empty = " " * term.height * term.width

print(term.bold_red("Warning! Screen may blink rapidly!"))
print()
print("Press return to continue, 'q' to stop test")
term.inkey()

with term.fullscreen():
    for step in range(300):
        with term.synchronized_output():
            print(term.home + empty, flush=True)
            print(term.home + fill, flush=True)
            print(term.home + f'step={step}')
        if term.inkey(0.01) == 'q':
            break

print(term.clear + "Test complete!")
