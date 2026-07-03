"""Tests for Terminal() sequences and sequence-awareness."""
# std imports
import sys
import platform
from io import StringIO

# 3rd party
import pytest

# local
from .conftest import IS_WINDOWS
from .accessories import (
    TestTerminal, unicode_cap, unicode_parm, pty_test)


@pytest.mark.skipif(IS_WINDOWS, reason="requires real tty")
def test_capability():
    """Check that capability lookup works."""
    def child():
        # Also test that Terminal grabs a reasonable default stream.
        t = TestTerminal(force_styling=True)
        sc = unicode_cap('sc', t)
        assert t.save == sc
        assert t.save == sc  # Make sure caching doesn't screw it up.

    child()


def test_capability_without_tty():
    """Assert capability templates are '' when stream is not a tty."""
    def child():
        t = TestTerminal(stream=StringIO())
        assert t.save == ''
        assert t.red == ''

    child()


def test_capability_with_forced_tty():
    """force styling should return sequences even for non-ttys."""
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        assert t.save == unicode_cap('sc', t)

    child()


def test_basic_url():
    """force styling should return sequences even for non-ttys."""
    def child():
        # given
        t = TestTerminal(stream=StringIO(), force_styling=True)
        given_url = 'https://blessed.readthedocs.org'
        given_text = 'documentation'
        expected_output = f'\x1b]8;;{given_url}\x1b\\{given_text}\x1b]8;;\x1b\\'

        # exercise
        result = t.link(given_url, 'documentation')

        # verify
        assert repr(result) == repr(expected_output)

    child()


def test_url_with_id():
    """force styling should return sequences even for non-ttys."""
    def child():
        # given
        t = TestTerminal(stream=StringIO(), force_styling=True)
        given_url = 'https://blessed.readthedocs.org'
        given_text = 'documentation'
        given_url_id = '123'
        expected_output = f'\x1b]8;id={given_url_id};{given_url}\x1b\\{given_text}\x1b]8;;\x1b\\'

        # exercise
        result = t.link(given_url, 'documentation', given_url_id)

        # verify
        assert repr(result) == repr(expected_output)

    child()


def test_parametrization():
    """Test parameterizing a capability."""
    def child():
        term = TestTerminal(force_styling=True)
        assert term.cup(3, 4) == unicode_parm('cup', term, 3, 4)

    child()


def test_height_and_width():
    """Assert that ``height_and_width()`` returns full integers."""
    def child():
        t = TestTerminal()  # kind shouldn't matter.
        assert isinstance(t.height, int)
        assert isinstance(t.width, int)

    child()


def test_stream_attr():
    """Make sure Terminal ``stream`` is stdout by default."""
    def child():
        assert TestTerminal().stream == sys.__stdout__

    child()


def test_location_with_styling(any_term):
    """Make sure ``location()`` works on all terminals."""
    def child_with_styling(kind):
        t = TestTerminal(kind=kind, stream=StringIO(), force_styling=True)
        with t.location(3, 4):
            t.stream.write('hi')
        expected_output = ''.join(
            (unicode_cap('sc', t) or '\x1b[s',
             unicode_parm('cup', t, 4, 3),
             'hi',
             unicode_cap('rc', t) or '\x1b[u'))
        assert t.stream.getvalue() == expected_output

    child_with_styling(any_term)


def test_location_without_styling():
    """Make sure ``location()`` silently passes without styling."""
    def child_without_styling():
        """No side effect for location as a context manager without styling."""
        t = TestTerminal(stream=StringIO(), force_styling=None)

        with t.location(3, 4):
            t.stream.write('hi')

        assert t.stream.getvalue() == 'hi'

    child_without_styling()


def test_horizontal_location(any_term):
    """Make sure we can move the cursor horizontally without changing rows."""
    def child(kind):
        t = TestTerminal(kind=kind, stream=StringIO(), force_styling=True)
        with t.location(x=5):
            pass
        _hpa = unicode_parm('hpa', t, 5)
        if not _hpa and (kind.startswith('screen') or
                         kind.startswith('ansi')):
            _hpa = '\x1b[6G'
        expected_output = ''.join(
            (unicode_cap('sc', t) or '\x1b[s',
             _hpa,
             unicode_cap('rc', t) or '\x1b[u'))
        assert (t.stream.getvalue() == expected_output), (
            repr(t.stream.getvalue()), repr(expected_output))

    child(any_term)


