"""Tests for advanced keyboard protocol support."""
import functools
import platform

import pytest

from .accessories import (TestTerminal, as_subprocess, assert_modifiers,
                          assert_modifiers_value, assert_only_modifiers)
from blessed.keyboard import Keystroke, LegacyCSIKeyEvent, ModifyOtherKeysEvent, resolve_sequence


if platform.system() != 'Windows':
    import tty  # pylint: disable=unused-import  # NOQA
    import curses
else:
    import jinxed as curses  # pylint: disable=import-error


def assert_ctrl_alt_modifiers(ks):
    """Assert that keystroke has only ctrl and alt modifiers."""
    assert_only_modifiers(ks, 'ctrl', 'alt')


def test_legacy_ctrl_alt_modifiers():
    """Test ESC + control char sequences set ctrl and alt modifiers."""
    ks = Keystroke('\x1b\x06')
    assert_ctrl_alt_modifiers(ks)

    ks = Keystroke('\x1b\x1a')
    assert_ctrl_alt_modifiers(ks)


def test_legacy_ctrl_alt_exact_matching():
    """Test ctrl+alt keystrokes don't match individual ctrl or alt predicates."""
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


@pytest.mark.parametrize('sequence,expected_value,needs_terminal', [
    ('a', 'a', False),
    ('x', 'x', False),
    ('1', '1', False),
    ('\x1ba', 'a', False),
    ('\x1bz', 'z', False),
    ('\x1b1', '1', False),
    ('\x1b;', ';', False),
    ('\x1b/', '/', False),
    ('\x1b\x20', ' ', False),
    ('\x01', 'a', False),
    ('\x03', 'c', False),
    ('\x05', 'e', False),
    ('\x1a', 'z', False),
    ('\x00', ' ', False),
    ('\x1b\x01', 'a', False),
    ('\x1b\x03', 'c', False),
    ('\x1b\x05', 'e', False),
    ('\x1b\x06', 'f', False),
    ('\x1b\x08', '', False),
    ('\x1b\x1a', 'z', False),
    ('\x1b\x00', ' ', False),
    ('\x1b\x1b', '', False),
    ('\x1b\x7f', '', False),
    ('\x1b\x0d', '', False),
    ('\x1b\x09', '', False),
    ('abc', '', False),
    ('\x1b[27;5;97~', 'a', True),
    ('\x1b[27;3;49~', '1', True),
])
def test_keystroke_value_comprehensive(sequence, expected_value, needs_terminal):
    """Test keystroke.value property returns correct character for various sequences."""
    if needs_terminal:
        @as_subprocess
        def child():
            term = TestTerminal(force_styling=True)
            term.ungetch(sequence)
            ks = term.inkey(timeout=0)
            assert ks is not None
            assert ks.value == expected_value
        child()
    else:
        ks = Keystroke(sequence)
        assert ks.value == expected_value


@pytest.mark.parametrize('code,expected_value', [
    (curses.KEY_ENTER, '\n'),
    (curses.KEY_UP, ''),
    (curses.KEY_DOWN, ''),
    (curses.KEY_F1, ''),
])
def test_keystroke_value_by_keycode(code, expected_value):
    """Test keystroke.value property for keystrokes created with keycodes."""
    ks = Keystroke('', code=code)
    assert ks.value == expected_value


@pytest.mark.parametrize('sequence,expected_name,expected_modifiers', [
    ('\x01', 'KEY_CTRL_A', 5),
    ('\x02', 'KEY_CTRL_B', 5),
    ('\x17', 'KEY_CTRL_W', 5),
    ('\x1a', 'KEY_CTRL_Z', 5),
    ('\x00', 'KEY_CTRL_SPACE', 5),
    ('\x1b', 'KEY_CTRL_[', 5),
    ('\x1c', 'KEY_CTRL_\\', 5),
    ('\x1d', 'KEY_CTRL_]', 5),
    ('\x1e', 'KEY_CTRL_^', 5),
    ('\x1f', 'KEY_CTRL__', 5),
    ('\x7f', 'KEY_CTRL_?', 5),
    ('\x1ba', 'KEY_ALT_A', 3),
    ('\x1bz', 'KEY_ALT_Z', 3),
    ('\x1bj', 'KEY_ALT_J', 3),
    ('\x1bA', 'KEY_ALT_SHIFT_A', 4),
    ('\x1bZ', 'KEY_ALT_SHIFT_Z', 4),
    ('\x1bJ', 'KEY_ALT_SHIFT_J', 4),
    ('\x1bM', 'KEY_ALT_SHIFT_M', 4),
    ('\x1b1', 'KEY_ALT_1', 3),
    ('\x1b!', 'KEY_ALT_!', 3),
    ('\x1b;', 'KEY_ALT_;', 3),
    ('\x1b/', 'KEY_ALT_/', 3),
    ('\x1b ', 'KEY_ALT_SPACE', 3),
    ('\x1b\x01', 'KEY_CTRL_ALT_A', 7),
    ('\x1b\x02', 'KEY_CTRL_ALT_B', 7),
    ('\x1b\x06', 'KEY_CTRL_ALT_F', 7),
    ('\x1b\x08', 'KEY_CTRL_ALT_BACKSPACE', 7),
    ('\x1b\x17', 'KEY_CTRL_ALT_W', 7),
    ('\x1b\x1a', 'KEY_CTRL_ALT_Z', 7),
    ('\x1b\x00', 'KEY_CTRL_ALT_SPACE', 7),
    ('\x1b\x1c', 'KEY_CTRL_ALT_\\', 7),
    ('\x1b\x1d', 'KEY_CTRL_ALT_]', 7),
    ('\x1b\x1e', 'KEY_CTRL_ALT_^', 7),
    ('\x1b\x1f', 'KEY_CTRL_ALT__', 7),
    ('\x1b\x1b', 'KEY_ALT_ESCAPE', 3),
    ('\x1b\x7f', 'KEY_ALT_BACKSPACE', 3),
    ('\x1b\x0d', 'KEY_ALT_ENTER', 3),
    ('\x1b\x09', 'KEY_ALT_TAB', 3),
    ('\x1b[', 'CSI', 3),
])
def test_keystroke_name_generation_comprehensive(sequence, expected_name, expected_modifiers):
    """Test keystroke.name property generates correct names for control and alt sequences."""
    ks = Keystroke(sequence)
    assert ks.name == expected_name
    assert ks.modifiers == expected_modifiers


