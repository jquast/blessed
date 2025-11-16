#!/usr/bin/env python
from blessed import Terminal

term = Terminal()

# Check for sixel support
if not term.does_sixel():
    print("This terminal does not support sixel graphics")
else:
    print("This terminal probably supports sixel graphics")

# Get display dimensions
height, width = term.get_sixel_height_and_width()
if (height, width) == (-1, -1):
    print("Could not determine sixel dimensions")
else:
    print(f"Sixel area: {width}x{height} (px)")

# Get color support
colors = term.get_sixel_colors()
if colors == -1:
    print("Could not determine color support")
else:
    print(f"Colors available: {colors}")

# Get cell dimensions for positioning
cell_height, cell_width = term.get_cell_height_and_width()
if (cell_height, cell_width) == (-1, -1):
    print("Could not determine cell size")
else:
    print(f"Character cells: {cell_width}x{cell_height} (px)")
