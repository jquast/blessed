# -*- coding: utf-8 -*-
"""Tests for keyboard support."""
# std imports
import os
import platform
import sys
import tempfile
import functools
from unittest import mock

# 3rd party
import pytest

# local
from blessed._compat import unicode_chr
from .accessories import TestTerminal, as_subprocess
from .conftest import IS_WINDOWS

if platform.system() != 'Windows':
    import curses
    import tty  # pylint: disable=unused-import  # NOQA
else:
    import jinxed as curses


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


def test_stdout_notty_kb_is_None():
    """term._keyboard_fd should be None when os.isatty returns False for output."""
    @as_subprocess
    def child():
        isatty = os.isatty
        with mock.patch('os.isatty') as mock_isatty:
            mock_isatty.side_effect = (
                lambda fd: False if fd == sys.__stdout__.fileno() else isatty(fd)
            )
            term = TestTerminal()
            assert term._keyboard_fd is None
            assert 'Output stream is not a TTY' in term.errors
    child()


def test_stdin_notty_kb_is_None():
    """term._keyboard_fd should be None when os.isatty returns False for stdin."""
    @as_subprocess
    def child():
        isatty = os.isatty
        with mock.patch('os.isatty') as mock_isatty:
            mock_isatty.side_effect = (
                lambda fd: False if fd == sys.__stdin__.fileno() else isatty(fd)
            )
            term = TestTerminal()
            assert term._keyboard_fd is None
    child()


def test_stdin_redirect():
    """term._keyboard_fd should be None when stdin.fileno() raises an exception."""
    @as_subprocess
    def child():
        with mock.patch.object(sys.__stdin__, 'fileno') as mock_fileno:
            mock_fileno.side_effect = ValueError('fileno is not implemented on this stream')
            term = TestTerminal()
            assert term._keyboard_fd is None
    child()


def test_keystroke_default_args():
    """Test keyboard.Keystroke constructor with default arguments."""
    from blessed.keyboard import Keystroke
    ks = Keystroke()
    assert ks._name is None
    assert ks.name == ks._name
    assert ks._code is None
    assert ks.code == ks._code
    assert u'x' + ks == u'x'
    assert not ks.is_sequence
    assert repr(ks) in {"u''",  # py26, 27
                        "''"}  # py33


def test_a_keystroke():
    """Test keyboard.Keystroke constructor with set arguments."""
    from blessed.keyboard import Keystroke
    ks = Keystroke(ucs=u'x', code=1, name=u'the X')
    assert ks._name == u'the X'
    assert ks.name == ks._name
    assert ks._code == 1
    assert ks.code == ks._code
    assert u'x' + ks == u'xx'
    assert ks.is_sequence
    assert repr(ks) == "the X"