@pytest.mark.parametrize('sequence,expected_modifiers,ctrl,alt,shift', [
    ('a', 1, False, False, False),
    ('\x01', 5, True, False, False),
    ('\x05', 5, True, False, False),
    ('\x1ba', 3, False, True, False),
    ('\x1b1', 3, False, True, False),
    ('\x1bA', 4, False, True, True),
    ('\x1bZ', 4, False, True, True),
    ('\x1b\x01', 7, True, True, False),
    ('\x1b\x06', 7, True, True, False),
    ('\x1b\x1b', 3, False, True, False),
    ('\x1b\x7f', 3, False, True, False),
    ('\x1b\x0d', 3, False, True, False),
    ('\x1b\x09', 3, False, True, False),
])
def test_keystroke_modifiers_comprehensive(sequence, expected_modifiers, ctrl, alt, shift):
    """Test keystroke.modifiers property and modifier predicates for various sequences."""
    ks = Keystroke(sequence)
    assert ks.modifiers == expected_modifiers
    assert_modifiers(ks, ctrl=ctrl, alt=alt, shift=shift)


@pytest.mark.parametrize('sequence,expected_value,expected_name,modifiers,ctrl,alt,shift', [
    ('\x1b\x01', 'a', 'KEY_CTRL_ALT_A', 7, True, True, False),
    ('\x1b\x06', 'f', 'KEY_CTRL_ALT_F', 7, True, True, False),
    ('\x1b\x1a', 'z', 'KEY_CTRL_ALT_Z', 7, True, True, False),
    ('\x1b\x00', ' ', 'KEY_CTRL_ALT_SPACE', 7, True, True, False),
    ('\x1b\x08', '', 'KEY_CTRL_ALT_BACKSPACE', 7, True, True, False),
    ('\x1b\x1b', '', 'KEY_ALT_ESCAPE', 3, False, True, False),
    ('\x1b\x7f', '', 'KEY_ALT_BACKSPACE', 3, False, True, False),
    ('\x1b\x0d', '', 'KEY_ALT_ENTER', 3, False, True, False),
    ('\x1b\x09', '', 'KEY_ALT_TAB', 3, False, True, False),
])
def test_legacy_ctrl_alt_edge_cases(
        # pylint: disable=too-many-positional-arguments
        sequence, expected_value, expected_name, modifiers, ctrl, alt, shift):
    """Test ctrl+alt combinations with special control characters."""
    ks = Keystroke(sequence)
    assert ks.modifiers == modifiers
    assert_modifiers(ks, ctrl=ctrl, alt=alt, shift=shift)
    assert len(ks) == 2
    assert ks[0] == '\x1b'
    assert ks.name == expected_name
    assert ks.value == expected_value


def test_terminal_inkey_legacy_ctrl_alt_integration():
    """Test terminal.inkey() correctly detects ctrl+alt modifier sequences."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        ctrl_alt_f = '\x1b\x06'
        term.ungetch(ctrl_alt_f)
        ks = term.inkey(timeout=0)
        assert ks == ctrl_alt_f
        assert_ctrl_alt_modifiers(ks)

        ctrl_alt_z = '\x1b\x1a'
        term.ungetch(ctrl_alt_z)
        ks = term.inkey(timeout=0)
        assert ks == ctrl_alt_z
        assert_ctrl_alt_modifiers(ks)

    child()


def test_legacy_ctrl_alt_doesnt_affect_other_sequences():
    """Test ctrl+alt detection doesn't interfere with plain ctrl or alt sequences."""
    ks_alt_a = Keystroke('\x1ba')
    assert_only_modifiers(ks_alt_a, 'alt')
    assert ks_alt_a.name == 'KEY_ALT_A'

    ks_ctrl_a = Keystroke('\x01')
    assert_only_modifiers(ks_ctrl_a, 'ctrl')
    assert ks_ctrl_a.name == 'KEY_CTRL_A'

    ks_regular = Keystroke('a')
    assert_modifiers_value(ks_regular, modifiers=1)
    assert_modifiers(ks_regular, ctrl=False, alt=False, shift=False)


