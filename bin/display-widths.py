#!/usr/bin/env python
"""Display graphemes whose rendered width differs by terminal as a labeled grid."""
# pylint: disable=invalid-name
#         Invalid module name "display-terminal-width"

# local
from blessed import Terminal

LABEL_WIDTH = 20
CELL_WIDTH = 12

# Examples "problematic" graphemes, derived from wcwidth "correction tables" and
# the ucs-detect project data: graphemes that carry per-terminal width corrections
ROWS = (
    ('Ambiguous width', ('\u00a7', '\u00b1', '\u00d7', '\u00f7')),
    ('VS-16', ('\u2764\ufe0f', '\u263a\ufe0f', '\u26a0\ufe0f', '\u2708\ufe0f')),
    ('Regional Indicator', ('\U0001f1e6', '\U0001f1fa\U0001f1f8',
                            '\U0001f1ef\U0001f1f5', '\U0001f1e9\U0001f1ea')),
    ('ZWJ', ('\U0001f9d1\u200d\U0001f33e',
             '\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466',
             '\U0001f9d1\u200d\U0001f393', '\U0001f9d1\u200d\U0001f4bb')),
    ('Devanagari', ('\u0924\u093e\u0903', '\u0930\u094d\u200d\u092f\u093e', '\u0915\u094d\u0937',
                    '\u0915\u094d\u0915')),
    ('Bengali', ('\u0995\u09bf\u0982', '\u09b8\u09cd\u09af\u09c7', '\u09b8\u09cd\u09ac\u09c0',
                 '\u09b8\u09cd\u09a4\u09bf')),
    ('Gujarati', ('\u0ab8\u0acd\u0ab8\u0abe', '\u0ab8\u0acd\u0ab5\u0ac0',
                  '\u0ab8\u0acd\u0ab5\u0abe', '\u0ab8\u0acd\u0ab0\u0ac0')),
    ('Gurmukhi', ('\u0a5c\u0a40\u0a02', '\u0a39\u0a40\u0a02',
                  '\u0a39\u0a3f\u0a71', '\u0a39\u0a3f\u0a70')),
    ('Tamil', ('\u0bb5\u0bbe', '\u0bb3\u0bbe',
               '\u0bb2\u0bbe', '\u0bb1\u0bbe')),
    ('Telugu', ('\u0c2f\u0c41\u0c02', '\u0c28\u0c41\u0c02',
                '\u0c26\u0c41\u0c02', '\u0c1f\u0c41\u0c02')),
    ('Kannada', ('\u0cb8\u0cbe\u0c82', '\u0cb6\u0cbe\u0c82',
                 '\u0cb5\u0cc1\u0c82', '\u0cb0\u0cbe\u0c82')),
    ('Malayalam', ('\u0d39\u0d3f\u0d02', '\u0d38\u0d4d\u0d38\u0d4b', '\u0d38\u0d4d\u0d38\u0d3f',
                   '\u0d38\u0d4d\u0d35\u0d40')),
    ('Sinhala', ('\u0dc4\u0dd2\u0d82', '\u0daf\u0dd2\u0d82', '\u0dc4\u0dcf', '\u0dc3\u0dcf')),
    ('Khmer', ('\u1796\u17c4\u17c7', '\u1794\u17c4\u17c7',
               '\u1793\u17c4\u17c7', '\u1793\u17c1\u17c7')),
    ('Myanmar', ('\u101c\u103b\u103e\u1031', '\u101c\u103b\u1031', '\u1019\u103c\u1031',
                 '\u1017\u103c\u1031')),
)


def main():
    """Program entry point."""
    term = Terminal()
    term.detect_ambiguous_width()

    columns = len(ROWS[0][1])
    border = term.cyan('+' + '-' * LABEL_WIDTH + ('+' + '-' * CELL_WIDTH) * columns + '+')
    fill = term.bright_yellow('.')
    title = 'Unidentified Terminal'
    if (_sw_ver := term.get_software_version()):
        title = repr(_sw_ver)

    print(term.center(title))
    print(border)
    for label, graphemes in ROWS:
        row = term.cyan('|') + term.magenta((' ' + label).ljust(LABEL_WIDTH)) + term.cyan('|')
        for grapheme in graphemes:
            row += term.magenta(term.center(grapheme, CELL_WIDTH, fill)) + term.cyan('|')
        print(row)
        print(border)


if __name__ == '__main__':
    main()