def test_vertical_location(any_term):
    """Make sure we can move the cursor vertically without changing columns."""
    def child(kind):
        t = TestTerminal(kind=kind, stream=StringIO(), force_styling=True)
        with t.location(y=5):
            pass
        _vpa = unicode_parm('vpa', t, 5)
        if not _vpa and (kind.startswith('screen') or
                         kind.startswith('ansi')):
            _vpa = '\x1b[6d'

        expected_output = ''.join(
            (unicode_cap('sc', t) or '\x1b[s',
             _vpa,
             unicode_cap('rc', t) or '\x1b[u'))
        assert t.stream.getvalue() == expected_output

    child(any_term)


@pytest.mark.skipif(IS_WINDOWS, reason="requires multiprocess")
def test_screen_ansi_hpa_from_jinxed():
    """hpa for screen and ansi comes from jinxed terminfo directly."""
    def child(kind):
        t = TestTerminal(kind=kind, stream=StringIO(), force_styling=True)
        COL = 5
        with t.location(x=COL):
            pass
        expected_output = ''.join((
            unicode_cap('sc', t) or '\x1b[s',
            t.move_x(COL),
            unicode_cap('rc', t) or '\x1b[u',
        ))
        assert t.stream.getvalue() == expected_output

    child('screen')
    child('screen-256color')
    child('ansi')


@pytest.mark.skipif(IS_WINDOWS, reason="requires multiprocess")
def test_screen_ansi_vpa_from_jinxed():
    """vpa for screen and ansi comes from jinxed terminfo directly."""
    def child(kind):
        t = TestTerminal(kind=kind, stream=StringIO(), force_styling=True)
        ROW = 5
        with t.location(y=ROW):
            pass
        expected_output = ''.join((
            unicode_cap('sc', t) or '\x1b[s',
            t.move_y(ROW),
            unicode_cap('rc', t) or '\x1b[u',
        ))
        assert t.stream.getvalue() == expected_output

    child('screen')
    child('screen-256color')
    child('ansi')


@pytest.mark.skipif(IS_WINDOWS, reason="requires multiprocess")
def test_ansi_civis_cnorm_from_jinxed():
    """civis and cnorm for ansi come from jinxed terminfo directly."""
    def child(kind):
        t = TestTerminal(kind=kind, stream=StringIO(), force_styling=True)
        with t.hidden_cursor():
            pass
        expected_output = ''.join((
            unicode_cap('civis', t),
            unicode_cap('cnorm', t),
        ))
        assert t.stream.getvalue() == expected_output

    child('ansi')


@pytest.mark.skipif(IS_WINDOWS, reason="requires multiprocess")
def test_ansi_sc_rc_from_jinxed():
    """sc and rc for ansi come from jinxed terminfo directly."""
    def child(kind):
        t = TestTerminal(kind=kind, stream=StringIO(), force_styling=True)
        with t.location():
            pass
        expected_output = ''.join((
            unicode_cap('sc', t),
            unicode_cap('rc', t),
        ))
        assert t.stream.getvalue() == expected_output

    child('ansi')


def test_zero_location(any_term):
    """Make sure ``location()`` pays attention to 0-valued args."""
    def child(kind):
        t = TestTerminal(kind=kind, stream=StringIO(), force_styling=True)
        with t.location(0, 0):
            pass
        expected_output = ''.join(
            (unicode_cap('sc', t) or '\x1b[s',
             unicode_parm('cup', t, 0, 0),
             unicode_cap('rc', t) or '\x1b[u'))
        assert t.stream.getvalue() == expected_output

    child(any_term)


def test_mnemonic_colors(any_term):
    """Make sure color shortcuts work."""

    def child(kind):
        def color(t, num):
            return t.number_of_colors and unicode_parm('setaf', t, num) or ''

        def on_color(t, num):
            return t.number_of_colors and unicode_parm('setab', t, num) or ''

        # Avoid testing red, blue, yellow, and cyan, since they might someday
        # change depending on terminal type.
        t = TestTerminal(kind=kind)
        assert t.white == color(t, 7)
        assert t.green == color(t, 2)  # Make sure it's different than white.
        assert t.on_black == on_color(t, 0)
        assert t.on_green == on_color(t, 2)
        assert t.bright_black == color(t, 8)
        assert t.bright_green == color(t, 10)
        assert t.on_bright_black == on_color(t, 8)
        assert t.on_bright_green == on_color(t, 10)

    child(any_term)


