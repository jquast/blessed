# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""Tests for keyboard support."""
# std imports
import os
import platform
import tempfile
import functools

# 3rd party
import pytest

# local

from .accessories import TestTerminal, as_subprocess
from .conftest import IS_WINDOWS

try:
    from unittest import mock
except ImportError:
    import mock

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


def test_legacy_ctrl_alt_modifiers():
    """Infer modifiers from legacy Ctrl+Alt."""
    from blessed.keyboard import Keystroke

    ks = Keystroke('\x1b\x06')
    assert ks.modifiers == 7
    assert ks.modifiers_bits == 6
    assert ks._ctrl is True
    assert ks._alt is True
    assert ks._shift is False

    ks = Keystroke('\x1b\x1a')
    assert ks.modifiers == 7
    assert ks.modifiers_bits == 6
    assert ks._ctrl is True
    assert ks._alt is True
    assert ks._shift is False


def test_legacy_ctrl_alt_exact_matching():
    """Ctrl+Alt sequences don't match exact is_ctrl/is_alt."""
    from blessed.keyboard import Keystroke

    ks = Keystroke('\x1b\x06')
    assert ks.is_ctrl('f') is False
    assert ks.is_ctrl('F') is False
    assert ks.is_ctrl() is False
    assert ks.is_alt('f') is False
    assert ks.is_alt('F') is False
    assert ks.is_alt() is False

    ks = Keystroke('\x1b\x1a')
    assert ks.is_ctrl('z') is False
    assert ks.is_ctrl('Z') is False
    assert ks.is_ctrl() is False
    assert ks.is_alt('z') is False
    assert ks.is_alt('Z') is False
    assert ks.is_alt() is False


def test_legacy_ctrl_alt_edge_cases():
    """Edge cases for legacy Ctrl+Alt sequences."""
    from blessed.keyboard import Keystroke

    ctrl_alt_cases = [
        ('\x1b\x01', 'ctrl+alt+a'),
        ('\x1b\x06', 'ctrl+alt+f'),
        ('\x1b\x1a', 'ctrl+alt+z'),
        ('\x1b\x00', 'ctrl+alt+@'),
        ('\x1b\x08', 'ctrl+alt+backspace'),
    ]

    for sequence, description in ctrl_alt_cases:
        ks = Keystroke(sequence)
        assert ks.modifiers == 7
        assert ks._ctrl is True
        assert ks._alt is True
        assert ks._shift is False
        assert len(ks) == 2
        assert ks[0] == '\x1b'

    alt_only_cases = [
        ('\x1b\x1b', 'alt+escape', 'KEY_ALT_ESCAPE'),
        ('\x1b\x7f', 'alt+backspace', 'KEY_ALT_BACKSPACE'),
        ('\x1b\x0d', 'alt+enter', 'KEY_ALT_ENTER'),
        ('\x1b\x09', 'alt+tab', 'KEY_ALT_TAB'),
    ]

    for sequence, description, expected_name in alt_only_cases:
        ks = Keystroke(sequence)
        assert ks.modifiers == 3
        assert ks._ctrl is False
        assert ks._alt is True
        assert ks._shift is False
        assert ks.name == expected_name
        assert len(ks) == 2
        assert ks[0] == '\x1b'


def test_terminal_inkey_legacy_ctrl_alt_integration():
    """Terminal.inkey() handles legacy Ctrl+Alt sequences."""
    from blessed import Terminal

    @as_subprocess
    def child():
        term = Terminal(force_styling=True)

        ctrl_alt_f = '\x1b\x06'
        term.ungetch(ctrl_alt_f)
        ks = term.inkey(timeout=0)
        assert ks == ctrl_alt_f
        assert ks.modifiers == 7
        assert ks._ctrl is True
        assert ks._alt is True
        assert ks._shift is False

        ctrl_alt_z = '\x1b\x1a'
        term.ungetch(ctrl_alt_z)
        ks = term.inkey(timeout=0)
        assert ks == ctrl_alt_z
        assert ks.modifiers == 7
        assert ks._ctrl is True
        assert ks._alt is True
        assert ks._shift is False

    child()


def test_legacy_ctrl_alt_doesnt_affect_other_sequences():
    """Test that legacy Ctrl+Alt detection doesn't interfere with existing sequences."""
    from blessed.keyboard import Keystroke

    # Regular Alt sequences should still work (ESC + printable)
    ks_alt_a = Keystroke('\x1ba')  # Alt+a
    assert ks_alt_a.modifiers == 3  # 1 + 2 (alt only)
    assert ks_alt_a._ctrl is False
    assert ks_alt_a._alt is True
    assert ks_alt_a.name == 'KEY_ALT_A'

    # Regular Ctrl sequences should still work (single control char)
    ks_ctrl_a = Keystroke('\x01')  # Ctrl+a
    assert ks_ctrl_a.modifiers == 5  # 1 + 4 (ctrl only)
    assert ks_ctrl_a._ctrl is True
    assert ks_ctrl_a._alt is False
    assert ks_ctrl_a.name == 'KEY_CTRL_A'

    # Regular printable characters should have no modifiers
    ks_regular = Keystroke('a')
    assert ks_regular.modifiers == 1  # No modifiers
    assert ks_regular._ctrl is False
    assert ks_regular._alt is False


def test_keystroke_legacy_ctrl_alt_name_generation():
    """Test name generation for legacy Ctrl+Alt (metaSendsEscape + control char)."""
    from blessed.keyboard import Keystroke

    # Test basic letter mappings
    test_cases = [
        ('\x1b\x17', 'KEY_CTRL_ALT_W'),  # ESC + Ctrl+W (0x17 = 23, W = 23rd letter)
        ('\x1b\x01', 'KEY_CTRL_ALT_A'),  # ESC + Ctrl+A
        ('\x1b\x02', 'KEY_CTRL_ALT_B'),  # ESC + Ctrl+B
        ('\x1b\x1a', 'KEY_CTRL_ALT_Z'),  # ESC + Ctrl+Z
    ]

    for sequence, expected_name in test_cases:
        ks = Keystroke(sequence)
        assert ks.name == expected_name
        # Verify it has the correct modifiers
        assert ks.modifiers == 7  # 1 + 2 (alt) + 4 (ctrl)
        assert ks._ctrl is True
        assert ks._alt is True
        assert ks._shift is False

    # Test special symbol mappings for Ctrl+Alt (not C0 exceptions)
    symbol_test_cases = [
        ('\x1b\x00', 'KEY_CTRL_ALT_@'),   # ESC + Ctrl+@ (NUL) - Ctrl+Alt
        ('\x1b\x1c', 'KEY_CTRL_ALT_\\'),  # ESC + Ctrl+\ (FS) - Ctrl+Alt
        ('\x1b\x1d', 'KEY_CTRL_ALT_]'),   # ESC + Ctrl+] (GS) - Ctrl+Alt
        ('\x1b\x1e', 'KEY_CTRL_ALT_^'),   # ESC + Ctrl+^ (RS) - Ctrl+Alt
        ('\x1b\x1f', 'KEY_CTRL_ALT__'),   # ESC + Ctrl+_ (US) - Ctrl+Alt
        ('\x1b\x08', 'KEY_CTRL_ALT_H'),   # ESC + Ctrl+H (BS) - Ctrl+Alt Backspace
    ]

    for sequence, expected_name in symbol_test_cases:
        ks = Keystroke(sequence)
        assert ks.name == expected_name
        # Verify it has the correct modifiers
        assert ks.modifiers == 7  # 1 + 2 (alt) + 4 (ctrl)
        assert ks._ctrl is True
        assert ks._alt is True
        assert ks._shift is False

    # Test C0 exceptions that should be Alt-only
    alt_only_symbol_cases = [
        ('\x1b\x1b', 'KEY_ALT_ESCAPE'),   # ESC + ESC - Alt+Escape per legacy spec
        ('\x1b\x7f', 'KEY_ALT_BACKSPACE'),  # ESC + DEL - Alt+Backspace per legacy spec
    ]

    for sequence, expected_name in alt_only_symbol_cases:
        ks = Keystroke(sequence)
        assert ks.name == expected_name
        # Verify it has the correct modifiers (Alt-only)
        assert ks.modifiers == 3  # 1 + 2 (alt only)
        assert ks._ctrl is False
        assert ks._alt is True
        assert ks._shift is False

    # Test that existing naming is unchanged
    # Regular Alt sequences (ESC + printable)
    assert Keystroke('\x1ba').name == 'KEY_ALT_A'  # Alt+a
    assert Keystroke('\x1bz').name == 'KEY_ALT_Z'  # Alt+z
    assert Keystroke('\x1b1').name == 'KEY_ALT_1'  # Alt+1

    # Test new ALT_SHIFT naming for uppercase letters
    assert Keystroke('\x1bA').name == 'KEY_ALT_SHIFT_A'  # Alt+A (uppercase)
    assert Keystroke('\x1bZ').name == 'KEY_ALT_SHIFT_Z'  # Alt+Z (uppercase)

    # Regular Ctrl sequences (single control char)
    assert Keystroke('\x01').name == 'KEY_CTRL_A'  # Ctrl+a
    assert Keystroke('\x1a').name == 'KEY_CTRL_Z'  # Ctrl+z
    assert Keystroke('\x00').name == 'KEY_CTRL_@'  # Ctrl+@
    assert Keystroke('\x7f').name == 'KEY_CTRL_?'  # Ctrl+?

    # Test that explicit names are preserved
    ks_with_name = Keystroke('\x1b\x17', name='CUSTOM_NAME')
    assert ks_with_name.name == 'CUSTOM_NAME'

    # Test edge cases - unmapped control characters should not generate names
    # (though in practice, all control chars 0-31 and 127 should be mapped)
    # We don't expect any unmapped ones in the current implementation


