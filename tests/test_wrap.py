"""Tests for Terminal.wrap()"""

# std imports
import sys
import textwrap

# 3rd party
import pytest

# local
from .conftest import TEST_QUICK
from .accessories import TestTerminal, as_subprocess

TEXTWRAP_KEYWORD_COMBINATIONS = [
    {'break_long_words': False, 'drop_whitespace': False, 'subsequent_indent': ''},
    {'break_long_words': False, 'drop_whitespace': True, 'subsequent_indent': ''},
    {'break_long_words': False, 'drop_whitespace': False, 'subsequent_indent': ' '},
    {'break_long_words': False, 'drop_whitespace': True, 'subsequent_indent': ' '},
    {'break_long_words': True, 'drop_whitespace': False, 'subsequent_indent': ''},
    {'break_long_words': True, 'drop_whitespace': True, 'subsequent_indent': ''},
    {'break_long_words': True, 'drop_whitespace': False, 'subsequent_indent': ' '},
    {'break_long_words': True, 'drop_whitespace': True, 'subsequent_indent': ' '},
    {
        'break_long_words': True, 'drop_whitespace': False,
        'subsequent_indent': '', 'max_lines': 4, 'placeholder': '~',
    },
    # break_on_hyphens combinations
    {'break_long_words': True, 'drop_whitespace': True, 'break_on_hyphens': True},
    {'break_long_words': True, 'drop_whitespace': True, 'break_on_hyphens': False},
]
if TEST_QUICK:
    # test only one feature: everything on
    TEXTWRAP_KEYWORD_COMBINATIONS = [
        {'break_long_words': True, 'drop_whitespace': True, 'subsequent_indent': ' '}
    ]


def test_SequenceWrapper_invalid_width():
    """Test exception thrown from invalid width."""
    WIDTH = -3

    @as_subprocess
    def child():
        term = TestTerminal()
        try:
            my_wrapped = term.wrap('------- -------------', WIDTH)
        except ValueError as err:
            assert err.args[0] == f"invalid width {WIDTH}({type(WIDTH)}) (must be integer > 0)"
        else:
            assert False, 'Previous stmt should have raised exception.'
            del my_wrapped  # assigned but never used

    child()


@pytest.mark.parametrize("kwargs", TEXTWRAP_KEYWORD_COMBINATIONS)
def test_SequenceWrapper(many_columns, kwargs):
    """Test that text wrapping matches internal extra options."""
    @as_subprocess
    def child(width, pgraph, kwargs):
        # build a test paragraph, along with a very colorful version
        term = TestTerminal()
        attributes = ('bright_red', 'on_bright_blue', 'underline', 'reverse',
                      'red_reverse', 'red_on_white', 'on_bright_white')
        term.bright_red('x')
        term.on_bright_blue('x')
        term.underline('x')
        term.reverse('x')
        term.red_reverse('x')
        term.red_on_white('x')
        term.on_bright_white('x')

        pgraph_colored = ''.join(
            getattr(term, (attributes[idx % len(attributes)]))(char)
            if char != ' ' else ' '
            for idx, char in enumerate(pgraph))

        internal_wrapped = textwrap.wrap(pgraph, width=width, **kwargs)
        my_wrapped = term.wrap(pgraph, width=width, **kwargs)
        my_wrapped_colored = term.wrap(pgraph_colored, width=width, **kwargs)

        # Older versions of textwrap could leave a preceding all whitespace line
        # https://github.com/python/cpython/issues/140627
        if (
            kwargs.get('drop_whitespace') and
            sys.version_info[:2] < (3, 15) and
            not internal_wrapped[0].strip()
        ):
            internal_wrapped = internal_wrapped[1:]
            # # This also means any subsequent indent got applied to the first line
            if kwargs.get('subsequent_indent'):
                internal_wrapped[0] = internal_wrapped[0][len(kwargs['subsequent_indent']):]

        # ensure we textwrap ascii the same as python
        assert internal_wrapped == my_wrapped

        # ensure content matches for each line, when the sequences are
        # stripped back off of each line
        for left, right in zip(internal_wrapped, my_wrapped_colored):
            assert left == term.strip_seqs(right)

        # ensure our colored textwrap is the same paragraph length
        assert (len(internal_wrapped) == len(my_wrapped_colored))

    child(width=many_columns, kwargs=kwargs,
          pgraph=' Z! a bc defghij klmnopqrstuvw<<>>xyz012345678900 ' * 2)
    child(width=many_columns, kwargs=kwargs, pgraph='a bb ccc')


