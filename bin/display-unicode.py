#!/usr/bin/env python
"""Display terminal Unicode support using cursor location detection."""
# pylint: disable=invalid-name
#         Invalid module name "display-unicode"
import sys


def measure_width(term, text, timeout=1):
    """Measure actual rendered width of text using CPR."""
    _, x1 = term.get_location(timeout=timeout)
    if x1 == -1:
        return None
    sys.stdout.write(text)
    sys.stdout.flush()
    _, x2 = term.get_location(timeout=timeout)
    if x2 == -1:
        return None
    # Clear the test character
    sys.stdout.write(term.move_x(x1) + ' ' * (x2 - x1) + term.move_x(x1))
    sys.stdout.flush()
    return x2 - x1


WIDE_VERSION_TESTS = (
    # First NEW wide character introduced in each Unicode version (9.0+)
    ('9.0.0', '\u231A'),      # U+231A WATCH (first new wide in 9.0)
    ('10.0.0', '\u312E'),     # U+312E BOPOMOFO LETTER O WITH DOT ABOVE
    ('11.0.0', '\u312F'),     # U+312F BOPOMOFO LETTER NN
    ('12.0.0', '\U00016FE2'),  # U+16FE2 OLD CHINESE HOOK MARK
    ('12.1.0', '\u32FF'),     # U+32FF SQUARE ERA NAME REIWA
    ('13.0.0', '\u31BB'),     # U+31BB BOPOMOFO FINAL LETTER G
    ('14.0.0', '\U0001AFF0'),  # U+1AFF0 KATAKANA LETTER MINNAN TONE-2
    ('15.0.0', '\U0001B132'),  # U+1B132 HIRAGANA LETTER SMALL KO
    ('15.1.0', '\u2FFC'),     # U+2FFC KANGXI RADICAL SIMPLIFIED WALK
    ('16.0.0', '\u2630'),     # U+2630 TRIGRAM FOR HEAVEN
)

EMOJI_ZWJ_TESTS = (
    # First NEW ZWJ emoji sequence per Emoji version (11.0+)
    ('11.0', '\U0001F468\u200D\U0001F9B0'),  # man: red hair
    ('12.0', '\U0001F9D1\u200D\U0001F91D\u200D\U0001F9D1'),  # people holding hands
    ('12.1', '\U0001F9D1\u200D\U0001F33E'),  # farmer
    ('13.0', '\U0001F9D1\u200D\U0001F384'),  # mx claus
    ('13.1', '\u2764\uFE0F\u200D\U0001F525'),  # heart on fire
    ('14.0', '\U0001FAF1\U0001F3FB\u200D\U0001FAF2\U0001F3FC'),  # handshake: light, medium-light
    ('15.0', '\U0001F426\u200D\u2B1B'),  # black bird
    ('15.1', '\U0001F3C3\u200D\u27A1\uFE0F'),  # person running facing right
)

VS16_TEST = '\u231A\uFE0F'  # watch + VS16


def detect_wide_version(term, timeout=0.5):
    """Detect highest supported Unicode version for wide characters."""
    best_version = None
    for version, char in WIDE_VERSION_TESTS:
        width = measure_width(term, char, timeout)
        if width == 2:
            best_version = version
    return best_version


def detect_zwj_version(term, timeout=0.5):
    """Detect highest supported Emoji ZWJ version."""
    best_version = None
    for version, seq in EMOJI_ZWJ_TESTS:
        width = measure_width(term, seq, timeout)
        # ZWJ sequences should render as width 2 (single emoji)
        if width == 2:
            best_version = version
    return best_version


def detect_vs16_support(term, timeout=1):
    return measure_width(term, VS16_TEST, timeout) == 2


def main():
    """Program entry point."""
    # local
    from blessed import Terminal

    term = Terminal()
    print('Unicode Support Report')
    print('======================')
    print()

    wide_ver = detect_wide_version(term)
    if not wide_ver:
        print(term.bold_red('This terminal does not support unicode'))
        return

    print('- Wide characters ' + term.bold_green(f'supported (v{wide_ver})'))

    print('- Emojis with ZWJ ', end='')
    zwj_ver = detect_zwj_version(term)
    if zwj_ver:
        print(term.bold_green(f'supported (v{zwj_ver})'))
    else:
        print(term.bold_red('not supported'))

    print('- Emojis with VS-16 ', end='')
    if detect_vs16_support(term):
        print(term.bold_green('supported'))
    else:
        print(term.bold_red('not supported'))

    ambig_txt = 'wide (2)' if term.detect_ambiguous_width() == 2 else 'narrow (1)'
    print(f'- Ambiguous width is {ambig_txt}')


if __name__ == '__main__':
    main()