def test_legacy_spec_compliance_menu_key():
    """Test that MENU key (CSI 29~) works according to legacy spec."""
    from blessed.keyboard import _match_legacy_csi_modifiers, LegacyCSIKeyEvent, KEY_MENU

    # Test basic MENU key without modifiers
    # Note: this would typically be CSI 29~ but our matcher only handles with modifiers
    # The basic form would be handled by traditional keymap

    # Test MENU key with modifiers
    test_cases = [
        ('\x1b[29;2~', 'Shift+Menu', 2, {'shift': True}),
        ('\x1b[29;3~', 'Alt+Menu', 3, {'alt': True}),
        ('\x1b[29;5~', 'Ctrl+Menu', 5, {'ctrl': True}),
        ('\x1b[29;7~', 'Ctrl+Alt+Menu', 7, {'ctrl': True, 'alt': True}),
    ]

    for sequence, description, expected_mod, expected_flags in test_cases:
        ks = _match_legacy_csi_modifiers(sequence)
        assert ks is not None, f"Failed to match {description} sequence={sequence!r}"
        assert ks._mode == -3  # Legacy CSI mode
        assert isinstance(ks._match, LegacyCSIKeyEvent)

        event = ks._match
        assert event.kind == 'tilde'
        assert event.key_id == 29  # MENU tilde number
        assert event.modifiers == expected_mod

        # Check that it maps to the correct keycode
        assert ks._code == KEY_MENU

        # Check modifier flags
        assert ks.modifiers == expected_mod
        assert ks._shift == expected_flags.get('shift', False), f"shift failed for {description}"
        assert ks._ctrl == expected_flags.get('ctrl', False), f"ctrl failed for {description}"
        assert ks._alt == expected_flags.get('alt', False), f"alt failed for {description}"

        # Check dynamic name generation includes MENU
        assert 'MENU' in ks.name, f"name should contain MENU for {description}, got {ks.name!r}"


def test_legacy_spec_compliance_c0_controls():
    """Test C0 control modifier inference per legacy spec."""
    from blessed.keyboard import Keystroke

    # Test Alt-only C0 controls per legacy spec table
    alt_only_cases = [
        ('\x1b\x0d', 'Alt+Enter', 3, 'Enter'),      # ESC + CR
        ('\x1b\x1b', 'Alt+Escape', 3, 'Escape'),    # ESC + ESC
        ('\x1b\x7f', 'Alt+Backspace', 3, 'DEL'),    # ESC + DEL
        ('\x1b\x09', 'Alt+Tab', 3, 'Tab'),          # ESC + TAB
    ]

    for sequence, description, expected_mod, key_name in alt_only_cases:
        ks = Keystroke(sequence)

        assert ks.modifiers == expected_mod
        assert ks._alt is True
        assert ks._ctrl is False
        assert ks._shift is False

        # These should match exact alt checks
        assert ks.is_alt() is True
        assert ks.is_ctrl() is False

    # Test Ctrl+Alt combinations that still use ESC + control char
    ctrl_alt_cases = [
        ('\x1b\x01', 'Ctrl+Alt+A', 7),        # ESC + Ctrl+A
        ('\x1b\x06', 'Ctrl+Alt+F', 7),        # ESC + Ctrl+F
        ('\x1b\x1a', 'Ctrl+Alt+Z', 7),        # ESC + Ctrl+Z
        ('\x1b\x00', 'Ctrl+Alt+Space', 7),    # ESC + NUL (Ctrl+Space)
        ('\x1b\x08', 'Ctrl+Alt+Backspace', 7),  # ESC + BS (Ctrl+Backspace)
    ]

    for sequence, description, expected_mod in ctrl_alt_cases:
        ks = Keystroke(sequence)

        assert ks.modifiers == expected_mod
        assert ks._ctrl is True
        assert ks._alt is True
        assert ks._shift is False

        # These should NOT match exact checks since both modifiers are present
        assert ks.is_ctrl() is False
        assert ks.is_alt() is False


def test_legacy_spec_compliance_text_keys():
    """Test text key modifier inference per legacy spec algorithm."""
    from blessed.keyboard import Keystroke

    # Test that existing Alt + printable behavior is preserved
    printable_alt_cases = [
        ('\x1ba', 'Alt+a', 3),
        ('\x1b1', 'Alt+1', 3),
        ('\x1b;', 'Alt+;', 3),
        ('\x1bZ', 'Alt+Shift+Z', 4),
    ]

    for sequence, description, expected_mod in printable_alt_cases:
        ks = Keystroke(sequence)

        assert ks.modifiers == expected_mod
        assert ks._alt is True
        assert ks._ctrl is False

        # For Alt+uppercase, we need exact=False since Shift is also present
        if expected_mod == 4:  # Alt+Shift
            assert ks.is_alt(exact=False) is True
        else:
            assert ks.is_alt() is True

    # Test that existing Ctrl behavior is preserved
    ctrl_cases = [
        ('\x01', 'Ctrl+A', 5),
        ('\x06', 'Ctrl+F', 5),
        ('\x1a', 'Ctrl+Z', 5),
    ]

    for sequence, description, expected_mod in ctrl_cases:
        ks = Keystroke(sequence)

        assert ks.modifiers == expected_mod
        assert ks._ctrl is True
        assert ks._alt is False
        assert ks.is_ctrl() is True


def test_ss3_no_modifier_sequences():
    """Test SS3 sequences (no modifiers) per legacy spec."""
    from blessed.keyboard import resolve_sequence, get_keyboard_sequences, get_keyboard_codes
    from .accessories import TestTerminal

    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        keymap = get_keyboard_sequences(term)
        codes = get_keyboard_codes()
        prefixes = set()

        def resolve(seq):
            return resolve_sequence(seq, keymap, codes, prefixes, final=True)

        # Test SS3 sequences from DEFAULT_SEQUENCE_MIXIN
        ss3_cases = [
            ('\x1bOP', 'F1', curses.KEY_F1),        # SS3 P
            ('\x1bOQ', 'F2', curses.KEY_F2),        # SS3 Q
            ('\x1bOR', 'F3', curses.KEY_F3),        # SS3 R
            ('\x1bOS', 'F4', curses.KEY_F4),        # SS3 S
            ('\x1bOA', 'Up', curses.KEY_UP),        # SS3 A
            ('\x1bOB', 'Down', curses.KEY_DOWN),    # SS3 B
            ('\x1bOC', 'Right', curses.KEY_RIGHT),  # SS3 C
            ('\x1bOD', 'Left', curses.KEY_LEFT),    # SS3 D
            ('\x1bOH', 'Home', curses.KEY_HOME),    # SS3 H
            ('\x1bOF', 'End', curses.KEY_END),      # SS3 F
        ]

        for sequence, description, expected_code in ss3_cases:
            ks = resolve(sequence)

            # Should be recognized and have correct keycode
            assert ks == sequence
            assert ks.code == expected_code
            assert ks.name is not None
            assert ks.name.startswith('KEY_')

            # Should have no modifiers (base value 1)
            assert ks.modifiers == 1
            assert ks._ctrl is False
            assert ks._alt is False
            assert ks._shift is False

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
    from blessed.keyboard import Keystroke
    ks = Keystroke()
    assert ks._name is None
    assert ks.name == ks._name
    assert ks._code is None
    assert ks.code == ks._code
    assert 'x' + ks == 'x'
    assert not ks.is_sequence
    assert repr(ks) in {"u''",  # py26, 27
                        "''"}  # py33


