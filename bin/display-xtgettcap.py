#!/usr/bin/env python
"""
Query and display XTGETTCAP terminal capabilities in tabular format.

Usage::

    python bin/display-xtgettcap.py
"""
# std imports
import sys

# local
from blessed import Terminal
from blessed._capabilities import XTGETTCAP_CAPABILITIES


def main():
    """Main program entry point."""
    term = Terminal()

    result = term.get_xtgettcap()
    if result is None:
        print(f'{term.bold("XTGETTCAP")}: {term.bright_red("not supported")}')
        sys.exit(1)

    reported = len(result)
    total = len(XTGETTCAP_CAPABILITIES)
    print(f'{term.bold("XTGETTCAP")}: {reported}/{total} capabilities reported')
    print()
    print(f'   Terminal: {result.terminal_name}')
    print(f'   Colors: {result.num_colors}')
    print(f'   RGB: {result.rgb_bits}')
    print()

    # column widths
    cap_w = max([len(cap) for cap, _ in XTGETTCAP_CAPABILITIES] + [len('CAP')])
    desc_w = max([len(desc) for _, desc in XTGETTCAP_CAPABILITIES] + [len('Description')])

    # headers
    hdr_cap, hdr_desc, hdr_val = 'Cap', 'Description', 'Value'
    print(f'  {term.bold(hdr_cap.ljust(cap_w))}  '
          f'{term.bold(hdr_desc.ljust(desc_w))}  '
          f'{term.bold(hdr_val)}')
    print(f'  {"─" * cap_w}  {"─" * desc_w}  {"─" * 30}')

    # display all xtgettcaps with their descriptions
    for capname, desc in XTGETTCAP_CAPABILITIES:
        _color = term.bright_green if capname in result else term.bright_black
        value = result.get(capname, '--')
        print(f'  {_color(capname.ljust(cap_w))}  {desc.ljust(desc_w)}  {value!r}')


if __name__ == '__main__':
    main()
