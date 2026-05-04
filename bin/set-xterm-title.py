#!/usr/bin/env python3
"""Set the xterm window title using blessed."""
import argparse
import sys

from blessed import Terminal


def main():
    parser = argparse.ArgumentParser(description='Set the xterm window title.')
    parser.add_argument('title', nargs='+', help='Title text to set.')
    parser.add_argument('-m', '--mode', type=int, default=0, choices=[0, 1, 2],
                        help='OSC mode: 0=both (default), 1=icon only, 2=title only.')
    args = parser.parse_args()

    term = Terminal()
    title = ' '.join(args.title)
    seq = term.set_window_title(title, mode=args.mode)
    if not seq:
        print('Terminal does not support styling.', file=sys.stderr)
        raise SystemExit(1)
    sys.stdout.write(seq)
    sys.stdout.flush()


if __name__ == '__main__':
    main()
