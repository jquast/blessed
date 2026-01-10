#!/usr/bin/env python
"""Example of Terminal.scroll_region()."""
from blessed import Terminal

term = Terminal()

with term.fullscreen(), term.cbreak():
    # Draw header
    print(term.home + term.clear, end='')
    print(term.reverse(term.center("Scroll region demo")), end='')

    # Draw footer
    print(term.move_yx(term.height - 1, 0), end='')
    print(term.reverse(term.center("Press any key to stop")), end='')

    # create scrolling region
    with term.scroll_region(top=1, height=term.height - 2):
        # Print text within scrolling region
        print(term.move_yx(1, 0), end='')
        for line_num in range(1000):
            print(f'\n{line_num:4d}: Lorem ipsum dolor sit amet, consectetur adipiscing elit.', end='')
            if term.inkey(0.01):
                break