def test_a_keystroke():
    """Test keyboard.Keystroke constructor with set arguments."""
    from blessed.keyboard import Keystroke
    ks = Keystroke(ucs=u'x', code=1, name=u'the X')
    assert ks._name == 'the X'
    assert ks.name == ks._name
    assert ks._code == 1
    assert ks.code == ks._code
    assert 'x' + ks == 'xx'
    assert ks.is_sequence
    assert repr(ks) == "the X"


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


def test_resolve_sequence():
    """Test resolve_sequence for order-dependent mapping."""
    from blessed.keyboard import resolve_sequence, OrderedDict, get_leading_prefixes
    mapper = OrderedDict(((u'SEQ1', 1),
                          (u'SEQ2', 2),
                          # takes precedence over LONGSEQ, first-match
                          (u'KEY_LONGSEQ_longest', 3),
                          (u'LONGSEQ', 4),
                          # won't match, LONGSEQ is first-match in this order
                          (u'LONGSEQ_longer', 5),
                          # falls through for L{anything_else}
                          (u'L', 6)))
    codes = {1: 'KEY_SEQ1',
             2: 'KEY_SEQ2',
             3: 'KEY_LONGSEQ_longest',
             4: 'KEY_LONGSEQ',
             5: 'KEY_LONGSEQ_longer',
             6: 'KEY_L'}
    prefixes = get_leading_prefixes(mapper)
    ks = resolve_sequence(u'', mapper, codes, prefixes, final=True)
    assert ks == ''
    assert ks.name is None
    assert ks.code is None
    assert not ks.is_sequence
    assert repr(ks) in {"u''",  # py26, 27
                        "''"}  # py33

    ks = resolve_sequence(u'notfound', mapper, codes, prefixes, final=True)
    assert ks == 'n'
    assert ks.name is None
    assert ks.code is None
    assert not ks.is_sequence
    assert repr(ks) in {"u'n'", "'n'"}

    ks = resolve_sequence(u'SEQ1', mapper, codes, prefixes, final=True)
    assert ks == 'SEQ1'
    assert ks.name == 'KEY_SEQ1'
    assert ks.code == 1
    assert ks.is_sequence
    assert repr(ks) == "KEY_SEQ1"

    ks = resolve_sequence(u'LONGSEQ_longer', mapper, codes, prefixes, final=True)
    assert ks == 'LONGSEQ'
    assert ks.name == 'KEY_LONGSEQ'
    assert ks.code == 4
    assert ks.is_sequence
    assert repr(ks) == "KEY_LONGSEQ"

    ks = resolve_sequence(u'LONGSEQ', mapper, codes, prefixes, final=True)
    assert ks == 'LONGSEQ'
    assert ks.name == 'KEY_LONGSEQ'
    assert ks.code == 4
    assert ks.is_sequence
    assert repr(ks) == "KEY_LONGSEQ"

    ks = resolve_sequence(u'Lxxxxx', mapper, codes, prefixes, final=True)
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
        from blessed.keyboard import resolve_sequence

        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes,
                                    prefixes=term._keymap_prefixes,
                                    final=True)

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


@pytest.mark.parametrize('sequence,char,expected', [
    # Positive cases - basic control characters
    ('\x01', 'a', True), ('\x01', 'A', True),  # Ctrl+A
    ('\x1a', 'z', True), ('\x1a', 'Z', True),  # Ctrl+Z
    # Special control mappings
    ('\x00', '@', True),   # Ctrl+@
    ('\x1b', '[', True),   # Ctrl+[
    ('\x1c', '\\', True),  # Ctrl+\
    ('\x1d', ']', True),   # Ctrl+]
    ('\x1e', '^', True),   # Ctrl+^
    ('\x1f', '_', True),   # Ctrl+_
    ('\x7f', '?', True),   # Ctrl+?
    # Negative cases
    ('a', 'a', False),      # Regular 'a'
    ('\x01', 'b', False),   # Ctrl+A != Ctrl+B
    ('\x1ba', 'a', False),  # Alt+a, not Ctrl+a
])
def test_keystroke_ctrl(sequence, char, expected):
    """Test Keystroke.is_ctrl() method for control character detection."""
    from blessed.keyboard import Keystroke
    assert Keystroke(sequence).is_ctrl(char) is expected


def test_keystroke_alt():
    """Test Keystroke.is_alt() method for Alt+character detection."""
    from blessed.keyboard import Keystroke

    # Test basic Alt combinations
    assert Keystroke('\x1ba').is_alt('a') is True  # Alt+a
    assert Keystroke('\x1ba').is_alt('A') is True  # Case insensitive by default
    assert Keystroke('\x1bz').is_alt('z') is True  # Alt+z
    assert Keystroke('\x1bZ').is_alt('Z', exact=False) is True  # Alt+Z (now has Shift too)

    # Test case sensitivity control
    assert Keystroke('\x1ba').is_alt('A', ignore_case=True) is True
    assert Keystroke('\x1ba').is_alt('A', ignore_case=False) is False
    # Now has Shift too, so exact=False needed
    assert Keystroke('\x1bA').is_alt('A', ignore_case=False, exact=False) is True

    # Test without character argument (any Alt+char)
    assert Keystroke('\x1ba').is_alt() is True     # Alt+a
    assert Keystroke('\x1b1').is_alt() is True     # Alt+1
    assert Keystroke('\x1b ').is_alt() is True     # Alt+space

    # Test negative cases
    assert Keystroke('a').is_alt('a') is False     # Regular 'a'
    assert Keystroke('\x1b').is_alt('a') is False  # Just ESC
    assert Keystroke('\x1ba').is_alt('b') is False  # Alt+a != Alt+b
    assert Keystroke('\x1bab').is_alt('a') is False  # Too long
    assert Keystroke('\x1b\x01').is_alt() is False  # Non-printable second char


def test_keystroke_ctrl_alt_names():
    """Test that Keystroke names are synthesized correctly for CTRL and ALT."""
    from blessed.keyboard import Keystroke

    # Test CTRL names
    assert Keystroke('\x01').name == 'KEY_CTRL_A'
    assert Keystroke('\x1a').name == 'KEY_CTRL_Z'
    assert Keystroke('\x00').name == 'KEY_CTRL_@'
    assert Keystroke('\x1b').name == 'KEY_CTRL_['
    assert Keystroke('\x1c').name == 'KEY_CTRL_\\'
    assert Keystroke('\x1d').name == 'KEY_CTRL_]'
    assert Keystroke('\x1e').name == 'KEY_CTRL_^'
    assert Keystroke('\x1f').name == 'KEY_CTRL__'
    assert Keystroke('\x7f').name == 'KEY_CTRL_?'

    # Test ALT names
    assert Keystroke('\x1ba').name == 'KEY_ALT_A'
    assert Keystroke('\x1bz').name == 'KEY_ALT_Z'
    assert Keystroke('\x1bA').name == 'KEY_ALT_SHIFT_A'
    assert Keystroke('\x1b1').name == 'KEY_ALT_1'
    assert Keystroke('\x1b!').name == 'KEY_ALT_!'

    # Test that existing names are preserved
    ks_with_name = Keystroke('\x01', name='EXISTING_NAME')
    assert ks_with_name.name == 'EXISTING_NAME'


def test_keystroke_is_sequence_enhanced():
    """Test that is_sequence includes multi-char sequences like Alt combinations."""
    from blessed.keyboard import Keystroke

    # Test original behavior
    assert Keystroke('a').is_sequence is False
    assert Keystroke('\x01', code=1).is_sequence is True
    assert Keystroke('\x01', mode=123).is_sequence is True

    # Test new behavior for multi-char sequences
    assert Keystroke('\x1ba').is_sequence is True   # Alt+a (len > 1)
    assert Keystroke('ab').is_sequence is True      # Any multi-char
    assert Keystroke('\x1b[A').is_sequence is True  # Escape sequence (len > 1)


def test_modifiers_inference_legacy_ctrl():
    """Test modifier inference from legacy control characters."""
    from blessed.keyboard import Keystroke

    # Ctrl+a as legacy control character
    ks = Keystroke('\x01')  # Ctrl+A

    assert ks.modifiers == 5  # 1 + 4 (ctrl)
    assert ks.modifiers_bits == 4
    assert ks._ctrl is True
    assert ks._alt is False
    assert ks._shift is False


def test_modifiers_inference_legacy_alt():
    """Test modifier inference from legacy Alt (meta sends escape)."""
    from blessed.keyboard import Keystroke

    # Alt+a as ESC+a
    ks = Keystroke('\x1ba')

    assert ks.modifiers == 3  # 1 + 2 (alt)
    assert ks.modifiers_bits == 2
    assert ks._ctrl is False
    assert ks._alt is True
    assert ks._shift is False


