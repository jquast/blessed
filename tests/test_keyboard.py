"""Tests for keyboard support."""
# std imports
import io
import os
import platform
import sys
import tempfile
import collections
from unittest import mock

# 3rd party
import pytest

# local
from .conftest import IS_WINDOWS
from .accessories import TestTerminal, as_subprocess

# isort: off
if platform.system() != 'Windows':
    import tty  # pylint: disable=unused-import  # NOQA
    import curses
else:
    import jinxed as curses


@pytest.mark.skipif(IS_WINDOWS, reason="no tty module")
def test_getch_raises_eoferror_on_eof():
    """getch() raises EOFError when keyboard fd is at EOF."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        read_fd, write_fd = os.pipe()
        os.close(write_fd)
        term._keyboard_fd = read_fd
        try:
            with pytest.raises(EOFError):
                term.getch()
        finally:
            os.close(read_fd)
    child()


@pytest.mark.skipif(IS_WINDOWS, reason="no tty module")
def test_flushinp_handles_eof():
    """flushinp() returns buffered data when keyboard fd reaches EOF."""
    @as_subprocess
    def child():
        import codecs
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b'xy')
        os.close(write_fd)
        term._keyboard_fd = read_fd
        term._keyboard_decoder = codecs.getincrementaldecoder('utf-8')()
        try:
            result = term.flushinp(timeout=1)
            assert 'x' in result
            assert 'y' in result
        finally:
            os.close(read_fd)
    child()


@pytest.mark.skipif(IS_WINDOWS, reason="no tty module")
def test_getch_sets_eof_flag():
    """getch() sets _keyboard_eof flag on EOF."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        read_fd, write_fd = os.pipe()
        os.close(write_fd)
        term._keyboard_fd = read_fd
        try:
            assert term._keyboard_eof is False
            with pytest.raises(EOFError):
                term.getch()
            assert term._keyboard_eof is True
        finally:
            os.close(read_fd)
    child()


