#!/usr/bin/env python
"""
A simple "game": hit all application keys to win.

Display all known key capabilities that may match the terminal. As each key is pressed on input, it
is lit up and points are scored.
"""
from __future__ import division, print_function

# std imports
import sys
import functools

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

    def echo(text):
        """Display ``text`` and flush output."""
        sys.stdout.write(u'{}'.format(text))
        sys.stdout.flush()


def refresh(term, board, level, score, inps):
    """Refresh the game screen."""
    echo(term.home + term.clear)
    level_color = level % 7
    if level_color == 0:
        level_color = 4
    bottom = 0
    for keycode, attr in board.items():
        echo(u''.join((
            term.move_yx(attr['row'], attr['column']),
            term.color(level_color),
            (term.reverse if attr['hit'] else term.bold),
            keycode,
            term.normal)))
        bottom = max(bottom, attr['row'])
    echo(term.move_yx(term.height, 0) + 'level: %s score: %s' % (level, score,))
    if bottom >= (term.height - 5):
        sys.stderr.write(
            ('\n' * (term.height // 2)) +
            term.center(term.red_underline('cheater!')) + '\n')
        sys.stderr.write(
            term.center("(use a larger screen)") +
            ('\n' * (term.height // 2)))
        sys.exit(1)
    echo(term.move_yx(bottom + 1, 0))
    echo('Press ^C to exit.')
    for row, inp in enumerate(inps[(term.height - (bottom + 3)) * -1:], 1):
        echo(term.move_yx(bottom + row + 1, 0))
        echo('{0!r}, {1}, {2}'.format(
            inp.__str__() if inp.is_sequence else inp,
             inp.code,
             inp.name))
        echo(term.clear_eol)


def build_gameboard(term):
    """Build the gameboard layout."""
    column, row = 0, 0
    board = {}
    spacing = 2
    for keycode in sorted(term._keycodes.values()):
        if (keycode.startswith('KEY_F')
                and keycode[-1].isdigit()
                and int(keycode[len('KEY_F'):]) > 24):
            continue
        if column + len(keycode) + (spacing * 2) >= term.width:
            column = 0
            row += 1
        board[keycode] = {'column': column,
                          'row': row,
                          'hit': 0,
                          }
        column += len(keycode) + (spacing * 2)
    return board


def add_score(score, pts, level):
    """Add points to score, determine and return new score and level."""
    lvl_multiplier = 10
    score += pts
    if (score % (pts * lvl_multiplier)) == 0:
        level += 1
    return score, level


def main():
    """Program entry point."""
    term = Terminal()
    score = level = hit_highbit = hit_unicode = 0
    dirty = True

    gameboard = build_gameboard(term)
    inps = []

    with term.raw(), term.keypad(), term.location():
        inp = term.inkey(timeout=0)
        while inp != chr(3):
            if dirty:
                refresh(term, gameboard, level, score, inps)
                dirty = False
            inp = term.inkey(timeout=5.0)
            dirty = True
            if (inp.is_sequence and
                    inp.name in gameboard and
                    gameboard[inp.name]['hit'] == 0):
                gameboard[inp.name]['hit'] = 1
                score, level = add_score(score, 100, level)
            elif inp and not inp.is_sequence and 128 <= ord(inp) <= 255:
                hit_highbit += 1
                if hit_highbit < 5:
                    score, level = add_score(score, 100, level)
            elif inp and not inp.is_sequence and ord(inp) > 256:
                hit_unicode += 1
                if hit_unicode < 5:
                    score, level = add_score(score, 100, level)
            inps.append(inp)

    with term.cbreak():
        echo(term.move_y(term.height))
        echo(
            u'{term.clear_eol}Your final score was {score} '
            u'at level {level}{term.clear_eol}\n'
            u'{term.clear_eol}\n'
            u'{term.clear_eol}You hit {hit_highbit} '
            u' 8-bit characters\n{term.clear_eol}\n'
            u'{term.clear_eol}You hit {hit_unicode} '
            u' unicode characters.\n{term.clear_eol}\n'
            u'{term.clear_eol}press any key\n'.format(
                term=term,
                score=score, level=level,
                hit_highbit=hit_highbit,
                hit_unicode=hit_unicode)
        )
        term.inkey()


if __name__ == '__main__':
    main()
