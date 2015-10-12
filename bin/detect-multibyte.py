#!/usr/bin/env python
# coding: utf-8
"""
Problem: A screen drawing application wants to detect whether the terminal
client is capable of rendering utf-8.  Some transports, such as a serial link,
often cannot forward their ``LANG`` environment preference, or protocols such
as telnet and rlogin often assume mutual agreement by manual configuration.

We can interactively determine whether the connecting terminal emulator is
rendering in utf8 by making an inquiry of their cursor position:

    - request cursor position (p0).

    - display multibyte character.

    - request cursor position (p1).

If the horizontal distance of (p0, p1) is 1 cell, we know the connecting
client is certainly matching our intended encoding.

As an exercise, it may be possible to use this technique to accurately
determine to the remote encoding without protocol negotiation using cursor
positioning alone, as demonstrated by the following diagram,

.. image:: https://github.com/jquast/blessed/blob/master/docs/_static/soulburner-ru-family-encodings.jpg
    :alt: Cyrillic encodings flowchart
"""
# std imports
from __future__ import print_function
import collections
import sys

# local,
from blessed import Terminal

import time

def get_pos(term):
    """Get cursor position, calling os.exit(2) if not determined."""

    Position = collections.namedtuple('Position', ('row', 'column'))

    pos = Position(*term.get_location(timeout=5.0))

    if -1 in pos:
        print('stdin: not a human', file=sys.stderr)
        exit(2)

    return pos


def main():
    """Program entry point."""

    term = Terminal()

    # move to bottom of screen, temporarily, where we're likely to do
    # the least damage, as we are performing something of a "destructive
    # write and erase" onto this screen location.  Furthermore, stderr is
    # used to pre
    with term.cbreak(), term.location(y=term.height - 1, x=0):

        # store first position
        pos0 = get_pos(term)

        # display multibyte character
        print(u'⦰', end='')

        # store second position
        pos1 = get_pos(term)

        # determine distance
        horizontal_distance = pos1.column - pos0.column
        multibyte_capable = bool(horizontal_distance == 1)

        # rubout character(s)
        print('\b \b' * horizontal_distance, end='')

    # returned to our original starting position,
    if not multibyte_capable:
        print('multibyte encoding failed, horizontal distance is {0}, '
              'expected 1 for unicode point https://codepoints.net/U+29B0'
              .format(horizontal_distance), file=sys.stderr)
        exit(1)

    print('{checkbox} multibyte encoding supported!'
          .format(checkbox=term.bold_green(u'✓')))
if __name__ == '__main__':
    exit(main())
