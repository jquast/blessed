#!/usr/bin/env python
"""Query terminal foreground and background colors."""
from blessed import Terminal

term = Terminal()

# Get foreground color
r, g, b = term.get_fgcolor()
if (r, g, b) != (-1, -1, -1):
    print(f"Foreground color: RGB({r}, {g}, {b})")
    print(f"  Hex: #{r:04x}{g:04x}{b:04x}")
else:
    print("Could not determine foreground color")

# Get background color
r, g, b = term.get_bgcolor()
if (r, g, b) != (-1, -1, -1):
    print(f"Background color: RGB({r}, {g}, {b})")
    print(f"  Hex: #{r:04x}{g:04x}{b:04x}")
else:
    print("Could not determine background color")