def test_callable_numeric_colors(any_term):
    """``color(n)`` should return a formatting wrapper."""
    def child(kind):
        t = TestTerminal(kind=kind)
        if t.magenta:
            assert t.color(5)('smoo') == f'{t.magenta}smoo{t.normal}'
        else:
            assert t.color(5)('smoo') == 'smoo'

        if t.on_magenta:
            assert t.on_color(5)('smoo') == f'{t.on_magenta}smoo{t.normal}'
        else:
            assert t.color(5)('smoo') == 'smoo'

        if t.color(4):
            assert t.color(4)('smoo') == f'{t.color(4)}smoo{t.normal}'
        else:
            assert t.color(4)('smoo') == 'smoo'

        if t.on_green:
            assert t.on_color(2)('smoo') == f'{t.on_green}smoo{t.normal}'
        else:
            assert t.on_color(2)('smoo') == 'smoo'

        if t.on_color(6):
            assert t.on_color(6)('smoo') == f'{t.on_color(6)}smoo{t.normal}'
        else:
            assert t.on_color(6)('smoo') == 'smoo'

    child(any_term)


def test_null_callable_numeric_colors(any_term):
    """``color(n)`` should be a no-op on null terminals."""
    def child(kind):
        t = TestTerminal(stream=StringIO(), kind=kind)
        assert t.color(5)('smoo') == 'smoo'
        assert t.on_color(6)('smoo') == 'smoo'

    child(any_term)


def test_naked_color_cap(any_term):
    """``term.color`` should return a stringlike capability."""
    def child(kind):
        t = TestTerminal(kind=kind)
        assert f'{t.color}' == f'{t.setaf}'

    child(any_term)


def test_formatting_functions(any_term):
    """Test simple and compound formatting wrappers."""
    def child(kind):
        t = TestTerminal(kind=kind)
        # test simple sugar,
        expected_output = ''.join((t.bold, 'hi', t.normal)) if t.bold else 'hi'
        assert t.bold('hi') == expected_output
        expected_output = ''.join((t.green, 'hi', t.normal)) if t.green else 'hi'
        assert t.green('hi') == expected_output
        # Test unicode
        expected_output = ''.join((t.underline, 'boö', t.normal)) if t.underline else 'boö'
        assert t.underline('boö') == expected_output
        expected_output = ''.join((t.strikethrough, 'sx', t.normal)) if t.strikethrough else 'sx'
        assert t.strikethrough('sx') == expected_output
        expected_output = ''.join((t.overline, 'ol', t.normal)) if t.overline else 'ol'
        assert t.overline('ol') == expected_output

    child(any_term)


def test_compound_formatting(any_term):
    """Test simple and compound formatting wrappers."""
    def child(kind):
        t = TestTerminal(kind=kind)
        expected_output = (
            ''.join((t.bold, t.green, 'boö', t.normal)) if any((t.bold, t.green)) else 'boö'
        )
        assert t.bold_green('boö') == expected_output

        expected_output = (
            ''.join((t.on_bright_red, t.bold, t.bright_green, t.underline, 'meh', t.normal))
            if any((t.on_bright_red, t.bold, t.bright_green, t.underline))
            else 'meh'
        )
        assert t.on_bright_red_bold_bright_green_underline('meh') == expected_output

        expected_output = (
            ''.join((t.strikethrough, t.bold, 'sx', t.normal))
            if any((t.strikethrough, t.bold)) else 'sx'
        )
        assert t.strikethrough_bold('sx') == expected_output

    child(any_term)


def test_nested_formatting(any_term):
    """Test complex nested compound formatting, wow!"""
    def child(kind):
        t = TestTerminal(kind=kind)

        # Test deeply nested styles
        given = t.green('-a-', t.bold('-b-', t.underline('-c-'),
                                      '-d-'),
                        '-e-')
        expected = ''.join((
            t.green, '-a-', t.bold, '-b-', t.underline, '-c-', t.normal,
            t.green, t.bold, '-d-',
            t.normal, t.green, '-e-', t.normal))
        assert given == expected

        # Test off-and-on nested styles
        given = t.green('off ', t.underline('ON'),
                        ' off ', t.underline('ON'),
                        ' off')
        expected = ''.join((
            t.green, 'off ', t.underline, 'ON',
            t.normal, t.green, ' off ', t.underline, 'ON',
            t.normal, t.green, ' off', t.normal))
        assert given == expected

    child(any_term)