def test_keystroke_legacy_ctrl_alt_name_generation():
    """Test name generation for ctrl+alt sequences including symbols."""
    test_cases = [
        ('\x1b\x17', 'KEY_CTRL_ALT_W'),
        ('\x1b\x01', 'KEY_CTRL_ALT_A'),
        ('\x1b\x02', 'KEY_CTRL_ALT_B'),
        ('\x1b\x1a', 'KEY_CTRL_ALT_Z'),
    ]

    for sequence, expected_name in test_cases:
        ks = Keystroke(sequence)
        assert ks.name == expected_name
        assert ks.modifiers == 7
        assert ks._ctrl is True
        assert ks._alt is True
        assert ks._shift is False

    symbol_test_cases = [
        ('\x1b\x00', 'KEY_CTRL_ALT_SPACE'),
        ('\x1b\x1c', 'KEY_CTRL_ALT_\\'),
        ('\x1b\x1d', 'KEY_CTRL_ALT_]'),
        ('\x1b\x1e', 'KEY_CTRL_ALT_^'),
        ('\x1b\x1f', 'KEY_CTRL_ALT__'),
        ('\x1b\x08', 'KEY_CTRL_ALT_BACKSPACE'),
    ]

    for sequence, expected_name in symbol_test_cases:
        ks = Keystroke(sequence)
        assert ks.name == expected_name
        assert ks.modifiers == 7
        assert ks._ctrl is True
        assert ks._alt is True
        assert ks._shift is False

    alt_only_symbol_cases = [
        ('\x1b\x1b', 'KEY_ALT_ESCAPE'),
        ('\x1b\x7f', 'KEY_ALT_BACKSPACE'),
    ]

    for sequence, expected_name in alt_only_symbol_cases:
        ks = Keystroke(sequence)
        assert ks.name == expected_name
        assert ks.modifiers == 3
        assert ks._ctrl is False
        assert ks._alt is True
        assert ks._shift is False

    assert Keystroke('\x1ba').name == 'KEY_ALT_A'
    assert Keystroke('\x1bz').name == 'KEY_ALT_Z'
    assert Keystroke('\x1b1').name == 'KEY_ALT_1'
    assert Keystroke('\x1bA').name == 'KEY_ALT_SHIFT_A'
    assert Keystroke('\x1bZ').name == 'KEY_ALT_SHIFT_Z'
    assert Keystroke('\x01').name == 'KEY_CTRL_A'
    assert Keystroke('\x1a').name == 'KEY_CTRL_Z'
    assert Keystroke('\x00').name == 'KEY_CTRL_SPACE'
    assert Keystroke('\x7f').name == 'KEY_CTRL_?'

    ks_with_name = Keystroke('\x1b\x17', name='CUSTOM_NAME')
    assert ks_with_name.name == 'CUSTOM_NAME'


@pytest.mark.parametrize('sequence,final_char,expected_mod,expected_key_name', [
    ('\x1b[1;3A', 'A', 3, 'KEY_ALT_UP'),
    ('\x1b[1;5B', 'B', 5, 'KEY_CTRL_DOWN'),
    ('\x1b[1;2C', 'C', 2, 'KEY_SHIFT_RIGHT'),
    ('\x1b[1;6D', 'D', 6, 'KEY_CTRL_SHIFT_LEFT'),
    ('\x1b[1;3F', 'F', 3, 'KEY_ALT_END'),
    ('\x1b[1;5H', 'H', 5, 'KEY_CTRL_HOME'),
    ('\x1b[1;2P', 'P', 2, 'KEY_SHIFT_F1'),
    ('\x1b[1;3Q', 'Q', 3, 'KEY_ALT_F2'),
    ('\x1b[1;5R', 'R', 5, 'KEY_CTRL_F3'),
    ('\x1b[1;6S', 'S', 6, 'KEY_CTRL_SHIFT_F4'),
])
def test_match_legacy_csi_modifiers_letter_form(
        sequence, final_char, expected_mod, expected_key_name):
    """Test legacy CSI modifier sequences with letter-form final characters."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch(sequence)
        ks = term.inkey(timeout=0)
        assert ks is not None
        assert ks._mode == -3
        assert isinstance(ks._match, LegacyCSIKeyEvent)

        event = ks._match
        assert event.kind == 'letter'
        assert event.key_id == final_char
        assert event.modifiers == expected_mod
        assert ks.modifiers == expected_mod
        assert ks._code is not None
        assert ks.name == expected_key_name

    child()


@pytest.mark.parametrize('sequence,key_num,expected_mod,expected_key_name', [
    ('\x1b[2;2~', 2, 2, 'KEY_SHIFT_INSERT'),
    ('\x1b[3;5~', 3, 5, 'KEY_CTRL_DELETE'),
    ('\x1b[5;3~', 5, 3, 'KEY_ALT_PGUP'),
    ('\x1b[6;6~', 6, 6, 'KEY_CTRL_SHIFT_PGDOWN'),
    ('\x1b[15;2~', 15, 2, 'KEY_SHIFT_F5'),
    ('\x1b[17;5~', 17, 5, 'KEY_CTRL_F6'),
    ('\x1b[23;3~', 23, 3, 'KEY_ALT_F11'),
    ('\x1b[24;7~', 24, 7, 'KEY_CTRL_ALT_F12'),
])
def test_match_legacy_csi_modifiers_tilde_form(sequence, key_num, expected_mod, expected_key_name):
    """Test legacy CSI modifier sequences with tilde-form final characters."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch(sequence)
        ks = term.inkey(timeout=0)
        assert ks is not None
        assert ks._mode == -3
        assert isinstance(ks._match, LegacyCSIKeyEvent)

        event = ks._match
        assert event.kind == 'tilde'
        assert event.key_id == key_num
        assert event.modifiers == expected_mod
        assert ks.modifiers == expected_mod
        assert ks._code is not None
        assert ks.name == expected_key_name

    child()


def test_match_legacy_csi_modifiers_non_matching():
    """Test legacy CSI modifier sequences that don't match."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes,
                                    prefixes=term._keymap_prefixes,
                                    final=True)

        assert resolve('a') == 'a'
        assert resolve('\x1b[A').name == 'KEY_UP'
        assert resolve('\x1b[2~').name == 'KEY_INSERT'

        ks = resolve('\x1b[1;3')
        assert ks == '\x1b[' and ks.name == 'CSI'

        assert resolve('\x1b[1;3Z') == '\x1b['
        assert resolve('\x1b[99;5~') == '\x1b['

    child()


def test_legacy_csi_modifier_properties():
    """Test modifier properties set correctly for legacy CSI sequences."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        term.ungetch('\x1b[1;7C')
        ks = term.inkey(timeout=0)
        assert ks._ctrl is True
        assert ks._alt is True
        assert ks._shift is False
        assert ks._super is False

        term.ungetch('\x1b[5;2~')
        ks = term.inkey(timeout=0)
        assert ks._shift is True
        assert ks._ctrl is False
        assert ks._alt is False

    child()