def test_modifiers_inference_no_modifiers():
    """Test that regular characters have no modifiers."""
    from blessed.keyboard import Keystroke

    ks = Keystroke('a')

    assert ks.modifiers == 1  # No modifiers
    assert ks.modifiers_bits == 0
    assert ks._ctrl is False
    assert ks._alt is False
    assert ks._shift is False


def test_individual_modifier_properties():
    """Test individual modifier flag properties using new dynamic API."""
    from blessed.keyboard import Keystroke, KittyKeyEvent

    test_letter = 'a'
    # Test single modifier cases (exact=True should work)
    single_modifier_cases = [
        (1, {}),  # No modifiers
        (2, {'shift': True}),  # 1 + 1
        (3, {'alt': True}),    # 1 + 2
        (5, {'ctrl': True}),   # 1 + 4
        (9, {'super': True}),  # 1 + 8
        (17, {'hyper': True}),  # 1 + 16
        (33, {'meta': True}),  # 1 + 32
        (65, {'caps_lock': True}),  # 1 + 64
        (129, {'num_lock': True}),  # 1 + 128
    ]

    for modifiers_value, expected_flags in single_modifier_cases:
        # Create a Kitty keystroke with the modifier value
        kitty_event = KittyKeyEvent(unicode_key=ord(test_letter), shifted_key=None, base_key=None,
                                    modifiers=modifiers_value, event_type=1, int_codepoints=[])
        ks = Keystroke(f'\x1b[{ord(test_letter)};{modifiers_value}u', mode=-1, match=kitty_event)

        # Check each modifier property using dynamic predicates (exact=True by default)
        # For single modifiers, exact matching should work, it is allowed to *not* pass
        # the alphanumeric, eg. is_alt() instead of is_alt('a'), verify that here, also
        assert ks.is_shift() == expected_flags.get('shift', False)
        assert ks.is_alt() == expected_flags.get('alt', False)
        assert ks.is_ctrl() == expected_flags.get('ctrl', False)
        assert ks.is_super() == expected_flags.get('super', False)
        assert ks.is_hyper() == expected_flags.get('hyper', False)
        assert ks.is_meta() == expected_flags.get('meta', False)
        assert ks.is_shift('a') == expected_flags.get('shift', False)
        assert ks.is_alt('a') == expected_flags.get('alt', False)
        assert ks.is_ctrl('a') == expected_flags.get('ctrl', False)
        assert ks.is_super('a') == expected_flags.get('super', False)
        assert ks.is_hyper('a') == expected_flags.get('hyper', False)
        assert ks.is_meta('a') == expected_flags.get('meta', False)

        # Test private properties are accessible internally
        assert ks._shift == expected_flags.get('shift', False)
        assert ks._alt == expected_flags.get('alt', False)
        assert ks._ctrl == expected_flags.get('ctrl', False)
        assert ks._super == expected_flags.get('super', False)
        assert ks._hyper == expected_flags.get('hyper', False)
        assert ks._meta == expected_flags.get('meta', False)
        assert ks._caps_lock == expected_flags.get('caps_lock', False)
        assert ks._num_lock == expected_flags.get('num_lock', False)

    # Test multi-modifier case: Shift+Alt+Ctrl
    kitty_event = KittyKeyEvent(unicode_key=ord(test_letter), shifted_key=None, base_key=None,
                                modifiers=8, event_type=1, int_codepoints=[])  # 1 + (1+2+4) = 8
    ks = Keystroke('\x1b[{ord(test_letter)};8u', mode=-1, match=kitty_event)

    # With exact=True (default), individual modifiers should return False since multiple are present
    assert ks.is_shift(test_letter) is False
    assert ks.is_alt(test_letter) is False
    assert ks.is_ctrl(test_letter) is False

    # But private properties should reflect the actual bits
    assert ks._shift is True
    assert ks._alt is True
    assert ks._ctrl is True
    assert ks._super is False

    # With exact=False (subset matching), can be true! Not sure who would want
    # this, but it's there for you!
    assert ks.is_shift(exact=False) is True   # Shift is present
    assert ks.is_alt(exact=False) is True     # Alt is present
    assert ks.is_ctrl(exact=False) is True    # Ctrl is present
    assert ks.is_super(exact=False) is False  # Super is not present
    assert ks.is_shift(test_letter, exact=False) is True   # Shift is present
    assert ks.is_alt(test_letter, exact=False) is True     # Alt is present
    assert ks.is_ctrl(test_letter, exact=False) is True    # Ctrl is present
    assert ks.is_super(test_letter, exact=False) is False  # Super is not present


def test_keystroke_value_property():
    """Test the new value property for text character extraction."""
    from blessed.keyboard import Keystroke

    # Plain printable characters
    assert Keystroke('a').value == 'a'
    assert Keystroke('A').value == 'A'
    assert Keystroke('1').value == '1'
    assert Keystroke(';').value == ';'
    assert Keystroke(' ').value == ' '

    # Alt+printable (ESC + char) - return the printable part
    assert Keystroke('\x1ba').value == 'a'  # Alt+a -> 'a'
    assert Keystroke('\x1bA').value == 'A'  # Alt+A -> 'A'
    assert Keystroke('\x1b1').value == '1'  # Alt+1 -> '1'

    # Ctrl+letter - return lowercase letter
    assert Keystroke('\x01').value == 'a'   # Ctrl+A -> 'a'
    assert Keystroke('\x1a').value == 'z'   # Ctrl+Z -> 'z'

    # Ctrl+symbol - return symbol
    assert Keystroke('\x00').value == '@'   # Ctrl+@ -> '@'
    assert Keystroke('\x1b').value == '['   # Ctrl+[ -> '['
    assert Keystroke('\x7f').value == '?'   # Ctrl+? -> '?'

    # Application keys - return empty string
    arrow_key = Keystroke('\x1b[A', code=1, name='KEY_UP')
    assert arrow_key.value == ''  # Application keys return empty string


def test_value_property_unicode_and_complex():
    """Test value property with Unicode characters and complex sequences."""
    from blessed.keyboard import Keystroke, KittyKeyEvent
    import curses

    # Unicode characters (non-ASCII)
    omega_kitty = KittyKeyEvent(unicode_key=937, shifted_key=None, base_key=None,
                                modifiers=1, event_type=1, int_codepoints=[])
    omega_ks = Keystroke('\x1b[937u', mode=-1, match=omega_kitty)
    assert omega_ks.value == 'Ω'  # Unicode Omega

    # Emoji with ZWJ sequence via int_codepoints
    emoji_kitty = KittyKeyEvent(unicode_key=0, shifted_key=None, base_key=None,
                                modifiers=1, event_type=1, int_codepoints=[128104, 8205, 128187])
    emoji_ks = Keystroke('\x1b[0;;1;128104:8205:128187u', mode=-1, match=emoji_kitty)
    assert emoji_ks.value == '👨‍💻'  # Man technologist emoji with ZWJ

    # Function keys return empty string
    f10_ks = Keystroke('\x1b[21~', code=curses.KEY_F10, name='KEY_F10')
    assert f10_ks.value == ''  # F10 -> empty string

    # DEC events return empty string
    paste_ks = Keystroke('\x1b[200~hello\x1b[201~', mode=2004, match=None)
    assert paste_ks.value == ''  # Bracketed paste -> empty string


def test_dynamic_compound_modifier_predicates():
    """Test the new dynamic compound modifier predicates."""
    from blessed.keyboard import Keystroke, KittyKeyEvent

    # Create a Keystroke with Ctrl+Alt+A
    kitty_event = KittyKeyEvent(unicode_key=97, shifted_key=None, base_key=None,
                                modifiers=7, event_type=1, int_codepoints=[])  # 1 + 2 + 4 = 7
    ks = Keystroke('\x1b[97;7u', mode=-1, match=kitty_event)

    # Test compound predicates - should work with exact=False (subset matching)
    assert ks.is_ctrl(exact=False) is True      # Ctrl is present
    assert ks.is_alt(exact=False) is True       # Alt is present
    assert ks.is_ctrl_alt(exact=True) is True   # Exactly Ctrl+Alt
    assert ks.is_alt_ctrl(exact=True) is True   # Order shouldn't matter

    # Test with character matching
    assert ks.is_ctrl_alt('a', exact=True) is True
    assert ks.is_ctrl_alt('A', exact=True) is True  # Case insensitive by default
    assert ks.is_ctrl_alt('b', exact=True) is False  # Wrong character

    # Test exact=True should fail when other modifiers present
    assert ks.is_ctrl(exact=True) is False      # Not exactly Ctrl (Alt also present)
    assert ks.is_alt(exact=True) is False       # Not exactly Alt (Ctrl also present)

    # Test single modifier keystroke
    ks_ctrl_only = Keystroke('\x01')  # Ctrl+A
    assert ks_ctrl_only.is_ctrl(exact=True) is True    # Exactly Ctrl
    assert ks_ctrl_only.is_ctrl('a', exact=True) is True
    assert ks_ctrl_only.is_alt(exact=True) is False    # No Alt
    assert ks_ctrl_only.is_ctrl_alt(exact=True) is False  # Not Ctrl+Alt