def test_formatting_functions_without_tty(any_term):
    """Test crazy-ass formatting wrappers when there's no tty."""
    def child(kind):
        t = TestTerminal(kind=kind, stream=StringIO(), force_styling=False)
        assert t.bold('hi') == 'hi'
        assert t.green('hi') == 'hi'
        # Test non-ASCII chars, no longer really necessary:
        assert t.bold_green('boö') == 'boö'
        assert t.bold_underline_green_on_red('loo') == 'loo'

        # Test deeply nested styles
        given = t.green('-a-', t.bold('-b-', t.underline('-c-'),
                                      '-d-'),
                        '-e-')
        expected = '-a--b--c--d--e-'
        assert given == expected

        # Test off-and-on nested styles
        given = t.green('off ', t.underline('ON'),
                        ' off ', t.underline('ON'),
                        ' off')
        expected = 'off ON off ON off'
        assert given == expected
        assert t.on_bright_red_bold_bright_green_underline('meh') == 'meh'

    child(any_term)


def test_nice_formatting_errors(any_term):
    """Make sure you get nice hints if you misspell a formatting wrapper."""
    def child(kind):
        t = TestTerminal(kind=kind)
        try:
            t.bold_misspelled('hey')
            assert not t.is_a_tty, 'Should have thrown exception'
        except TypeError as e:
            assert 'Unknown terminal capability,' in e.args[0]
        try:
            t.bold_misspelled('hey')  # unicode
            assert not t.is_a_tty, 'Should have thrown exception'
        except TypeError as e:
            assert 'Unknown terminal capability,' in e.args[0]

        try:
            t.bold_misspelled(None)  # an arbitrary non-string
            assert not t.is_a_tty, 'Should have thrown exception'
        except TypeError as e:
            assert 'Unknown terminal capability,' not in e.args[0]

        if platform.python_implementation() != 'PyPy':
            # PyPy fails to toss an exception, Why?!
            try:
                t.bold_misspelled('a', 'b')  # >1 string arg
                assert not t.is_a_tty, 'Should have thrown exception'
            except TypeError as e:
                assert 'Unknown terminal capability,' in e.args[0], e.args

    child(any_term)


def test_null_callable_string(any_term):
    """Make sure NullCallableString tolerates all kinds of args."""
    def child(kind):
        t = TestTerminal(stream=StringIO(), kind=kind)
        assert t.clear == ''
        assert t.move(False) == ''
        assert t.move_x(1) == ''
        assert t.bold() == ''
        assert t.bold('', 'x', 'huh?') == 'xhuh?'
        assert t.clear('x') == 'x'

    child(any_term)


def test_padd():
    """Test Terminal.padd(seq)."""
    def child(kind):
        # local

        from blessed.sequences import Sequence
        term = TestTerminal(kind=kind)
        assert Sequence('xyz\b', term).padd() == 'xy'
        assert Sequence('xyz\b-', term).padd() == 'xy-'
        assert Sequence('xxxx\x1b[3Dzz', term).padd() == 'xzz'
        assert Sequence('\x1b[3D', term).padd() == ''  # "Trim left"
        assert Sequence(term.red('xxxx\x1b[3Dzz'), term).padd() == term.red('xzz')
    kind = 'vtwin10' if IS_WINDOWS else 'xterm-256color'
    child(kind)


def test_split_seqs(any_term):
    """Test Terminal.split_seqs."""
    def child(kind):
        # local

        term = TestTerminal(kind=kind)

        if term.sc and term.rc:
            given_text = f'{term.sc}AB{term.rc}CD'
            expected = [term.sc, 'A', 'B', term.rc, 'C', 'D']
            result = list(term.split_seqs(given_text))
            assert result == expected

    child(any_term)


def test_split_seqs_maxsplit1(any_term):
    """Test Terminal.split_seqs with maxsplit=1."""
    def child(kind):
        # local

        term = TestTerminal(kind=kind)

        if term.bold:
            given_text = f'{term.bold}bbq'
            expected = [term.bold, 'bbq']
            result = list(term.split_seqs(given_text, 1))
            assert result == expected

            # Another case where split matches exactly
            assert list(term.split_seqs(f'{term.bold}b', 1)) == [term.bold, 'b']

    child(any_term)


def test_split_seqs_term_right(any_term):
    """Test Terminal.split_seqs with parameterized sequence"""
    def child(kind):
        # local

        term = TestTerminal(kind=kind)

        if term.move_up:
            given_text = f'XY{term.move_right}VK'
            expected = ['X', 'Y', term.move_right, 'V', 'K']
            result = list(term.split_seqs(given_text))
            assert result == expected

    child(any_term)


