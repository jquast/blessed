# -*- coding: utf-8 -*-
"""Tests for keyboard support."""
# std imports
import os
import platform
import tempfile
import functools

# 3rd party
import pytest

# local
from .conftest import IS_WINDOWS
from .accessories import TestTerminal, as_subprocess

try:
    # std imports
    from unittest import mock
except ImportError:
    # 3rd party
    import mock

if platform.system() != 'Windows':
    # std imports
    import tty  # pylint: disable=unused-import  # NOQA
    import curses
else:
    # 3rd party
    import jinxed as curses  # pylint: disable=import-error


@pytest.mark.skipif(IS_WINDOWS, reason="?")
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


@pytest.mark.skipif(IS_WINDOWS, reason="?")
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


@pytest.mark.skipif(IS_WINDOWS, reason="?")
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


def test_notty_kb_is_None():
    """term._keyboard_fd should be None when os.isatty returns False."""
    # in this scenario, stream is sys.__stdout__,
    # but os.isatty(0) is False,
    # such as when piping output to less(1)
    @as_subprocess
    def child():
        with mock.patch("os.isatty") as mock_isatty:
            mock_isatty.return_value = False
            term = TestTerminal()
            assert term._keyboard_fd is None
    child()


def test_keystroke_default_args():
    """Test keyboard.Keystroke constructor with default arguments."""
    # local
    from blessed.keyboard import Keystroke
    ks = Keystroke()
    assert ks._name is None
    assert ks.name == ks._name
    assert ks._code is None
    assert ks.code == ks._code
    assert 'x' + ks == 'x'
    assert not ks.is_sequence
    assert repr(ks) == "''"


def test_a_keystroke():
    """Test keyboard.Keystroke constructor with set arguments."""
    # local
    from blessed.keyboard import Keystroke
    ks = Keystroke(ucs='x', code=1, name='the X')
    assert ks._name == 'the X'
    assert ks.name == ks._name
    assert ks._code == 1
    assert ks.code == ks._code
    assert 'x' + ks == 'xx'
    assert ks.is_sequence
    assert repr(ks) == "the X"


def test_get_keyboard_codes():
    """Test all values returned by get_keyboard_codes are from curses."""
    # local
    import blessed.keyboard
    exemptions = dict(blessed.keyboard.CURSES_KEYCODE_OVERRIDE_MIXIN)
    for value, keycode in blessed.keyboard.get_keyboard_codes().items():
        if keycode in exemptions:
            assert value == exemptions[keycode]
            continue
        if keycode[4:] in blessed.keyboard._CURSES_KEYCODE_ADDINS:
            assert not hasattr(curses, keycode)
            assert hasattr(blessed.keyboard, keycode)
            assert getattr(blessed.keyboard, keycode) == value
        else:
            assert hasattr(curses, keycode)
            assert getattr(curses, keycode) == value


def test_alternative_left_right():
    """Test _alternative_left_right behavior for space/backspace."""
    # local
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
    # local
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
    # local
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