def test_is_ctrl_exact_matching_legacy():
    """Test exact matching for is_ctrl with legacy control characters."""
    from blessed.keyboard import Keystroke

    # Legacy Ctrl+a
    ks = Keystroke('\x01')
    assert ks.is_ctrl('a') is True
    assert ks.is_ctrl('A') is True  # Case insensitive
    assert ks.is_ctrl('b') is False
    assert ks.is_ctrl() is True

    # Test special control mappings
    assert Keystroke('\x00').is_ctrl('@') is True  # Ctrl+@
    assert Keystroke('\x1b').is_ctrl('[') is True  # Ctrl+[ (ESC)
    assert Keystroke('\x7f').is_ctrl('?') is True  # Ctrl+?


def test_is_alt_exact_matching_legacy():
    """Test exact matching for is_alt with legacy Alt combinations."""
    from blessed.keyboard import Keystroke

    # Legacy Alt+a
    ks = Keystroke('\x1ba')
    assert ks.is_alt('a') is True
    assert ks.is_alt('A') is True   # Case insensitive by default
    assert ks.is_alt('b') is False
    assert ks.is_alt() is True

    # Case sensitivity control
    ks = Keystroke('\x1bA')  # Alt+A (uppercase)
    # Now has Shift too, so exact=False needed
    assert ks.is_alt('a', ignore_case=True, exact=False) is True
    assert ks.is_alt('a', ignore_case=False, exact=False) is False
    assert ks.is_alt('A', ignore_case=False, exact=False) is True


def test_lock_keys_ignored_in_exact_matching():
    """Test that caps_lock and num_lock are ignored in exact matching."""
    from blessed.keyboard import Keystroke, KittyKeyEvent

    # Ctrl+a with caps_lock on should still match is_ctrl('a')
    kitty_event = KittyKeyEvent(unicode_key=97, shifted_key=None, base_key=None,
                                modifiers=69, event_type=1, int_codepoints=[])  # 1 + 4 + 64
    ks = Keystroke('\x1b[97;69u', mode=-1, match=kitty_event)
    assert ks._caps_lock is True
    assert ks._ctrl is True
    assert ks.is_ctrl('a') is True  # Should still match despite caps_lock

    # Alt+a with num_lock on should still match is_alt('a')
    kitty_event = KittyKeyEvent(unicode_key=97, shifted_key=None, base_key=None,
                                modifiers=131, event_type=1, int_codepoints=[])  # 1 + 2 + 128
    ks = Keystroke('\x1b[97;131u', mode=-1, match=kitty_event)
    assert ks._num_lock is True
    assert ks._alt is True
    assert ks.is_alt('a') is True  # Should still match despite num_lock


def test_modifiers_bits_edge_cases():
    """Test edge cases for modifiers_bits property."""
    from blessed.keyboard import Keystroke

    # Ensure modifiers_bits never goes negative
    ks = Keystroke('a')  # modifiers = 1
    assert ks.modifiers_bits == 0  # max(0, 1 - 1) = 0

    # Test with constructed keystroke with modifiers = 0 (shouldn't happen normally)
    ks = Keystroke('a')
    ks._modifiers = 0  # Force set to 0
    assert ks.modifiers_bits == 0  # max(0, 0 - 1) = 0


def test_comprehensive_modifier_combinations():
    """Test comprehensive modifier combinations work correctly."""
    from blessed.keyboard import Keystroke, KittyKeyEvent

    # Test a complex modifier combination: Ctrl+Shift+Alt+Super
    expected_bits = 0b1 | 0b10 | 0b100 | 0b1000  # shift + alt + ctrl + super = 15
    expected_modifiers = 1 + expected_bits  # 16

    kitty_event = KittyKeyEvent(unicode_key=97, shifted_key=None, base_key=None,
                                modifiers=expected_modifiers, event_type=1, int_codepoints=[])
    ks = Keystroke(f'\x1b[97;{expected_modifiers}u', mode=-1, match=kitty_event)

    assert ks.modifiers == expected_modifiers
    assert ks.modifiers_bits == expected_bits
    assert ks._shift is True
    assert ks._alt is True
    assert ks._ctrl is True
    assert ks._super is True
    assert ks._hyper is False
    assert ks._meta is False

    # This should NOT match exact ctrl or alt since other modifiers are present
    assert ks.is_ctrl('a') is False
    assert ks.is_alt('a') is False
    assert ks.is_ctrl() is False
    assert ks.is_alt() is False


def test_ghostty_f3_tilde_form_variants():
    """Test F3 tilde-form sequences for ghostty terminal compatibility."""
    from blessed.keyboard import _match_legacy_csi_modifiers, LegacyCSIKeyEvent

    # Test all F3 modifier combinations in tilde form (ghostty peculiarity)
    f3_test_cases = [
        ('\x1b[13;2~', 2, 'Shift+F3', {'shift': True}),
        ('\x1b[13;3~', 3, 'Alt+F3', {'alt': True}),
        ('\x1b[13;5~', 5, 'Ctrl+F3', {'ctrl': True}),
        ('\x1b[13;6~', 6, 'Ctrl+Shift+F3', {'ctrl': True, 'shift': True}),
        ('\x1b[13;7~', 7, 'Ctrl+Alt+F3', {'ctrl': True, 'alt': True}),
        ('\x1b[13;8~', 8, 'Ctrl+Alt+Shift+F3', {'ctrl': True, 'alt': True, 'shift': True}),
    ]

    for sequence, expected_mod, description, expected_flags in f3_test_cases:
        ks = _match_legacy_csi_modifiers(sequence)
        assert ks is not None, f"Failed to match {description} sequence={sequence!r}"
        assert ks._mode == -3  # Legacy CSI mode
        assert isinstance(ks._match, LegacyCSIKeyEvent)

        event = ks._match
        assert event.kind == 'tilde'
        assert event.key_id == 13  # F3 tilde number
        assert event.modifiers == expected_mod

        # Check modifiers are properly detected
        assert ks.modifiers == expected_mod
        assert ks._code == curses.KEY_F3  # Should map to F3 keycode

        # Check individual modifier flags
        assert ks._shift == expected_flags.get('shift', False), f"shift failed for {description}"
        assert ks._alt == expected_flags.get('alt', False), f"alt failed for {description}"
        assert ks._ctrl == expected_flags.get('ctrl', False), f"ctrl failed for {description}"

        # Check dynamic name generation
        expected_name_parts = ['KEY']
        if ks._ctrl:
            expected_name_parts.append('CTRL')
        if ks._alt:
            expected_name_parts.append('ALT')
        if ks._shift:
            expected_name_parts.append('SHIFT')
        expected_name_parts.append('F3')
        expected_name = '_'.join(expected_name_parts)

        assert ks.name == expected_name


def test_alt_uppercase_sets_shift_modifier_and_name():
    """Test that Alt+uppercase letters correctly set both Alt and Shift modifiers."""
    from blessed.keyboard import Keystroke

    # Test lowercase Alt+j - should be Alt-only
    ks_lower = Keystroke('\x1bj')  # Alt+j
    assert ks_lower.modifiers == 3  # 1 + 2 (alt only)
    assert ks_lower._alt is True
    assert ks_lower._shift is False
    assert ks_lower.name == 'KEY_ALT_J'

    # Test uppercase Alt+J - should be Alt+Shift
    ks_upper = Keystroke('\x1bJ')  # Alt+Shift+J
    assert ks_upper.modifiers == 4  # 1 + 2 (alt) + 1 (shift) = 4
    assert ks_upper._alt is True
    assert ks_upper._shift is True
    assert ks_upper.name == 'KEY_ALT_SHIFT_J'

    # Test various uppercase letters
    test_cases = [
        ('\x1bA', 'KEY_ALT_SHIFT_A'),
        ('\x1bZ', 'KEY_ALT_SHIFT_Z'),
        ('\x1bM', 'KEY_ALT_SHIFT_M'),
    ]

    for sequence, expected_name in test_cases:
        ks = Keystroke(sequence)
        assert ks.modifiers == 4
        assert ks._alt is True
        assert ks._shift is True
        assert ks.name == expected_name

    # Test that non-alphabetic printable characters remain Alt-only
    non_alpha_cases = [
        ('\x1b1', 'KEY_ALT_1', 3),  # Alt+1
        ('\x1b!', 'KEY_ALT_!', 3),  # Alt+!
        ('\x1b;', 'KEY_ALT_;', 3),  # Alt+;
        ('\x1b ', 'KEY_ALT_ ', 3),  # Alt+space (though space might not have a name)
    ]

    for sequence, expected_name, expected_modifiers in non_alpha_cases:
        ks = Keystroke(sequence)
        assert ks.modifiers == expected_modifiers
        assert ks._alt is True
        assert ks._shift is False
        if expected_name.endswith(' '):  # Space might not have a name
            continue
        assert ks.name == expected_name