def test_split_seqs_maxsplit3_and_term_right(any_term):
    """Test Terminal.split_seqs with parameterized sequence."""
    def child(kind):
        # local

        term = TestTerminal(kind=kind)

        if term.move_right(32):
            given_text = f'PQ{term.move_right(32)}RS'
            expected = ['P', 'Q', term.move_right(32), 'RS']
            result = list(term.split_seqs(given_text, 3))
            assert result == expected

        if term.move_up(45):
            given_text = f'XY{term.move_up(45)}VK'
            expected = ['X', 'Y', term.move_up(45), 'V', 'K']
            result = list(term.split_seqs(given_text))
            assert result == expected

    child(any_term)


def test_invalid_params_for_horizontal_distance(any_term):
    """Raise error if text parametrized horizontal distance is invalid"""
    def child(kind):
        term = TestTerminal(stream=StringIO(), kind=kind, force_styling=True)
        with pytest.raises(ValueError) as e:
            term.caps['parm_left_cursor'].horizontal_distance('\x1b[C')
            assert e.value == "Invalid parameters for termccap parm_left_cursor: '\x1b[C'"

    child(any_term)


def test_formatting_other_string(any_term):
    """FormattingOtherString output depends on how it's called"""
    def child(kind):
        t = TestTerminal(stream=StringIO(), kind=kind, force_styling=True)

        assert t.move_left == t.cub1
        assert t.move_left() == t.cub1
        assert t.move_left(2) == t.cub(2)

        assert t.move_right == t.cuf1
        assert t.move_right() == t.cuf1
        assert t.move_right(2) == t.cuf(2)

        assert t.move_up == t.cuu1
        assert t.move_up() == t.cuu1
        assert t.move_up(2) == t.cuu(2)

        assert t.move_down == t.cud1
        assert t.move_down() == t.cud1
        assert t.move_down(2) == t.cud(2)

    child(any_term)


def test_termcap_match_optional():
    """When match_optional is given, numeric matches are optional"""
    def child():
        # local
        from blessed.sequences import Termcap

        t = TestTerminal(force_styling=True)
        cap = Termcap.build('move_right', t.cuf, 'cuf', nparams=1,
                            match_grouped=True, match_optional=True)

        # Digits absent
        assert cap.re_compiled.match(t.cuf1).group(1) is None

        # Digits present
        assert cap.re_compiled.match(t.cuf()).group(1) == '0'
        assert cap.re_compiled.match(t.cuf(1)).group(1) == '1'
        assert cap.re_compiled.match(t.cuf(22)).group(1) == '22'

        # Make sure match is not too generalized
        assert cap.re_compiled.match(t.cub(2)) is None
        assert cap.re_compiled.match(t.cub1) is None

    child()


def test_truncate(any_term):
    """Test terminal.truncate and make sure it agrees with terminal.length"""
    def child(kind):
        # local

        term = TestTerminal(kind=kind)

        test_string = (
            f'{term.red("Testing")} {term.yellow("makes")} {term.green("me")} '
            f'{term.blue("feel")} {term.indigo("good")}{term.normal}'
        )
        stripped_string = term.strip_seqs(test_string)
        for i in range(len(stripped_string)):
            test_l = term.length(term.truncate(test_string, i))
            assert test_l == len(stripped_string[:i])

        # Verify truncating removes "good" - check length and visible content
        target_width = term.length(test_string) - len("good")
        trunc = term.truncate(test_string, target_width)
        assert term.length(trunc) == target_width
        assert term.strip_seqs(trunc) == "Testing makes me feel "

    child(any_term)


def test_truncate_wide_end(any_term):
    """Ensure that terminal.truncate has the correct behaviour for wide characters."""
    def child(kind):
        # local

        term = TestTerminal(kind=kind)
        # ABＣ where Ｃ is width 2 - truncating to 3 fills with space
        test_string = "AB\uff23"
        assert term.truncate(test_string, 3) == "AB "
        assert term.truncate(test_string, 4) == "AB\uff23"

    child(any_term)