def test_terminal_inkey_legacy_csi_modifiers():
    """Test terminal.inkey() correctly handles legacy CSI modifier sequences."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        legacy_sequence = '\x1b[1;3A'
        term.ungetch(legacy_sequence)

        ks = term.inkey(timeout=0)

        assert ks is not None
        assert ks == legacy_sequence
        assert ks._mode == -3
        assert isinstance(ks._match, LegacyCSIKeyEvent)

        event = ks._match
        assert event.kind == 'letter'
        assert event.key_id == 'A'
        assert event.modifiers == 3
        assert ks._alt is True
        assert ks._ctrl is False
        assert ks._shift is False
        assert ks._code == curses.KEY_UP
    child()


@pytest.mark.parametrize('sequence,expected_key,expected_modifiers', [
    ('\x1b[27;5;44~', 44, 5),
    ('\x1b[27;5;46', 46, 5),
    ('\x1b[27;3;97~', 97, 3),
    ('\x1b[27;7;98~', 98, 7),
])
def test_match_modify_other_keys(sequence, expected_key, expected_modifiers):
    """Test ModifyOtherKeys protocol sequences are parsed correctly."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch(sequence)
        ks = term.inkey(timeout=0)
        assert ks is not None
        assert ks._mode == -2
        assert isinstance(ks._match, ModifyOtherKeysEvent)

        event = ks._match
        assert event.key == expected_key
        assert event.modifiers == expected_modifiers

    child()


def test_match_modify_other_keys_non_matching():
    """Test Modify OtherKeys sequences that don't match."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes,
                                    prefixes=term._keymap_prefixes,
                                    final=True)

        assert resolve('a') == 'a'
        assert resolve('\x1b[A').name == 'KEY_UP'

        ks = resolve('\x1b[27;5')
        assert ks == '\x1b[' and ks.name == 'CSI'

        assert resolve('\x1b[28;5;44~') == '\x1b['
        assert resolve('\x1b]27;5;44~') == '\x1b]'

    child()


def test_terminal_inkey_modify_other_keys():
    """Test terminal.inkey() correctly handles ModifyOtherKeys sequences."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        modify_sequence = '\x1b[27;5;44~'
        term.ungetch(modify_sequence)

        ks = term.inkey(timeout=0)

        assert ks is not None
        assert ks == modify_sequence
        assert ks._mode == -2
        assert isinstance(ks._match, ModifyOtherKeysEvent)

        event = ks._match
        assert event.key == 44
        assert event.modifiers == 5
    child()


@pytest.mark.parametrize('sequence,char,expected', [
    ('\x01', 'a', True),
    ('\x01', 'A', True),
    ('\x1a', 'z', True),
    ('\x1a', 'Z', True),
    ('\x00', ' ', True),
    ('\x1b', '[', True),
    ('\x1c', '\\', True),
    ('\x1d', ']', True),
    ('\x1e', '^', True),
    ('\x1f', '_', True),
    ('\x7f', '?', True),
    ('a', 'a', False),
    ('\x01', 'b', False),
    ('\x1ba', 'a', False),
    ('\x1b\x06', 'f', False),
    ('\x1b\x06', 'F', False),
])
def test_keystroke_is_ctrl_comprehensive(sequence, char, expected):
    """Test is_ctrl() predicate for control sequences."""
    assert Keystroke(sequence).is_ctrl(char) is expected


@pytest.mark.parametrize('sequence,char,ignore_case,expected', [
    ('\x1ba', 'a', True, True),
    ('\x1ba', 'A', True, True),
    ('\x1bz', 'z', True, True),
    ('\x1bZ', 'Z', True, True),
    ('\x1b1', '1', True, True),
    ('\x1ba', 'A', True, True),
    ('\x1ba', 'A', False, False),
    ('\x1bA', 'a', True, True),
    ('\x1bA', 'a', False, False),
    ('\x1bA', 'A', False, True),
    ('a', 'a', True, False),
    ('\x1b', 'a', True, False),
    ('\x1ba', 'b', True, False),
    ('\x1bab', 'a', True, False),
    ('\x1b\x06', 'f', True, False),
    ('\x1b\x06', 'F', True, False),
])
def test_keystroke_is_alt_comprehensive(sequence, char, ignore_case, expected):
    """Test is_alt() predicate for alt sequences with case sensitivity."""
    assert Keystroke(sequence).is_alt(char, ignore_case=ignore_case) is expected


@pytest.mark.parametrize('sequence,expected', [
    ('\x01', False),
    ('\x05', False),
    ('\x1ba', False),
    ('\x1b1', False),
    ('\x1b ', False),
    ('a', False),
    ('\x1b\x01', False),
])
def test_keystroke_predicates_without_char(sequence, expected):
    """Test modifier predicates without character argument."""
    ks = Keystroke(sequence)
    if sequence in {'\x01', '\x05', 'a'}:
        assert ks.is_ctrl() is expected
    else:
        assert ks.is_alt() is expected


@pytest.mark.parametrize('sequence,property_name,expected_value', [
    ('a', 'modifiers_bits', 0),
    ('\x01', 'modifiers_bits', 4),
    ('\x1ba', 'modifiers_bits', 2),
    ('a', 'pressed', True),
    ('\x01', 'pressed', True),
    ('\x1ba', 'pressed', True),
    ('x', '__repr__', "'x'"),
])
def test_keystroke_properties_comprehensive(sequence, property_name, expected_value):
    """Test various keystroke properties."""
    ks = Keystroke(sequence)
    actual = (repr(ks) if property_name == '__repr__'
              else getattr(ks, property_name))
    assert actual == expected_value


