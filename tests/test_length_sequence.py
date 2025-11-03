"""Tests for Terminal methods that account for sequences in strings"""

# std imports
import os
import sys
import struct
import platform
import itertools
from io import StringIO

# 3rd party
import pytest

# local
from .conftest import IS_WINDOWS
from .accessories import TestTerminal, as_subprocess

if platform.system() != 'Windows':
    # std imports
    import fcntl
    import termios


def test_length_cjk():
    """Test length of East Asian characters"""
    @as_subprocess
    def child():
        term = TestTerminal()

        # given,
        given = term.bold_red('コンニチハ, セカイ!')
        expected = sum((2, 2, 2, 2, 2, 1, 1, 2, 2, 2, 1,))

        # exercise,
        assert term.length(given) == expected

    child()


def test_length_with_zwj_is_wrong():
    """Because of the way Zero-Width Joiner (ZWJ) is measured, blessed gets this wrong"""
    # But for the time being, so do many terminals (~85%), so its not a huge deal..
    # https://ucs-detect.readthedocs.io/results.html
    @as_subprocess
    def child():
        term = TestTerminal()
        # RGI_Emoji_ZWJ_Sequence  ; family: woman, woman, girl, boy
        given = term.bold_red('\U0001F469\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466')
        expected = sum((2, 0, 2, 0, 2, 0, 2))

        # exercise,
        assert term.length(given) == expected
    child()


def test_length_ansiart():
    """Test length of ANSI art"""
    @as_subprocess
    def child(kind):
        term = TestTerminal(kind=kind)
        # this 'ansi' art contributed by xzip!impure for another project,
        # unlike most CP-437 DOS ansi art, this is actually utf-8 encoded.
        fname = os.path.join(os.path.dirname(__file__), 'wall.ans')
        with open(fname, encoding='utf-8') as ansiart:
            lines = ansiart.readlines()
        assert term.length(lines[0]) == 67  # ^[[64C^[[34m▄▓▄
        assert term.length(lines[1]) == 75
        assert term.length(lines[2]) == 78
        assert term.length(lines[3]) == 78
        assert term.length(lines[4]) == 78
        assert term.length(lines[5]) == 78
        assert term.length(lines[6]) == 77
    kind = 'vtwin10' if IS_WINDOWS else 'xterm-256color'
    child(kind)


