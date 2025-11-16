#!/usr/bin/env python
import threading
from blessed import Terminal

term = Terminal()

_resize_pending = threading.Event()


def on_resize(*args):
    _resize_pending.set()


def display_size(term):
    # conditionally refresh sixel size when enabled
    sixel_height, sixel_width = 0, 0
    if term.does_sixel():
        sixel_height, sixel_width = term.get_sixel_height_and_width(force=True)
    print()
    print(f'height={term.height}, width={term.width}, ' +
          f'pixel_height={term.pixel_height}, pixel_width={term.pixel_width}, ' +
          f'sixel_height={sixel_height}, sixel_width={sixel_width}',
          end='', flush=True)


if not term.does_inband_resize():
    print('In-band Window Resize not supported on this terminal')
    import sys
    if sys.platform != 'win32':
        import signal
        signal.signal(signal.SIGWINCH, on_resize)

with term.cbreak(), term.notify_on_resize():
    print("press 'q' to quit.")
    display_size(term)

    while True:
        inp = term.inkey(timeout=0.1)

        if inp == 'q':
            break

        if inp.name == 'RESIZE_EVENT':
            _resize_pending.set()
        elif _resize_pending.is_set():
            _resize_pending.clear()
            display_size(term)
