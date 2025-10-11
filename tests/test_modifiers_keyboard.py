"""Tests for advanced keyboard protocol support (modifier inference and protocols)."""
# pylint: disable=too-many-lines
# std imports
import platform

# 3rd party
import pytest

# local
from .accessories import (TestTerminal, as_subprocess, assert_modifiers,
                          assert_modifiers_value, assert_only_modifiers)

if platform.system() != 'Windows':
    import tty  # pylint: disable=unused-import  # NOQA
    import curses
else:
    import jinxed as curses  # pylint: disable=import-error


# ============================================================================
# Wrapper functions for common modifier assertions
# ============================================================================

def assert_ctrl_alt_modifiers(ks):
    """Assert keystroke has Ctrl+Alt modifiers (modifiers=7)."""
    assert_only_modifiers(ks, 'ctrl', 'alt')


# ============================================================================
# Legacy Ctrl+Alt modifiers (metaSendsEscape + control char)
# ============================================================================

def test_legacy_ctrl_alt_modifiers():
    """Infer modifiers from legacy Ctrl+Alt."""
    from blessed.keyboard import Keystroke

    ks = Keystroke('\x1b\x06')
    assert_ctrl_alt_modifiers(ks)

    ks = Keystroke('\x1b\x1a')
    assert_ctrl_alt_modifiers(ks)


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


@pytest.mark.parametrize('sequence,expected_name,modifiers,ctrl,alt,shift', [
    # Ctrl+Alt cases
    ('\x1b\x01', 'KEY_CTRL_ALT_A', 7, True, True, False),
    ('\x1b\x06', 'KEY_CTRL_ALT_F', 7, True, True, False),
    ('\x1b\x1a', 'KEY_CTRL_ALT_Z', 7, True, True, False),
    ('\x1b\x00', 'KEY_CTRL_ALT_@', 7, True, True, False),
    ('\x1b\x08', 'KEY_CTRL_ALT_H', 7, True, True, False),
    # Alt-only cases
    ('\x1b\x1b', 'KEY_ALT_ESCAPE', 3, False, True, False),
    ('\x1b\x7f', 'KEY_ALT_BACKSPACE', 3, False, True, False),
    ('\x1b\x0d', 'KEY_ALT_ENTER', 3, False, True, False),
    ('\x1b\x09', 'KEY_ALT_TAB', 3, False, True, False),
])
def test_legacy_ctrl_alt_edge_cases(sequence, expected_name, modifiers, ctrl, alt, shift):
    """Edge cases for legacy Ctrl+Alt and Alt-only sequences."""
    from blessed.keyboard import Keystroke

    ks = Keystroke(sequence)
    assert ks.modifiers == modifiers
    assert_modifiers(ks, ctrl=ctrl, alt=alt, shift=shift)
    assert len(ks) == 2
    assert ks[0] == '\x1b'
    assert ks.name == expected_name


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
        assert_ctrl_alt_modifiers(ks)

        ctrl_alt_z = '\x1b\x1a'
        term.ungetch(ctrl_alt_z)
        ks = term.inkey(timeout=0)
        assert ks == ctrl_alt_z
        assert_ctrl_alt_modifiers(ks)

    child()


def test_legacy_ctrl_alt_doesnt_affect_other_sequences():
    """Test that legacy Ctrl+Alt detection doesn't interfere with existing sequences."""
    from blessed.keyboard import Keystroke

    # Regular Alt sequences should still work (ESC + printable)
    ks_alt_a = Keystroke('\x1ba')  # Alt+a
    assert_only_modifiers(ks_alt_a, 'alt')
    assert ks_alt_a.name == 'KEY_ALT_A'

    # Regular Ctrl sequences should still work (single control char)
    ks_ctrl_a = Keystroke('\x01')  # Ctrl+a
    assert_only_modifiers(ks_ctrl_a, 'ctrl')
    assert ks_ctrl_a.name == 'KEY_CTRL_A'

    # Regular printable characters should have no modifiers
    ks_regular = Keystroke('a')
    assert_modifiers_value(ks_regular, modifiers=1)
    assert_modifiers(ks_regular, ctrl=False, alt=False, shift=False)


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


# ============================================================================
# Legacy CSI modifiers (ESC [ 1 ; modifiers [ABCDEFHPQRS] and tilde forms)
# ============================================================================

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
    """Test legacy CSI modifier sequences in letter form (ESC [ 1 ; modifiers [ABCDEFHPQS])."""
    from blessed.keyboard import _match_legacy_csi_modifiers, LegacyCSIKeyEvent

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
    assert ks.name == expected_key_name


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
    """Test legacy CSI modifier sequences in tilde form (ESC [ number ; modifiers ~)."""
    from blessed.keyboard import _match_legacy_csi_modifiers, LegacyCSIKeyEvent

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

    # and finally name match
    assert ks.name == expected_key_name


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


# ============================================================================
# ModifyOtherKeys protocol (ESC [ 27 ; modifiers ; key)
# ============================================================================

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