def test_sequence_length(all_terms):
    """Ensure T.length(string containing sequence) is correct."""
    # pylint: disable=too-complex,too-many-statements
    @as_subprocess
    def child(kind):
        term = TestTerminal(kind=kind, force_styling=True)

        # Make sure to test with 24-bit color on at least one terminal
        if kind == 'xterm':
            term.number_of_colors = 1 << 24

        # Create a list of ascii characters, to be separated
        # by word, to be zipped up with a cycling list of
        # terminal sequences. Then, compare the length of
        # each, the basic plain_texterm.__len__ vs. the Terminal
        # method length. They should be equal.
        plain_text = ('The softest things of the world '
                      'Override the hardest things of the world '
                      'That which has no substance '
                      'Enters into that which has no openings')
        if term.bold:
            assert term.length(term.bold) == 0
            assert term.length(term.bold('x')) == 1
            assert term.length(term.bold_red) == 0
            assert term.length(term.bold_red('x')) == 1
            assert term.length(term.bold_on_red) == 0
            assert term.length(term.bold_on_red('x')) == 1
            assert term.length(term.bold_olivedrab4) == 0
            assert term.length(term.bold_olivedrab4('x')) == 1
            assert term.length(term.bold_on_olivedrab4) == 0
            assert term.length(term.bold_on_olivedrab4('x')) == 1
            assert term.strip(term.bold) == ''
            assert term.rstrip(term.bold) == ''
            assert term.lstrip(term.bold) == ''
            assert term.strip(term.bold('  x  ')) == 'x'
            assert term.strip(term.bold('z  x  q'), 'zq') == '  x  '
            assert term.rstrip(term.bold('  x  ')) == '  x'
            assert term.lstrip(term.bold('  x  ')) == 'x  '
            assert term.strip(term.bold_red) == ''
            assert term.rstrip(term.bold_red) == ''
            assert term.lstrip(term.bold_red) == ''
            assert term.strip(term.bold_on_red) == ''
            assert term.rstrip(term.bold_on_red) == ''
            assert term.lstrip(term.bold_on_red) == ''
            assert term.strip(term.bold_olivedrab4) == ''
            assert term.rstrip(term.bold_olivedrab4) == ''
            assert term.lstrip(term.bold_olivedrab4) == ''
            assert term.strip(term.bold_on_olivedrab4) == ''
            assert term.rstrip(term.bold_on_olivedrab4) == ''
            assert term.lstrip(term.bold_on_olivedrab4) == ''
            assert term.strip(term.bold_red('  x  ')) == 'x'
            assert term.rstrip(term.bold_red('  x  ')) == '  x'
            assert term.lstrip(term.bold_red('  x  ')) == 'x  '
            assert term.strip(term.bold_on_red('  x  ')) == 'x'
            assert term.rstrip(term.bold_on_red('  x  ')) == '  x'
            assert term.lstrip(term.bold_on_red('  x  ')) == 'x  '
            assert term.strip(term.bold_olivedrab4('  x  ')) == 'x'
            assert term.rstrip(term.bold_olivedrab4('  x  ')) == '  x'
            assert term.lstrip(term.bold_olivedrab4('  x  ')) == 'x  '
            assert term.strip(term.bold_on_olivedrab4('  x  ')) == 'x'
            assert term.rstrip(term.bold_on_olivedrab4('  x  ')) == '  x'
            assert term.lstrip(term.bold_on_olivedrab4('  x  ')) == 'x  '
            assert term.strip_seqs(term.bold) == ''
            assert term.strip_seqs(term.bold('  x  ')) == '  x  '
            assert term.strip_seqs(term.bold_red) == ''
            assert term.strip_seqs(term.bold_red('  x  ')) == '  x  '
            assert term.strip_seqs(term.bold_on_red) == ''
            assert term.strip_seqs(term.bold_on_red('  x  ')) == '  x  '
            assert term.strip_seqs(term.bold_olivedrab4) == ''
            assert term.strip_seqs(term.bold_olivedrab4('  x  ')) == '  x  '
            assert term.strip_seqs(term.bold_on_olivedrab4) == ''
            assert term.strip_seqs(term.bold_on_olivedrab4('  x  ')) == '  x  '

        if term.underline:
            assert term.length(term.underline) == 0
            assert term.length(term.underline('x')) == 1
            assert term.length(term.underline_red) == 0
            assert term.length(term.underline_red('x')) == 1
            assert term.length(term.underline_on_red) == 0
            assert term.length(term.underline_on_red('x')) == 1
            assert term.length(term.underline_olivedrab4) == 0
            assert term.length(term.underline_olivedrab4('x')) == 1
            assert term.length(term.underline_on_olivedrab4) == 0
            assert term.length(term.underline_on_olivedrab4('x')) == 1
            assert term.strip(term.underline) == ''
            assert term.strip(term.underline('  x  ')) == 'x'
            assert term.strip(term.underline_red) == ''
            assert term.strip(term.underline_red('  x  ')) == 'x'
            assert term.rstrip(term.underline_red('  x  ')) == '  x'
            assert term.lstrip(term.underline_red('  x  ')) == 'x  '
            assert term.strip(term.underline_on_red) == ''
            assert term.strip(term.underline_on_red('  x  ')) == 'x'
            assert term.rstrip(term.underline_on_red('  x  ')) == '  x'
            assert term.lstrip(term.underline_on_red('  x  ')) == 'x  '
            assert term.strip(term.underline_olivedrab4) == ''
            assert term.strip(term.underline_olivedrab4('  x  ')) == 'x'
            assert term.rstrip(term.underline_olivedrab4('  x  ')) == '  x'
            assert term.lstrip(term.underline_olivedrab4('  x  ')) == 'x  '
            assert term.strip(term.underline_on_olivedrab4) == ''
            assert term.strip(term.underline_on_olivedrab4('  x  ')) == 'x'
            assert term.rstrip(term.underline_on_olivedrab4('  x  ')) == '  x'
            assert term.lstrip(term.underline_on_olivedrab4('  x  ')) == 'x  '
            assert term.strip_seqs(term.underline) == ''
            assert term.strip_seqs(term.underline('  x  ')) == '  x  '
            assert term.strip_seqs(term.underline_red) == ''
            assert term.strip_seqs(term.underline_red('  x  ')) == '  x  '
            assert term.strip_seqs(term.underline_on_red) == ''
            assert term.strip_seqs(term.underline_on_red('  x  ')) == '  x  '
            assert term.strip_seqs(term.underline_olivedrab4) == ''
            assert term.strip_seqs(term.underline_olivedrab4('  x  ')) == '  x  '
            assert term.strip_seqs(term.underline_on_olivedrab4) == ''
            assert term.strip_seqs(term.underline_on_olivedrab4('  x  ')) == '  x  '

        if term.reverse:
            assert term.length(term.reverse) == 0
            assert term.length(term.reverse('x')) == 1
            assert term.length(term.reverse_red) == 0
            assert term.length(term.reverse_red('x')) == 1
            assert term.length(term.reverse_on_red) == 0
            assert term.length(term.reverse_on_red('x')) == 1
            assert term.length(term.reverse_olivedrab4) == 0
            assert term.length(term.reverse_olivedrab4('x')) == 1
            assert term.length(term.reverse_on_olivedrab4) == 0
            assert term.length(term.reverse_on_olivedrab4('x')) == 1
            assert term.strip(term.reverse) == ''
            assert term.strip(term.reverse('  x  ')) == 'x'
            assert term.strip(term.reverse_red) == ''
            assert term.strip(term.reverse_red('  x  ')) == 'x'
            assert term.rstrip(term.reverse_red('  x  ')) == '  x'
            assert term.lstrip(term.reverse_red('  x  ')) == 'x  '
            assert term.strip(term.reverse_on_red) == ''
            assert term.strip(term.reverse_on_red('  x  ')) == 'x'
            assert term.rstrip(term.reverse_on_red('  x  ')) == '  x'
            assert term.lstrip(term.reverse_on_red('  x  ')) == 'x  '
            assert term.strip(term.reverse_olivedrab4) == ''
            assert term.strip(term.reverse_olivedrab4('  x  ')) == 'x'
            assert term.rstrip(term.reverse_olivedrab4('  x  ')) == '  x'
            assert term.lstrip(term.reverse_olivedrab4('  x  ')) == 'x  '
            assert term.strip(term.reverse_on_olivedrab4) == ''
            assert term.strip(term.reverse_on_olivedrab4('  x  ')) == 'x'
            assert term.rstrip(term.reverse_on_olivedrab4('  x  ')) == '  x'
            assert term.lstrip(term.reverse_on_olivedrab4('  x  ')) == 'x  '
            assert term.strip_seqs(term.reverse) == ''
            assert term.strip_seqs(term.reverse('  x  ')) == '  x  '
            assert term.strip_seqs(term.reverse_red) == ''
            assert term.strip_seqs(term.reverse_red('  x  ')) == '  x  '
            assert term.strip_seqs(term.reverse_on_red) == ''
            assert term.strip_seqs(term.reverse_on_red('  x  ')) == '  x  '
            assert term.strip_seqs(term.reverse_olivedrab4) == ''
            assert term.strip_seqs(term.reverse_olivedrab4('  x  ')) == '  x  '
            assert term.strip_seqs(term.reverse_on_olivedrab4) == ''
            assert term.strip_seqs(term.reverse_on_olivedrab4('  x  ')) == '  x  '

        if term.blink:
            assert term.length(term.blink) == 0
            assert term.length(term.blink('x')) == 1
            assert term.length(term.blink_red) == 0
            assert term.length(term.blink_red('x')) == 1
            assert term.length(term.blink_on_red) == 0
            assert term.length(term.blink_on_red('x')) == 1
            assert term.length(term.blink_olivedrab4) == 0
            assert term.length(term.blink_olivedrab4('x')) == 1
            assert term.length(term.blink_on_olivedrab4) == 0
            assert term.length(term.blink_on_olivedrab4('x')) == 1
            assert term.strip(term.blink) == ''
            assert term.strip(term.blink('  x  ')) == 'x'
            assert term.strip(term.blink('z  x  q'), 'zq') == '  x  '
            assert term.strip(term.blink_red) == ''
            assert term.strip(term.blink_red('  x  ')) == 'x'
            assert term.strip(term.blink_on_red) == ''
            assert term.strip(term.blink_on_red('  x  ')) == 'x'
            assert term.strip(term.blink_olivedrab4) == ''
            assert term.strip(term.blink_olivedrab4('  x  ')) == 'x'
            assert term.strip(term.blink_on_olivedrab4) == ''
            assert term.strip(term.blink_on_olivedrab4('  x  ')) == 'x'
            assert term.strip_seqs(term.blink) == ''
            assert term.strip_seqs(term.blink('  x  ')) == '  x  '
            assert term.strip_seqs(term.blink_red) == ''
            assert term.strip_seqs(term.blink_red('  x  ')) == '  x  '
            assert term.strip_seqs(term.blink_on_red) == ''
            assert term.strip_seqs(term.blink_on_red('  x  ')) == '  x  '
            assert term.strip_seqs(term.blink_olivedrab4) == ''
            assert term.strip_seqs(term.blink_olivedrab4('  x  ')) == '  x  '
            assert term.strip_seqs(term.blink_on_olivedrab4) == ''
            assert term.strip_seqs(term.blink_on_olivedrab4('  x  ')) == '  x  '

        if term.home:
            assert term.length(term.home) == 0
            assert term.strip(term.home) == ''
        if term.clear_eol:
            assert term.length(term.clear_eol) == 0
            assert term.strip(term.clear_eol) == ''
        if term.enter_fullscreen:
            assert term.length(term.enter_fullscreen) == 0
            assert term.strip(term.enter_fullscreen) == ''
        if term.exit_fullscreen:
            assert term.length(term.exit_fullscreen) == 0
            assert term.strip(term.exit_fullscreen) == ''

        # horizontally, we decide move_down and move_up are 0,
        assert term.length(term.move_down) == 0
        assert term.length(term.move_down(2)) == 0
        assert term.length(term.move_up) == 0
        assert term.length(term.move_up(2)) == 0

        # other things aren't so simple, somewhat edge cases,
        # moving backwards and forwards horizontally must be
        # accounted for as a "length", as <x><move right 10><y>
        # will result in a printed column length of 12 (even
        # though columns 2-11 are non-destructive space
        assert term.length('x\b') == 0
        assert term.strip('x\b') == ''

        # XXX why are some terminals width of 9 here ??
        assert term.length('\t') in {8, 9}
        assert term.strip('\t') == ''

        assert term.length(f'_{term.move_left}') == 0
        assert term.length(term.move_right) == 1

        if term.cub:
            assert term.length(f'{"_" * 10}{term.cub(10)}') == 0

        if term.cuf:
            assert term.length(term.cuf(10)) == 10

        # vertical spacing is unaccounted as a 'length'
        assert term.length(term.move_up) == 0
        assert term.length(term.cuu(10)) == 0
        assert term.length(term.move_down) == 0
        assert term.length(term.cud(10)) == 0

        # this is how manpages perform underlining, this is done
        # with the 'overstrike' capability of teletypes, and apparently
        # less(1), '123' -> '1\b_2\b_3\b_'
        text_wseqs = ''.join(itertools.chain(
            *zip(plain_text, itertools.cycle(['\b_']))))
        assert term.length(text_wseqs) == len(plain_text)

    child(all_terms)


