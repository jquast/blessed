#!/usr/bin/env python
"""
Report the "tofus" for codepoints found in filepaths given by argument.

Requires a terminal implementing a font glyph coverage protocol, either mintty's ``OSC 7771`` or the
``APC 25a1`` Glyph Protocol of Rio terminal.
"""
# std imports
import sys
import unicodedata

# 3rd party
from wcwidth import iter_graphemes

# local
from blessed import Terminal

# Unicode Default_Ignorable_Code_Point ranges, of DerivedCoreProperties.txt.
DEFAULT_IGNORABLE_RANGES = (
    (0x000AD, 0x000AD),  # SOFT HYPHEN
    (0x0034F, 0x0034F),  # COMBINING GRAPHEME JOINER
    (0x0061C, 0x0061C),  # ARABIC LETTER MARK
    (0x0115F, 0x01160),  # HANGUL CHOSEONG FILLER, HANGUL JUNGSEONG FILLER
    (0x017B4, 0x017B5),  # KHMER VOWEL INHERENT AQ, AA
    (0x0180B, 0x0180F),  # MONGOLIAN FREE VARIATION SELECTORS, VOWEL SEPARATOR
    (0x0200B, 0x0200F),  # ZERO WIDTH SPACE through RIGHT-TO-LEFT MARK
    (0x0202A, 0x0202E),  # bidi embedding and override
    (0x02060, 0x0206F),  # WORD JOINER through NOMINAL DIGIT SHAPES
    (0x03164, 0x03164),  # HANGUL FILLER
    (0x0FE00, 0x0FE0F),  # VARIATION SELECTOR-1 through -16
    (0x0FEFF, 0x0FEFF),  # ZERO WIDTH NO-BREAK SPACE
    (0x0FFA0, 0x0FFA0),  # HALFWIDTH HANGUL FILLER
    (0x0FFF0, 0x0FFF8),  # reserved
    (0x1BCA0, 0x1BCA3),  # SHORTHAND FORMAT
    (0x1D173, 0x1D17A),  # MUSICAL SYMBOL BEGIN BEAM through END PHRASE
    (0xE0000, 0xE0FFF),  # LANGUAGE TAG, tag characters, VARIATION SELECTOR-17 to -256
)


def is_drawn(char):
    """Whether *char* is drawn, and so needs a glyph of its own in the font."""
    return not any(start <= ord(char) <= stop
                   for start, stop in DEFAULT_IGNORABLE_RANGES)


def missing_codepoints(coverage, grapheme):
    """Return the drawn codepoints of *grapheme* the font has no glyph for."""
    # a codepoint the terminal would not answer for is not a codepoint it called
    # uncovered, and is assumed renderable, as reported by main() below
    return {char for char in unicodedata.normalize('NFC', grapheme)
            if is_drawn(char) and char not in coverage
            and ord(char) not in coverage.unknown}


def describe(char):
    """Return the Unicode name of *char*, or its category when it has none."""
    return unicodedata.name(char, '').title() or f'<{unicodedata.category(char)}>'


def status(term, message):
    """Overwrite the transient status line on stderr, cleared by an empty *message*."""
    print('\r' + message + term.clear_eol, end='' if message else '\n',
          file=sys.stderr, flush=True)


def label_codepoints(grapheme, missing):
    """Return ``'U+XXXX Name + ...'`` for the *missing* codepoints of *grapheme*."""
    return ' + '.join(f'U+{ord(char):04X} {describe(char)}'
                      for char in unicodedata.normalize('NFC', grapheme)
                      if char in missing)


def main():
    term = Terminal()

    graphemes = set()
    for filepath in sys.argv[1:]:
        with open(filepath, 'r', encoding='utf-8') as fin:
            status(term, f'read: {filepath}')
            graphemes.update(iter_graphemes(fin.read()))
    if not graphemes:
        print(f'usage: {sys.executable} {__file__} FILE [FILE ...]', file=sys.stderr)
        return 2

    # zero-width graphemes occupy no cell of their own to be a tofu in
    to_test = sorted(gr for gr in graphemes if term.length(gr) != 0)

    status(term, 'testing...')
    # one call resolves every codepoint of every grapheme, in batched round-trips
    coverage = term.get_font_coverage(''.join(
        unicodedata.normalize('NFC', grapheme) for grapheme in to_test))
    if not coverage:
        status(term, '')
        print('Font glyph protocol not supported by this terminal.', file=sys.stderr)
        return 1
    if coverage.unknown:
        print(f'{len(coverage.unknown)} codepoints went unanswered by the terminal, '
              f'and are assumed renderable.', file=sys.stderr)

    missing = {grapheme: found
               for grapheme in to_test
               if (found := missing_codepoints(coverage, grapheme))}

    status(term, 'reporting...')
    if not missing:
        status(term, '')
        print(f'No tofus discovered of {len(to_test)} graphemes tested', file=sys.stderr)
        return 0

    # collect first, so that the columns may be sized to the widest of them
    rows = []
    for filepath in sys.argv[1:]:
        with open(filepath, 'r', encoding='utf-8') as fin:
            for lineno, line in enumerate(fin, 1):
                cells = list(iter_graphemes(line.rstrip('\n')))
                for grapheme in dict.fromkeys(cells):
                    if grapheme in missing:
                        rows.append((cells.count(grapheme),
                                     f'{filepath}:{lineno}', grapheme))

    count_width = max(len(str(count)) for count, _, _ in rows)
    where_width = max(len(where) for _, where, _ in rows)
    tofu_count = sum(count for count, _, _ in rows)

    status(term, '')
    print(f'{tofu_count} tofus of {len(to_test)} graphemes tested, listed with the '
          f'codepoints the font has no glyph for:\n', file=sys.stderr)

    for count, where, grapheme in rows:
        # the cluster occupies one or two cells, pad the narrow ones to align
        cell = grapheme + ' ' * (2 - term.length(grapheme))
        prefix = f'{count:>{count_width}} {where:<{where_width}} │{cell}│ '
        codepoints = label_codepoints(grapheme, missing[grapheme])
        print(term.truncate(prefix + codepoints, term.width))

    return 1


if __name__ == '__main__':
    sys.exit(main())