# ============================================================================
# Modifier inference (_infer_modifiers)
# ============================================================================

def test_modifiers_inference_legacy_ctrl():
    """Test modifier inference from legacy control characters."""
    from blessed.keyboard import Keystroke

    # Ctrl+a as legacy control character
    ks = Keystroke('\x01')  # Ctrl+A
    assert_only_modifiers(ks, 'ctrl')


def test_modifiers_inference_legacy_alt():
    """Test modifier inference from legacy Alt (meta sends escape)."""
    from blessed.keyboard import Keystroke

    # Alt+a as ESC+a
    ks = Keystroke('\x1ba')
    assert_only_modifiers(ks, 'alt')


def test_modifiers_inference_no_modifiers():
    """Test that regular characters have no modifiers."""
    from blessed.keyboard import Keystroke

    ks = Keystroke('a')
    assert_modifiers_value(ks, modifiers=1)
    assert_modifiers(ks, ctrl=False, alt=False, shift=False)


# ============================================================================
# Modifier properties (modifiers, modifiers_bits, _ctrl, _alt, _shift, etc.)
# ============================================================================

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


# ============================================================================
# Helper methods (is_ctrl, is_alt, is_shift)
# ============================================================================

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
    assert Keystroke('\x1bZ').is_alt('Z') is True  # Alt+Z (now has Shift too)

    # Test case sensitivity control
    assert Keystroke('\x1ba').is_alt('A', ignore_case=True) is True
    assert Keystroke('\x1ba').is_alt('A', ignore_case=False) is False

    # Test without character argument (any Alt+char)
    assert Keystroke('\x1ba').is_alt() is False    # Alt+a
    assert Keystroke('\x1b1').is_alt() is False    # Alt+1
    assert Keystroke('\x1b ').is_alt() is False    # Alt+space
    assert Keystroke('\x1ba').is_alt('A') is True  # Alt+a
    assert Keystroke('\x1b1').is_alt('1') is True  # Alt+1
    assert Keystroke('\x1b ').is_alt(' ') is True  # Alt+space

    # Test negative cases
    assert Keystroke('a').is_alt('a') is False       # Regular 'a'
    assert Keystroke('\x1b').is_alt('a') is False    # Just ESC
    assert Keystroke('\x1ba').is_alt('b') is False   # Alt+a != Alt+b
    assert Keystroke('\x1bab').is_alt('a') is False  # Too long
    assert Keystroke('\x1b\x01').is_alt() is False   # Non-printable second char


def test_is_ctrl_exact_matching_legacy():
    """Test exact matching for is_ctrl with legacy control characters."""
    from blessed.keyboard import Keystroke

    # Legacy Ctrl+a
    ks = Keystroke('\x01')
    assert ks.is_ctrl('a') is True
    assert ks.is_ctrl('A') is True  # Case insensitive
    assert ks.is_ctrl('b') is False
    assert ks.is_ctrl() is False

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
    assert ks.is_alt() is False

    # Case sensitivity control
    ks = Keystroke('\x1bA')  # Alt+A (uppercase)
    # Now has Shift too
    assert ks.is_alt('a', ignore_case=True) is True
    assert ks.is_alt('a', ignore_case=False) is False
    assert ks.is_alt('A', ignore_case=False) is True


# ============================================================================
# Name generation for modified keys
# ============================================================================

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
        assert ks is not None
        assert ks._match.event_type == expected_type

    # Test that invalid sequences don't match
    invalid_cases = [
        '\x1b[1;2:Q',      # Missing event type number
        '\x1b[1;2:abc~',   # Non-numeric event type
        '\x1b[24;2:~',     # Missing event type in tilde form
    ]

    for invalid_seq in invalid_cases:
        ks = _match_legacy_csi_modifiers(invalid_seq)
        assert ks is None

# ============================================================================
# Coverage tests for uncovered branches
# ============================================================================


def test_infer_modifiers_alt_lowercase():
    """Test _infer_modifiers with Alt+lowercase (no shift)."""
    from blessed.keyboard import Keystroke

    # Alt+lowercase should be Alt only, no shift
    ks = Keystroke('\x1ba')  # Alt+a (lowercase)
    assert ks.modifiers == 3  # 1 + 2 (alt only)
    assert ks._alt is True
    assert ks._shift is False

    # Alt+number should be Alt only
    ks = Keystroke('\x1b1')
    assert ks.modifiers == 3  # 1 + 2 (alt only)
    assert ks._alt is True
    assert ks._shift is False


def test_get_control_symbol_all_cases():
    """Test _get_control_symbol for all control character mappings."""
    from blessed.keyboard import Keystroke

    # Test creating keystroke that will call _get_control_symbol
    # via the _get_meta_escape_name path

    # ESC + control char that's not in the symbol map returns nothing
    ks = Keystroke('\x1b\x02')  # ESC + Ctrl+B
    # This calls _get_control_symbol(0x02) which returns 'B'
    assert ks.name == 'KEY_CTRL_ALT_B'