def test_env_winsize():
    """Test height and width is appropriately queried in a pty."""
    @as_subprocess
    def child():
        # set the pty's virtual window size
        os.environ['COLUMNS'] = '99'
        os.environ['LINES'] = '11'
        term = TestTerminal(stream=StringIO())
        save_init = term._init_descriptor
        save_stdout = sys.__stdout__
        try:
            term._init_descriptor = None
            sys.__stdout__ = None
            winsize = term._height_and_width()
            width = term.width
            height = term.height
        finally:
            term._init_descriptor = save_init
            sys.__stdout__ = save_stdout
        assert winsize.ws_col == width == 99
        assert winsize.ws_row == height == 11

    child()


@pytest.mark.skipif(IS_WINDOWS, reason="requires fcntl")
def test_winsize(many_lines, many_columns):
    """Test height and width is appropriately queried in a pty."""
    pixel_width, pixel_height = 1024, 768

    @as_subprocess
    def child(lines=25, cols=80):
        # set the pty's virtual window size
        val = struct.pack('HHHH', lines, cols, pixel_width, pixel_height)
        # pylint: disable-next=possibly-used-before-assignment
        fcntl.ioctl(sys.__stdout__.fileno(), termios.TIOCSWINSZ, val)
        term = TestTerminal()
        winsize = term._height_and_width()
        assert term.width == cols
        assert term.height == lines
        assert winsize.ws_col == cols
        assert winsize.ws_row == lines
        assert term.pixel_width == pixel_width
        assert term.pixel_height == pixel_height

    child(lines=many_lines, cols=many_columns)


