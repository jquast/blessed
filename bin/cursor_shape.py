#!/usr/bin/env python3
"""Demonstrate DECSCUSR cursor shape changes with line editor input."""
from blessed import Terminal
from blessed.line_editor import LineEditor

term = Terminal()


def readline(col, width=40):
    """Read a line of input at current position."""
    ed = LineEditor(max_width=width, limit=200)
    while True:
        result = ed.feed_key(term.inkey())
        if result.line is not None or result.eof or result.interrupt:
            return result.line or ''
        if result.changed:
            ds = ed.display
            print(term.move_x(col) + term.clear_eol + ds.text
                  + term.move_x(col + ds.cursor), end='', flush=True)


print("Cursor shape demo -- type with each shape, press Enter to continue.\n")

with term.cbreak():
    for name, value in sorted(term.CursorShape.STYLES.items()):
        if name == 'default':
            continue
        label = f"  {name}: "
        print(label, end='', flush=True)
        with term.cursor_shape(value):
            readline(col=len(label))
        print()

print("\nCursor restored to terminal default.")