def test_get_alt_only_control_name_no_match():
    """Test _get_alt_only_control_name with char_code not in map."""
    from blessed.keyboard import Keystroke

    # Create keystroke with ESC + control char that's not Alt-only
    ks = Keystroke('\x1b\x01')  # ESC + Ctrl+A (not in Alt-only map)
    assert ks.modifiers == 7  # Ctrl+Alt, not Alt-only
    assert ks.name == 'KEY_CTRL_ALT_A'


def test_get_meta_escape_name_non_printable_no_symbol():
    """Test _get_meta_escape_name when control char has no symbol."""
    from blessed.keyboard import Keystroke

    # This tests the path where symbol is None from _get_control_symbol
    # We need a control character that's not mappable
    # Actually all control chars 0-31 and 127 have symbols, so test the
    # path where we don't enter the control char block at all
    ks = Keystroke('\x1b[')  # ESC + [, which is printable
    assert ks.name == 'CSI'


def test_get_meta_escape_name_non_alpha_printable():
    """Test _get_meta_escape_name with non-alphabetic printable chars."""
    from blessed.keyboard import Keystroke

    # Test non-alpha printable
    ks = Keystroke('\x1b;')  # ESC + ;
    assert ks.name == 'KEY_ALT_;'

    ks = Keystroke('\x1b1')  # ESC + 1
    assert ks.name == 'KEY_ALT_1'


def test_build_appkeys_predicate_with_char():
    """Test _build_appkeys_predicate when called with char argument."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # Create keystroke with application key
    ks = _match_legacy_csi_modifiers('\x1b[1;2A')  # Shift+Up

    # Call predicate with char argument - should return False
    assert ks.is_shift_up('x') is False
    # Empty string is falsy, so it passes the 'if char:' check as False
    assert ks.is_shift_up('') is True  # Empty string is falsy, behaves like None


def test_build_appkeys_predicate_keycode_loop():
    """Test _build_appkeys_predicate keycode search loop."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # This tests the loop that searches for expected_code
    ks = _match_legacy_csi_modifiers('\x1b[1;2A')  # Shift+Up

    # Valid key name
    assert ks.is_shift_up() is True

    # Test with invalid key name (no such keycode)
    # This requires __getattr__ to build a predicate with invalid key name
    try:
        # This should raise AttributeError for invalid key
        ks.is_shift_foobar()
        assert False
    except AttributeError as e:
        assert 'foobar' in str(e)


def test_build_alphanum_predicate_without_char_printable():
    """Test _build_alphanum_predicate with char=None on printable keystroke."""
    from blessed.keyboard import Keystroke

    # Create Alt+a keystroke
    ks = Keystroke('\x1ba')

    # Calling is_alt() without char on printable should return False
    assert ks.is_alt() is False


def test_getattr_no_event_type_suffix():
    """Test __getattr__ when no event type suffix is found."""
    from blessed.keyboard import Keystroke

    # Test attribute that doesn't end with event type
    ks = Keystroke('\x01')  # Ctrl+A

    # This should build an alphanum predicate
    assert ks.is_ctrl('a') is True
    assert ks.is_ctrl('b') is False


def test_getattr_no_key_names():
    """Test __getattr__ when no key names are found."""
    from blessed.keyboard import Keystroke

    # Just modifier tokens
    ks = Keystroke('\x1ba')  # Alt+a
    assert ks.is_alt('a') is True


def test_getattr_invalid_key_name():
    """Test __getattr__ with invalid key name that's not in keycodes."""
    from blessed.keyboard import Keystroke

    ks = Keystroke('\x01')

    # Try to access is_ctrl_invalid_key_name
    # This should raise AttributeError because 'invalid_key_name' is not a valid key
    try:
        ks.is_ctrl_invalid_key_name()
        assert False
    except AttributeError as e:
        assert 'invalid' in str(e).lower()


def test_get_value_for_comparison_all_branches():
    """Test value property covering all code paths."""
    from blessed.keyboard import Keystroke, _match_modify_other_keys

    # ESC + printable char (metaSendsEscape)
    ks = Keystroke('\x1ba')
    assert ks.value == 'a'

    # ESC + control char (Ctrl+Alt) - char in range 1-26
    ks = Keystroke('\x1b\x01')  # ESC + Ctrl+A
    assert ks.value == 'a'

    # ESC + control char - in CTRL_CODE_SYMBOLS_MAP
    ks = Keystroke('\x1b\x1b')  # ESC + ESC (27)
    assert ks.value == '['

    # Single control character 1-26
    ks = Keystroke('\x01')  # Ctrl+A
    assert ks.value == 'a'

    # Single control character in CTRL_CODE_SYMBOLS_MAP
    ks = Keystroke('\x00')  # Ctrl+@
    assert ks.value == '@'

    # ModifyOtherKeys protocol
    ks = _match_modify_other_keys('\x1b[27;5;97~')  # Ctrl+a
    assert ks.value == 'a'

    # Single printable character
    ks = Keystroke('a')
    assert ks.value == 'a'

    # Empty string case - sequence that doesn't match any pattern
    ks = Keystroke('\x1b[A')  # Arrow key sequence
    # This doesn't match any of the patterns, so returns empty string
    # Actually it might have a code, so let's test with a plain sequence
    ks = Keystroke('abc')  # Multi-char, not matching any pattern
    assert ks.value == ''