def test_Sequence_alignment_fixed_width(all_terms):
    """Test alignment methods with width provided"""
    @as_subprocess
    def child(kind):
        term = TestTerminal(kind=kind)
        pony_msg = 'pony express, all aboard, choo, choo!'
        pony_len = len(pony_msg)
        pony_colored = ''.join(
            f'{term.color(n % 7)}{ch}' for n, ch in enumerate(pony_msg)
        ) + term.normal
        ladjusted = term.ljust(pony_colored, 88)
        radjusted = term.rjust(pony_colored, 88)
        centered = term.center(pony_colored, 88)
        assert term.length(pony_colored) == pony_len
        assert term.length(centered.strip()) == pony_len
        assert term.length(centered) == len(pony_msg.center(88))
        assert term.length(ladjusted.strip()) == pony_len
        assert term.length(ladjusted) == len(pony_msg.ljust(88))
        assert term.length(radjusted.strip()) == pony_len
        assert term.length(radjusted) == len(pony_msg.rjust(88))

    child(kind=all_terms)


@pytest.mark.skipif(IS_WINDOWS, reason="requires fcntl")
def test_Sequence_alignment(all_terms):
    """Tests methods related to Sequence class, namely ljust, rjust, center."""
    @as_subprocess
    def child(kind, lines=25, cols=80):
        # set the pty's virtual window size
        val = struct.pack('HHHH', lines, cols, 0, 0)
        fcntl.ioctl(sys.__stdout__.fileno(), termios.TIOCSWINSZ, val)
        term = TestTerminal(kind=kind)

        pony_msg = 'pony express, all aboard, choo, choo!'
        pony_len = len(pony_msg)
        pony_colored = ''.join(
            f'{term.color(n % 7)}{ch}' for n, ch in enumerate(pony_msg)
        )
        pony_colored += term.normal
        ladjusted = term.ljust(pony_colored)
        radjusted = term.rjust(pony_colored)
        centered = term.center(pony_colored)
        assert term.length(pony_colored) == pony_len
        assert term.length(centered.strip()) == pony_len
        assert term.length(centered) == len(pony_msg.center(term.width))
        assert term.length(ladjusted.strip()) == pony_len
        assert term.length(ladjusted) == len(pony_msg.ljust(term.width))
        assert term.length(radjusted.strip()) == pony_len
        assert term.length(radjusted) == len(pony_msg.rjust(term.width))

    child(kind=all_terms)


