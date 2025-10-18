#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

# check basic mouse support
if not term.does_mouse():
    print(f"mouse_enabled() {term.bright_red('not supported')} on this Terminal")
else:
    # check for, enable, and report all supported advanced features
    feature_kwargs = {mouse_feature: True
                      for mouse_feature in ('report_pixels', 'report_drag', 'report_motion')
                      if term.does_mouse(**{mouse_feature: True})}
    with term.mouse_enabled(**feature_kwargs):
        print(f"mouse_enabled({', '.join(feature_kwargs)}) enabled")