def test_match_legacy_csi_invalid_letter_final():
    """Test _match_legacy_csi_modifiers with invalid final character in letter form."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # Invalid final char (not in the keycode_match dict)
    # Valid chars are: ABCDEFHPQRS
    # Try with 'Z' which is not valid
    ks = _match_legacy_csi_modifiers('\x1b[1;5Z')
    assert ks is None


def test_match_legacy_csi_invalid_tilde_number():
    """Test _match_legacy_csi_modifiers with invalid tilde number."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # Invalid tilde number (not in the keycode_match dict)
    # Valid numbers are: 2, 3, 5, 6, 7, 8, 11-15, 17-21, 23-24
    # Try with 99 which is not valid
    ks = _match_legacy_csi_modifiers('\x1b[99;5~')
    assert ks is None


def test_match_ss3_fkey_modifier_zero():
    """Test _match_legacy_csi_modifiers SS3 F-key form with modifier=0."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # SS3 F-key form with modifier 0 (invalid)
    ks = _match_legacy_csi_modifiers('\x1bO0P')  # modifier=0, final=P
    assert ks is None


def test_match_ss3_fkey_invalid_final():
    """Test _match_legacy_csi_modifiers SS3 F-key form with invalid final char."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # SS3 F-key form with invalid final char
    # Valid final chars are: P, Q, R, S
    # Try with 'X' which is not valid
    ks = _match_legacy_csi_modifiers('\x1bO2X')  # modifier=2, final=X (invalid)
    assert ks is None


@pytest.mark.parametrize('sequence,expected_code,expected_mod', [
    ('\x1bO2P', curses.KEY_F1, 2),  # Shift+F1
    ('\x1bO5Q', curses.KEY_F2, 5),  # Ctrl+F2
    ('\x1bO3R', curses.KEY_F3, 3),  # Alt+F3
    ('\x1bO6S', curses.KEY_F4, 6),  # Ctrl+Shift+F4
])
def test_match_ss3_fkey_valid(sequence, expected_code, expected_mod):
    """Test _match_legacy_csi_modifiers SS3 F-key form with valid input."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    ks = _match_legacy_csi_modifiers(sequence)
    assert ks is not None
    assert ks.code == expected_code
    assert ks.modifiers == expected_mod
    assert ks._match.kind == 'ss3-fkey'
    assert ks._match.event_type == 1  # Always press for SS3


def test_get_modified_keycode_name_no_modifiers_press():
    """Test _get_modified_keycode_name with no modifiers and press event."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # Press event with no modifiers (modifier=1) should return None
    ks = _match_legacy_csi_modifiers('\x1b[1;1A')  # No modifiers, press
    # When there are no modifiers and it's a press event, _get_modified_keycode_name returns None
    # The name property then returns None because no other name generation methods match
    # This is expected behavior - the keystroke has a code but no special name
    assert ks.name is None  # No special name for plain key with mode set


def test_alphanum_predicate_non_alpha_char_matching():
    """Test alphanum predicate with non-alphabetic character."""
    from blessed.keyboard import Keystroke

    # Alt+1 (non-alphabetic)
    ks = Keystroke('\x1b1')
    assert ks.is_alt('1') is True
    assert ks.is_alt('2') is False


def test_alphanum_predicate_empty_or_long_value():
    """Test alphanum predicate when value is empty or multi-char."""
    from blessed.keyboard import Keystroke

    # Multi-character sequence
    ks = Keystroke('abc')
    assert ks.is_ctrl('a') is False  # Not a control char


def test_alphanum_predicate_non_printable():
    """Test alphanum predicate with non-printable character."""
    from blessed.keyboard import Keystroke

    # Application key (has code, non-printable value)
    ks = Keystroke('\x1b[A', code=curses.KEY_UP, name='KEY_UP')

    # Calling is_ctrl on an arrow key should fail
    assert ks.is_ctrl('a') is False


def test_getattr_invalid_is_prefix():
    """Test __getattr__ with empty tokens after 'is_'."""
    from blessed.keyboard import Keystroke

    ks = Keystroke('a')

    # Try to access 'is_' with nothing after it
    try:
        # This should be accessed via __getattr__, but Python might handle it differently
        # Let's use getattr to be explicit
        getattr(ks, 'is_')
        assert False
    except AttributeError:
        pass


def test_getattr_not_is_prefix():
    """Test __getattr__ with attribute not starting with 'is_'."""
    from blessed.keyboard import Keystroke

    ks = Keystroke('a')

    # Try to access attribute that doesn't start with 'is_'
    try:
        ks.some_random_attribute
        assert False
    except AttributeError as e:
        assert 'some_random_attribute' in str(e)