def test_hyperlink_nostyling():
    """Test length our of hyperlink URL's."""
    @as_subprocess
    def child():
        # given,
        term = TestTerminal(force_styling=None)
        given_basic_url = term.link(
            'https://blessed.readthedocs.org', 'blessed')
        assert given_basic_url == 'blessed'

    child()


def test_basic_hyperlinks():
    """Test length our of hyperlink URL's."""
    @as_subprocess
    def child():
        # given,
        term = TestTerminal()
        given_basic_url = term.link(
            'https://blessed.readthedocs.org', 'blessed')
        # exercise,
        split_parts = term.split_seqs(given_basic_url)
        # verify
        if term.does_styling:
            assert split_parts[0] == '\x1b]8;;https://blessed.readthedocs.org\x1b\\'
            assert term.length(split_parts[0]) == 0
            assert ''.join(split_parts[1:8]) == 'blessed'
            assert split_parts[8] == '\x1b]8;;\x1b\\'
            assert len(split_parts) == 9
        else:
            assert ''.join(split_parts) == 'blessed'

    child()


def test_hyperlink_with_id():
    """Test length our of hyperlink URL's with ID."""
    @as_subprocess
    def child():
        # given,
        term = TestTerminal()
        given_advanced_urltext = term.link(
            'https://blessed.readthedocs.org', 'blessed', '123')
        # exercise,
        split_parts = term.split_seqs(given_advanced_urltext)
        # verify,
        if term.does_styling:
            assert split_parts[0] == '\x1b]8;id=123;https://blessed.readthedocs.org\x1b\\'
            assert term.length(split_parts[0]) == 0
            assert ''.join(split_parts[1:8]) == 'blessed'
            assert split_parts[8] == '\x1b]8;;\x1b\\'
            assert len(split_parts) == 9
        else:
            assert ''.join(split_parts) == 'blessed'

    child()