def test_compatibility_with_existing_behavior():
    """Test that existing keyboard behavior remains unchanged."""
    from blessed.keyboard import Keystroke

    # Regular keys should work as before
    ks = Keystroke('a')
    assert str(ks) == 'a'
    assert ks.is_sequence is False

    # Multi-character sequences
    ks = Keystroke('\x1b[A', code=1, name='KEY_UP')
    assert ks.name == 'KEY_UP'
    assert ks.code == 1
    assert ks.is_sequence is True

    # Legacy control and alt names should still work
    assert Keystroke('\x01').name == 'KEY_CTRL_A'
    assert Keystroke('\x1ba').name == 'KEY_ALT_A'


@pytest.mark.parametrize('sequence,expected_key,expected_modifiers,description', [
    # Basic with tilde
    ('\x1b[27;5;44~', 44, 5, 'Ctrl+, (comma)'),
    # Without tilde
    ('\x1b[27;5;46', 46, 5, 'Ctrl+. (period)'),
    # Various modifier combinations
    ('\x1b[27;3;97~', 97, 3, 'Alt+a'),
    ('\x1b[27;7;98~', 98, 7, 'Ctrl+Alt+b'),
])
def test_match_modify_other_keys(sequence, expected_key, expected_modifiers, description):
    """Test xterm ModifyOtherKeys sequences with various combinations."""
    from blessed.keyboard import _match_modify_other_keys, ModifyOtherKeysEvent

    ks = _match_modify_other_keys(sequence)
    assert ks is not None
    assert ks._mode == -2  # ModifyOtherKeys mode indicator
    assert isinstance(ks._match, ModifyOtherKeysEvent)

    event = ks._match
    assert event.key == expected_key
    assert event.modifiers == expected_modifiers


def test_match_modify_other_keys_non_matching():
    """Test that non-ModifyOtherKeys sequences don't match."""
    from blessed.keyboard import _match_modify_other_keys

    assert _match_modify_other_keys('a') is None
    assert _match_modify_other_keys('\x1b[A') is None  # Regular arrow key
    assert _match_modify_other_keys('\x1b[27;5') is None  # Incomplete
    assert _match_modify_other_keys('\x1b[28;5;44~') is None  # Wrong prefix
    assert _match_modify_other_keys('\x1b]27;5;44~') is None  # Wrong CSI


def test_match_legacy_csi_modifiers_letter_form():
    """Test legacy CSI modifier sequences in letter form."""
    from blessed.keyboard import _match_legacy_csi_modifiers, LegacyCSIKeyEvent

    # ESC [ 1 ; modifiers [ABCDEFHPQS]
    test_cases = [
        ('\x1b[1;3A', 'A', 3, 'KEY_UP'),        # Alt+Up
        ('\x1b[1;5B', 'B', 5, 'KEY_DOWN'),      # Ctrl+Down
        ('\x1b[1;2C', 'C', 2, 'KEY_RIGHT'),     # Shift+Right
        ('\x1b[1;6D', 'D', 6, 'KEY_LEFT'),      # Ctrl+Shift+Left
        ('\x1b[1;3F', 'F', 3, 'KEY_END'),       # Alt+End
        ('\x1b[1;5H', 'H', 5, 'KEY_HOME'),      # Ctrl+Home
        ('\x1b[1;2P', 'P', 2, 'KEY_F1'),        # Shift+F1
        ('\x1b[1;3Q', 'Q', 3, 'KEY_F2'),        # Alt+F2
        ('\x1b[1;5R', 'R', 5, 'KEY_F3'),        # Ctrl+F3
        ('\x1b[1;6S', 'S', 6, 'KEY_F4'),        # Ctrl+Shift+F4
    ]

    for sequence, final_char, expected_mod, expected_key_name in test_cases:
        ks = _match_legacy_csi_modifiers(sequence)
        assert ks is not None
        assert ks._mode == -3  # Legacy CSI mode
        assert isinstance(ks._match, LegacyCSIKeyEvent)

        event = ks._match
        assert event.kind == 'letter'
        assert event.key_id == final_char
        assert event.modifiers == expected_mod

        # Check modifiers are properly detected
        assert ks.modifiers == expected_mod

        # Check that the base keycode is set correctly
        assert ks._code is not None


def test_match_legacy_csi_modifiers_tilde_form():
    """Test legacy CSI modifier sequences in tilde form."""
    from blessed.keyboard import _match_legacy_csi_modifiers, LegacyCSIKeyEvent

    # ESC [ number ; modifiers ~
    test_cases = [
        ('\x1b[2;2~', 2, 2, 'KEY_INSERT'),     # Shift+Insert
        ('\x1b[3;5~', 3, 5, 'KEY_DELETE'),     # Ctrl+Delete
        ('\x1b[5;3~', 5, 3, 'KEY_PGUP'),       # Alt+PageUp
        ('\x1b[6;6~', 6, 6, 'KEY_PGDOWN'),     # Ctrl+Shift+PageDown
        ('\x1b[15;2~', 15, 2, 'KEY_F5'),       # Shift+F5
        ('\x1b[17;5~', 17, 5, 'KEY_F6'),       # Ctrl+F6
        ('\x1b[23;3~', 23, 3, 'KEY_F11'),      # Alt+F11
        ('\x1b[24;7~', 24, 7, 'KEY_F12'),      # Ctrl+Alt+F12
    ]

    for sequence, key_num, expected_mod, expected_key_name in test_cases:
        ks = _match_legacy_csi_modifiers(sequence)
        assert ks is not None
        assert ks._mode == -3  # Legacy CSI mode
        assert isinstance(ks._match, LegacyCSIKeyEvent)

        event = ks._match
        assert event.kind == 'tilde'
        assert event.key_id == key_num
        assert event.modifiers == expected_mod

        # Check modifiers are properly detected
        assert ks.modifiers == expected_mod

        # Check that the base keycode is set correctly
        assert ks._code is not None


def test_match_legacy_csi_modifiers_non_matching():
    """Test that non-legacy-CSI sequences don't match."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # Should not match
    assert _match_legacy_csi_modifiers('a') is None
    assert _match_legacy_csi_modifiers('\x1b[A') is None  # No modifiers
    assert _match_legacy_csi_modifiers('\x1b[2~') is None  # No modifiers
    assert _match_legacy_csi_modifiers('\x1b[1;3') is None  # Incomplete
    assert _match_legacy_csi_modifiers('\x1b[1;3Z') is None  # Unknown final char
    assert _match_legacy_csi_modifiers('\x1b[99;5~') is None  # Unknown tilde number


def test_legacy_csi_modifier_properties():
    """Test that legacy CSI modifier keystrokes have correct modifier properties."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # Test Ctrl+Alt+Right (1 + 2 + 4 = 7)
    ks = _match_legacy_csi_modifiers('\x1b[1;7C')
    assert ks._ctrl is True
    assert ks._alt is True
    assert ks._shift is False
    assert ks._super is False

    # Test Shift+PageUp (1 + 1 = 2)
    ks = _match_legacy_csi_modifiers('\x1b[5;2~')
    assert ks._shift is True
    assert ks._ctrl is False
    assert ks._alt is False


def test_terminal_inkey_modify_other_keys():
    """Test that Terminal.inkey() properly handles xterm ModifyOtherKeys sequences."""
    from blessed import Terminal
    from blessed.keyboard import ModifyOtherKeysEvent

    @as_subprocess
    def child():
        term = Terminal(force_styling=True)

        # Simulate ModifyOtherKeys input by adding to keyboard buffer
        # Ctrl+, (comma)
        modify_sequence = '\x1b[27;5;44~'
        term.ungetch(modify_sequence)

        ks = term.inkey(timeout=0)

        # Should have been parsed as a ModifyOtherKeys sequence
        assert ks is not None
        assert ks == modify_sequence
        assert ks._mode == -2  # ModifyOtherKeys mode indicator
        assert isinstance(ks._match, ModifyOtherKeysEvent)

        # Verify the parsed event data
        event = ks._match
        assert event.key == 44         # comma
        assert event.modifiers == 5    # Ctrl modifier
    child()