def test_multiline():
    """Test that text wrapping matches internal extra options."""

    @as_subprocess
    def child():
        # build a test paragraph, along with a very colorful version
        term = TestTerminal()
        given_string = f'\n{32 * "A"}\n{32 * "B"}\n{32 * "C"}\n\n'
        expected = [
            '',
            'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
            'AA',
            'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
            'BB',
            'CCCCCCCCCCCCCCCCCCCCCCCCCCCCCC',
            'CC',
            '',
        ]
        result = term.wrap(given_string, width=30)
        assert expected == result

    child()


def test_east_asian_emojis_width_1():
    """Tests edge-case of east-asian and emoji characters split into single columns."""
    @as_subprocess
    def child():
        term = TestTerminal()
        # by @grayjk from https://github.com/jquast/blessed/issues/273
        result = term.wrap('\u5973', 1)
        assert result == ['\u5973']

        # ZWJ sequences are measured correctly: first emoji is width 2, ZWJ skips
        # itself and the following character on repeat until end of sequence,
        # Total width is 2.
        # RGI_Emoji_ZWJ_Sequence  ; family: woman, woman, girl, boy
        given = '\U0001F469\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466'
        result = term.wrap(given, 2)
        assert result == ['\U0001F469\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466']

        # in another example, two *narrow* characters, \u1100, "ᄀ" HANGUL
        # CHOSEONG KIYEOK (consonant) is joined with \u1161, "ᅡ" HANGUL
        # JUNGSEONG A (vowel), to form a single *wide* character "가" HANGUL
        # SYLLABLE GA.
        # 
        # This test isn't so great because a naive measurement accidentally
        # gets it right, there are a number of sequences like that.
        given = '\u1100\u1161\u1100\u1161'
        result = term.wrap(given, 2)
        assert result == [given[:2], given[2:]]

    child()


def test_emojis_width_2_and_greater():
    """Tests emoji characters split into multiple columns."""
    @as_subprocess
    def child():
        term = TestTerminal()
        given = '\U0001F469\U0001F467\U0001F466'  # woman, girl, boy
        result = term.wrap(given, 2)
        assert result == list(given)
        result = term.wrap(given, 3)
        assert result == list(given)
        result = term.wrap(given, 4)
        assert result == ['\U0001F469\U0001F467', '\U0001F466']
        result = term.wrap(given, 5)
        assert result == ['\U0001F469\U0001F467', '\U0001F466']
        result = term.wrap(given, 6)
        assert result == ['\U0001F469\U0001F467\U0001F466']
        result = term.wrap(given, 7)
        assert result == ['\U0001F469\U0001F467\U0001F466']

    child()


def test_greedy_join_with_cojoining():
    """Test that a word with trailing combining (café) wraps correctly."""
    @as_subprocess
    def child():
        term = TestTerminal()
        given = 'cafe\u0301-latte'
        # Use break_on_hyphens=False to test combining character handling
        result = term.wrap(given, 5, break_on_hyphens=False)
        assert result == ['cafe\u0301-', 'latte']
        result = term.wrap(given, 4, break_on_hyphens=False)
        assert result == ['cafe\u0301', '-lat', 'te']
        result = term.wrap(given, 3, break_on_hyphens=False)
        assert result == ['caf', 'e\u0301-l', 'att', 'e']
        result = term.wrap(given, 2, break_on_hyphens=False)
        assert result == ['ca', 'fe\u0301', '-l', 'at', 'te']

    child()