def test_resolve_sequence():
    """Test resolve_sequence for order-dependent mapping."""
    # local
    from blessed.keyboard import OrderedDict, resolve_sequence
    mapper = OrderedDict((('SEQ1', 1),
                          ('SEQ2', 2),
                          # takes precedence over LONGSEQ, first-match
                          ('KEY_LONGSEQ_longest', 3),
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
    assert not ks.is_sequence
    assert repr(ks) == "''"

    ks = resolve_sequence('notfound', mapper=mapper, codes=codes)
    assert ks == 'n'
    assert ks.name is None
    assert ks.code is None
    assert not ks.is_sequence
    assert repr(ks) == "'n'"

    ks = resolve_sequence('SEQ1', mapper, codes)
    assert ks == 'SEQ1'
    assert ks.name == 'KEY_SEQ1'
    assert ks.code == 1
    assert ks.is_sequence
    assert repr(ks) == "KEY_SEQ1"

    ks = resolve_sequence('LONGSEQ_longer', mapper, codes)
    assert ks == 'LONGSEQ'
    assert ks.name == 'KEY_LONGSEQ'
    assert ks.code == 4
    assert ks.is_sequence
    assert repr(ks) == "KEY_LONGSEQ"

    ks = resolve_sequence('LONGSEQ', mapper, codes)
    assert ks == 'LONGSEQ'
    assert ks.name == 'KEY_LONGSEQ'
    assert ks.code == 4
    assert ks.is_sequence
    assert repr(ks) == "KEY_LONGSEQ"

    ks = resolve_sequence('Lxxxxx', mapper, codes)
    assert ks == 'L'
    assert ks.name == 'KEY_L'
    assert ks.code == 6
    assert ks.is_sequence
    assert repr(ks) == "KEY_L"


def test_keyboard_prefixes():
    """Test keyboard.prefixes."""
    # local
    from blessed.keyboard import get_leading_prefixes
    keys = ['abc', 'abdf', 'e', 'jkl']
    pfs = get_leading_prefixes(keys)
    assert pfs == {'a', 'ab', 'abd', 'j', 'jk'}


@pytest.mark.skipif(IS_WINDOWS, reason="no multiprocess")
def test_keypad_mixins_and_aliases():  # pylint: disable=too-many-statements
    """Test PC-Style function key translations when in ``keypad`` mode."""
    # Key     plain   app     modified
    # Up      ^[[A    ^[OA    ^[[1;mA
    # Down    ^[[B    ^[OB    ^[[1;mB
    # Right   ^[[C    ^[OC    ^[[1;mC
    # Left    ^[[D    ^[OD    ^[[1;mD
    # End     ^[[F    ^[OF    ^[[1;mF
    # Home    ^[[H    ^[OH    ^[[1;mH
    @as_subprocess
    def child(kind):  # pylint: disable=too-many-statements
        term = TestTerminal(kind=kind, force_styling=True)
        # local
        from blessed.keyboard import resolve_sequence

        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes)

        assert resolve(chr(10)).name == "KEY_ENTER"
        assert resolve(chr(13)).name == "KEY_ENTER"
        assert resolve(chr(8)).name == "KEY_BACKSPACE"
        assert resolve(chr(9)).name == "KEY_TAB"
        assert resolve(chr(27)).name == "KEY_ESCAPE"
        assert resolve(chr(127)).name == "KEY_BACKSPACE"
        assert resolve("\x1b[A").name == "KEY_UP"
        assert resolve("\x1b[B").name == "KEY_DOWN"
        assert resolve("\x1b[C").name == "KEY_RIGHT"
        assert resolve("\x1b[D").name == "KEY_LEFT"
        assert resolve("\x1b[U").name == "KEY_PGDOWN"
        assert resolve("\x1b[V").name == "KEY_PGUP"
        assert resolve("\x1b[H").name == "KEY_HOME"
        assert resolve("\x1b[F").name == "KEY_END"
        assert resolve("\x1b[K").name == "KEY_END"
        assert resolve("\x1bOM").name == "KEY_ENTER"
        assert resolve("\x1bOj").name == "KEY_KP_MULTIPLY"
        assert resolve("\x1bOk").name == "KEY_KP_ADD"
        assert resolve("\x1bOl").name == "KEY_KP_SEPARATOR"
        assert resolve("\x1bOm").name == "KEY_KP_SUBTRACT"
        assert resolve("\x1bOn").name == "KEY_KP_DECIMAL"
        assert resolve("\x1bOo").name == "KEY_KP_DIVIDE"
        assert resolve("\x1bOX").name == "KEY_KP_EQUAL"
        assert resolve("\x1bOp").name == "KEY_KP_0"
        assert resolve("\x1bOq").name == "KEY_KP_1"
        assert resolve("\x1bOr").name == "KEY_KP_2"
        assert resolve("\x1bOs").name == "KEY_KP_3"
        assert resolve("\x1bOt").name == "KEY_KP_4"
        assert resolve("\x1bOu").name == "KEY_KP_5"
        assert resolve("\x1bOv").name == "KEY_KP_6"
        assert resolve("\x1bOw").name == "KEY_KP_7"
        assert resolve("\x1bOx").name == "KEY_KP_8"
        assert resolve("\x1bOy").name == "KEY_KP_9"
        assert resolve("\x1b[1~").name == "KEY_FIND"
        assert resolve("\x1b[2~").name == "KEY_INSERT"
        assert resolve("\x1b[3~").name == "KEY_DELETE"
        assert resolve("\x1b[4~").name == "KEY_SELECT"
        assert resolve("\x1b[5~").name == "KEY_PGUP"
        assert resolve("\x1b[6~").name == "KEY_PGDOWN"
        assert resolve("\x1b[7~").name == "KEY_HOME"
        assert resolve("\x1b[8~").name == "KEY_END"
        assert resolve("\x1b[OA").name == "KEY_UP"
        assert resolve("\x1b[OB").name == "KEY_DOWN"
        assert resolve("\x1b[OC").name == "KEY_RIGHT"
        assert resolve("\x1b[OD").name == "KEY_LEFT"
        assert resolve("\x1b[OF").name == "KEY_END"
        assert resolve("\x1b[OH").name == "KEY_HOME"
        assert resolve("\x1bOP").name == "KEY_F1"
        assert resolve("\x1bOQ").name == "KEY_F2"
        assert resolve("\x1bOR").name == "KEY_F3"
        assert resolve("\x1bOS").name == "KEY_F4"

    child('xterm')


def test_ESCDELAY_unset_unchanged():
    """Unset ESCDELAY leaves DEFAULT_ESCDELAY unchanged in _reinit_escdelay()."""
    if 'ESCDELAY' in os.environ:
        del os.environ['ESCDELAY']
    # local
    import blessed.keyboard
    prev_value = blessed.keyboard.DEFAULT_ESCDELAY
    blessed.keyboard._reinit_escdelay()
    assert blessed.keyboard.DEFAULT_ESCDELAY == prev_value


def test_ESCDELAY_bad_value_unchanged():
    """Invalid ESCDELAY leaves DEFAULT_ESCDELAY unchanged in _reinit_escdelay()."""
    os.environ['ESCDELAY'] = 'XYZ123!'
    # local
    import blessed.keyboard
    prev_value = blessed.keyboard.DEFAULT_ESCDELAY
    blessed.keyboard._reinit_escdelay()
    assert blessed.keyboard.DEFAULT_ESCDELAY == prev_value
    del os.environ['ESCDELAY']


def test_ESCDELAY_10ms():
    """Verify ESCDELAY modifies DEFAULT_ESCDELAY in _reinit_escdelay()."""
    os.environ['ESCDELAY'] = '1234'
    # local
    import blessed.keyboard
    blessed.keyboard._reinit_escdelay()
    assert blessed.keyboard.DEFAULT_ESCDELAY == 1.234
    del os.environ['ESCDELAY']