def test_get_keyboard_codes():
    """Test all values returned by get_keyboard_codes are from curses."""
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
    from blessed.keyboard import _alternative_left_right
    term = mock.Mock()
    term._cuf1 = u''
    term._cub1 = u''
    assert not bool(_alternative_left_right(term))
    term._cuf1 = u' '
    term._cub1 = u'\b'
    assert not bool(_alternative_left_right(term))
    term._cuf1 = u'seq-right'
    term._cub1 = u'seq-left'
    assert (_alternative_left_right(term) == {
        u'seq-right': curses.KEY_RIGHT,
        u'seq-left': curses.KEY_LEFT})


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
    from blessed.keyboard import resolve_sequence, OrderedDict, get_leading_prefixes
    mapper = OrderedDict((('SEQ1', 1),
                          ('SEQ2', 2),
                          # takes precedence over LONGSEQ, first-match
                          ('LONGSEQ', 4),
                          # won't match, LONGSEQ is first-match in this order
                          ('LONGSEQ_longer', 5),
                          # falls through for L{anything_else}
                          ('L', 6)))
    codes = {1: 'KEY_SEQ1',
             2: 'KEY_SEQ2',
             4: 'KEY_LONGSEQ',
             5: 'KEY_LONGSEQ_longer',
             6: 'KEY_L'}
    prefixes = get_leading_prefixes(mapper)
    ks = resolve_sequence('', mapper, codes, prefixes, final=True)
    assert ks == ''
    assert ks.name is None
    assert ks.code is None
    assert not ks.is_sequence
    assert repr(ks) == "''"

    ks = resolve_sequence('notfound', mapper, codes, prefixes, final=True)
    assert ks == 'n'
    assert ks.name is None
    assert ks.code is None
    assert not ks.is_sequence
    assert repr(ks) == "'n'"

    ks = resolve_sequence('SEQ1', mapper, codes, prefixes, final=True)
    assert ks == 'SEQ1'
    assert ks.name == 'KEY_SEQ1'
    assert ks.code == 1
    assert ks.is_sequence
    assert repr(ks) == "KEY_SEQ1"

    ks = resolve_sequence('LONGSEQ_longer', mapper, codes, prefixes, final=True)
    assert ks == 'LONGSEQ'
    assert ks.name == 'KEY_LONGSEQ'
    assert ks.code == 4
    assert ks.is_sequence
    assert repr(ks) == "KEY_LONGSEQ"

    ks = resolve_sequence('LONGSEQ', mapper, codes, prefixes, final=True)
    assert ks == 'LONGSEQ'
    assert ks.name == 'KEY_LONGSEQ'
    assert ks.code == 4
    assert ks.is_sequence
    assert repr(ks) == "KEY_LONGSEQ"

    ks = resolve_sequence('Lxxxxx', mapper, codes, prefixes, final=True)
    assert ks == 'L'
    assert ks.name == 'KEY_L'
    assert ks.code == 6
    assert ks.is_sequence
    assert repr(ks) == "KEY_L"


def test_keyboard_prefixes():
    """Test keyboard.prefixes."""
    from blessed.keyboard import get_leading_prefixes
    keys = ['abc', 'abdf', 'e', 'jkl']
    pfs = get_leading_prefixes(keys)
    assert pfs == {u'a', u'ab', u'abd', u'j', u'jk'}


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
    def child(kind):
        term = TestTerminal(kind=kind, force_styling=True)
        from blessed.keyboard import resolve_sequence

        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes,
                                    prefixes=term._keymap_prefixes,
                                    final=True)

        assert resolve(unicode_chr(10)).name == "KEY_ENTER"
        assert resolve(unicode_chr(13)).name == "KEY_ENTER"
        assert resolve(unicode_chr(8)).name == "KEY_BACKSPACE"
        assert resolve(unicode_chr(9)).name == "KEY_TAB"
        assert resolve(unicode_chr(27)).name == "KEY_ESCAPE"
        assert resolve(unicode_chr(127)).name == "KEY_BACKSPACE"
        assert resolve(u"\x1b[A").name == "KEY_UP"
        assert resolve(u"\x1b[B").name == "KEY_DOWN"
        assert resolve(u"\x1b[C").name == "KEY_RIGHT"
        assert resolve(u"\x1b[D").name == "KEY_LEFT"
        assert resolve(u"\x1b[U").name == "KEY_PGDOWN"
        assert resolve(u"\x1b[V").name == "KEY_PGUP"
        assert resolve(u"\x1b[H").name == "KEY_HOME"
        assert resolve(u"\x1b[F").name == "KEY_END"
        assert resolve(u"\x1b[K").name == "KEY_END"
        assert resolve(u"\x1bOM").name == "KEY_ENTER"
        assert resolve(u"\x1bOj").name == "KEY_KP_MULTIPLY"
        assert resolve(u"\x1bOk").name == "KEY_KP_ADD"
        assert resolve(u"\x1bOl").name == "KEY_KP_SEPARATOR"
        assert resolve(u"\x1bOm").name == "KEY_KP_SUBTRACT"
        assert resolve(u"\x1bOn").name == "KEY_KP_DECIMAL"
        assert resolve(u"\x1bOo").name == "KEY_KP_DIVIDE"
        assert resolve(u"\x1bOX").name == "KEY_KP_EQUAL"
        assert resolve(u"\x1bOp").name == "KEY_KP_0"
        assert resolve(u"\x1bOq").name == "KEY_KP_1"
        assert resolve(u"\x1bOr").name == "KEY_KP_2"
        assert resolve(u"\x1bOs").name == "KEY_KP_3"
        assert resolve(u"\x1bOt").name == "KEY_KP_4"
        assert resolve(u"\x1bOu").name == "KEY_KP_5"
        assert resolve(u"\x1bOv").name == "KEY_KP_6"
        assert resolve(u"\x1bOw").name == "KEY_KP_7"
        assert resolve(u"\x1bOx").name == "KEY_KP_8"
        assert resolve(u"\x1bOy").name == "KEY_KP_9"
        assert resolve(u"\x1b[1~").name == "KEY_FIND"
        assert resolve(u"\x1b[2~").name == "KEY_INSERT"
        assert resolve(u"\x1b[3~").name == "KEY_DELETE"
        assert resolve(u"\x1b[4~").name == "KEY_SELECT"
        assert resolve(u"\x1b[5~").name == "KEY_PGUP"
        assert resolve(u"\x1b[6~").name == "KEY_PGDOWN"
        assert resolve(u"\x1b[7~").name == "KEY_HOME"
        assert resolve(u"\x1b[8~").name == "KEY_END"
        assert resolve(u"\x1b[OA").name == "KEY_UP"
        assert resolve(u"\x1b[OB").name == "KEY_DOWN"
        assert resolve(u"\x1b[OC").name == "KEY_RIGHT"
        assert resolve(u"\x1b[OD").name == "KEY_LEFT"
        assert resolve(u"\x1b[OF").name == "KEY_END"
        assert resolve(u"\x1b[OH").name == "KEY_HOME"
        assert resolve(u"\x1bOP").name == "KEY_F1"
        assert resolve(u"\x1bOQ").name == "KEY_F2"
        assert resolve(u"\x1bOR").name == "KEY_F3"
        assert resolve(u"\x1bOS").name == "KEY_F4"

    child('xterm')