@pytest.mark.skipif(IS_WINDOWS, reason="no tty module")
def test_kbhit_returns_false_after_eof():
    """kbhit() returns False once _keyboard_eof is set."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        read_fd, write_fd = os.pipe()
        os.close(write_fd)
        term._keyboard_fd = read_fd
        try:
            term._keyboard_eof = True
            assert term.kbhit(timeout=0) is False
        finally:
            os.close(read_fd)
    child()


@pytest.mark.skipif(IS_WINDOWS, reason="no tty module")
def test_inkey_raises_EOF():
    """inkey() returns empty Keystroke when keyboard fd is at EOF."""
    @as_subprocess
    def child():
        import codecs
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        read_fd, write_fd = os.pipe()
        os.close(write_fd)
        term._keyboard_fd = read_fd
        term._keyboard_decoder = codecs.getincrementaldecoder('utf-8')()
        try:
            with pytest.raises(EOFError):
                term.inkey(timeout=0)
            assert term._keyboard_eof is True
        finally:
            os.close(read_fd)
    child()


@pytest.mark.skipif(IS_WINDOWS, reason="no tty module")
def test_break_input_no_kb():
    """cbreak() should not call tty.setcbreak() without keyboard."""
    @as_subprocess
    def child():
        with tempfile.NamedTemporaryFile() as stream:
            term = TestTerminal(stream=stream)
            with mock.patch("tty.setcbreak") as mock_setcbreak:
                with term.cbreak():
                    assert not mock_setcbreak.called
                assert term._keyboard_fd is None
    child()


@pytest.mark.skipif(IS_WINDOWS, reason="no tty module")
def test_raw_input_no_kb():
    """raw should not call tty.setraw() without keyboard."""
    @as_subprocess
    def child():
        with tempfile.NamedTemporaryFile() as stream:
            term = TestTerminal(stream=stream)
            with mock.patch("tty.setraw") as mock_setraw:
                with term.raw():
                    assert not mock_setraw.called
            assert term._keyboard_fd is None
    child()


@pytest.mark.skipif(IS_WINDOWS, reason="no tty module")
def test_raw_input_with_kb():
    """raw should call tty.setraw() when with keyboard."""
    @as_subprocess
    def child():
        term = TestTerminal()
        assert term._keyboard_fd is not None
        with mock.patch("tty.setraw") as mock_setraw:
            with term.raw():
                assert mock_setraw.called
    child()


def test_stdout_notty_kb_is_None():
    """term._keyboard_fd should be None when os.isatty returns False for output."""
    # In this scenario, stream is sys.__stdout__, but os.isatty(1) is False
    # such as when piping output to less(1)
    @as_subprocess
    def child():
        isatty = os.isatty
        with mock.patch('os.isatty') as mock_isatty:
            mock_isatty.side_effect = (
                lambda fd: False if fd == sys.__stdout__.fileno() else isatty(fd))
            term = TestTerminal()
            assert term._keyboard_fd is None
            # pylint: disable=use-a-generator
            assert any(['stream not a TTY' in err
                        for err in term.errors]), term.errors
    child()


def test_stdin_fileno_is_None():
    """term._keyboard_fd should be None when stdin.fileno() raises an exception."""
    @as_subprocess
    def child():
        with mock.patch.object(sys.__stdin__, 'fileno') as mock_fileno:
            mock_fileno.side_effect = ValueError('fileno is not implemented on this stream')
            term = TestTerminal()
            assert term._keyboard_fd is None
            # pylint: disable=use-a-generator
            assert any(['fileno is not implemented on this stream' in err
                        for err in term.errors])
    child()


def test_stdin_as_bytesio_is_None():
    """term._keyboard_fd should be None when sys.__stdin__.fileno() raises exception."""
    # In this scenario, stream is sys.__stdout__, but sys.__stdin__ is BytesIO
    # This may happen in a test scenario or when the program is wrapped in another interface
    @as_subprocess
    def child():
        with mock.patch('sys.__stdin__', new=io.BytesIO()):
            term = TestTerminal()
            assert term._keyboard_fd is None
            # pylint: disable=use-a-generator
            assert any([err.startswith('Unable to determine input stream file descriptor')
                        for err in term.errors])
    child()


def test_stdin_notty_kb_is_None():
    """term._keyboard_fd should be None when os.isatty returns False for input."""
    # In this scenario, stream is sys.__stdout__, but os.isatty(0) is False,
    # such as when piping from another program
    @as_subprocess
    def child():
        isatty = os.isatty
        with mock.patch('os.isatty') as mock_isatty:
            mock_isatty.side_effect = (
                lambda fd:
                    True if fd == sys.__stdout__.fileno()
                    else False if fd == sys.__stdin__.fileno()
                    else isatty(fd)
            )
            term = TestTerminal()
            assert term._keyboard_fd is None
            assert 'Input stream is not a TTY' in term.errors
    child()


def test_keystroke_default_args():
    """Test keyboard.Keystroke constructor with default arguments."""
    from blessed.keyboard import Keystroke
    ks = Keystroke()
    assert ks._name is None
    assert ks.name == ks._name
    assert ks._code is None
    assert ks.code == ks._code
    assert f'x{ks}' == 'x'
    assert not ks.is_sequence
    assert repr(ks) == "''"


def test_a_keystroke():
    """Test keyboard.Keystroke constructor with set arguments."""
    from blessed.keyboard import Keystroke
    ks = Keystroke(ucs='x', code=1, name='the X')
    assert ks._name == 'the X'
    assert ks.name == ks._name
    assert ks._code == 1
    assert ks.code == ks._code
    assert f'x{ks}' == 'xx'
    assert ks.is_sequence
    assert repr(ks) == "the X"


def test_get_keyboard_codes():
    """Test all values returned by get_keyboard_codes are from curses."""
    import blessed.keyboard
    exemptions = dict(blessed.keyboard.CURSES_KEYCODE_OVERRIDE_MIXIN)
    # Add PUA overrides to exemptions since they intentionally override curses keys
    exemptions.update(blessed.keyboard.KITTY_PUA_KEYCODE_OVERRIDE_MIXIN)
    # List of homemade keycodes that are not in curses
    homemade_keycodes = ('TAB', 'KP_MULTIPLY', 'KP_ADD', 'KP_SEPARATOR',
                         'KP_SUBTRACT', 'KP_DECIMAL', 'KP_DIVIDE', 'KP_EQUAL',
                         'KP_0', 'KP_1', 'KP_2', 'KP_3', 'KP_4', 'KP_5',
                         'KP_6', 'KP_7', 'KP_8', 'KP_9', 'MENU',
                         # Kitty protocol PUA keycodes
                         'KP_0', 'KP_1', 'KP_2', 'KP_3', 'KP_4',
                         'KP_5', 'KP_6', 'KP_7', 'KP_8', 'KP_9',
                         'KP_DECIMAL', 'KP_DIVIDE', 'KP_MULTIPLY',
                         'KP_SUBTRACT', 'KP_ADD', 'KP_ENTER', 'KP_EQUAL',
                         'KP_SEPARATOR', 'KP_LEFT', 'KP_RIGHT', 'KP_UP',
                         'KP_DOWN', 'KP_PAGE_UP', 'KP_PAGE_DOWN', 'KP_HOME',
                         'KP_END', 'KP_INSERT', 'KP_DELETE', 'KP_BEGIN',
                         # Lock and special function keys
                         'CAPS_LOCK', 'SCROLL_LOCK', 'NUM_LOCK',
                         'PRINT_SCREEN', 'PAUSE', 'MENU',
                         # Extended F-keys F13-F35 may exist in curses on some systems
                         # Only list those that don't exist in curses as "homemade"
                         # Media control keys
                         'MEDIA_PLAY', 'MEDIA_PAUSE', 'MEDIA_PLAY_PAUSE',
                         'MEDIA_REVERSE', 'MEDIA_STOP', 'MEDIA_FAST_FORWARD',
                         'MEDIA_REWIND', 'MEDIA_TRACK_NEXT', 'MEDIA_TRACK_PREVIOUS',
                         'MEDIA_RECORD', 'LOWER_VOLUME', 'RAISE_VOLUME',
                         'MUTE_VOLUME',
                         # ISO level shift keys
                         'ISO_LEVEL3_SHIFT', 'ISO_LEVEL5_SHIFT',
                         # Modifier keys
                         'LEFT_SHIFT', 'LEFT_CONTROL', 'LEFT_ALT', 'LEFT_SUPER',
                         'LEFT_HYPER', 'LEFT_META', 'RIGHT_SHIFT', 'RIGHT_CONTROL',
                         'RIGHT_ALT', 'RIGHT_SUPER', 'RIGHT_HYPER', 'RIGHT_META',
                         'CPR_RESPONSE')
    for value, keycode in blessed.keyboard.get_keyboard_codes().items():
        if keycode in exemptions:
            assert value == exemptions[keycode]
            continue
        if keycode[4:] in homemade_keycodes:
            assert not hasattr(curses, keycode)
            assert hasattr(blessed.keyboard, keycode)
            assert getattr(blessed.keyboard, keycode) == value
        else:
            assert hasattr(curses, keycode)
            assert getattr(curses, keycode) == value


def test_alternative_left_right():
    """Test _alternative_left_right behavior for space/backspace."""
    from blessed.keyboard import _alternative_left_right
    term = mock.Mock()
    term._cuf1 = ''
    term._cub1 = ''
    assert not bool(_alternative_left_right(term))
    term._cuf1 = ' '
    term._cub1 = '\b'
    assert not bool(_alternative_left_right(term))
    term._cuf1 = 'seq-right'
    term._cub1 = 'seq-left'
    assert (_alternative_left_right(term) == {
        'seq-right': curses.KEY_RIGHT,
        'seq-left': curses.KEY_LEFT})


def test_cuf1_and_cub1_as_RIGHT_LEFT(all_terms):
    """Test that cuf1 and cub1 are assigned KEY_RIGHT and KEY_LEFT."""
    from blessed.keyboard import get_keyboard_sequences

    @as_subprocess
    def child(kind):
        term = TestTerminal(kind=kind, force_styling=True)
        keymap = get_keyboard_sequences(term)
        if term._cuf1:
            assert term._cuf1 in keymap
            assert keymap[term._cuf1] == term.KEY_RIGHT
        if term._cub1:
            assert term._cub1 in keymap
            if term._cub1 == '\b':
                assert keymap[term._cub1] == term.KEY_BACKSPACE
            else:
                assert keymap[term._cub1] == term.KEY_LEFT

    child(all_terms)


def test_get_keyboard_sequences_sort_order():
    """ordereddict ensures sequences are ordered longest-first."""
    @as_subprocess
    def child(kind):
        term = TestTerminal(kind=kind, force_styling=True)
        maxlen = None
        for sequence in term._keymap:
            if maxlen is not None:
                assert len(sequence) <= maxlen
            assert sequence
            maxlen = len(sequence)
    kind = 'vtwin10' if IS_WINDOWS else 'xterm-256color'
    child(kind)


def test_get_keyboard_sequence(monkeypatch):
    """Test keyboard.get_keyboard_sequence."""
    import blessed.keyboard

    (KEY_SMALL, KEY_LARGE, KEY_MIXIN) = range(3)
    (CAP_SMALL, CAP_LARGE) = 'cap-small cap-large'.split()
    (SEQ_SMALL, SEQ_LARGE, SEQ_MIXIN, SEQ_ALT_CUF1, SEQ_ALT_CUB1) = (
        b'seq-small-a',
        b'seq-large-abcdefg',
        b'seq-mixin',
        b'seq-alt-cuf1',
        b'seq-alt-cub1_')

    # patch curses functions
    monkeypatch.setattr(curses, 'tigetstr',
                        lambda cap: {CAP_SMALL: SEQ_SMALL,
                                     CAP_LARGE: SEQ_LARGE}[cap])

    monkeypatch.setattr(blessed.keyboard, 'capability_names',
                        dict(((KEY_SMALL, CAP_SMALL,),
                              (KEY_LARGE, CAP_LARGE,))))

    # patch global sequence mix-in
    monkeypatch.setattr(blessed.keyboard,
                        'DEFAULT_SEQUENCE_MIXIN', (
                            (SEQ_MIXIN.decode('latin1'), KEY_MIXIN),))

    # patch for _alternative_left_right
    term = mock.Mock()
    term._cuf1 = SEQ_ALT_CUF1.decode('latin1')
    term._cub1 = SEQ_ALT_CUB1.decode('latin1')
    keymap = blessed.keyboard.get_keyboard_sequences(term)

    assert list(keymap.items()) == [
        (SEQ_LARGE.decode('latin1'), KEY_LARGE),
        (SEQ_ALT_CUB1.decode('latin1'), curses.KEY_LEFT),
        (SEQ_ALT_CUF1.decode('latin1'), curses.KEY_RIGHT),
        (SEQ_SMALL.decode('latin1'), KEY_SMALL),
        (SEQ_MIXIN.decode('latin1'), KEY_MIXIN)]


def test_resolve_sequence_order():
    """Test resolve_sequence for order-dependent mapping."""
    from blessed.keyboard import resolve_sequence
    mapper = collections.OrderedDict(
        (('SEQ1', 1),
         ('SEQ2', 2),
         # takes precedence over LONGSEQ, first-match
         ('LONGSEQ', 4),
         # won't match, LONGSEQ is first-match in this order
         ('LONGSEQ_longer', 5),
         # falls through for L{anything_else}
         ('L', 6)))
    codes = {1: 'KEY_SEQ1',
             2: 'KEY_SEQ2',
             3: 'KEY_LONGSEQ_longest',
             4: 'KEY_LONGSEQ',
             5: 'KEY_LONGSEQ_longer',
             6: 'KEY_L'}
    ks = resolve_sequence('', mapper, codes)
    assert ks == ''
    assert ks.name is None
    assert ks.code is None
    assert ks.mode is None
    assert not ks.is_sequence
    assert repr(ks) == "''"

    ks = resolve_sequence('notfound', mapper=mapper, codes=codes)
    assert ks == 'n'
    assert ks.name is None
    assert ks.code is None
    assert ks.mode is None
    assert not ks.is_sequence
    assert repr(ks) == "'n'"

    ks = resolve_sequence('SEQ1', mapper, codes)
    assert ks == 'SEQ1'
    assert ks.name == 'KEY_SEQ1'
    assert ks.code == 1
    assert ks.is_sequence
    assert ks.mode is None
    assert repr(ks) == "KEY_SEQ1"

    ks = resolve_sequence('LONGSEQ_longer', mapper, codes)
    assert ks == 'LONGSEQ'
    assert ks.name == 'KEY_LONGSEQ'
    assert ks.code == 4
    assert ks.is_sequence
    assert ks.mode is None
    assert repr(ks) == "KEY_LONGSEQ"

    ks = resolve_sequence('LONGSEQ', mapper, codes)
    assert ks == 'LONGSEQ'
    assert ks.name == 'KEY_LONGSEQ'
    assert ks.code == 4
    assert ks.is_sequence
    assert ks.mode is None
    assert repr(ks) == "KEY_LONGSEQ"

    ks = resolve_sequence('Lxxxxx', mapper, codes)
    assert ks == 'L'
    assert ks.name == 'KEY_L'
    assert ks.code == 6
    assert ks.is_sequence
    assert ks.mode is None
    assert repr(ks) == "KEY_L"


@pytest.mark.parametrize("seq,capture_cpr,expected_name,expected_yx", [
    # any legal row2+ CPR response,
    ('\x1b[3;4R', True, 'CPR_RESPONSE', (2, 3)),
    ('\x1b[2;1R', True, 'CPR_RESPONSE', (1, 0)),
    ('\x1b[100;200R', True, 'CPR_RESPONSE', (99, 199)),
    ('\x1b[3;4R', False, 'CPR_RESPONSE', (2, 3)),
    ('\x1b[2;1R', False, 'CPR_RESPONSE', (1, 0)),
    ('\x1b[100;200R', False, 'CPR_RESPONSE', (99, 199)),
    # CPR response with 0-index is invalid ('CSI')
    ('\x1b[0;100R', True, 'CSI', (-1, -1)),
    ('\x1b[0;100R', False, 'CSI', (-1, -1)),
    ('\x1b[100;0R', True, 'CSI', (-1, -1)),
    ('\x1b[100;0R', False, 'CSI', (-1, -1)),
    # row 1 may be ambiguous with 'KEY*F3' depending on capture_cpr argument
    ('\x1b[1;1R', False, 'KEY_F3', (0, 0)),
    ('\x1b[1;1R', True, 'CPR_RESPONSE', (0, 0)),
    ('\x1b[1;2R', False, 'KEY_SHIFT_F3', (0, 1)),
    ('\x1b[1;2R', True, 'CPR_RESPONSE', (0, 1)),
    ('\x1b[1;3R', False, 'KEY_ALT_F3', (0, 2)),
    ('\x1b[1;3R', True, 'CPR_RESPONSE', (0, 2)),
])
def test_cpr_response(seq, capture_cpr, expected_name, expected_yx):
    """CPR response matched as single CPR_RESPONSE keystroke."""
    from blessed.keyboard import resolve_sequence
    expected_kb_proto = expected_name not in ('CPR_RESPONSE', 'CSI')
    mapper = collections.OrderedDict()
    ks = resolve_sequence(seq, mapper, {}, capture_cpr=capture_cpr)
    if expected_name == 'CSI':
        assert str(ks).startswith('\x1b[')
    else:
        assert str(ks) == seq
    assert ks.name == expected_name
    assert ks.cpr_yx == expected_yx
    assert ks.cpr_xy == (expected_yx[1], expected_yx[0])
    assert ks.is_sequence
    assert ks.uses_keyboard_protocol == expected_kb_proto


@pytest.mark.parametrize("sequence,expected_name", [
    ('\x1b[1;2R', 'KEY_SHIFT_F3'),
    ('\x1b[0;5R', 'CSI'),
])
def test_cpr_response_not_matched(sequence, expected_name):
    """Row 0 or 1 not matched as CPR."""
    from blessed.keyboard import resolve_sequence
    mapper = collections.OrderedDict()
    ks = resolve_sequence(sequence, mapper, {})
    assert ks.name == expected_name


def test_cpr_response_with_trailing_text():
    """CPR matcher consumes only the CPR sequence."""
    from blessed.keyboard import resolve_sequence
    mapper = collections.OrderedDict()
    ks = resolve_sequence('\x1b[5;10Rextra', mapper, {})
    assert ks == '\x1b[5;10R'
    assert ks.name == 'CPR_RESPONSE'


def test_keyboard_prefixes():
    """Test keyboard.prefixes."""
    from blessed.keyboard import get_leading_prefixes
    keys = ['abc', 'abdf', 'e', 'jkl']
    pfs = get_leading_prefixes(keys)
    assert pfs == {'a', 'ab', 'abd', 'j', 'jk'}


@pytest.mark.skipif(IS_WINDOWS, reason="not applicable")
def test_keypad_mixins_and_aliases():
    """Test PC-Style function key translations, including ``keypad`` mode."""
    # Key     plain   app     modified
    # Up      ^[[A    ^[OA    ^[[1;mA
    # Down    ^[[B    ^[OB    ^[[1;mB
    # Right   ^[[C    ^[OC    ^[[1;mC
    # Left    ^[[D    ^[OD    ^[[1;mD
    # End     ^[[F    ^[OF    ^[[1;mF
    # Home    ^[[H    ^[OH    ^[[1;mH
    # pylint: disable=too-many-statements
    @as_subprocess
    def child(kind):
        term = TestTerminal(kind=kind, force_styling=True)

        term.ungetch(chr(10))
        assert term.inkey(timeout=0).name == "KEY_ENTER"
        term.ungetch(chr(13))
        assert term.inkey(timeout=0).name == "KEY_ENTER"
        term.ungetch(chr(8))
        assert term.inkey(timeout=0).name == "KEY_BACKSPACE"
        term.ungetch(chr(9))
        assert term.inkey(timeout=0).name == "KEY_TAB"
        term.ungetch(chr(27))
        assert term.inkey(timeout=0).name == "KEY_ESCAPE"
        term.ungetch(chr(127))
        assert term.inkey(timeout=0).name == "KEY_BACKSPACE"
        term.ungetch("\x1b[A")
        assert term.inkey(timeout=0).name == "KEY_UP"
        term.ungetch("\x1b[B")
        assert term.inkey(timeout=0).name == "KEY_DOWN"
        term.ungetch("\x1b[C")
        assert term.inkey(timeout=0).name == "KEY_RIGHT"
        term.ungetch("\x1b[D")
        assert term.inkey(timeout=0).name == "KEY_LEFT"
        term.ungetch("\x1b[E")
        assert term.inkey(timeout=0).name == "KEY_CENTER"
        term.ungetch("\x1b[U")
        assert term.inkey(timeout=0).name == "KEY_PGDOWN"
        term.ungetch("\x1b[V")
        assert term.inkey(timeout=0).name == "KEY_PGUP"
        term.ungetch("\x1b[H")
        assert term.inkey(timeout=0).name == "KEY_HOME"
        term.ungetch("\x1b[F")
        assert term.inkey(timeout=0).name == "KEY_END"
        term.ungetch("\x1b[K")
        assert term.inkey(timeout=0).name == "KEY_END"
        term.ungetch("\x1bOM")
        assert term.inkey(timeout=0).name == "KEY_ENTER"
        term.ungetch("\x1bOj")
        assert term.inkey(timeout=0).name == "KEY_KP_MULTIPLY"
        term.ungetch("\x1bOk")
        assert term.inkey(timeout=0).name == "KEY_KP_ADD"
        term.ungetch("\x1bOl")
        assert term.inkey(timeout=0).name == "KEY_KP_SEPARATOR"
        term.ungetch("\x1bOm")
        assert term.inkey(timeout=0).name == "KEY_KP_SUBTRACT"
        term.ungetch("\x1bOn")
        assert term.inkey(timeout=0).name == "KEY_KP_DECIMAL"
        term.ungetch("\x1bOo")
        assert term.inkey(timeout=0).name == "KEY_KP_DIVIDE"
        term.ungetch("\x1bOX")
        assert term.inkey(timeout=0).name == "KEY_KP_EQUAL"
        term.ungetch("\x1bOp")
        assert term.inkey(timeout=0).name == "KEY_KP_0"
        term.ungetch("\x1bOq")
        assert term.inkey(timeout=0).name == "KEY_KP_1"
        term.ungetch("\x1bOr")
        assert term.inkey(timeout=0).name == "KEY_KP_2"
        term.ungetch("\x1bOs")
        assert term.inkey(timeout=0).name == "KEY_KP_3"
        term.ungetch("\x1bOt")
        assert term.inkey(timeout=0).name == "KEY_KP_4"
        term.ungetch("\x1bOu")
        assert term.inkey(timeout=0).name == "KEY_KP_5"
        term.ungetch("\x1bOv")
        assert term.inkey(timeout=0).name == "KEY_KP_6"
        term.ungetch("\x1bOw")
        assert term.inkey(timeout=0).name == "KEY_KP_7"
        term.ungetch("\x1bOx")
        assert term.inkey(timeout=0).name == "KEY_KP_8"
        term.ungetch("\x1bOy")
        assert term.inkey(timeout=0).name == "KEY_KP_9"
        term.ungetch("\x1b[1~")
        assert term.inkey(timeout=0).name == "KEY_HOME"
        term.ungetch("\x1b[2~")
        assert term.inkey(timeout=0).name == "KEY_INSERT"
        term.ungetch("\x1b[3~")
        assert term.inkey(timeout=0).name == "KEY_DELETE"
        term.ungetch("\x1b[4~")
        assert term.inkey(timeout=0).name == "KEY_END"
        term.ungetch("\x1b[5~")
        assert term.inkey(timeout=0).name == "KEY_PGUP"
        term.ungetch("\x1b[6~")
        assert term.inkey(timeout=0).name == "KEY_PGDOWN"
        term.ungetch("\x1b[7~")
        assert term.inkey(timeout=0).name == "KEY_HOME"
        term.ungetch("\x1b[8~")
        assert term.inkey(timeout=0).name == "KEY_END"
        term.ungetch("\x1b[OA")
        assert term.inkey(timeout=0).name == "KEY_UP"
        term.ungetch("\x1b[OB")
        assert term.inkey(timeout=0).name == "KEY_DOWN"
        term.ungetch("\x1b[OC")
        assert term.inkey(timeout=0).name == "KEY_RIGHT"
        term.ungetch("\x1b[OD")
        assert term.inkey(timeout=0).name == "KEY_LEFT"
        term.ungetch("\x1b[OF")
        assert term.inkey(timeout=0).name == "KEY_END"
        term.ungetch("\x1b[OH")
        assert term.inkey(timeout=0).name == "KEY_HOME"
        term.ungetch("\x1bOP")
        assert term.inkey(timeout=0).name == "KEY_F1"
        term.ungetch("\x1bOQ")
        assert term.inkey(timeout=0).name == "KEY_F2"
        term.ungetch("\x1bOR")
        assert term.inkey(timeout=0).name == "KEY_F3"
        term.ungetch("\x1bOS")
        assert term.inkey(timeout=0).name == "KEY_F4"

    child('xterm')


@pytest.mark.skipif(IS_WINDOWS, reason="not applicable")
def test_kp_begin_center_key():
    """Test KP_BEGIN/center key (numpad 5) with modifiers and event types."""
    @as_subprocess
    def child(kind):
        term = TestTerminal(kind=kind, force_styling=True)

        term.ungetch('\x1b[E')
        ks = term.inkey(timeout=0)
        assert ks and str(ks) == '\x1b[E'
        assert ks.code == curses.KEY_B2
        assert ks.name == 'KEY_CENTER'

        term.ungetch('\x1b[1;5E')
        ks = term.inkey(timeout=0)
        assert ks and str(ks) == '\x1b[1;5E'
        assert ks.code == curses.KEY_B2
        assert ks.name == 'KEY_CTRL_CENTER'

        term.ungetch('\x1b[1;3E')
        ks = term.inkey(timeout=0)
        assert ks and str(ks) == '\x1b[1;3E'
        assert ks.code == curses.KEY_B2
        assert ks.name == 'KEY_ALT_CENTER'

        term.ungetch('\x1b[1;7E')
        ks = term.inkey(timeout=0)
        assert ks and str(ks) == '\x1b[1;7E'
        assert ks.code == curses.KEY_B2
        assert ks.name == 'KEY_CTRL_ALT_CENTER'

    child('xterm')


def test_ESCDELAY_unset_unchanged():
    """Unset ESCDELAY leaves DEFAULT_ESCDELAY unchanged in _reinit_escdelay()."""
    if 'ESCDELAY' in os.environ:
        del os.environ['ESCDELAY']
    import blessed.keyboard
    prev_value = blessed.keyboard.DEFAULT_ESCDELAY
    blessed.keyboard._reinit_escdelay()
    assert blessed.keyboard.DEFAULT_ESCDELAY == prev_value


def test_ESCDELAY_bad_value_unchanged():
    """Invalid ESCDELAY leaves DEFAULT_ESCDELAY unchanged in _reinit_escdelay()."""
    os.environ['ESCDELAY'] = 'XYZ123!'
    import blessed.keyboard
    prev_value = blessed.keyboard.DEFAULT_ESCDELAY
    blessed.keyboard._reinit_escdelay()
    assert blessed.keyboard.DEFAULT_ESCDELAY == prev_value
    del os.environ['ESCDELAY']


def test_ESCDELAY_10ms():
    """Verify ESCDELAY modifies DEFAULT_ESCDELAY in _reinit_escdelay()."""
    os.environ['ESCDELAY'] = '1234'
    import blessed.keyboard
    blessed.keyboard._reinit_escdelay()
    assert blessed.keyboard.DEFAULT_ESCDELAY == 1.234
    del os.environ['ESCDELAY']


def test_unsupported_high_byte_metasendsescape():
    """Test ESC + high-byte character (> 126) defaults to no modifiers."""
    # this library does not support the (very legacy) alt sends 8th bit high
    from blessed.keyboard import Keystroke

    ks = Keystroke('\x1b\x80')  # ESC + char with code 128
    assert ks.modifiers == 1    # No modifiers detected
    assert len(ks) == 2

    # Another high byte
    ks = Keystroke('\x1b\xff')  # ESC + char with code 255
    assert ks.modifiers == 1    # No modifiers detected


def test_is_incomplete_keystroke():
    """Test _is_incomplete_keystroke private method."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        # Case 1: Exact match - text is a known prefix
        assert term._is_incomplete_keystroke('\x1b[')
        assert term._is_incomplete_keystroke('\x1b[1')
        assert term._is_incomplete_keystroke('\x1b[15')

        # Case 2: Building toward - text is a partial match for a longer prefix
        # '\x1b' is building toward '\x1b[', '\x1b[1', '\x1b[15', etc.
        assert term._is_incomplete_keystroke('\x1b')

        # Case 3: Extending beyond - text starts with a known prefix but continues
        # '\x1b[15~' completes to F5, but '\x1b[15~x' extends beyond the prefix '\x1b[15'
        # this is for 'bracketed paste' and really really long sequences
        assert term._is_incomplete_keystroke('\x1b[15~xxx')
        assert term._is_incomplete_keystroke('\x1b[200~data')

        # Case 4: No match - text doesn't relate to any known prefix
        assert not term._is_incomplete_keystroke('')
        assert not term._is_incomplete_keystroke('x')
        assert not term._is_incomplete_keystroke('xyz')

    child()