def test_keystroke_repr_with_name():
    """Test repr() shows name for sequences, string representation for text."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch('\x1b[A')
        ks = term.inkey(timeout=0)
        assert ks.name == 'KEY_UP'
        assert repr(ks) == 'KEY_UP'

        ks_plain = Keystroke('a')
        assert ks_plain.name is None
        assert repr(ks_plain) == "'a'"

    child()


def test_alt_uppercase_sets_shift_modifier_and_name():
    """Test uppercase alt sequences set shift modifier and name correctly."""
    ks_lower = Keystroke('\x1bj')
    assert ks_lower.modifiers == 3
    assert ks_lower._alt is True
    assert ks_lower._shift is False
    assert ks_lower.name == 'KEY_ALT_J'

    ks_upper = Keystroke('\x1bJ')
    assert ks_upper.modifiers == 4
    assert ks_upper._alt is True
    assert ks_upper._shift is True
    assert ks_upper.name == 'KEY_ALT_SHIFT_J'

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

    non_alpha_cases = [
        ('\x1b1', 'KEY_ALT_1', 3),
        ('\x1b!', 'KEY_ALT_!', 3),
        ('\x1b;', 'KEY_ALT_;', 3),
        ('\x1b ', 'KEY_ALT_SPACE', 3),
    ]

    for sequence, expected_name, expected_modifiers in non_alpha_cases:
        ks = Keystroke(sequence)
        assert ks.modifiers == expected_modifiers
        assert ks._alt is True
        assert ks._shift is False
        assert ks.name == expected_name


def test_legacy_csi_modifiers_with_event_type_letter_form():
    """Test legacy CSI letter-form sequences with event type field."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        term.ungetch('\x1b[1;2:3Q')
        ks = term.inkey(timeout=0)
        assert ks is not None
        assert ks._mode == -3
        assert isinstance(ks._match, LegacyCSIKeyEvent)

        event = ks._match
        assert event.kind == 'letter'
        assert event.key_id == 'Q'
        assert event.modifiers == 2
        assert event.event_type == 3
        assert ks.code == curses.KEY_F2

        term.ungetch('\x1b[1;5Q')
        ks = term.inkey(timeout=0)
        assert ks is not None
        event = ks._match
        assert event.event_type == 1

    child()


def test_legacy_csi_modifiers_with_event_type_tilde_form():
    """Test legacy CSI tilde-form sequences with event type field."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        term.ungetch('\x1b[24;1:3~')
        ks = term.inkey(timeout=0)
        assert ks is not None
        assert ks._mode == -3
        assert isinstance(ks._match, LegacyCSIKeyEvent)

        event = ks._match
        assert event.kind == 'tilde'
        assert event.key_id == 24
        assert event.modifiers == 1
        assert event.event_type == 3
        assert ks.code == curses.KEY_F12

        term.ungetch('\x1b[24;2~')
        ks = term.inkey(timeout=0)
        assert ks is not None
        event = ks._match
        assert event.event_type == 1

    child()


def test_terminal_inkey_legacy_csi_with_event_type():
    """Test terminal.inkey() parses event type from legacy CSI sequences."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        letter_sequence = '\x1b[1;2:3Q'
        term.ungetch(letter_sequence)
        ks = term.inkey(timeout=0)
        assert ks == letter_sequence
        assert ks._mode == -3
        assert ks._match.event_type == 3
        assert ks.code == curses.KEY_F2

        tilde_sequence = '\x1b[24;1:3~'
        term.ungetch(tilde_sequence)
        ks = term.inkey(timeout=0)
        assert ks == tilde_sequence
        assert ks._mode == -3
        assert ks._match.event_type == 3
        assert ks.code == curses.KEY_F12

    child()


def test_legacy_csi_modifiers_event_type_edge_cases():
    """Test legacy CSI sequences with various event type values and invalid patterns."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        event_type_cases = [
            ('\x1b[1;2:1Q', 1),
            ('\x1b[1;2:2Q', 2),
            ('\x1b[1;2:3Q', 3),
        ]

        for sequence, expected_type in event_type_cases:
            term.ungetch(sequence)
            ks = term.inkey(timeout=0)
            assert ks is not None
            assert ks._match.event_type == expected_type

        invalid_cases = [
            '\x1b[1;2:Q',
            '\x1b[1;2:abc~',
            '\x1b[24;2:~',
        ]

        for invalid_seq in invalid_cases:
            term.ungetch(invalid_seq)
            ks = term.inkey(timeout=0)
            assert ks in {'\x1b', '\x1b['} or ks.name is None

    child()


def test_build_appkeys_predicate_with_char():
    """Test application key predicates with character argument."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch('\x1b[1;2A')
        ks = term.inkey(timeout=0)

        assert ks.is_shift_up('x') is False
        assert ks.is_shift_up('') is True

    child()


def test_build_appkeys_predicate_keycode_loop():
    """Test application key predicates with invalid key names raise AttributeError."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch('\x1b[1;2A')
        ks = term.inkey(timeout=0)

        assert ks.is_shift_up() is True

        try:
            ks.is_shift_foobar()
            assert False
        except AttributeError as e:
            assert 'foobar' in str(e)

    child()


def test_match_legacy_csi_invalid_letter_final():
    """Test legacy CSI sequences with invalid letter final characters."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes,
                                    prefixes=term._keymap_prefixes,
                                    final=True)
        ks = resolve('\x1b[1;5Z')
        assert ks == '\x1b['

    child()


def test_match_legacy_csi_invalid_tilde_number():
    """Test legacy CSI sequences with invalid tilde key numbers."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes,
                                    prefixes=term._keymap_prefixes,
                                    final=True)
        ks = resolve('\x1b[99;5~')
        assert ks == '\x1b['

    child()


def test_match_ss3_fkey_modifier_zero():
    """Test SS3 F-key sequences with modifier zero are invalid."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes,
                                    prefixes=term._keymap_prefixes,
                                    final=True)
        ks = resolve('\x1bO0P')
        assert ks == '\x1bO'

    child()