@pytest.mark.skipif(IS_WINDOWS, reason="no multiprocess")
def test_kp_begin_center_key():
    """Test KP_BEGIN/center key (numpad 5) with modifiers and event types."""
    @as_subprocess
    def child():
        from blessed.keyboard import _match_legacy_csi_modifiers

        # Basic sequence without modifiers
        ks = _match_legacy_csi_modifiers('\x1b[E')
        assert ks is None  # Doesn't match - needs modifiers for legacy CSI

        # With modifiers - Ctrl
        ks = _match_legacy_csi_modifiers('\x1b[1;5E')
        assert ks is not None
        assert ks.code == curses.KEY_B2
        assert ks.name == 'KEY_CTRL_CENTER'

        # With modifiers - Alt
        ks = _match_legacy_csi_modifiers('\x1b[1;3E')
        assert ks is not None
        assert ks.code == curses.KEY_B2
        assert ks.name == 'KEY_ALT_CENTER'

        # With modifiers - Ctrl+Alt
        ks = _match_legacy_csi_modifiers('\x1b[1;7E')
        assert ks is not None
        assert ks.code == curses.KEY_B2
        assert ks.name == 'KEY_CTRL_ALT_CENTER'

        # With event type - release (the original issue case)
        ks = _match_legacy_csi_modifiers('\x1b[1;1:3E')
        assert ks is not None
        assert ks.code == curses.KEY_B2
        assert ks.released
        assert ks.name == 'KEY_CENTER_RELEASED'

        # With event type - repeat
        ks = _match_legacy_csi_modifiers('\x1b[1;1:2E')
        assert ks is not None
        assert ks.code == curses.KEY_B2
        assert ks.repeated
        assert ks.name == 'KEY_CENTER_REPEATED'

        # With modifiers and event type
        ks = _match_legacy_csi_modifiers('\x1b[1;5:3E')
        assert ks is not None
        assert ks.code == curses.KEY_B2
        assert ks.released
        assert ks.name == 'KEY_CTRL_CENTER_RELEASED'

    child()


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