def test_terminal_inkey_legacy_csi_modifiers():
    """Test that Terminal.inkey() properly handles legacy CSI modifier sequences."""
    from blessed import Terminal
    from blessed.keyboard import LegacyCSIKeyEvent

    @as_subprocess
    def child():
        term = Terminal(force_styling=True)

        # Simulate legacy CSI modifier input
        # Alt+Up arrow
        legacy_sequence = '\x1b[1;3A'
        term.ungetch(legacy_sequence)

        ks = term.inkey(timeout=0)

        # Should have been parsed as a legacy CSI modifier sequence
        assert ks is not None
        assert ks == legacy_sequence
        assert ks._mode == -3  # Legacy CSI mode indicator
        assert isinstance(ks._match, LegacyCSIKeyEvent)

        # Verify the parsed event data
        event = ks._match
        assert event.kind == 'letter'
        assert event.key_id == 'A'     # Up arrow
        assert event.modifiers == 3    # Alt modifier

        # Check modifier properties work
        assert ks._alt is True
        assert ks._ctrl is False
        assert ks._shift is False

        # Check that base keycode is correct
        assert ks._code == curses.KEY_UP
    child()


def test_terminal_inkey_fallback_to_legacy():
    """Test that legacy sequences still work when new protocols don't match."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        # Regular arrow key sequence (legacy)
        legacy_sequence = '\x1b[A'
        term.ungetch(legacy_sequence)

        ks = term.inkey(timeout=0)

        assert ks == legacy_sequence
        assert ks._code is not None
        assert ks._mode is None or ks._mode >= 0
    child()


def test_terminal_inkey_f3_high_strangeness():
    """Test Terminal.inkey integration with 'F3' modifiers."""
    # "F3" has its issues,
    #
    # a long sordid history, starting with that the vt220 didn't have F1-F4,
    # Xenix and SCO had more than F12,
    # that xterm (curses?) has definitions for up to 64 function keys
    # https://unix.stackexchange.com/questions/479192/why-does-xterm-support-63-function-keys
    # but are just aliases for modifiers of the first 12 or 24,
    # and that xterm simulates Shift+F3 as though it is F15,
    #
    # and well, for whatever reason modifiers on F3 have an entirely different
    # structure than F1,F2, and F4 on many terminals!
    #
    # F1 Function Key
    # ===============
    # F1: '\x1bOP'
    # Shift+F1: '\x1b[1;2P'
    # Alt+F1: '\x1b[1;3P'
    # Ctrl+Alt+Shift+F1: '\x1b[1;8P'
    #
    # F2 Function Key
    # ===============
    # F2: '\x1bOQ'
    # Shift+F2: '\x1b[1;2Q'
    # Ctrl+Alt+Shift+F2: '\x1b[1;6P'

    # F3 Function Key ?!
    # ==================
    # F3: '\x1bOR'
    # Shift+F3: '\x1b[13;2~'
    # Alt+F3: '\x1b[13;2~'
    # Shift+F3: '\x1b[13;2~'
    # Ctrl+Alt+Shift+F3: '\x1b[13;8~'
    #
    from blessed.keyboard import LegacyCSIKeyEvent

    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        # Test a couple of F3 tilde-form variants via Terminal.inkey()
        test_cases = [
            ('\x1b[13;2~', 'Shift+F3', 2, {'shift': True}),
            ('\x1b[13;3~', 'Alt+F3', 3, {'alt': True}),
            ('\x1b[13;6~', 'Ctrl+Shift+F3', 6, {'ctrl': True, 'shift': True}),
            ('\x1b[13;7~', 'Ctrl+Alt+F3', 7, {'ctrl': True, 'alt': True}),
            ('\x1b[13;8~', 'Ctrl+Alt+Shift+F3', 8, {'ctrl': True, 'alt': True, 'shift': True}),
        ]

        for sequence, description, expected_mod, expected_flags in test_cases:
            # Use ungetch to simulate input from ghostty terminal
            term.ungetch(sequence)

            ks = term.inkey(timeout=0)

            # Should have been parsed correctly
            assert ks is not None
            assert ks == sequence
            assert ks._mode == -3  # Legacy CSI mode
            assert isinstance(ks._match, LegacyCSIKeyEvent)

            # Verify the parsed event data
            event = ks._match
            assert event.kind == 'tilde'
            assert event.key_id == 13  # F3 tilde number
            assert event.modifiers == expected_mod

            # Check that it maps to the correct base keycode
            assert ks._code == curses.KEY_F3

            # Check modifier flags
            assert ks.modifiers == expected_mod
            assert ks._shift == expected_flags.get('shift', False)
            assert ks._ctrl == expected_flags.get('ctrl', False)
            assert ks._alt == expected_flags.get('alt', False)

            # Check that dynamic name generation works
            assert ks.name.startswith('KEY_')
            assert ks.name.endswith('_F3')
    child()


def test_is_known_input_prefix_dec_events():
    """Test _is_known_input_prefix correctly identifies DEC event sequences."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        # Test sequences that SHOULD be treated as keyboard prefixes
        keyboard_sequences = [
            '\x1b[200~',           # Bracketed paste start
            '\x1b[200~{test}',     # Partial bracketed paste
            '\x1b[I',              # Focus gained
            '\x1b[O',              # Focus lost
            '\x1b[M',              # Legacy mouse
            '\x1b[<',              # SGR mouse start
            '\x1b[<0;10;20',       # Partial SGR mouse
        ]

        # Test sequences that should NOT be treated as keyboard prefixes (terminal responses)
        terminal_response_sequences = [
            '\x1b[?1$y',           # DEC mode query response (DECCKM disabled)
            '\x1b[?1;1$y',         # DEC mode query response (DECCKM enabled)
            '\x1b[?2004;2$y',      # Bracketed paste mode response (disabled)
            '\x1b[?64;1;2;4;7c',   # Device Attributes response
            '\x1b]10;rgb:ffff/ffff/ffff\x07',  # Foreground color response
            '\x1b[42;10R',         # Cursor position report
            '\x1b[?u',             # Kitty keyboard protocol response start
            '\x1b[?0u',            # Kitty keyboard protocol response
        ]

        # Test keyboard sequences (should return True)
        for seq in keyboard_sequences:
            is_prefix = term._is_known_input_prefix(seq)
            assert is_prefix is True

        # Test terminal response sequences (should return False)
        for seq in terminal_response_sequences:
            is_prefix = term._is_known_input_prefix(seq)
            assert is_prefix is False

    child()


def test_is_known_input_prefix_traditional_sequences():
    """Test _is_known_input_prefix works with traditional keyboard sequences."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        # Test traditional sequences that should be recognized from keymap
        traditional_sequences = [
            '\x1b[A',      # Up arrow
            '\x1b[B',      # Down arrow
            '\x1b[C',      # Right arrow
            '\x1b[D',      # Left arrow
            '\x1b[H',      # Home
            '\x1b[F',      # End
            '\x1b[1~',     # Find
            '\x1b[2~',     # Insert
            '\x1b',        # Just CSI prefix
            '\x1b[',       # CSI sequence start
        ]

        for seq in traditional_sequences:
            is_prefix = term._is_known_input_prefix(seq)
            assert is_prefix is True

    child()


def test_bracketed_paste():
    """Test that bracketed paste works through immediate inkey()."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        # Test complete bracketed paste sequence
        paste_sequence = '\x1b[200~{test}\x1b[201~'
        term.ungetch(paste_sequence)

        ks = term.inkey(timeout=0)

        # Should be recognized as bracketed paste event
        assert ks == paste_sequence
        assert ks._mode == 2004  # BRACKETED_PASTE mode

        # Should be able to extract the pasted text
        event_values = ks.mode_values()
        assert event_values.text == '{test}'

    child()


