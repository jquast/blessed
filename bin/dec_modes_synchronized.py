#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

print("Animating blocks (press Ctrl+C to stop)...")
print("On terminals with synchronized output, this won't blink!")

fillblocks = "█" * term.height * term.width
emptyblocks = " " * term.height * term.width

try:
    for step in range(500):
        with term.dec_modes_enabled(term.DecPrivateMode.SYNCHRONIZED_OUTPUT, timeout=1):
            print(term.home + emptyblocks, flush=True)
            print(term.home + fillblocks, flush=True)
            print(term.home + f'step={step}')
        term.inkey(0.01)
except KeyboardInterrupt:
    print(term.clear + "Done!")
