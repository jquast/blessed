#!/usr/bin/env python
"""Demonstrate both ASCII in-terminal progress bars and OSC 9;4 taskbar/dock progress."""
# local
from blessed import Terminal


def make_bar(term, state, value=0):
    """Return a labeled ASCII progress-bar string with OSC 9;4 sequence."""
    width = max(10, term.width - 25)
    filled = int(width * value / 100)
    bar = '[' + '=' * filled + '>' + ' ' * (width - filled - 1) + ']'
    ascii_bar = f'{state.title():>13s}: {bar} {value:3d}%'
    return term.move_x(0) + ascii_bar + term.progress_bar(state, value) + term.clear_eol


def dexit(term, delay):
    if term.inkey(delay) == 'q':
        quit()


def main():
    """Program entry point."""
    term = Terminal()

    print(term.reverse(term.center('Progress Bar Demo')))
    print('Progress bar demo')

    def echo(*args):
        print(*args, sep='', end='', flush=True)

    with term.cbreak(), term.hidden_cursor():
        # Normal progress 0 -> 100
        for val_pct in range(0, 101):
            echo(make_bar(term, 'normal', val_pct))
            dexit(term, 0.03)
        echo(make_bar(term, 'clear'))

        # Static states
        for state in ('error', 'paused', 'indeterminate'):
            echo(make_bar(term, state))
            dexit(term, 2)
            echo(make_bar(term, 'clear'))

        # Reverse progress 100 -> 0
        for val_pct in range(100, -1, -1):
            echo(make_bar(term, 'normal', val_pct))
            dexit(term, 0.03)

        echo(make_bar(term, 'clear'))

    print('\nDemo complete.')


if __name__ == '__main__':
    main()
