#!/usr/bin/env python
"""
Example application for the 'blessed' Terminal library for python.

This isn't a real progress bar, just a sample "animated prompt" of sorts that demonstrates the
separate move_x() and move_yx() capabilities, made mainly to test the `hpa' compatibility for
'screen' terminal type which fails to provide one, but blessed recognizes that it actually does, and
provides a proxy.
"""

# std imports
import sys

# local
from blessed import Terminal


def main():
    """Program entry point."""
    term = Terminal()
    assert term.hpa(1) != '', (
        'Terminal does not support hpa (Horizontal position absolute)')

    col, offset = 1, 1
    with term.cbreak():
        inp = None
        print("press 'X' to stop.")
        sys.stderr.write(term.move_yx(term.height, 0) + '[')
        sys.stderr.write(term.move_x(term.width - 1) + ']' + term.move_x(1))
        while inp != 'X':
            if col >= (term.width - 2):
                offset = -1
            elif col <= 1:
                offset = 1
            sys.stderr.write(term.move_x(col))
            if offset == -1:
                sys.stderr.write('.')
            else:
                sys.stderr.write('=')
            col += offset
            sys.stderr.write(term.move_x(col))
            sys.stderr.write('|\b')
            sys.stderr.flush()
            inp = term.inkey(0.04)
    print()


if __name__ == '__main__':
    main()
