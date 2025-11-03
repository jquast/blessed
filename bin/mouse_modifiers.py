#!/usr/bin/env python
from blessed import Terminal

term = Terminal()
counts = dict()

with term.fullscreen(), term.cbreak(), term.mouse_enabled():
    while True:
        inp = term.inkey(timeout=None)

        # Check if this is a mouse event
        if inp.name and inp.name.startswith('MOUSE_'):
            # Use the keystroke name for button identification
            counts[inp.name] = counts.get(inp.name, 0) + 1
            with term.synchronized_output():
                print(term.home + term.clear)
                print(term.bold("Mouse Modifier Example, press Ctrl+C to quit"))
                print()

                # Display the most recent event
                print(f"button={inp.name} at (y={inp.y}, x={inp.x})")
                print()

                # Display totals
                print("Totals: ")
                for button_name, count in sorted(counts.items()):
                    print(f"{button_name}: {count}")