def test_placeholder():
    """ENsure placeholder behavior matches stdlib"""

    @as_subprocess
    def child():
        term = TestTerminal()
        text = 'The quick brown fox jumps over the lazy dog'
        kwargs = {'width': 1, 'max_lines': 3, 'placeholder': '...'}

        try:
            textwrap.wrap(text, **kwargs)
        except Exception as e:  # pylint: disable=broad-exception-caught
            stdlib_exc = e
        else:
            stdlib_exc = None

        with pytest.raises(stdlib_exc.__class__) as exc:
            term.wrap(text, **kwargs)
        assert exc.value.args == stdlib_exc.args

        kwargs = {'width': 10, 'max_lines': 3, 'placeholder': '...'}
        assert term.wrap(text, **kwargs) == textwrap.wrap(text, **kwargs)

        text = '1234567890 1234567890 extra'
        kwargs = {'width': 10, 'max_lines': 2, 'placeholder': '...'}
        assert term.wrap(text, **kwargs) == textwrap.wrap(text, **kwargs)

        text = '1234567890 1234567890'
        kwargs = {'width': 10, 'max_lines': 1, 'placeholder': '...'}
        assert term.wrap(text, **kwargs) == textwrap.wrap(text, **kwargs)

        text = 'short 1234567890 extra'
        kwargs = {'width': 10, 'max_lines': 2, 'placeholder': '...'}
        assert term.wrap(text, **kwargs) == textwrap.wrap(text, **kwargs)

    child()


def test_break_on_hyphens_in_handle_long_word():
    """Test break_on_hyphens is respected in _handle_long_word()."""
    @as_subprocess
    def child():
        term = TestTerminal()

        # Edge case: word forces _handle_long_word() to break it
        text = 'a-b-c-d'
        width = 3

        result = term.wrap(text, width=width, break_on_hyphens=True)
        assert result == ['a-', 'b-', 'c-d']

        result = term.wrap(text, width=width, break_on_hyphens=False)
        assert result == ['a-b', '-c-', 'd']

    child()


@pytest.mark.skipif(sys.version_info < (3, 10), reason="break_on_hyphens behavior differs")
def test_break_on_hyphens():
    """Test break_on_hyphens behavior matches stdlib for hyphenated words."""
    @as_subprocess
    def child():
        term = TestTerminal()
        attributes = ('bright_red', 'on_bright_blue', 'underline')

        # Test various hyphenated words
        test_cases = [
            ('hello-world', 8),       # breaks at hyphen when enabled
            ('super-long-hyphenated-word', 10),  # multiple hyphens
            ('a-b-c-d', 3),            # short segments
        ]

        for text, width in test_cases:
            # Create colored version
            text_colored = ''.join(
                getattr(term, attributes[idx % len(attributes)])(char)
                if char != '-' else char
                for idx, char in enumerate(text.replace('-', '')))
            # Re-insert hyphens in the right positions
            text_colored = ''
            attr_idx = 0
            for char in text:
                if char == '-':
                    text_colored += char
                else:
                    text_colored += getattr(term, attributes[attr_idx % len(attributes)])(char)
                    attr_idx += 1

            for break_hyphens in [True, False]:
                expected = textwrap.wrap(text, width=width, break_on_hyphens=break_hyphens)
                result_plain = term.wrap(text, width=width, break_on_hyphens=break_hyphens)
                result_colored = term.wrap(text_colored,
                                           width=width, break_on_hyphens=break_hyphens)
                result_stripped = [term.strip_seqs(line) for line in result_colored]

                # Plain text should match stdlib exactly
                assert result_plain == expected, (
                    f"Plain text mismatch for {text!r} at width={width}, "
                    f"break_on_hyphens={break_hyphens}: {result_plain} != {expected}"
                )

                # Colored text should match when sequences are stripped
                assert result_stripped == expected, (
                    f"Colored text mismatch for {text!r} at width={width}, "
                    f"break_on_hyphens={break_hyphens}: {result_stripped} != {expected}"
                )

    child()


def test_wrap_leading_sequence_preserved():
    """Leading escape sequence on first word should not be lost."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        # Color the first word - the leading sequence should be preserved
        text = term.red('The') + ' quick brown fox'
        result = term.wrap(text, width=20)
        # First line should start with the red sequence
        assert result[0].startswith('\x1b[')

    child()


@pytest.mark.parametrize("link", [
    '\x1b]8;;url\x1b\\x\x1b]8;;\x1b\\',
    '\x1b]8;;url\x07x\x1b]8;;\x07',
])
def test_wrap_hyperlink_osc8(link):
    """Test wrap with OSC 8 hyperlinks using ST and BEL terminators."""
    @as_subprocess
    def child(link):
        term = TestTerminal(force_styling=True)
        result = term.wrap(link, width=10)
        assert [term.strip_seqs(line) for line in result] == ['x']

    child(link)