def test_truncate_wcwidth_clipping(any_term):
    """Ensure that terminal.truncate has the correct behaviour for control characters."""
    def child(kind):
        # local

        term = TestTerminal(kind=kind)
        assert term.truncate("", 4) == ""
        # Control character \x01 has zero width
        test_string = term.blue("one\x01two")
        trunc = term.truncate(test_string, 4)
        assert term.length(trunc) == 4
        assert term.strip_seqs(trunc) == "one\x01t"

    child(any_term)


def test_truncate_padding(any_term):
    """Ensure that terminal.truncate correctly handles cursor movement sequences."""
    def child(kind):
        # local

        term = TestTerminal(kind=kind)

        if term.move_right(5):
            test_right_string = term.blue(f"one{term.move_right(5)}two")
            trunc = term.truncate(test_right_string, 9)
            assert term.length(trunc) == 9
            assert term.strip_seqs(trunc) == "one     t"

        test_bs_string = term.blue("one\b\b\btwo")
        trunc_bs = term.truncate(test_bs_string, 3)
        assert term.length(trunc_bs) == 3
        assert term.strip_seqs(trunc_bs) == "two"

    if any_term != 'vtwin10':
        # padding doesn't work the same on windows !
        child(any_term)


@pytest.mark.skipif(IS_WINDOWS, reason="requires fcntl")
def test_truncate_default():
    """Ensure that terminal.truncate functions with the default argument."""
    def child(term):
        assert term.width == 80

        test = f'Testing {term.red("attention ")}{term.blue("please.")}'
        trunc = term.truncate(test)
        assert term.length(trunc) <= term.width

        # Verify truncation to terminal width with SGR propagation
        trunc_long = term.truncate(term.red('x' * 1000))
        assert term.length(trunc_long) == term.width
        assert term.strip_seqs(trunc_long) == 'x' * term.width

    pty_test(child, parent_func=None, test_name='test_truncate_default')


def test_truncate_zwj_emoji(any_term):
    """Test truncate handles ZWJ emoji sequences."""
    def child(kind):
        # local

        term = TestTerminal(kind=kind)

        # Family emoji: 👨 + ZWJ + 👩 + ZWJ + 👧 (wcswidth=2)
        given_zwj = '\U0001F468\u200D\U0001F469\u200D\U0001F467'
        given = given_zwj + 'ABCDEF'

        # width 1: ZWJ emoji (width 2) doesn't fit, replaced with space
        assert term.truncate(given, 1) == ' '
        # width 2: ZWJ emoji fits exactly
        assert term.truncate(given, 2) == given_zwj
        # width 5: ZWJ (2) + ABC (3) = 5
        assert term.truncate(given, 5) == given_zwj + 'ABC'
        # width 8: everything fits (2 + 6 = 8)
        assert term.truncate(given, 8) == given

    child(any_term)


def test_truncate_vs16_emoji(any_term):
    """Test truncate handles VS-16 emoji sequences."""
    def child(kind):
        # local

        term = TestTerminal(kind=kind)

        # Heart ❤ (U+2764) + VS-16 has width 2; truncating to 1 fills with space
        # since the grapheme cluster cannot be split
        assert term.truncate('\u2764\uFE0F', 1) == ' '
        assert term.truncate('\u2764\uFE0F', 2) == '\u2764\uFE0F'
        assert term.truncate('X\u2764\uFE0F', 1) == 'X'
        assert term.truncate('X\u2764\uFE0F', 2) == 'X '
        assert term.truncate('X\u2764\uFE0F', 3) == 'X\u2764\uFE0F'

    child(any_term)


@pytest.mark.skipif(sys.version_info[:2] < (3, 8), reason="Only supported on Python >= 3.8")
def test_supports_index(any_term):
    """Ensure sequence formatting methods support objects with __index__()"""

    def child(kind):
        # local
        from blessed.sequences import Sequence

        class Indexable:
            """Custom class implementing __index__()"""

            def __index__(self):
                return 100

        term = TestTerminal(kind=kind)
        seq = Sequence('abcd', term)
        indexable = Indexable()

        assert seq.rjust(100) == seq.rjust(indexable)
        assert seq.ljust(100) == seq.ljust(indexable)
        assert seq.center(100) == seq.center(indexable)
        assert seq.truncate(100) == seq.truncate(indexable)

        seq = Sequence('abcd' * 30, term)
        assert seq.truncate(100) == seq.truncate(indexable)

    child(any_term)


def test_get_proxy_string_deprecated():
    """get_proxy_string() returns None (deprecated, no warning emitted)."""
    from blessed.formatters import get_proxy_string
    assert get_proxy_string(None, 'any_cap') is None