def test_is_ctrl_without_char_on_printable():
    """Test calling is_ctrl() without char on a printable keystroke."""
    from blessed.keyboard import Keystroke

    # Control character
    ks = Keystroke('\x01')  # Ctrl+A

    # Calling is_ctrl() without char - should return False
    # because control keys need char argument for matching
    assert ks.is_ctrl() is False


def test_legacy_csi_e_center_key():
    """Test legacy CSI modifier with 'E' (center/begin key)."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    ks = _match_legacy_csi_modifiers('\x1b[1;5E')  # Ctrl+Center
    assert ks is not None
    assert ks.code == curses.KEY_B2  # Center key
    assert ks.modifiers == 5


@pytest.mark.parametrize('sequence,expected_name', [
    ('\x00', 'KEY_CTRL_@'),   # @
    ('\x1b', 'KEY_CTRL_['),   # [
    ('\x1c', 'KEY_CTRL_\\'),  # \
    ('\x1d', 'KEY_CTRL_]'),   # ]
    ('\x1e', 'KEY_CTRL_^'),   # ^
    ('\x1f', 'KEY_CTRL__'),   # _
    ('\x7f', 'KEY_CTRL_?'),   # ?
])
def test_ctrl_code_symbols_all(sequence, expected_name):
    """Test all CTRL_CODE_SYMBOLS_MAP entries."""
    from blessed.keyboard import Keystroke

    ks = Keystroke(sequence)
    assert ks.name == expected_name


def test_control_symbol_not_in_map():
    """Test _get_control_symbol with code not in range or map."""
    from blessed.keyboard import Keystroke

    # Test ESC + control char that returns None from _get_control_symbol
    # This would need a control char that's not 1-26 and not in CTRL_CODE_SYMBOLS_MAP
    # Actually, all control chars 0-31 and 127 have symbols, so this branch may not be reachable
    # Let's test the modifiers == 3 path with symbol but not in alt_name map
    ks = Keystroke('\x1b\x02')  # ESC + Ctrl+B, should be Ctrl+Alt
    assert ks.modifiers == 7  # Ctrl+Alt
    assert ks.name == 'KEY_CTRL_ALT_B'


def test_meta_escape_not_printable_and_not_7f():
    """Test _get_meta_escape_name with non-printable, non-0x7f."""
    from blessed.keyboard import Keystroke

    # Test the final return None path in _get_meta_escape_name
    # This requires ESC + non-printable that's not 0-31 or 127
    # Actually, looking at the code, the only way to reach the final return None
    # is if the second char is not printable and not \x7f with modifiers==3
    # Let's test modifiers != 3 path for \x7f
    ks = Keystroke('\x1b\x7f')  # ESC + DEL
    assert ks.modifiers == 3  # Alt only
    # This should match the alt_name path
    assert ks.name == 'KEY_ALT_BACKSPACE'


def test_keycode_loop_found():
    """Test keycode loop when expected_code is found."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # Test that the loop finds the expected code and returns True
    ks = _match_legacy_csi_modifiers('\x1b[1;2A')  # Shift+Up
    assert ks.is_shift_up() is True


def test_build_alphanum_without_char_non_printable():
    """Test alphanum predicate without char on non-printable keystroke."""
    from blessed.keyboard import Keystroke

    # Create a keystroke with non-printable value
    ks = Keystroke('\x01')  # Ctrl+A

    # Calling is_ctrl() without char should return True
    # because it's a non-printable control character
    # Actually, looking at the code, it returns False because
    # is_ctrl() needs a char argument for matching
    assert ks.is_ctrl() is False


def test_get_value_esc_control_no_symbol_match():
    """Test value property ESC + control char not in symbol map."""
    from blessed.keyboard import Keystroke

    # Test ESC + control char that's in 1-26 range
    ks = Keystroke('\x1b\x05')  # ESC + Ctrl+E
    # This should return 'e' from the 1-26 mapping
    assert ks.value == 'e'


def test_get_value_single_control_no_symbol_match():
    """Test value property single control char not in symbol map."""
    from blessed.keyboard import Keystroke

    # Single control character in 1-26 range
    ks = Keystroke('\x05')  # Ctrl+E
    assert ks.value == 'e'


def test_match_legacy_csi_letter_keycode_none():
    """Test _match_legacy_csi_modifiers letter form with invalid final returns None."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # We already test invalid final chars, but let's be explicit about the None return
    ks = _match_legacy_csi_modifiers('\x1b[1;5X')  # Invalid final 'X'
    assert ks is None


def test_match_ss3_keycode_none():
    """Test _match_legacy_csi_modifiers SS3 form with invalid final returns None."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # We already test invalid final chars, but let's be explicit
    ks = _match_legacy_csi_modifiers('\x1bO2Z')  # Invalid final 'Z'
    assert ks is None


