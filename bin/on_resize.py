#!/usr/bin/env python
from blessed import Terminal

term = Terminal()


def on_resize():
    print()
    print(f'height={term.height}, width={term.width}, ' +
          f'pixel_height={term.pixel_height}, pixel_width={term.pixel_width}',
          end='', flush=True)


if not term.does_inband_resize():
    print('In-band Window Resize not supported on this terminal')
    import sys
    if sys.platform != 'win32':
        import signal

        def _on_resize(*args):
            on_resize()
        signal.signal(signal.SIGWINCH, _on_resize)
    else:
        print('Resizing not supported on this platform')

with term.cbreak(), term.notify_on_resize():
    print("press 'q' to quit.")
    # display initial size
    on_resize()
    while True:
        inp = term.inkey()
        if inp == 'q':
            break
        # capture in-band resize events
        if inp.name == 'RESIZE_EVENT':
            on_resize()