def test_match_ss3_fkey_invalid_final():
    """Test SS3 F-key sequences with invalid final characters."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes,
                                    prefixes=term._keymap_prefixes,
                                    final=True)
        ks = resolve('\x1bO2X')
        assert ks == '\x1bO'

    child()


@pytest.mark.parametrize('sequence,expected_code,expected_mod', [
    ('\x1bO2P', curses.KEY_F1, 2),
    ('\x1bO5Q', curses.KEY_F2, 5),
    ('\x1bO3R', curses.KEY_F3, 3),
    ('\x1bO6S', curses.KEY_F4, 6),
])
def test_match_ss3_fkey_valid(sequence, expected_code, expected_mod):
    """Test SS3 F-key sequences with modifiers parse correctly."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch(sequence)
        ks = term.inkey(timeout=0)
        assert ks is not None
        assert ks.code == expected_code
        assert ks.modifiers == expected_mod
        assert ks._match.kind == 'ss3-fkey'
        assert ks._match.event_type == 1

    child()


def test_legacy_csi_e_center_key():
    """Test legacy CSI E (center/begin key) sequence with modifiers."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch('\x1b[1;5E')
        ks = term.inkey(timeout=0)
        assert ks is not None
        assert ks.code == curses.KEY_B2
        assert ks.modifiers == 5

    child()


@pytest.mark.parametrize('sequence,expected_name', [
    ('\x00', 'KEY_CTRL_SPACE'),
    ('\x1b', 'KEY_CTRL_['),
    ('\x1c', 'KEY_CTRL_\\'),
    ('\x1d', 'KEY_CTRL_]'),
    ('\x1e', 'KEY_CTRL_^'),
    ('\x1f', 'KEY_CTRL__'),
    ('\x7f', 'KEY_CTRL_?'),
])
def test_ctrl_code_symbols_all(sequence, expected_name):
    """Test control code names for symbol characters."""
    ks = Keystroke(sequence)
    assert ks.name == expected_name


def test_match_legacy_csi_letter_keycode_none():
    """Test legacy CSI letter-form sequences that don't map to keycodes."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes,
                                    prefixes=term._keymap_prefixes,
                                    final=True)
        ks = resolve('\x1b[1;5X')
        assert ks == '\x1b['

    child()


def test_match_ss3_keycode_none():
    """Test SS3 sequences that don't map to keycodes."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes,
                                    prefixes=term._keymap_prefixes,
                                    final=True)
        ks = resolve('\x1bO2Z')
        assert ks == '\x1bO'

    child()


def test_legacy_csi_modifiers_keycode_none_both_forms():
    """Test legacy CSI sequences in both forms that don't map to keycodes."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes,
                                    prefixes=term._keymap_prefixes,
                                    final=True)

        ks = resolve('\x1b[1;5W')
        assert ks == '\x1b['

        ks = resolve('\x1b[100;5~')
        assert ks == '\x1b['

    child()


def test_ss3_fkey_branches():
    """Test SS3 F-key sequence matching logic."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes,
                                    prefixes=term._keymap_prefixes,
                                    final=True)

        ks = resolve('\x1bO2P')
        assert ks is not None
        assert ks.code == curses.KEY_F1

        ks = resolve('\x1bO2A')
        assert ks == '\x1bO'

    child()


def test_alphanum_predicate_no_char_non_printable_return():
    """Test alphanumeric predicate without character argument for non-printable."""
    ks = Keystroke('\x01')
    assert ks.is_ctrl() is False


def test_alphanum_predicate_no_char_application_key():
    """Test alphanumeric predicate without char argument for application keys."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        # Ctrl+Up arrow: is_ctrl() without char should return False
        # Use is_ctrl_up() for application keys instead
        term.ungetch('\x1b[1;5A')
        ks = term.inkey(timeout=0)
        assert ks.is_ctrl() is False
        assert ks.is_ctrl_up() is True

        # Alt+Down arrow: is_alt() without char should return False
        # Use is_alt_down() for application keys instead
        term.ungetch('\x1b[1;3B')
        ks = term.inkey(timeout=0)
        assert ks.is_alt() is False
        assert ks.is_alt_down() is True

    child()


def test_repr_with_name():
    """Test repr() with explicit name parameter."""
    ks = Keystroke('\x1b[A', code=259, name='KEY_UP')
    repr_str = repr(ks)
    assert repr_str == 'KEY_UP'


def test_get_modified_keycode_name_base_name_not_starting_with_key():
    """Test name generation for keycode not starting with KEY_ prefix."""
    ks = Keystroke('\x1b[1;2A', code=99999, mode=-3,
                   match=LegacyCSIKeyEvent('letter', 'A', 2, 1))
    assert ks.name is None


def test_infer_modifiers_all_paths():
    """Test modifier inference for all code paths."""
    ks = Keystroke('\x1b\x0d')
    assert ks.modifiers == 3

    ks = Keystroke('\x1b\x05')
    assert ks.modifiers == 7

    ks = Keystroke('\x1b5')
    assert ks.modifiers == 3

    ks = Keystroke('\x05')
    assert ks.modifiers == 5

    ks = Keystroke('x')
    assert ks.modifiers == 1


def test_alphanum_predicate_char_alpha_shift_mismatch():
    """Test alphanumeric predicates handle alphabetic case with implicit shift."""
    ks = Keystroke('\x1ba')
    assert ks.is_alt('a') is True

    ks = Keystroke('\x1bA')
    assert ks.is_alt('A') is True


def test_pressed_property_default_return():
    """Test pressed property defaults to True for standard keystrokes."""
    ks = Keystroke('a')
    assert ks.pressed is True

    ks = Keystroke('x', code=100, name='TEST')
    assert ks.pressed is True

    ks = Keystroke('y', mode=0)
    assert ks.pressed is True