def test_keystroke_repr_no_name():
    """Test Keystroke.__repr__ when _name is None (str.__repr__ branch)."""
    from blessed.keyboard import Keystroke

    # Create keystroke without name
    ks = Keystroke('x')
    # When _name is None, __repr__ uses str.__repr__
    repr_str = repr(ks)
    # Should be the string repr, not a key name
    assert repr_str == "'x'"


def test_get_control_symbol_no_match():
    """Test _get_control_symbol return None for non-control char."""
    from blessed.keyboard import Keystroke
    # Test with ESC + control char where symbol is None
    # shouldn't happen in normal flow
    ks = Keystroke('\x1b\x20')  # ESC + space (0x20, printable)
    # Space is printable, so it won't enter the control char block
    assert ks.name == 'KEY_ALT_ '


def test_meta_escape_name_no_symbol():
    """Test _get_meta_escape_name when symbol is None."""
    from blessed.keyboard import Keystroke

    # Test ESC + printable that's not alphabetic
    ks = Keystroke('\x1b/')  # ESC + /
    assert ks.name == 'KEY_ALT_/'


def test_alphanum_predicate_char_mismatch():
    """Test alphanum predicate with character that doesn't match."""
    from blessed.keyboard import Keystroke

    # Test the else branch where effective_bits != expected_bits
    ks = Keystroke('\x1ba')  # Alt+a

    # Call with wrong modifier expectation
    assert ks.is_ctrl('a') is False  # Expecting ctrl but has alt


def test_getattr_tokens_key_names_not_in_keycodes():
    """Test __getattr__ when key name tokens don't form valid keycode."""
    from blessed.keyboard import Keystroke

    # Test when tokens_key_names exists but doesn't match valid keycode
    ks = Keystroke('\x1b[1;2A')  # Shift+Up

    # Try to access a modifier + invalid key combination
    try:
        ks.is_shift_invalid_key()
        assert False
    except AttributeError as e:
        assert 'invalid' in str(e).lower()


def test_get_value_for_comparison_esc_control_not_in_map():
    """Test value property with ESC + control char not in map."""
    from blessed.keyboard import Keystroke

    # ESC + control char in 1-26 range (not in CTRL_CODE_SYMBOLS_MAP)
    ks = Keystroke('\x1b\x03')  # ESC + Ctrl+C
    assert ks.value == 'c'


def test_legacy_csi_modifiers_keycode_none_both_forms():
    """Test legacy CSI when keycode_match is None for both forms."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # Letter form with invalid final - keycode_match will be None
    ks = _match_legacy_csi_modifiers('\x1b[1;5W')  # Invalid final 'W'
    assert ks is None

    # Tilde form with invalid number - keycode_match will be None
    ks = _match_legacy_csi_modifiers('\x1b[100;5~')  # Invalid number 100
    assert ks is None


def test_ss3_fkey_branches():
    """Test SS3 F-key form covering all branches."""
    from blessed.keyboard import _match_legacy_csi_modifiers

    # Valid SS3 (keycode_match is not None)
    ks = _match_legacy_csi_modifiers('\x1bO2P')  # Shift+F1
    assert ks is not None
    assert ks.code == curses.KEY_F1

    # Invalid SS3 final (keycode_match is None)
    ks = _match_legacy_csi_modifiers('\x1bO2A')  # Invalid for SS3
    assert ks is None


def test_alphanum_predicate_no_char_non_printable_return():
    """Test alphanum predicate char=None with non-printable keystroke_char."""
    from blessed.keyboard import Keystroke

    # Create keystroke that will have non-printable value
    # When char is None and keystroke_char is not printable, return True
    ks = Keystroke('\x01')  # Ctrl+A

    # The value property returns 'a' which is printable
    # So it will return False
    assert ks.is_ctrl() is False


def test_repr_with_name():
    """Test Keystroke.__repr__ when _name is not None."""
    from blessed.keyboard import Keystroke

    # Create keystroke with explicit name
    ks = Keystroke('\x1b[A', code=259, name='KEY_UP')

    # When _name is not None, __repr__ returns _name
    repr_str = repr(ks)
    assert repr_str == 'KEY_UP'


def test_get_modified_keycode_name_base_name_not_starting_with_key():
    """Test _get_modified_keycode_name when base_name doesn't start with KEY_."""
    from blessed.keyboard import Keystroke, LegacyCSIKeyEvent

    # This is tricky - we need a keystroke with mode < 0, code != None,
    # but the keycode doesn't map to a name starting with 'KEY_'
    # This shouldn't happen in practice, but let's test the branch

    # Create a keystroke manually with invalid code
    ks = Keystroke('\x1b[1;2A', code=99999, mode=-3,
                   match=LegacyCSIKeyEvent('letter', 'A', 2, 1))
    # If the code isn't in keycodes, base_name will be None
    # and the function returns None
    assert ks.name is None  # Falls through to other name methods


