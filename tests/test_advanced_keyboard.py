"""Tests for advanced keyboard protocol support (modifier inference and protocols)."""
# pylint: disable=too-many-lines
# std imports
import platform

# 3rd party
import pytest

# local
from .accessories import TestTerminal, as_subprocess

if platform.system() != 'Windows':
    import tty  # pylint: disable=unused-import  # NOQA
    import curses
else:
    import jinxed as curses  # pylint: disable=import-error


# ============================================================================
# Legacy Ctrl+Alt modifiers (metaSendsEscape + control char)
# ============================================================================

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
        ('\x1b\x01', 'KEY_CTRL_ALT_A'),
        ('\x1b\x06', 'KEY_CTRL_ALT_F'),
        ('\x1b\x1a', 'KEY_CTRL_ALT_Z'),
        ('\x1b\x00', 'KEY_CTRL_ALT_@'),
        ('\x1b\x08', 'KEY_CTRL_ALT_H'),
    ]

    for sequence, expected_key_name in ctrl_alt_cases:
        ks = Keystroke(sequence)
        assert ks.modifiers == 7
        assert ks._ctrl is True
        assert ks._alt is True
        assert ks._shift is False
        assert len(ks) == 2
        assert ks[0] == '\x1b'
        assert ks.name == expected_key_name

    alt_only_cases = [
        ('\x1b\x1b', 'KEY_ALT_ESCAPE'),
        ('\x1b\x7f', 'KEY_ALT_BACKSPACE'),
        ('\x1b\x0d', 'KEY_ALT_ENTER'),
        ('\x1b\x09', 'KEY_ALT_TAB'),
    ]

    for sequence, expected_name in alt_only_cases:
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


# ============================================================================
# Legacy CSI modifiers (ESC [ 1 ; modifiers [ABCDEFHPQRS] and tilde forms)
# ============================================================================

def test_match_legacy_csi_modifiers_letter_form():
    """Test legacy CSI modifier sequences in letter form."""
    from blessed.keyboard import _match_legacy_csi_modifiers, LegacyCSIKeyEvent

    # ESC [ 1 ; modifiers [ABCDEFHPQS]
    test_cases = [
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
        assert ks.name == expected_key_name


def test_match_legacy_csi_modifiers_tilde_form():
    """Test legacy CSI modifier sequences in tilde form."""
    from blessed.keyboard import _match_legacy_csi_modifiers, LegacyCSIKeyEvent

    # ESC [ number ; modifiers ~
    test_cases = [
        ('\x1b[2;2~', 2, 2, 'KEY_SHIFT_INSERT'),
        ('\x1b[3;5~', 3, 5, 'KEY_CTRL_DELETE'),
        ('\x1b[5;3~', 5, 3, 'KEY_ALT_PGUP'),
        ('\x1b[6;6~', 6, 6, 'KEY_CTRL_SHIFT_PGDOWN'),
        ('\x1b[15;2~', 15, 2, 'KEY_SHIFT_F5'),
        ('\x1b[17;5~', 17, 5, 'KEY_CTRL_F6'),
        ('\x1b[23;3~', 23, 3, 'KEY_ALT_F11'),
        ('\x1b[24;7~', 24, 7, 'KEY_CTRL_ALT_F12'),
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


# ============================================================================
# Event types (pressed, repeated, released)
# ============================================================================

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