def test_sequence_is_movement_false(all_terms):
    """Test parser about sequences that do not move the cursor."""
    @as_subprocess
    def child(kind):
        # local
        from blessed.sequences import measure_length
        term = TestTerminal(kind=kind)
        assert measure_length('', term) == 0
        # not even a mbs
        assert measure_length('xyzzy', term) == 0
        # negative numbers, though printable as %d, do not result
        # in movement; just garbage. Also not a valid sequence.
        assert measure_length(term.cuf(-333), term) == 0
        assert len(term.clear_eol) == measure_length(term.clear_eol, term)
        # various erases don't *move*
        assert len(term.clear_bol) == measure_length(term.clear_bol, term)
        assert len(term.clear_eos) == measure_length(term.clear_eos, term)
        assert len(term.bold) == measure_length(term.bold, term)
        # various paints don't move
        assert len(term.red) == measure_length(term.red, term)
        assert len(term.civis) == measure_length(term.civis, term)
        if term.cvvis:
            assert len(term.cvvis) == measure_length(term.cvvis, term)
        assert len(term.underline) == measure_length(term.underline, term)
        assert len(term.reverse) == measure_length(term.reverse, term)
        for _num in (0, term.number_of_colors):
            assert len(term.color(_num)) == measure_length(term.color(_num), term)
        assert len(term.normal_cursor) == measure_length(term.normal_cursor, term)
        assert len(term.hide_cursor) == measure_length(term.hide_cursor, term)
        assert len(term.save) == measure_length(term.save, term)
        assert len(term.italic) == measure_length(term.italic, term)
        assert (len(term.standout) == measure_length(term.standout, term)
                ), (term.standout, term._wont_move)

    child(all_terms)