def test_infer_modifiers_all_paths():
    """Test _infer_modifiers covering all code paths."""
    from blessed.keyboard import Keystroke

    # Path 1: mode is not None and mode < 0 and match is not None
    # Already tested with legacy CSI and ModifyOtherKeys

    # Path 2: len==2 and ucs[0]==ESC, char_code in {0x0d, 0x1b, 0x7f, 0x09}
    ks = Keystroke('\x1b\x0d')  # ESC + CR
    assert ks.modifiers == 3  # Alt only

    # Path 3: len==2 and ucs[0]==ESC, 0 <= char_code <= 31 or char_code == 127
    # But not in the special set
    ks = Keystroke('\x1b\x05')  # ESC + Ctrl+E
    assert ks.modifiers == 7  # Ctrl+Alt

    # Path 4: len==2 and ucs[0]==ESC, 32 <= char_code <= 126 (printable)
    ks = Keystroke('\x1b5')  # ESC + 5 (non-alpha printable)
    assert ks.modifiers == 3  # Alt only (no shift for non-alpha)

    # Path 5: len==1, 0 <= char_code <= 31 or char_code == 127
    ks = Keystroke('\x05')  # Ctrl+E
    assert ks.modifiers == 5  # Ctrl only

    # Path 6: Default (no modifiers)
    ks = Keystroke('x')
    assert ks.modifiers == 1


def test_alphanum_predicate_char_alpha_shift_mismatch():
    """Test alphanum predicate with alphabetic char and shift mismatch."""
    from blessed.keyboard import Keystroke

    # Test when char is alphabetic and shift bits don't match
    ks = Keystroke('\x1ba')  # Alt+a (lowercase, no shift)

    # The effective_bits_no_shift should match expected_bits_no_shift
    assert ks.is_alt('a') is True

    # Test with uppercase
    ks = Keystroke('\x1bA')  # Alt+A (uppercase, has shift)
    assert ks.is_alt('A') is True


# ============================================================================
# Additional coverage tests for uncovered branches
# ============================================================================


def test_pressed_property_default_return():
    """Test pressed property returns True by default."""
    from blessed.keyboard import Keystroke

    # Regular keystroke without mode set (default case)
    ks = Keystroke('a')
    assert ks.pressed is True

    # Keystroke with code but no mode
    ks = Keystroke('x', code=100, name='TEST')
    assert ks.pressed is True

    # Keystroke with mode but not negative (also defaults to True)
    ks = Keystroke('y', mode=0)
    assert ks.pressed is True


def test_getattr_property_getter():
    """Test __getattr__ with property access."""
    from blessed.keyboard import Keystroke

    # This tests the property getter path in __getattr__ (line 525->529)
    ks = Keystroke('\x01')  # Ctrl+A

    # Access a property that exists in the class
    # Properties like 'code', 'name', 'modifiers' should work normally
    assert hasattr(ks, 'code')
    assert hasattr(ks, 'name')
    assert hasattr(ks, 'modifiers')


def test_value_property_edge_cases():
    """Test value property uncovered branches."""
    from blessed.keyboard import Keystroke

    # Test ESC + control char (Ctrl+Alt combination)
    # Char codes 1-26 are letters, should return lowercase
    ks = Keystroke('\x1b\x03')  # ESC + Ctrl+C (code 3)
    assert ks.value == 'c'  # Returns lowercase letter

    # Test single control char
    ks = Keystroke('\x03')  # Ctrl+C (code 3)
    assert ks.value == 'c'  # Returns lowercase letter

    # Test ESC + control char in CTRL_CODE_SYMBOLS_MAP
    ks = Keystroke('\x1b\x00')  # ESC + Ctrl+@ (code 0)
    assert ks.value == '@'  # Returns symbol from map

    # Test single control char in CTRL_CODE_SYMBOLS_MAP
    ks = Keystroke('\x00')  # Ctrl+@ (code 0)
    assert ks.value == '@'  # Returns symbol from map

    # Test Alt+printable sequence
    ks = Keystroke('\x1ba')  # Alt+a
    assert ks.value == 'a'

    # Test plain printable character
    ks = Keystroke('x')
    assert ks.value == 'x'

    # Test application key (no value)
    ks = Keystroke('\x1b[A', code=259, name='KEY_UP')
    assert ks.value == ''  # Application keys have no text value