@pytest.mark.parametrize('sequence,fkey_char,expected_mod,mod_name,expected_flags', [
    ('\x1bO2P', 'P', 2, 'shift', {'shift': True}),
    ('\x1bO3P', 'P', 3, 'alt', {'alt': True}),
    ('\x1bO4P', 'P', 4, 'alt+shift', {'alt': True, 'shift': True}),
    ('\x1bO5P', 'P', 5, 'ctrl', {'ctrl': True}),
    ('\x1bO6P', 'P', 6, 'ctrl+shift', {'ctrl': True, 'shift': True}),
    ('\x1bO7P', 'P', 7, 'ctrl+alt', {'ctrl': True, 'alt': True}),
    ('\x1bO8P', 'P', 8, 'ctrl+alt+shift', {'ctrl': True, 'alt': True, 'shift': True}),
    ('\x1bO2Q', 'Q', 2, 'shift', {'shift': True}),
    ('\x1bO2R', 'R', 2, 'shift', {'shift': True}),
    ('\x1bO2S', 'S', 2, 'shift', {'shift': True}),
])
def test_ss3_fkey_modifier_sequences(sequence, fkey_char, expected_mod, mod_name, expected_flags):
    """Test SS3 F-key modifier sequences for F1-F4."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    ks = _match_legacy_csi_modifiers(sequence)
    assert ks is not None

    # Map F-key chars to codes
    fkey_codes = {'P': curses.KEY_F1, 'Q': curses.KEY_F2, 'R': curses.KEY_F3, 'S': curses.KEY_F4}
    assert ks.code == fkey_codes[fkey_char]
    assert ks.modifiers == expected_mod

    # Check modifier flags
    assert ks._shift == expected_flags.get('shift', False)
    assert ks._alt == expected_flags.get('alt', False)
    assert ks._ctrl == expected_flags.get('ctrl', False)


def test_ss3_fkey_match_properties():
    """Test SS3 match object properties."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    ks = _match_legacy_csi_modifiers('\x1bO6P')
    assert ks is not None
    assert ks._mode == -3  # Legacy CSI modifier mode
    assert ks._match is not None
    assert ks._match.kind == 'ss3-fkey'
    assert ks._match.key_id == 'P'
    assert ks._match.modifiers == 6


@pytest.mark.parametrize('sequence', [
    '\x1bOZ',      # Invalid final character
    '\x1bO2',      # Missing final character
    '\x1bO20P',    # Invalid modifier (too many digits)
    '\x1bO0P',     # Invalid modifier (0)
    '\x1b[2P',     # Wrong escape sequence (CSI instead of SS3)
])
def test_ss3_fkey_invalid_sequences_no_match(sequence):
    """Test that invalid SS3 sequences don't match."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    ks = _match_legacy_csi_modifiers(sequence)
    # Should either return None or not match this specific pattern
    if ks is not None:
        # If it matches, it should be a different pattern (CSI letter form)
        if hasattr(ks._match, 'kind'):
            assert ks._match.kind != 'ss3-fkey'


@pytest.mark.parametrize('sequence,expected_code', [
    ('\x1bOP', curses.KEY_F1),
    ('\x1bOQ', curses.KEY_F2),
    ('\x1bOR', curses.KEY_F3),
    ('\x1bOS', curses.KEY_F4),
])
def test_ss3_fkey_unmodified_backward_compatibility(sequence, expected_code):
    """Test that unmodified F1-F4 sequences are handled by DEFAULT_SEQUENCE_MIXIN."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # The legacy CSI modifier parser should NOT match these
    ks = _match_legacy_csi_modifiers(sequence)
    assert ks is None  # Should be handled by DEFAULT_SEQUENCE_MIXIN instead


@pytest.mark.parametrize('sequence,expected_code,expected_name', [
    ('\x1b[1;2P', curses.KEY_F1, 'KEY_SHIFT_F1'),
    ('\x1b[1;3Q', curses.KEY_F2, 'KEY_ALT_F2'),
    ('\x1b[1;5R', curses.KEY_F3, 'KEY_CTRL_F3'),
    ('\x1b[1;6S', curses.KEY_F4, 'KEY_CTRL_SHIFT_F4'),
])
def test_ss3_csi_letter_form_compatibility(sequence, expected_code, expected_name):
    """Test that CSI letter form F1-F4 sequences still work alongside SS3."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    ks = _match_legacy_csi_modifiers(sequence)
    assert ks is not None
    assert ks.code == expected_code
    assert ks.name == expected_name
    assert ks._match.kind == 'letter'  # Should be letter form, not ss3-fkey


def test_ss3_sequence_matching_order():
    """Test that SS3 F-key parsing doesn't interfere with other patterns."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # This should match the tilde form, not SS3 form
    ks = _match_legacy_csi_modifiers('\x1b[15;2~')  # Shift+F5
    assert ks is not None
    assert ks.code == curses.KEY_F5
    assert ks._match.kind == 'tilde'

    # This should match the SS3 form
    ks = _match_legacy_csi_modifiers('\x1bO2P')  # Shift+F1
    assert ks is not None
    assert ks.code == curses.KEY_F1
    assert ks._match.kind == 'ss3-fkey'


def test_legacy_csi_modifiers_with_event_type_letter_form():
    """Test legacy CSI modifier sequences with event_type in letter form."""
    from blessed.keyboard import _match_legacy_csi_modifiers, LegacyCSIKeyEvent

    # Test letter form with event_type: Shift+F2 key release
    ks = _match_legacy_csi_modifiers('\x1b[1;2:3Q')  # Shift+F2 (Q), release (3)
    assert ks is not None
    assert ks._mode == -3  # Legacy CSI mode
    assert isinstance(ks._match, LegacyCSIKeyEvent)

    event = ks._match
    assert event.kind == 'letter'
    assert event.key_id == 'Q'  # F2 letter
    assert event.modifiers == 2  # Shift modifier
    assert event.event_type == 3  # Release event
    assert ks.code == curses.KEY_F2

    # Test letter form without event_type (should default to 1)
    ks = _match_legacy_csi_modifiers('\x1b[1;5Q')  # Ctrl+F2, no event_type
    assert ks is not None
    event = ks._match
    assert event.event_type == 1  # Default to press event


def test_legacy_csi_modifiers_with_event_type_tilde_form():
    """Test legacy CSI modifier sequences with event_type in tilde form."""
    from blessed.keyboard import _match_legacy_csi_modifiers, LegacyCSIKeyEvent

    # Test tilde form with event_type: F12 key release
    # F12 (24), no extra modifiers (1), release (3)
    ks = _match_legacy_csi_modifiers('\x1b[24;1:3~')
    assert ks is not None
    assert ks._mode == -3  # Legacy CSI mode
    assert isinstance(ks._match, LegacyCSIKeyEvent)

    event = ks._match
    assert event.kind == 'tilde'
    assert event.key_id == 24  # F12 tilde number
    assert event.modifiers == 1  # No extra modifiers
    assert event.event_type == 3  # Release event
    assert ks.code == curses.KEY_F12

    # Test tilde form without event_type (should default to 1)
    ks = _match_legacy_csi_modifiers('\x1b[24;2~')  # Shift+F12, no event_type
    assert ks is not None
    event = ks._match
    assert event.event_type == 1  # Default to press event


def test_terminal_inkey_legacy_csi_with_event_type():
    """Test that Terminal.inkey() properly handles legacy CSI sequences with event_type."""
    @as_subprocess
    def child():
        from blessed import Terminal
        term = Terminal(force_styling=True)

        # Test letter form with event type
        letter_sequence = '\x1b[1;2:3Q'  # Shift+F2 release
        term.ungetch(letter_sequence)
        ks = term.inkey(timeout=0)
        assert ks == letter_sequence
        assert ks._mode == -3  # Legacy CSI mode
        assert ks._match.event_type == 3  # Release event
        assert ks.code == curses.KEY_F2

        # Test tilde form with event type
        tilde_sequence = '\x1b[24;1:3~'  # F12 release
        term.ungetch(tilde_sequence)
        ks = term.inkey(timeout=0)
        assert ks == tilde_sequence
        assert ks._mode == -3  # Legacy CSI mode
        assert ks._match.event_type == 3  # Release event
        assert ks.code == curses.KEY_F12

    child()


def test_legacy_csi_modifiers_event_type_edge_cases():
    """Test edge cases for legacy CSI modifier event_type parsing."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # Test various event types
    event_type_cases = [
        ('\x1b[1;2:1Q', 1, 'press'),    # Explicit press
        ('\x1b[1;2:2Q', 2, 'repeat'),   # Repeat
        ('\x1b[1;2:3Q', 3, 'release'),  # Release
    ]

    for sequence, expected_type, description in event_type_cases:
        ks = _match_legacy_csi_modifiers(sequence)
        assert ks is not None, f"Should match {description} event"
        assert ks._match.event_type == expected_type, f"Wrong event type for {description}"

    # Test that invalid sequences don't match
    invalid_cases = [
        '\x1b[1;2:Q',      # Missing event type number
        '\x1b[1;2:abc~',   # Non-numeric event type
        '\x1b[24;2:~',     # Missing event type in tilde form
    ]

    for invalid_seq in invalid_cases:
        ks = _match_legacy_csi_modifiers(invalid_seq)
        assert ks is None, f"Should not match invalid sequence {invalid_seq!r}"