def test_termcap_will_move_false(all_terms):  # pylint: disable=too-complex
    """Test parser about sequences that do not move the cursor."""
    @as_subprocess
    def child(kind):  # pylint: disable=too-many-branches
        # local
        from blessed.sequences import iter_parse
        term = TestTerminal(kind=kind)
        if term.clear_eol:
            assert not next(iter_parse(term, term.clear_eol))[1].will_move
        if term.clear_bol:
            assert not next(iter_parse(term, term.clear_bol))[1].will_move
        if term.clear_eos:
            assert not next(iter_parse(term, term.clear_eos))[1].will_move
        if term.bold:
            assert not next(iter_parse(term, term.bold))[1].will_move
        if term.red:
            assert not next(iter_parse(term, term.red))[1].will_move
        if term.civis:
            assert not next(iter_parse(term, term.civis))[1].will_move
        if term.cvvis:
            assert not next(iter_parse(term, term.cvvis))[1].will_move
        if term.underline:
            assert not next(iter_parse(term, term.underline))[1].will_move
        if term.reverse:
            assert not next(iter_parse(term, term.reverse))[1].will_move
        if term.color(0):
            assert not next(iter_parse(term, term.color(0)))[1].will_move
        if term.normal_cursor:
            assert not next(iter_parse(term, term.normal_cursor))[1].will_move
        if term.save:
            assert not next(iter_parse(term, term.save))[1].will_move
        if term.italic:
            assert not next(iter_parse(term, term.italic))[1].will_move
        if term.standout:
            assert not next(iter_parse(term, term.standout))[1].will_move

    child(all_terms)


def test_sequence_is_movement_true(all_terms):
    """Test parsers about sequences that move the cursor."""
    @as_subprocess
    def child(kind):
        # local
        from blessed.sequences import measure_length
        term = TestTerminal(kind=kind)
        # movements
        assert len(term.move(98, 76)) == measure_length(term.move(98, 76), term)
        assert len(term.move(54)) == measure_length(term.move(54), term)
        assert len(term.move_xy(1, 2)) == measure_length(term.move(1, 2), term)
        assert len(term.move_yx(3, 4)) == measure_length(term.move(3, 4), term)
        assert not term.cud1 or (len(term.cud1) ==
                                 measure_length(term.cud1, term))
        assert not term.cub1 or (len(term.cub1) ==
                                 measure_length(term.cub1, term))
        assert not term.cuf1 or (len(term.cuf1) ==
                                 measure_length(term.cuf1, term))
        assert not term.cuu1 or (len(term.cuu1) ==
                                 measure_length(term.cuu1, term))
        assert not term.cub or (len(term.cub(333)) ==
                                measure_length(term.cub(333), term))
        assert not term.cuf or (len(term.cuf(333)) ==
                                measure_length(term.cuf(333), term))
        assert not term.home or (len(term.home) ==
                                 measure_length(term.home, term))
        assert not term.restore or (len(term.restore) ==
                                    measure_length(term.restore, term))
        assert not term.clear or (len(term.clear) ==
                                  measure_length(term.clear, term))

    child(all_terms)


def test_termcap_will_move_true(all_terms):
    """Test parser about sequences that move the cursor."""
    @as_subprocess
    def child(kind):
        # local
        from blessed.sequences import iter_parse
        term = TestTerminal(kind=kind, force_styling=True)
        assert next(iter_parse(term, term.move(98, 76)))[1].will_move
        assert next(iter_parse(term, term.move_yx(8, 76)))[1].will_move
        assert next(iter_parse(term, term.move_xy(98, 7)))[1].will_move
        assert next(iter_parse(term, term.move(54)))[1].will_move
        assert next(iter_parse(term, term.cud1))[1].will_move
        assert next(iter_parse(term, term.cub1))[1].will_move
        assert next(iter_parse(term, term.cuf1))[1].will_move
        assert next(iter_parse(term, term.cuu1))[1].will_move
        if term.cub(333):
            assert next(iter_parse(term, term.cub(333)))[1].will_move
        if term.cuf(333):
            assert next(iter_parse(term, term.cuf(333)))[1].will_move
        assert next(iter_parse(term, term.home))[1].will_move
        assert next(iter_parse(term, term.restore))[1].will_move
        assert next(iter_parse(term, term.clear))[1].will_move
    child(all_terms)


def test_foreign_sequences():
    """Test parsers about sequences received from foreign sources."""
    @as_subprocess
    def child(kind):
        # local
        from blessed.sequences import measure_length
        term = TestTerminal(kind=kind)
        assert measure_length('\x1b[m', term) == len('\x1b[m')
    child(kind='ansi')