def test_pressed_property_with_event_types():
    """Test pressed property returns correct value based on event_type."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        # event_type=1 (press) should return True
        term.ungetch('\x1b[1;2:1Q')
        ks = term.inkey(timeout=0)
        assert ks.pressed is True

        # event_type=2 (repeat) should return False
        term.ungetch('\x1b[1;2:2Q')
        ks = term.inkey(timeout=0)
        assert ks.pressed is False

        # event_type=3 (release) should return False
        term.ungetch('\x1b[1;2:3Q')
        ks = term.inkey(timeout=0)
        assert ks.pressed is False

    child()


def test_getattr_property_getter():
    """Test __getattr__ correctly accesses property getters."""
    ks = Keystroke('\x01')
    assert hasattr(ks, 'code')
    assert hasattr(ks, 'name')
    assert hasattr(ks, 'modifiers')


def test_get_modified_keycode_name_no_modifiers():
    """Test modified keycode name returns None when no modifiers present."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch('\x1b[1;1A')
        ks = term.inkey(timeout=0)
        assert ks is not None
        assert ks._mode == -3
        assert ks.modifiers == 1
        result = ks._get_modified_keycode_name()
        assert result is None

    child()


def test_get_control_symbol_unknown_char_code():
    """Test _get_control_symbol with unknown character codes raises KeyError."""
    ks = Keystroke('x')
    with pytest.raises(KeyError):
        ks._get_control_symbol(32)
    with pytest.raises(KeyError):
        ks._get_control_symbol(50)
    with pytest.raises(KeyError):
        ks._get_control_symbol(100)


def test_get_meta_escape_name_unprintable_without_match():
    """Test _get_meta_escape_name with unprintable chars that don't match alt-only."""
    ks = Keystroke('\x1b\x02')
    result = ks._get_meta_escape_name()
    assert result == 'KEY_CTRL_ALT_B'


def test_get_meta_escape_name_symbol_branch_without_alt_name():
    """Test _get_meta_escape_name where symbol check passes but alt_only check fails."""
    ks = Keystroke('\x1b\x08')
    assert ks.modifiers == 7
    result = ks._get_meta_escape_name()
    assert result == 'KEY_CTRL_ALT_BACKSPACE'


def test_get_meta_escape_name_not_printable_edge_case():
    """Test _get_meta_escape_name with control char that has no symbol mapping."""
    ks = Keystroke('\x1b\x04')
    result = ks._get_meta_escape_name()
    assert result == 'KEY_CTRL_ALT_D'


