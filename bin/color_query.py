#!/usr/bin/env python
"""Query terminal foreground and background colors."""
from blessed import Terminal

term = Terminal()

fg_hex = term.get_fgcolor_hex()
bg_hex = term.get_bgcolor_hex()

bg_rgb = term.get_bgcolor(bits=8)
fg_rgb = term.get_fgcolor(bits=8)

print(f"Foreground {fg_hex} {fg_rgb}")
print(f"Background {bg_hex} {bg_rgb}")
