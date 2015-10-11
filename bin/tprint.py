#!/usr/bin/env python
"""A simple cmd-line tool for displaying FormattingString capabilities."""
from __future__ import print_function
import argparse

def main():
    """Program entry point."""
    from blessed import Terminal

    parser = argparse.ArgumentParser(
        description='displays argument as specified style')

    parser.add_argument('style', type=str, help='style formatter')
    parser.add_argument('text', type=str, nargs='+')


    term = Terminal()
    args = parser.parse_args()

    style = getattr(term, args.style)

    print(style(' '.join(args.text)))

if __name__ == '__main__':
    main()