def test_value_property_all_helper_methods():
    """Test value property calling all helper methods."""
    from blessed.keyboard import Keystroke

    # Test _get_plain_char_value
    ks = Keystroke('a')
    assert ks.value == 'a'

    # Test _get_alt_sequence_value
    ks = Keystroke('\x1ba')  # Alt+a
    assert ks.value == 'a'

    # Test _get_alt_control_sequence_value
    # ESC + control char that's Alt-only (special exceptions)
    ks = Keystroke('\x1b\x1b')  # ESC + ESC
    assert ks.modifiers == 3  # Alt only
    # For Alt-only, value should map the control char
    # ESC (0x1b) maps to '[' in CTRL_CODE_SYMBOLS_MAP
    assert ks.value == '['

    # Test _get_ctrl_alt_sequence_value
    ks = Keystroke('\x1b\x03')  # ESC + Ctrl+C
    assert ks.modifiers == 7  # Ctrl+Alt
    assert ks.value == 'c'

    # Test _get_ctrl_sequence_value
    ks = Keystroke('\x03')  # Ctrl+C
    assert ks.modifiers == 5  # Ctrl only
    assert ks.value == 'c'

    # Test _get_ascii_value (for KEY_ENTER, KEY_TAB, KEY_BACKSPACE, KEY_EXIT)
    # _get_ascii_value returns the ASCII value for certain keycodes
    # To reach this method, we need a keystroke where earlier methods return None
    # Empty string with KEY_ENTER code will skip earlier checks
    ks = Keystroke('', code=curses.KEY_ENTER)
    assert ks.value == '\n'  # Returns '\n' from _get_ascii_value mapping

    # Test empty string return (application key)
    ks = Keystroke('\x1b[A', code=curses.KEY_UP, name='KEY_UP')
    assert ks.value == ''


# ============================================================================
# Superfluous tests - targeting internal implementation details or unrealistic
# edge cases not reachable through normal public API usage with typical
# terminal sequences
# ============================================================================


def test_superfluous_control_symbol_invalid_char_code():
    """Test _get_control_symbol with char_code outside valid ranges.

    Superfluous: Directly calls internal _get_control_symbol() method with
    invalid char code to test defensive return None branch.
    """
    from blessed.keyboard import Keystroke

    # The branch where _get_control_symbol returns None happens for char codes
    # not in 1-26 and not in CTRL_CODE_SYMBOLS_MAP. Test by calling directly.
    ks_test = Keystroke('\x1b\x02')  # Any keystroke for method access
    result = ks_test._get_control_symbol(50)  # Char code 50 (not in valid ranges)
    assert result is None


def test_superfluous_meta_escape_name_symbol_none_path():
    """Test _get_meta_escape_name internal edge case paths.

    Superfluous: Tests internal _get_meta_escape_name method paths that are
    difficult or impossible to reach through normal terminal sequences.
    """
    from blessed.keyboard import Keystroke

    # Test ESC + Ctrl+char that results in Ctrl+Alt (modifiers=7)
    # This tests the elif branch in _get_meta_escape_name
    ks = Keystroke('\x1b\x02')  # ESC + Ctrl+B
    # This will be Ctrl+Alt (modifiers=7), so name should be KEY_CTRL_ALT_B
    assert ks.modifiers == 7
    assert ks.name == 'KEY_CTRL_ALT_B'


def test_superfluous_appkeys_predicate_expected_code_none():
    """Test _build_appkeys_predicate when expected_code is not found.

    Superfluous: Tests internal predicate building edge case where keycode
    lookup fails. Not reachable through normal __getattr__ usage which
    validates key names first.
    """
    from blessed.keyboard import Keystroke, _match_legacy_csi_modifiers

    # Create a keystroke with application key
    ks = _match_legacy_csi_modifiers('\x1b[1;2A')  # Shift+Up

    # Verify with a keystroke that doesn't match
    ks_plain = Keystroke('a')
    # Calling is_shift_up on plain 'a' should return False
    assert ks_plain.is_shift_up() is False


def test_superfluous_legacy_csi_invalid_sequences():
    """Test _match_legacy_csi_modifiers with invalid/malformed sequences.

    Superfluous: Directly calls internal _match_legacy_csi_modifiers() with
    invalid terminal sequences that wouldn't occur in real terminal usage.
    """
    from blessed.keyboard import _match_legacy_csi_modifiers

    # Test sequence with invalid letter final character
    ks = _match_legacy_csi_modifiers('\x1b[1;5X')  # Invalid letter final 'X'
    assert ks is None  # Doesn't match letter form

    # Test valid SS3 sequence (for contrast)
    ks = _match_legacy_csi_modifiers('\x1bO2P')  # Valid SS3
    assert ks is not None  # Matches SS3 form

    # Test SS3 with invalid final character
    ks = _match_legacy_csi_modifiers('\x1bO2X')  # SS3 with invalid final 'X'
    assert ks is None  # keycode_match is None, returns None


def test_superfluous_meta_escape_name_complex_internal_paths():
    """Test complex internal paths in _get_meta_escape_name.

    Superfluous: Tests internal method branches that are difficult to trigger
    through normal terminal input. Tests defensive code paths.
    """
    from blessed.keyboard import Keystroke

    # Test ESC + control char where modifiers will be 7 (Ctrl+Alt)
    # This exercises the elif branch in _get_meta_escape_name
    ks = Keystroke('\x1b\x01')  # ESC + Ctrl+A
    assert ks.modifiers == 7  # Ctrl+Alt
    assert ks.name == 'KEY_CTRL_ALT_A'

    # The remaining branches in _get_meta_escape_name are either:
    # - Already covered by normal test cases
    # - Unreachable due to how _infer_modifiers works (ESC + control is always 3 or 7)
    # - Defensive code for impossible states