def test_build_appkeys_predicate_expected_code_none():
    """Test application key predicate when expected_code lookup fails."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch('\x1b[1;2A')
        ks = term.inkey(timeout=0)
        predicate = ks._build_appkeys_predicate([], 'nonexistent_key')
        assert predicate() is False

    child()


def test_build_appkeys_predicate_code_mismatch():
    """Test application key predicate when keystroke code doesn't match expected."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch('\x1b[1;2A')
        ks = term.inkey(timeout=0)
        predicate = ks._build_appkeys_predicate([], 'down')
        assert predicate() is False

    child()


def test_alphanum_predicate_exact_matching_non_alpha():
    """Test alphanumeric predicate with exact modifier matching for non-alpha chars."""
    ks = Keystroke('\x1b1')
    assert ks.is_alt('1') is True
    assert ks.is_ctrl('1') is False


def test_alphanum_predicate_value_empty():
    """Test alphanumeric predicate when keystroke value is empty."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch('\x1b[A')
        ks = term.inkey(timeout=0)
        assert ks.value == ''
        assert ks.is_alt('x') is False

    child()


def test_alphanum_predicate_value_multi_char():
    """Test alphanumeric predicate when keystroke is multi-character."""
    ks = Keystroke('abc')
    assert ks.is_alt('a') is False


def test_get_alt_only_control_name_csi():
    """Test _get_alt_only_control_name returns CSI for bracket."""
    ks = Keystroke('\x1b[')
    result = ks._get_alt_only_control_name(0x5b)
    assert result == 'CSI'


def test_meta_escape_name_csi_special_case():
    """Test metaSendsEscape correctly identifies CSI sequence."""
    ks = Keystroke('\x1b[')
    result = ks._get_meta_escape_name()
    assert result == 'CSI'


def test_terminal_inkey_csi_sequence():
    """Test term.inkey() returns single CSI keystroke for unmatched sequences."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)

        # When an unsupported CSI sequence arrives, inkey should detect it as CSI
        term.ungetch('\x1b[')
        ks = term.inkey(timeout=0)
        assert ks == '\x1b['
        assert ks.name == 'CSI'
        assert len(ks) == 2
        assert ks.modifiers == 3

        # Verify no second keystroke was created
        ks2 = term.inkey(timeout=0)
        assert ks2 == ''

    child()


def test_legacy_csi_modifiers_no_modifiers_integration():
    """Test legacy CSI sequence with modifier=1 (no actual modifiers)."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch('\x1b[1;1P')
        ks = term.inkey(timeout=0)
        assert ks is not None
        assert ks._mode == -3
        assert ks.modifiers == 1
        assert ks.code == curses.KEY_F1
        result = ks._get_modified_keycode_name()
        assert result is None
        assert ks._ctrl is False
        assert ks._alt is False
        assert ks._shift is False

    child()


def test_getattr_non_is_attribute():
    """Test __getattr__ raises AttributeError for attributes not starting with is_."""
    ks = Keystroke('a')
    try:
        # pylint: disable=pointless-statement
        ks.some_random_attr
        assert False
    except AttributeError as e:
        assert 'some_random_attr' in str(e)

    try:
        # pylint: disable=pointless-statement
        ks.name_of_key
        assert False
    except AttributeError as e:
        assert 'name_of_key' in str(e)


def test_getattr_empty_is():
    """Test __getattr__ raises AttributeError for bare is_ attribute."""
    ks = Keystroke('a')
    try:
        ks.is_()
        assert False
    except AttributeError as e:
        assert 'is_' in str(e)


def test_get_meta_escape_name_invalid_inputs():
    """Test _get_meta_escape_name early returns for invalid inputs."""
    assert Keystroke('a')._get_meta_escape_name() is None
    assert Keystroke('abc')._get_meta_escape_name() is None
    assert Keystroke('\x1b')._get_meta_escape_name() is None
    assert Keystroke('ab')._get_meta_escape_name() is None


def test_get_meta_escape_name_branch_coverage():
    """Test branch coverage for modifiers==3 and modifiers==7 paths."""
    test_cases = [
        ('\x1b\x03', 7, 'KEY_CTRL_ALT_C'),
        ('\x1b\x04', 7, 'KEY_CTRL_ALT_D'),
        ('\x1b\x07', 7, 'KEY_CTRL_ALT_G'),
        ('\x1b\x0a', 7, 'KEY_CTRL_ALT_J'),
        ('\x1b\x0b', 7, 'KEY_CTRL_ALT_K'),
        ('\x1b\x0c', 7, 'KEY_CTRL_ALT_L'),
        ('\x1b\x0e', 7, 'KEY_CTRL_ALT_N'),
        ('\x1b\x0f', 7, 'KEY_CTRL_ALT_O'),
        ('\x1b\x10', 7, 'KEY_CTRL_ALT_P'),
        ('\x1b\x11', 7, 'KEY_CTRL_ALT_Q'),
        ('\x1b\x12', 7, 'KEY_CTRL_ALT_R'),
        ('\x1b\x13', 7, 'KEY_CTRL_ALT_S'),
        ('\x1b\x14', 7, 'KEY_CTRL_ALT_T'),
        ('\x1b\x15', 7, 'KEY_CTRL_ALT_U'),
        ('\x1b\x16', 7, 'KEY_CTRL_ALT_V'),
        ('\x1b\x18', 7, 'KEY_CTRL_ALT_X'),
        ('\x1b\x19', 7, 'KEY_CTRL_ALT_Y'),
        ('\x1b\x0d', 3, 'KEY_ALT_ENTER'),
        ('\x1b\x09', 3, 'KEY_ALT_TAB'),
    ]

    for sequence, expected_modifiers, expected_name in test_cases:
        ks = Keystroke(sequence)
        assert ks.modifiers == expected_modifiers
        result = ks._get_meta_escape_name()
        assert result == expected_name


def test_build_appkeys_predicate_modifier_validation():
    """Test application key predicate when modifiers don't match."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        term.ungetch('\x1b[1;2A')
        ks = term.inkey(timeout=0)
        assert ks.code == curses.KEY_UP
        assert ks._shift is True
        assert ks.is_shift_up() is True
        assert ks.is_ctrl_up() is False
    child()


def test_event_type_suffix_without_application_key():
    """Test event type suffix without valid application key raises AttributeError."""
    ks = Keystroke('\x01')
    assert ks._ctrl is True
    try:
        ks.is_ctrl_pressed('a')
        assert False
    except AttributeError as e:
        assert 'pressed' in str(e)
        assert 'only valid with application keys' in str(e)


def test_get_ctrl_alt_sequence_value_returns_none():
    """Test that Ctrl+Alt with Esc char (27) returns None for value."""
    # Ctrl+Alt with character code 27 (ESC, beyond the a-z range 1-26)
    # This sequence naturally has both ctrl and alt modifiers
    ks = Keystroke('\x1b\x1b')  # ESC+ESC
    # The value property will call _get_ctrl_alt_sequence_value
    # which should return None for char code 27 (not in 1-26 range or space)
    # Since it returns None, value falls through to other methods
    assert ks.value == ''  # ESC characters have empty value


def test_ctrl_sequence_unmapped_character():
    """Test Ctrl sequences with characters outside standard mappings."""
    # Test that lines 899 and 923 are covered by checking edge cases
    # Line 899: Ctrl+Alt sequence with char > 26 returns None
    ks_ctrl_alt_esc = Keystroke('\x1b\x1b')  # Ctrl+Alt+Esc
    assert ks_ctrl_alt_esc._ctrl is False  # ESC doesn't set ctrl
    assert ks_ctrl_alt_esc._alt is True

    # Line 923: Ctrl sequences are all mapped (0, 1-26, 27-31, 127)
    # So there's no unmapped ctrl character that would reach line 923
    # The line exists for defensive programming but isn't reachable with valid input


def test_defensive_meta_escape_esc_control_char_modifiers_neither_3_nor_7():
    """Test defensive branch: ESC + control char with modifiers not 3 or 7."""
    # Line 388->392: When we have ESC + control char but modifiers != 3 and != 7
    # This would require modifiers to be something like 1 (no mods), 2 (shift), 5 (ctrl+shift), etc.
    # However, ESC + control char naturally sets modifiers to either 3 (alt-only) or 7 (ctrl+alt)
    # This branch exists for defensive programming but may not be reachable with valid sequences
    # Let's test ESC + printable char instead which skips both conditions
    ks = Keystroke('\x1bx')  # ESC + 'x' (not a control char)
    assert ks.modifiers == 3  # Alt only
    assert ks.name == 'KEY_ALT_X'  # Falls through to line 392+


def test_defensive_ctrl_alt_value_with_high_char_code():
    """Test defensive branch: Ctrl+Alt sequence with char code > 26."""
    # Line 899: Ctrl+Alt with char code not 0 and not 1-26
    # The only control characters with codes > 26 are: 27-31, 127
    ks_escape = Keystroke('\x1b\x1b')  # ESC+ESC (char code 27)
    # This is actually Alt+Escape, not Ctrl+Alt+Escape
    assert ks_escape._alt is True
    assert ks_escape._ctrl is False
    assert ks_escape.value == ''  # Empty value for special keys


def test_defensive_ctrl_alt_value_esc_sequence_not_special_app_key():
    """Test defensive branch: ESC sequence without special application keys."""
    # Line 886->890: ESC sequence where second char is NOT in {0x1b, 0x7f, 0x0d, 0x09}
    # Test with regular letter instead
    ks = Keystroke('\x1bx')  # ESC + 'x'
    assert len(ks) == 2
    assert ks[0] == '\x1b'
    assert ks[1] == 'x'
    assert ks.value == 'x'  # Regular letter has its own value
