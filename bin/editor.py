#!/usr/bin/env python
"""
A Dumb full-screen editor.

This example program makes use of many context manager methods:
:meth:`~.Terminal.hidden_cursor`, :meth:`~.Terminal.raw`,
:meth:`~.Terminal.location`, :meth:`~.Terminal.fullscreen`, and
:meth:`~.Terminal.keypad`.

Early curses work focused namely around writing screen editors, naturally
any serious editor would make liberal use of special modes.

``Ctrl - L``
  refresh

``Ctrl - C``
  quit

``Ctrl - S``
  save
"""
from __future__ import division, print_function

# std imports
import functools
import collections

# local
from blessed import Terminal

# python 2/3 compatibility, provide 'echo' function as an
# alias for "print without newline and flush"
try:
    # pylint: disable=invalid-name
    #         Invalid constant name "echo"
    echo = functools.partial(print, end='', flush=True)
    echo(u'')
except TypeError:
    # TypeError: 'flush' is an invalid keyword argument for this function
    import sys

    def echo(text):
        """Display ``text`` and flush output."""
        sys.stdout.write(u'{}'.format(text))
        sys.stdout.flush()


def input_filter(keystroke):
    """
    For given keystroke, return whether it should be allowed as input.

    This somewhat requires that the interface use special application keys to perform functions, as
    alphanumeric input intended for persisting could otherwise be interpreted as a command sequence.
    """
    if keystroke.is_sequence:
        # Namely, deny multi-byte sequences (such as '\x1b[A'),
        return False
    if ord(keystroke) < ord(u' '):
        # or control characters (such as ^L),
        return False
    return True


def echo_yx(cursor, text):
    """Move to ``cursor`` and display ``text``."""
    echo(cursor.term.move_yx(cursor.y, cursor.x) + text)


Cursor = collections.namedtuple('Cursor', ('y', 'x', 'term'))


def readline(term, width=20):
    """A rudimentary readline implementation."""
    text = u''
    while True:
        inp = term.inkey()
        if inp.code == term.KEY_ENTER:
            break
        elif inp.code == term.KEY_ESCAPE or inp == chr(3):
            text = None
            break
        elif not inp.is_sequence and len(text) < width:
            text += inp
            echo(inp)
        elif inp.code in (term.KEY_BACKSPACE, term.KEY_DELETE):
            text = text[:-1]
            # https://utcc.utoronto.ca/~cks/space/blog/unix/HowUnixBackspaces
            #
            # "When you hit backspace, the kernel tty line discipline rubs out
            # your previous character by printing (in the simple case)
            # Ctrl-H, a space, and then another Ctrl-H."
            echo(u'\b \b')
    return text


def save(screen, fname):
    """Save screen contents to file."""
    if not fname:
        return
    with open(fname, 'w') as fout:
        cur_row = cur_col = 0
        for (row, col) in sorted(screen):
            char = screen[(row, col)]
            while row != cur_row:
                cur_row += 1
                cur_col = 0
                fout.write(u'\n')
            while col > cur_col:
                cur_col += 1
                fout.write(u' ')
            fout.write(char)
            cur_col += 1
        fout.write(u'\n')


def redraw(term, screen, start=None, end=None):
    """Redraw the screen."""
    if start is None and end is None:
        echo(term.clear)
        start, end = (Cursor(y=min([y for (y, x) in screen or [(0, 0)]]),
                             x=min([x for (y, x) in screen or [(0, 0)]]),
                             term=term),
                      Cursor(y=max([y for (y, x) in screen or [(0, 0)]]),
                             x=max([x for (y, x) in screen or [(0, 0)]]),
                             term=term))
    lastcol, lastrow = -1, -1
    for row, col in sorted(screen):
        if start.y <= row <= end.y and start.x <= col <= end.x:
            if col >= term.width or row >= term.height:
                # out of bounds
                continue
            if row != lastrow or col != lastcol + 1:
                # use cursor movement
                echo_yx(Cursor(row, col, term), screen[row, col])
            else:
                # just write past last one
                echo(screen[row, col])


