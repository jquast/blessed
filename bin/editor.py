#!/usr/bin/env python3
# Dumb full-screen editor. It doesn't save anything but to the screen.
#
# "Why wont python let me read memory
#  from screen like assembler? That's dumb." -hellbeard
from __future__ import division, print_function
import collections
import functools
from blessed import Terminal

echo = lambda text: (
    functools.partial(print, end='', flush=True)(text))

echo_yx = lambda cursor, text: (
    echo(cursor.term.move(cursor.y, cursor.x) + text))

Cursor = collections.namedtuple('Point', ('y', 'x', 'term'))

above = lambda csr, n: (
    Cursor(y=max(0, csr.y - n),
           x=csr.x,
           term=csr.term))

below = lambda csr, n: (
    Cursor(y=min(csr.term.height - 1, csr.y + n),
           x=csr.x,
           term=csr.term))

right_of = lambda csr, n: (
    Cursor(y=csr.y,
           x=min(csr.term.width - 1, csr.x + n),
           term=csr.term))

left_of = lambda csr, n: (
    Cursor(y=csr.y,
           x=max(0, csr.x - n),
           term=csr.term))

home = lambda csr: (
    Cursor(y=csr.y,
           x=0,
           term=csr.term))

end = lambda csr: (
    Cursor(y=csr.y,
           x=csr.term.width - 1,
           term=csr.term))

bottom = lambda csr: (
    Cursor(y=csr.term.height - 1,
           x=csr.x,
           term=csr.term))

top = lambda csr: (
    Cursor(y=1,
           x=csr.x,
           term=csr.term))

center = lambda csr: Cursor(
    csr.term.height // 2,
    csr.term.width // 2,
    csr.term)


lookup_move = lambda inp_code, csr, term: {
    # arrows
    csr.term.KEY_LEFT: left_of(csr, 1),
    csr.term.KEY_RIGHT: right_of(csr, 1),
    csr.term.KEY_DOWN: below(csr, 1),
    csr.term.KEY_UP: above(csr, 1),
    # keypad diagonals
    csr.term.KEY_LL: below(left_of(csr, 1), 1),
    csr.term.KEY_UL: above(left_of(csr, 1), 1),
    csr.term.KEY_LR: below(right_of(csr, 1), 1),
    csr.term.KEY_UR: above(right_of(csr, 1), 1),
    # center key == center of screen
    csr.term.KEY_CENTER: center(csr),
    # shift + arrows
    csr.term.KEY_SLEFT: left_of(csr, 10),
    csr.term.KEY_SRIGHT: right_of(csr, 10),
    csr.term.KEY_SDOWN: below(csr, 10),
    csr.term.KEY_SUP: above(csr, 10),
    # carriage return
    csr.term.KEY_ENTER: home(below(csr, 1)),
    # home, end
    csr.term.KEY_HOME: home(csr),
    csr.term.KEY_END: end(csr),
    # pgup, pgdown
    csr.term.KEY_PGUP: top(csr),
    csr.term.KEY_PGDOWN: bottom(csr),

}.get(inp_code, csr)


def readline(term, width=20):
    # a rudimentary readline function
    string = u''
    while True:
        inp = term.inkey()
        if inp.code == term.KEY_ENTER:
            break
        elif inp.code == term.KEY_ESCAPE or inp == chr(3):
            string = None
            break
        elif not inp.is_sequence and len(string) < width:
            string += inp
            echo(inp)
        elif inp.code in (term.KEY_BACKSPACE, term.KEY_DELETE):
            string = string[:-1]
            echo('\b \b')
    return string


def save(screen, fname):
    if not fname:
        return
    with open(fname, 'w') as fp:
        cur_row = cur_col = 0
        for (row, col) in sorted(screen):
            char = screen[(row, col)]
            while row != cur_row:
                cur_row += 1
                cur_col = 0
                fp.write(u'\n')
            while col > cur_col:
                cur_col += 1
                fp.write(u' ')
            fp.write(char)
            cur_col += 1
        fp.write(u'\n')


def redraw(term, screen, start=None, end=None):
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
        if (row >= start.y and row <= end.y and
                col >= start.x and col <= end.x):
            if col >= term.width or row >= term.height:
                # out of bounds
                continue
            if not (row == lastrow and col == lastcol + 1):
                # use cursor movement
                echo_yx(Cursor(row, col, term), screen[row, col])
            else:
                # just write past last one
                echo(screen[row, col])


def main():
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
                        term.ljust(term.bold_white('Filename: ')))
                echo_yx(right_of(home(bottom(csr)), len('Filename: ')), u'')
                save(screen, readline(term))
                echo_yx(home(bottom(csr)), term.clear_eol)
                redraw(term=term, screen=screen,
                       start=home(bottom(csr)),
                       end=end(bottom(csr)))
                continue

            elif inp == chr(12):
                # ^l refreshes
                redraw(term=term, screen=screen)

            n_csr = lookup_move(inp.code, csr, term)
            if n_csr != csr:
                # erase old cursor,
                echo_yx(csr, screen.get((csr.y, csr.x), u' '))
                csr = n_csr

            elif not inp.is_sequence and inp.isprintable():
                echo_yx(csr, inp)
                screen[(csr.y, csr.x)] = inp.__str__()
                n_csr = right_of(csr, 1)
                if n_csr == csr:
                    # wrap around margin
                    n_csr = home(below(csr, 1))
                csr = n_csr

if __name__ == '__main__':
    main()