def main():
    """Program entry point."""
    def above(csr, offset):
        return Cursor(y=max(0, csr.y - offset),
                      x=csr.x,
                      term=csr.term)

    def below(csr, offset):
        return Cursor(y=min(csr.term.height - 1, csr.y + offset),
                      x=csr.x,
                      term=csr.term)

    def right_of(csr, offset):
        return Cursor(y=csr.y,
                      x=min(csr.term.width - 1, csr.x + offset),
                      term=csr.term)

    def left_of(csr, offset):
        return Cursor(y=csr.y,
                      x=max(0, csr.x - offset),
                      term=csr.term)

    def home(csr):
        return Cursor(y=csr.y,
                      x=0,
                      term=csr.term)

    def end(csr):
        return Cursor(y=csr.y,
                      x=csr.term.width - 1,
                      term=csr.term)

    def bottom(csr):
        return Cursor(y=csr.term.height - 1,
                      x=csr.x,
                      term=csr.term)

    def center(csr):
        return Cursor(csr.term.height // 2,
                      csr.term.width // 2,
                      csr.term)

    def lookup_move(inp_code, csr):
        return {
            # arrows, including angled directionals
            csr.term.KEY_END: below(left_of(csr, 1), 1),
            csr.term.KEY_KP_1: below(left_of(csr, 1), 1),

            csr.term.KEY_DOWN: below(csr, 1),
            csr.term.KEY_KP_2: below(csr, 1),

            csr.term.KEY_PGDOWN: below(right_of(csr, 1), 1),
            csr.term.KEY_LR: below(right_of(csr, 1), 1),
            csr.term.KEY_KP_3: below(right_of(csr, 1), 1),

            csr.term.KEY_LEFT: left_of(csr, 1),
            csr.term.KEY_KP_4: left_of(csr, 1),

            csr.term.KEY_CENTER: center(csr),
            csr.term.KEY_KP_5: center(csr),

            csr.term.KEY_RIGHT: right_of(csr, 1),
            csr.term.KEY_KP_6: right_of(csr, 1),

            csr.term.KEY_HOME: above(left_of(csr, 1), 1),
            csr.term.KEY_KP_7: above(left_of(csr, 1), 1),

            csr.term.KEY_UP: above(csr, 1),
            csr.term.KEY_KP_8: above(csr, 1),

            csr.term.KEY_PGUP: above(right_of(csr, 1), 1),
            csr.term.KEY_KP_9: above(right_of(csr, 1), 1),

            # shift + arrows
            csr.term.KEY_SLEFT: left_of(csr, 10),
            csr.term.KEY_SRIGHT: right_of(csr, 10),
            csr.term.KEY_SDOWN: below(csr, 10),
            csr.term.KEY_SUP: above(csr, 10),

            # carriage return
            csr.term.KEY_ENTER: home(below(csr, 1)),
        }.get(inp_code, csr)

    term = Terminal()
    csr = Cursor(0, 0, term)
    screen = {}
    with term.hidden_cursor(), \
            term.raw(), \
            term.location(), \
            term.fullscreen(), \
            term.keypad():
        inp = None
        while True:
            echo_yx(csr, term.reverse(screen.get((csr.y, csr.x), u' ')))
            inp = term.inkey()

            if inp == chr(3):
                # ^c exits
                break

            elif inp == chr(19):
                # ^s saves
                echo_yx(home(bottom(csr)),
                        term.ljust(term.bold_white(u'Filename: ')))
                echo_yx(right_of(home(bottom(csr)), len(u'Filename: ')), u'')
                save(screen, readline(term))
                echo_yx(home(bottom(csr)), term.clear_eol)
                redraw(term=term, screen=screen,
                       start=home(bottom(csr)),
                       end=end(bottom(csr)))
                continue

            elif inp == chr(12):
                # ^l refreshes
                redraw(term=term, screen=screen)

            else:
                n_csr = lookup_move(inp.code, csr)

            if n_csr != csr:
                # erase old cursor,
                echo_yx(csr, screen.get((csr.y, csr.x), u' '))
                csr = n_csr

            elif input_filter(inp):
                echo_yx(csr, inp)
                screen[(csr.y, csr.x)] = inp.__str__()
                n_csr = right_of(csr, 1)
                if n_csr == csr:
                    # wrap around margin
                    n_csr = home(below(csr, 1))
                csr = n_csr


if __name__ == '__main__':
    main()
