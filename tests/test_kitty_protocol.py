# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""Tests specific to Kitty keyboard protocol features."""
import io
import os
import sys
import pty
import time
import math
import pytest

from blessed import Terminal
from blessed.keyboard import (
    KEY_LEFT_SHIFT, KEY_LEFT_CONTROL, KEY_RIGHT_ALT,
    _match_legacy_csi_modifiers,
    _match_kitty_key, KittyKeyEvent, Keystroke, KittyKeyboardProtocol, resolve_sequence,
)

from blessed.dec_modes import DecPrivateMode
from tests.accessories import (as_subprocess, SEMAPHORE, TestTerminal,
                               echo_off, read_until_eof, read_until_semaphore,
                               init_subproc_coverage)
from tests.conftest import IS_WINDOWS, TEST_KEYBOARD

# Skip PTY tests on Windows and build farms
pytestmark = pytest.mark.skipif(
    IS_WINDOWS,
    reason="PTY tests not supported on Windows")

# kitty keyboard sequence tests


def test_match_kitty_basic():
    """Basic Kitty protocol sequences."""
    ks = _match_kitty_key('\x1b[97u')
    assert ks is not None
    assert ks._mode == DecPrivateMode.SpecialInternalKitty
    assert isinstance(ks._match, KittyKeyEvent)

    event = ks._match
    assert event.unicode_key == 97
    assert event.shifted_key is None
    assert event.base_key is None
    assert event.modifiers == 1
    assert event.event_type == 1
    assert event.int_codepoints == ()


def test_match_kitty_with_modifiers():
    """Test Kitty protocol with modifiers."""
    # ESC [ key ; modifiers u
    ks = _match_kitty_key('\x1b[97;5u')  # Ctrl+a
    assert ks is not None
    event = ks._match
    assert event.unicode_key == 97
    assert event.modifiers == 5  # 1 + 4 (ctrl)


def test_match_kitty_with_shifted_key():
    """Test Kitty protocol with shifted key."""
    # ESC [ key : shifted_key ; modifiers u
    ks = _match_kitty_key('\x1b[97:65;2u')  # Shift+a (uppercase A)
    assert ks is not None
    event = ks._match
    assert event.unicode_key == 97
    assert event.shifted_key == 65  # ASCII 'A'
    assert event.modifiers == 2  # 1 + 1 (shift)


def test_match_kitty_with_base_key():
    """Test Kitty protocol with base layout key."""
    # ESC [ key : shifted_key : base_key ; modifiers u
    ks = _match_kitty_key('\x1b[1089::99;5u')  # Ctrl+С (Cyrillic) -> Ctrl+c
    assert ks is not None
    event = ks._match
    assert event.unicode_key == 1089  # Cyrillic С
    assert event.shifted_key is None
    assert event.base_key == 99  # ASCII 'c'
    assert event.modifiers == 5  # 1 + 4 (ctrl)


def test_match_kitty_with_event_type():
    """Test Kitty protocol with event type."""
    # ESC [ key ; modifiers : event_type u
    ks = _match_kitty_key('\x1b[97;1:3u')  # 'a' key release
    assert ks is not None
    event = ks._match
    assert event.unicode_key == 97
    assert event.modifiers == 1
    assert event.event_type == 3  # release event


def test_match_kitty_with_codepoints():
    """Test Kitty protocol with text codepoints."""
    # ESC [ key ; modifiers : event_type ; text_codepoints u
    ks = _match_kitty_key('\x1b[97;2;65u')  # Shift+a with text 'A'
    assert ks is not None
    event = ks._match
    assert event.unicode_key == 97
    assert event.modifiers == 2
    assert event.int_codepoints == (65,)  # ASCII 'A'


def test_match_kitty_complex():
    """Test complex Kitty protocol sequence."""
    # Full form with all parameters
    ks = _match_kitty_key('\x1b[97:65:99;6:2;65:66u')
    assert ks is not None
    event = ks._match
    assert event.unicode_key == 97
    assert event.shifted_key == 65
    assert event.base_key == 99
    assert event.modifiers == 6  # 1 + 1 (shift) + 4 (ctrl)
    assert event.event_type == 2  # repeat event
    assert event.int_codepoints == (65, 66)  # 'AB'


def test_match_kitty_non_matching():
    """Test that non-Kitty sequences don't match."""
    assert _match_kitty_key('a') is None
    assert _match_kitty_key('\x1b[A') is None  # Regular arrow key
    assert _match_kitty_key('\x1b[97') is None  # Incomplete sequence
    assert _match_kitty_key('\x1b]97u') is None  # Wrong CSI
    assert _match_kitty_key('\x1b[97v') is None  # Wrong terminator


def test_kitty_modifier_encoding():
    """Test Kitty modifier encoding according to spec."""
    # Test all modifier combinations
    modifiers = {
        'shift': 2,      # 1 + 1
        'alt': 3,        # 1 + 2
        'ctrl': 5,       # 1 + 4
        'super': 9,      # 1 + 8
        'hyper': 17,     # 1 + 16
        'meta': 33,      # 1 + 32
        'caps_lock': 65,  # 1 + 64
        'num_lock': 129,  # 1 + 128
        'ctrl+shift': 6,  # 1 + 1 + 4
        'ctrl+alt': 7,   # 1 + 2 + 4
    }

    for mod_value in modifiers.values():
        ks = _match_kitty_key(f'\x1b[97;{mod_value}u')  # 'a' with modifier
        assert ks is not None
        assert ks._match.modifiers == mod_value


def test_full_sequence_string_matching():
    """Test that the full sequence strings match correctly."""
    # Test that the sequence property contains the full matched string
    ks = _match_kitty_key('\x1b[97;5u')
    assert str(ks) == '\x1b[97;5u'


def test_sequence_properties():
    """Test Keystroke properties for Kitty protocol."""
    # Test Kitty sequence
    ks = _match_kitty_key('\x1b[97;5u')
    assert ks.is_sequence is True
    assert ks._mode == DecPrivateMode.SpecialInternalKitty
    assert ks._code is None  # No traditional keycode for these protocols


def test_terminal_inkey_kitty_protocol():
    """Test that Terminal.inkey() properly handles Kitty keyboard protocol sequences."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)

        # Simulate Kitty protocol input by adding to keyboard buffer
        # Basic Kitty sequence: Ctrl+a
        kitty_sequence = '\x1b[97;5u'
        term.ungetch(kitty_sequence)

        ks = term.inkey(timeout=0)

        # Should have been parsed as a Kitty protocol sequence
        assert ks is not None
        assert ks == kitty_sequence
        assert ks._mode == DecPrivateMode.SpecialInternalKitty
        assert isinstance(ks._match, KittyKeyEvent)

        # Verify the parsed event data
        event = ks._match
        assert event.unicode_key == 97  # 'a'
        assert event.modifiers == 5     # Ctrl modifier
        assert stream.getvalue() == ''
    child()


def test_terminal_inkey_kitty_precedence():
    """Test that Kitty protocol is checked before legacy sequences."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)

        # Add a sequence that could potentially match legacy patterns
        # but should be caught by Kitty protocol first
        kitty_sequence = '\x1b[65u'  # 'A' key in Kitty protocol
        term.ungetch(kitty_sequence)

        ks = term.inkey(timeout=0)

        # Should be parsed as Kitty, not as legacy sequence
        assert ks._mode == DecPrivateMode.SpecialInternalKitty
        event = ks._match
        assert event.unicode_key == 65  # 'A'
        assert stream.getvalue() == ''
    child()


def test_terminal_inkey_kitty_buffer_handling():
    """Test that input buffer is properly managed with Kitty protocol."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)

        # Add a Kitty sequence followed by extra characters
        sequence_with_extra = '\x1b[97;5u' + 'extra'
        term.ungetch(sequence_with_extra)

        ks = term.inkey(timeout=0)

        # Should parse just the Kitty sequence
        assert ks == '\x1b[97;5u'
        assert ks._mode == DecPrivateMode.SpecialInternalKitty

        # Extra characters should still be in buffer
        remaining = term.inkey(timeout=0)
        assert remaining == 'e'  # First character of 'extra'
        assert stream.getvalue() == ''
    child()


def test_terminal_inkey_kitty_modifier_combinations():
    """Test various modifier combinations work correctly with Terminal.inkey()."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)

        # Test Ctrl+Alt+Shift combination (1 + 2 + 1 + 4 = 8)
        kitty_complex = '\x1b[97;8u'  # Ctrl+Alt+Shift+a
        term.ungetch(kitty_complex)

        ks = term.inkey(timeout=0)
        event = ks._match

        assert event.unicode_key == 97
        assert event.modifiers == 8  # Ctrl+Alt+Shift combination
        assert stream.getvalue() == ''
    child()


def test_kitty_functional_keys():
    """Test Kitty protocol with functional keys from the specification."""
    # Test some functional keys that are specifically mentioned in the spec
    # These use the private use area codes
    functional_keys = {
        '\x1b[57358u': 'CAPS_LOCK',     # 57358 u
        '\x1b[57359u': 'SCROLL_LOCK',   # 57359 u
        '\x1b[57360u': 'NUM_LOCK',      # 57360 u
        '\x1b[57361u': 'PRINT_SCREEN',  # 57361 u
        '\x1b[57362u': 'PAUSE',         # 57362 u
        '\x1b[57363u': 'MENU',          # 57363 u
    }

    for sequence in functional_keys:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        assert ks._mode == DecPrivateMode.SpecialInternalKitty
        # The unicode_key should be the private use area code
        expected_code = int(sequence.split('[')[1].split('u')[0])
        assert ks._match.unicode_key == expected_code


def test_kitty_f_keys():
    """Test Kitty protocol with F13-F35 keys."""
    # Test extended F keys that are specific to Kitty protocol
    f_keys = {
        '\x1b[57376u': 'F13',  # 57376 u
        '\x1b[57377u': 'F14',  # 57377 u
        '\x1b[57398u': 'F35',  # 57398 u
    }

    for sequence in f_keys:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        assert ks._mode == DecPrivateMode.SpecialInternalKitty
        expected_code = int(sequence.split('[')[1].split('u')[0])
        assert ks._match.unicode_key == expected_code


def test_kitty_keypad_keys():
    """Test Kitty protocol with keypad keys."""
    # Test keypad keys that are specific to Kitty protocol
    keypad_keys = {
        '\x1b[57399u': 'KP_0',      # 57399 u
        '\x1b[57409u': 'KP_DECIMAL',  # 57409 u
        '\x1b[57414u': 'KP_ENTER',  # 57414 u
    }

    for sequence, expected_key in keypad_keys.items():
        ks = _match_kitty_key(sequence)
        assert ks is not None, f"Failed to match {expected_key}"
        assert ks._mode == DecPrivateMode.SpecialInternalKitty
        expected_code = int(sequence.split('[')[1].split('u')[0])
        assert ks._match.unicode_key == expected_code


def test_kitty_protocol_modifier_properties():
    """Test that Kitty protocol keystrokes have correct modifier properties."""
    # Test Ctrl+Alt+a
    ks = _match_kitty_key('\x1b[97;7u')  # 1 + 2 + 4 = 7
    assert ks._ctrl is True
    assert ks._alt is True
    assert ks._shift is False
    assert ks._super is False
    assert ks.value == 'a'
    assert ks.is_ctrl_alt('a')

    # Test with caps lock
    ks = _match_kitty_key('\x1b[97;69u')  # 1 + 4 + 64 = 69 (ctrl + a w/caps_lock)
    assert ks._ctrl is True
    assert ks._caps_lock is True
    assert ks._alt is False
    assert ks.value == 'a'
    assert ks.is_ctrl('a')


def test_kitty_protocol_is_ctrl_is_alt():
    """Test is_ctrl() and is_alt() methods work with Kitty protocol."""
    # Exactly Ctrl+a
    ks = _match_kitty_key('\x1b[97;5u')  # Ctrl+a
    assert ks.is_ctrl('a') is True
    assert ks.is_ctrl('A') is True  # Case insensitive
    assert ks.is_ctrl('b') is False
    assert ks.is_ctrl() is False

    # Exactly Alt+a
    ks = _match_kitty_key('\x1b[97;3u')  # Alt+a
    assert ks.is_alt('a') is True
    assert ks.is_alt('A') is True  # Case insensitive by default
    assert ks.is_alt('b') is False
    assert ks.is_alt() is True  # Any alt

    # Ctrl+Alt+a should NOT match exact is_ctrl('a') or is_alt('a')
    ks = _match_kitty_key('\x1b[97;7u')  # Ctrl+Alt+a
    assert ks.is_ctrl('a') is False  # Not exactly ctrl
    assert ks.is_alt('a') is False   # Not exactly alt

# KittyKeyboardProtocol class tests


def test_kitty_keyboard_protocol_parsing_flags_response():
    """Test parsing of Kitty keyboard flags response."""
    # Test that we can parse different flag values correctly
    test_cases = [
        (0, False, False, False, False, False),   # no flags
        (1, True, False, False, False, False),    # disambiguate only
        (2, False, True, False, False, False),    # report_events only
        (4, False, False, True, False, False),    # report_alternates only
        (8, False, False, False, True, False),    # report_all_keys only
        (16, False, False, False, False, True),   # report_text only
        (31, True, True, True, True, True),       # all flags
        (5, True, False, True, False, False),     # disambiguate + report_alternates
        (9, True, False, False, True, False),     # disambiguate + report_all_keys
        (18, False, True, False, False, True),    # report_events + report_text
    ]

    for value, dis, events, alt, all_keys, text in test_cases:
        proto = KittyKeyboardProtocol(value)
        assert proto.value == value
        assert proto.disambiguate == dis
        assert proto.report_events == events
        assert proto.report_alternates == alt
        assert proto.report_all_keys == all_keys
        assert proto.report_text == text


def test_kitty_keyboard_protocol_make_arguments():
    """Test KittyKeyboardProtocol.make_arguments() method."""
    # Test with no flags
    proto = KittyKeyboardProtocol(0)
    args = proto.make_arguments()
    expected = {
        'disambiguate': False,
        'report_events': False,
        'report_alternates': False,
        'report_all_keys': False,
        'report_text': False
    }
    assert args == expected

    # Test with all flags
    proto = KittyKeyboardProtocol(31)  # 0b11111
    args = proto.make_arguments()
    expected = {
        'disambiguate': True,
        'report_events': True,
        'report_alternates': True,
        'report_all_keys': True,
        'report_text': True
    }
    assert args == expected


def test_kitty_keyboard_protocol_repr():
    """Test KittyKeyboardProtocol string representation."""
    # Test with no flags
    proto = KittyKeyboardProtocol(0)
    repr_str = repr(proto)
    assert 'KittyKeyboardProtocol(value=0' in repr_str
    assert 'flags=[]' in repr_str

    # Test with all flags
    proto = KittyKeyboardProtocol(31)
    repr_str = repr(proto)
    assert 'KittyKeyboardProtocol(value=31' in repr_str
    assert 'disambiguate' in repr_str
    assert 'report_events' in repr_str
    assert 'report_alternates' in repr_str
    assert 'report_all_keys' in repr_str
    assert 'report_text' in repr_str


def test_kitty_keyboard_protocol_equality():
    """Test KittyKeyboardProtocol equality comparison."""
    proto1 = KittyKeyboardProtocol(5)
    proto2 = KittyKeyboardProtocol(5)
    proto3 = KittyKeyboardProtocol(10)

    # Test equality with same value
    assert proto1 == proto2
    assert proto1 == 5
    assert proto2 == 5

    # Test inequality with different values
    assert proto1 != proto3
    assert proto1 != 10
    assert proto1 != "not an int"


# PTY-based success tests

@pytest.mark.skipif(not TEST_KEYBOARD, reason="TEST_KEYBOARD not specified")
def test_get_kitty_keyboard_state_pty_success():
    """PTY test: get_kitty_keyboard_state with successful terminal response."""
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_get_kitty_keyboard_state_pty_success')
        term = TestTerminal()

        # Signal readiness and query Kitty state
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        flags = term.get_kitty_keyboard_state(timeout=0.1)

        # Write result to stdout for parent verification
        if flags is not None:
            os.write(sys.__stdout__.fileno(), str(flags.value).encode('ascii'))
        else:
            os.write(sys.__stdout__.fileno(), b'None')

        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        # Wait for child readiness
        read_until_semaphore(master_fd)
        stime = time.time()
        # Send both Kitty protocol flags response and DA1 response for boundary detection
        # flags=27: all basic flags set, and a DA1 response indicating VT terminal
        os.write(master_fd, u'\x1b[?27u\x1b[?64c'.encode('ascii'))
        output = read_until_eof(master_fd)

    pid, status = os.waitpid(pid, 0)
    # first call to get_kitty_keyboard_state causes both kitty and dec
    # parameters query to output, we faked a "response" that by writing to our
    # master pty side
    assert output == u'\x1b[?u\x1b[c' + '27'  # Should have parsed flags value 27
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


@pytest.mark.skipif(not TEST_KEYBOARD, reason="TEST_KEYBOARD not specified")
def test_enable_kitty_keyboard_pty_success():
    """PTY test: enable_kitty_keyboard with set and restore sequences."""
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_enable_kitty_keyboard_pty_success')
        term = TestTerminal()

        # Signal readiness
        os.write(sys.__stdout__.fileno(), SEMAPHORE)

        # Use context manager with comprehensive flags (27 = 1+2+8+16)
        with term.enable_kitty_keyboard(
            disambiguate=True,
            report_events=True,
            report_all_keys=True,
            report_text=True,
            timeout=1.0,
            force=True
        ):
            # Write marker to show we're inside the context
            os.write(sys.__stdout__.fileno(), b'INSIDE')

        # Write completion marker
        os.write(sys.__stdout__.fileno(), b'COMPLETE')

        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        # Wait for child readiness
        read_until_semaphore(master_fd)
        stime = time.time()

        # Send initial state response when child queries current flags (9 =
        # disambiguate + report_all_keys)
        os.write(master_fd, u'\x1b[?9u'.encode('ascii'))

        # Read all output from child
        output = read_until_eof(master_fd)

    pid, status = os.waitpid(pid, 0)

    # Verify child completed successfully
    assert 'INSIDE' in output
    assert 'COMPLETE' in output
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


# Interactive kitty mode tests

def test_kitty_state_0s_reply_via_ungetch():
    """0-second get_kitty_keyboard_state call with response via ungetch."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = True  # Force TTY behavior for testing
        stime = time.time()
        # Simulate Kitty keyboard state response - flags value 9 (disambiguate + report_all_keys)
        # Need both Kitty and DA response for boundary approach on first call
        term.ungetch(u'\x1b[?9u\x1b[?64c')

        flags = term.get_kitty_keyboard_state(timeout=0.01)
        assert math.floor(time.time() - stime) == 0.0
        assert flags is not None
        assert flags.value == 9
        assert flags.disambiguate is True
        assert flags.report_all_keys is True
        assert flags.report_events is False
    child()


def test_kitty_state_styling_indifferent():
    """Ensure get_kitty_keyboard_state() behavior is the same regardless of styling."""
    @as_subprocess
    def child():
        # Test with styling enabled
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = True  # Force TTY behavior for testing
        # Need both Kitty and DA response for boundary approach on first call
        term.ungetch(u'\x1b[?15u\x1b[?64c')  # flags value 15 (multiple flags)
        flags = term.get_kitty_keyboard_state(timeout=0.01)
        assert flags is not None
        assert flags.value == 15
        assert flags.disambiguate is True
        assert flags.report_events is True
        assert flags.report_alternates is True
        assert flags.report_all_keys is True  # bit 3 (8) is set in value 15
        assert flags.report_text is False

        # Test with styling disabled - should return None (not query)
        term = TestTerminal(stream=io.StringIO(), force_styling=False)
        term._is_a_tty = True
        term.ungetch(u'\x1b[?15u')
        flags = term.get_kitty_keyboard_state(timeout=0.01)
        assert flags is None
    child()


def test_kitty_state_timeout_handling():
    """Test get_kitty_keyboard_state timeout and sticky failure behavior."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = True  # Force TTY behavior for testing

        # Should have clean state initially
        assert term._kitty_kb_first_query_failed is False

        # First timeout should set sticky failure flag
        flags1 = term.get_kitty_keyboard_state(timeout=0.001)
        assert flags1 is None
        assert term._kitty_kb_first_query_failed is True

        # Subsequent calls should return None immediately (sticky failure)
        flags2 = term.get_kitty_keyboard_state(timeout=1.0)
        assert flags2 is None

        # Force should override sticky failure and attempt query again
        flags3 = term.get_kitty_keyboard_state(timeout=0.001, force=True)
        assert flags3 is None  # Still timeout, but sticky behavior was bypassed
    child()


def test_kitty_state_excludes_response_from_buffer():
    """get_kitty_keyboard_state should exclude response from buffer while preserving other data."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = True  # Force TTY behavior for testing
        # Buffer unrelated data before and after the kitty state response
        term.ungetch(u'abc' + u'\x1b[?13u' + u'xyz')

        # get_kitty_keyboard_state should parse and consume only the response
        # Use force=True to bypass boundary approach for this buffer management test
        flags = term.get_kitty_keyboard_state(timeout=0.01, force=True)
        assert flags is not None
        assert flags.value == 13

        # Remaining data should still be available for subsequent input
        remaining = u''
        while True:
            ks = term.inkey(timeout=0)
            if ks == u'':
                break
            remaining += ks
        assert remaining == u'abcxyz'
    child()


@pytest.mark.parametrize("force_styling,expected_sticky_flag", [
    (False, False),  # styling disabled -> no sticky flag
    (True, False),   # not a TTY -> no sticky flag
])
def test_get_kitty_keyboard_state_no_tty_or_disabled(force_styling, expected_sticky_flag):
    """Test get_kitty_keyboard_state returns None when not supported or not a TTY."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=force_styling)

        # Should return None immediately without attempting query
        result = term.get_kitty_keyboard_state(timeout=0.01)
        assert result is None
        assert term._kitty_kb_first_query_failed == expected_sticky_flag

        # All subsequent calls should return None
        result2 = term.get_kitty_keyboard_state(timeout=None)
        assert result2 is None

        # Force should also return None when not supported/not a TTY
        result3 = term.get_kitty_keyboard_state(timeout=0.01, force=True)
        assert result3 is None
        assert stream.getvalue() == ''
    child()


def test_enable_kitty_keyboard_handles_non_tty():
    """Test enable_kitty_keyboard handles non-TTY appropriately."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)

        # enable_kitty_keyboard should not emit sequences when not a TTY (unless force=True)
        with term.enable_kitty_keyboard(disambiguate=True, force=False):
            pass
        assert stream.getvalue() == ''

        # With force=True, should emit sequences even when not a TTY
        with term.enable_kitty_keyboard(disambiguate=True, force=True, timeout=0.01):
            pass
        assert stream.getvalue() == '\x1b[=1;1u'
    child()


def test_enable_kitty_keyboard_context_manager():
    """Test enable_kitty_keyboard context manager behavior."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)

        # Test that context manager exists and can be called
        with term.enable_kitty_keyboard(disambiguate=True, report_events=True):
            pass
        assert stream.getvalue() == ''

        # Test with all possible arguments (removed raw and push parameters)
        with term.enable_kitty_keyboard(
            disambiguate=False,
            report_events=True,
            report_alternates=True,
            report_all_keys=False,
            report_text=False,
            mode=2,
            timeout=0.1,
            force=True
        ):
            pass
        # Should have sequence to set flags (no previous flags to restore)
        assert stream.getvalue() == '\x1b[=6;2u'
    child()


def test_enable_kitty_keyboard_comprehensive_flags():
    """Test enable_kitty_keyboard with comprehensive flags (equivalent to old raw mode)."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)

        # Test comprehensive mode, should set:
        # disambiguate + report_events + report_all_keys + report_text)
        # flags = 1 + 2 + 8 + 16 = 27
        with term.enable_kitty_keyboard(
            disambiguate=True,
            report_events=True,
            report_all_keys=True,
            report_text=True,
            force=True,
            timeout=0.1
        ):
            pass
        # Should have sequence to set flags (no previous flags to restore)
        assert stream.getvalue() == '\x1b[=27;1u'
    child()


def test_enable_kitty_keyboard_no_styling():
    """Test enable_kitty_keyboard when styling is disabled."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=False)

        # Should work without error but do nothing
        with term.enable_kitty_keyboard(disambiguate=True):
            pass
        assert stream.getvalue() == ''
    child()


def test_kitty_keyboard_protocol_setters():
    """Test all KittyKeyboardProtocol property setters."""
    # Start with clean slate
    protocol = KittyKeyboardProtocol(0)
    assert protocol.value == 0
    assert not protocol.disambiguate
    assert not protocol.report_events
    assert not protocol.report_alternates
    assert not protocol.report_all_keys
    assert not protocol.report_text

    # Test setting each flag individually
    protocol.disambiguate = True
    assert protocol.value == 1  # 2^0 = 1
    assert protocol.disambiguate is True

    protocol.report_events = True
    assert protocol.value == 3  # 1 + 2 = 3
    assert protocol.report_events is True
    assert protocol.disambiguate is True  # Should still be True

    protocol.report_alternates = True
    assert protocol.value == 7  # 1 + 2 + 4 = 7
    assert protocol.report_alternates is True

    protocol.report_all_keys = True
    assert protocol.value == 15  # 1 + 2 + 4 + 8 = 15
    assert protocol.report_all_keys is True

    protocol.report_text = True
    assert protocol.value == 31  # 1 + 2 + 4 + 8 + 16 = 31
    assert protocol.report_text is True


def test_kitty_keyboard_protocol_setters_clearing():
    """Test clearing KittyKeyboardProtocol property flags."""
    # Start with all flags set
    protocol = KittyKeyboardProtocol(31)  # All 5 flags set
    assert protocol.value == 31
    assert all([
        protocol.disambiguate,
        protocol.report_events,
        protocol.report_alternates,
        protocol.report_all_keys,
        protocol.report_text
    ])

    # Clear flags one by one
    protocol.disambiguate = False
    assert protocol.value == 30  # 31 - 1 = 30
    assert not protocol.disambiguate
    assert protocol.report_events  # Others should remain

    protocol.report_events = False
    assert protocol.value == 28  # 30 - 2 = 28
    assert not protocol.report_events

    protocol.report_alternates = False
    assert protocol.value == 24  # 28 - 4 = 24
    assert not protocol.report_alternates

    protocol.report_all_keys = False
    assert protocol.value == 16  # 24 - 8 = 16
    assert not protocol.report_all_keys

    protocol.report_text = False
    assert protocol.value == 0  # 16 - 16 = 0
    assert not protocol.report_text


def test_kitty_keyboard_protocol_setters_independence():
    """Test that KittyKeyboardProtocol setters work independently."""
    protocol = KittyKeyboardProtocol(0)

    # Set every other flag
    protocol.disambiguate = True  # bit 0
    protocol.report_alternates = True  # bit 2
    protocol.report_text = True  # bit 4

    expected_value = 1 + 4 + 16  # = 21
    assert protocol.value == expected_value
    assert protocol.disambiguate is True
    assert protocol.report_events is False  # Should remain False
    assert protocol.report_alternates is True
    assert protocol.report_all_keys is False  # Should remain False
    assert protocol.report_text is True


def test_kitty_keyboard_protocol_setters_with_existing_values():
    """Test setters with pre-existing flag values."""
    # Start with some flags already set
    protocol = KittyKeyboardProtocol(15)  # First 4 flags set (1+2+4+8)
    assert protocol.disambiguate is True
    assert protocol.report_events is True
    assert protocol.report_alternates is True
    assert protocol.report_all_keys is True
    assert protocol.report_text is False

    # Turn off just one flag in the middle
    protocol.report_alternates = False  # Turn off bit 2
    expected = 15 - 4  # = 11
    assert protocol.value == expected
    assert protocol.disambiguate is True
    assert protocol.report_events is True
    assert protocol.report_alternates is False
    assert protocol.report_all_keys is True
    assert protocol.report_text is False


def test_get_kitty_keyboard_state_first_call_boundary_kitty_then_da():
    """Test boundary approach: Kitty response then DA response on first call."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)
        term._is_a_tty = True  # Force TTY behavior for testing

        # Buffer Kitty response followed by DA response (successful boundary case)
        term.ungetch(u'\x1b[?9u\x1b[?64;1;2;4c')  # Kitty flags 9, then DA with sixel

        flags = term.get_kitty_keyboard_state(timeout=0.01)

        # Should have successfully parsed Kitty flags
        assert flags is not None
        assert flags.value == 9
        assert flags.disambiguate is True
        assert flags.report_all_keys is True
        assert flags.report_events is False

        # Should have marked first query as attempted
        assert term._kitty_kb_first_query_attempted is True
        assert term._kitty_kb_first_query_failed is False
    child()


def test_get_kitty_keyboard_state_first_call_boundary_da_only():
    """Test boundary approach: DA response only (no Kitty) on first call."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)
        term._is_a_tty = True  # Force TTY behavior for testing

        # Buffer only DA response (no Kitty support)
        term.ungetch(u'\x1b[?64;1;2c')  # DA without sixel, no Kitty response

        flags = term.get_kitty_keyboard_state(timeout=0.01)

        # Should return None (no Kitty support detected)
        assert flags is None

        # Should have marked first query as attempted and failed
        assert term._kitty_kb_first_query_attempted is True
        assert term._kitty_kb_first_query_failed is True

        # Subsequent call should immediately return None (sticky failure)
        flags2 = term.get_kitty_keyboard_state(timeout=1.0)
        assert flags2 is None
    child()


def test_get_kitty_keyboard_state_first_call_boundary_timeout():
    """Test boundary approach: timeout on first call (no response)."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)
        term._is_a_tty = True  # Force TTY behavior for testing

        # No buffered response - will timeout

        flags = term.get_kitty_keyboard_state(timeout=0.001)

        # Should return None (timeout)
        assert flags is None

        # Should have marked first query as attempted and failed
        assert term._kitty_kb_first_query_attempted is True
        assert term._kitty_kb_first_query_failed is True

        # Subsequent call should immediately return None (sticky failure)
        flags2 = term.get_kitty_keyboard_state(timeout=1.0)
        assert flags2 is None
    child()


def test_get_kitty_keyboard_state_subsequent_call_uses_normal_query():
    """Test that after boundary approach, subsequent calls use normal single query."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)
        term._is_a_tty = True  # Force TTY behavior for testing

        # First call with successful boundary
        term.ungetch(u'\x1b[?15u\x1b[?64c')  # Kitty flags 15, then DA
        flags1 = term.get_kitty_keyboard_state(timeout=0.01)
        assert flags1 is not None
        assert flags1.value == 15
        assert term._kitty_kb_first_query_attempted is True
        assert term._kitty_kb_first_query_failed is False

        # Second call should use normal single-query approach
        term.ungetch(u'\x1b[?7u')  # Just Kitty response (no DA needed)
        flags2 = term.get_kitty_keyboard_state(timeout=0.01)
        assert flags2 is not None
        assert flags2.value == 7
    child()


def test_get_kitty_keyboard_state_force_bypasses_boundary():
    """Test that force=True bypasses boundary approach even on first call."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)
        term._is_a_tty = True  # Force TTY behavior for testing

        # Buffer only Kitty response (no DA)
        term.ungetch(u'\x1b[?13u')  # Just Kitty flags, no DA

        # First call with force=True should bypass boundary approach
        flags = term.get_kitty_keyboard_state(timeout=0.01, force=True)

        # Should have successfully parsed Kitty flags (no DA required)
        assert flags is not None
        assert flags.value == 13

        # Should not have marked first query as attempted (force bypassed boundary logic)
        assert term._kitty_kb_first_query_attempted is False
        assert term._kitty_kb_first_query_failed is False
    child()


def test_kitty_keyboard_protocol_setters_all_combinations():
    """Test all possible flag combinations work correctly."""
    # Test a comprehensive set of flag combinations
    test_cases = [
        {'disambiguate': True, 'expected': 1},
        {'report_events': True, 'expected': 2},
        {'report_alternates': True, 'expected': 4},
        {'report_all_keys': True, 'expected': 8},
        {'report_text': True, 'expected': 16},
        {'disambiguate': True, 'report_events': True, 'expected': 3},
        {'disambiguate': True, 'report_alternates': True, 'expected': 5},
        {'report_events': True, 'report_all_keys': True, 'expected': 10},
        {'report_alternates': True, 'report_text': True, 'expected': 20},
        {'disambiguate': True, 'report_events': True, 'report_alternates': True, 'expected': 7},
        {'report_all_keys': True, 'report_text': True, 'disambiguate': True, 'expected': 25},
    ]

    for case in test_cases:
        protocol = KittyKeyboardProtocol(0)
        expected = case.pop('expected')

        # Set the specified flags
        for flag_name, flag_value in case.items():
            setattr(protocol, flag_name, flag_value)

        assert protocol.value == expected

        # Verify individual flag values
        for flag_name, expected_flag_value in case.items():
            actual_flag_value = getattr(protocol, flag_name)
            assert actual_flag_value == expected_flag_value


def test_kitty_digit_name_synthesis():
    """Test Kitty keyboard protocol digit name synthesis with modifiers."""
    # Test digit name synthesis for Kitty sequences
    digit_test_cases = [
        ('\x1b[49;3u', 'KEY_ALT_1', 'Alt+1'),       # ASCII '1' = 49
        ('\x1b[49;5u', 'KEY_CTRL_1', 'Ctrl+1'),
        ('\x1b[49;4u', 'KEY_ALT_SHIFT_1', 'Alt+Shift+1'),  # Alt(2) + Shift(1) + base(1) = 4
        ('\x1b[50;3u', 'KEY_ALT_2', 'Alt+2'),       # ASCII '2' = 50
        ('\x1b[57;5u', 'KEY_CTRL_9', 'Ctrl+9'),     # ASCII '9' = 57
        ('\x1b[48;7u', 'KEY_CTRL_ALT_0', 'Ctrl+Alt+0'),  # ASCII '0' = 48, modifiers=7 (1+2+4)
    ]

    for sequence, expected_name, description in digit_test_cases:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        assert ks._mode == DecPrivateMode.SpecialInternalKitty
        assert ks.name == expected_name

    # Test that digits without modifiers don't get names (same as letters)
    ks_plain = _match_kitty_key('\x1b[49u')  # Plain '1' without modifiers
    assert ks_plain is not None
    assert ks_plain.name is None

    # Test that existing letter name synthesis still works
    ks_letter = _match_kitty_key('\x1b[97;3u')  # Alt+a
    assert ks_letter is not None
    assert ks_letter.name == 'KEY_ALT_A'


def test_kitty_letter_name_synthesis_basic_modifiers():
    """Test Kitty protocol letter name synthesis for basic modifier combinations."""
    # Test basic modifier combinations for letter 'a' (unicode_key=97)
    test_cases = [
        ('\x1b[97;5u', 'KEY_CTRL_A', 'Ctrl+a'),
        ('\x1b[97;3u', 'KEY_ALT_A', 'Alt+a'),
        ('\x1b[97;7u', 'KEY_CTRL_ALT_A', 'Ctrl+Alt+a'),
        ('\x1b[97;2u', 'KEY_SHIFT_A', 'Shift+a'),
        ('\x1b[97;6u', 'KEY_CTRL_SHIFT_A', 'Ctrl+Shift+a'),
        ('\x1b[97;4u', 'KEY_ALT_SHIFT_A', 'Alt+Shift+a'),
        ('\x1b[97;8u', 'KEY_CTRL_ALT_SHIFT_A', 'Ctrl+Alt+Shift+a'),
    ]

    for sequence, expected_name, description in test_cases:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        assert ks.name == expected_name
        assert ks._mode == DecPrivateMode.SpecialInternalKitty


def test_kitty_letter_name_synthesis_different_letters():
    """Test Kitty letter name synthesis works for different letters."""
    # Test various letters with Ctrl modifier
    letters_test_cases = [
        ('\x1b[65;5u', 'KEY_CTRL_A', 'A'),  # uppercase A
        ('\x1b[90;5u', 'KEY_CTRL_Z', 'Z'),  # uppercase Z
        ('\x1b[97;5u', 'KEY_CTRL_A', 'a'),  # lowercase a
        ('\x1b[122;5u', 'KEY_CTRL_Z', 'z'),  # lowercase z
        ('\x1b[77;3u', 'KEY_ALT_M', 'M'),   # Alt+M
        ('\x1b[109;3u', 'KEY_ALT_M', 'm'),  # Alt+m
    ]

    for sequence, expected_name, letter in letters_test_cases:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        assert ks.name == expected_name


def test_kitty_letter_name_synthesis_base_key_preference():
    """Test that base_key is preferred over unicode_key for letter naming."""
    # Test Cyrillic 'С' (unicode_key=1089) with base_key='c' (99)
    # Should synthesize name based on base_key 'c' -> 'KEY_CTRL_C'
    ks = _match_kitty_key('\x1b[1089::99;5u')  # Ctrl+Cyrillic С with base_key c
    assert ks is not None
    assert ks.name == 'KEY_CTRL_C'

    # Test when base_key is not present, should fall back to unicode_key
    ks = _match_kitty_key('\x1b[97;5u')  # Ctrl+a, no base_key
    assert ks is not None
    assert ks.name == 'KEY_CTRL_A'


def test_kitty_letter_name_synthesis_event_type_filtering():
    """Test that only keypress events (event_type=1) get synthesized names."""
    # Test keypress event (event_type=1) - should get name
    ks = _match_kitty_key('\x1b[97;5:1u')  # Ctrl+a keypress
    assert ks is not None
    assert ks.name == 'KEY_CTRL_A'

    # Test key release event (event_type=3) - should NOT get name
    ks = _match_kitty_key('\x1b[97;5:3u')  # Ctrl+a key release
    assert ks is not None
    assert ks.name is None

    # Test key repeat event (event_type=2) - should NOT get name
    ks = _match_kitty_key('\x1b[97;5:2u')  # Ctrl+a key repeat
    assert ks is not None
    assert ks.name is None

    # Test default event_type (1) - should get name
    ks = _match_kitty_key('\x1b[97;5u')  # Ctrl+a (default event_type=1)
    assert ks is not None
    assert ks.name == 'KEY_CTRL_A'


def test_kitty_letter_name_synthesis_non_letters_no_name():
    """Test that non-letter, non-digit keys do not get synthesized names."""
    # Test symbols and space - should not get names even with modifiers
    # (digits now DO get names with modifiers, so they're excluded from this test)
    # Special case: '[' always gets 'CSI' name
    non_letter_non_digit_cases = [
        ('\x1b[32;5u', 'Ctrl+Space', None),     # space
        ('\x1b[33;3u', 'Alt+!', None),          # exclamation
        ('\x1b[59;5u', 'Ctrl+;', None),         # semicolon
        ('\x1b[46;3u', 'Alt+.', None),          # period
        ('\x1b[64;5u', 'Ctrl+@', None),         # @ symbol
        ('\x1b[91;3u', 'Alt+[', 'CSI'),         # bracket - special case
    ]

    for sequence, description, expected_name in non_letter_non_digit_cases:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        if expected_name is None:
            assert ks.name is None
        else:
            assert ks.name == expected_name


def test_kitty_letter_name_synthesis_no_modifiers_no_name():
    """Test that plain letters without modifiers do not get synthesized names."""
    # Test plain letters (modifiers=1, meaning no modifiers) - should not get names
    plain_letter_cases = [
        ('\x1b[97;1u', 'a'),   # plain 'a'
        ('\x1b[65;1u', 'A'),   # plain 'A'
        ('\x1b[122;1u', 'z'),  # plain 'z'
        ('\x1b[90;1u', 'Z'),   # plain 'Z'
        ('\x1b[97u', 'a'),     # plain 'a' (default modifiers=1)
    ]

    for sequence, description in plain_letter_cases:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        assert ks.name is None


def test_kitty_letter_name_synthesis_supports_advanced_modifiers():
    """Test that advanced modifiers (super/hyper/meta) are supported in letter naming."""
    # Test that super/hyper/meta DO appear in letter names (new behavior)
    advanced_modifier_cases = [
        ('\x1b[97;9u', 'KEY_SUPER_A'),       # super (1+8=9) - should get name
        ('\x1b[97;17u', 'KEY_HYPER_A'),      # hyper (1+16=17) - should get name
        ('\x1b[97;33u', 'KEY_META_A'),        # meta (1+32=33) - should get name
        ('\x1b[97;13u', 'KEY_CTRL_SUPER_A'),  # ctrl+super (1+4+8=13) - should get both
        ('\x1b[97;11u', 'KEY_ALT_SUPER_A'),    # alt+super (1+2+8=11) - should get both
    ]

    for sequence, expected_name in advanced_modifier_cases:
        ks = _match_kitty_key(sequence)
        assert ks.name == expected_name


def test_kitty_letter_name_synthesis_preserves_explicit_names():
    """Test that explicitly set names are preserved over synthesized names."""
    # Create a Kitty keystroke with explicit name - should preserve it
    kitty_event = KittyKeyEvent(unicode_key=97, shifted_key=None, base_key=None,
                                modifiers=5, event_type=1, int_codepoints=())
    ks = Keystroke('\x1b[97;5u', name='CUSTOM_NAME',
                   mode=DecPrivateMode.SpecialInternalKitty, match=kitty_event)

    assert ks.name == 'CUSTOM_NAME'


def test_kitty_letter_name_synthesis_integration():
    """Test Kitty letter name synthesis integration with existing Terminal.inkey()."""
    @as_subprocess
    def child():
        term = Terminal(force_styling=True)

        # Test that Terminal.inkey() correctly synthesizes Kitty letter names
        test_sequences = [
            ('\x1b[97;5u', 'KEY_CTRL_A'),
            ('\x1b[122;3u', 'KEY_ALT_Z'),
            ('\x1b[77;7u', 'KEY_CTRL_ALT_M'),
            ('\x1b[98;6u', 'KEY_CTRL_SHIFT_B'),
        ]

        for sequence, expected_name in test_sequences:
            term.ungetch(sequence)
            ks = term.inkey(timeout=0)

            assert ks == sequence
            assert ks.name == expected_name
            assert ks._mode == DecPrivateMode.SpecialInternalKitty

    child()


def test_kitty_letter_name_synthesis_case_normalization():
    """Test that letter names are normalized to uppercase regardless of input case."""
    # Test both uppercase and lowercase unicode keys produce uppercase names
    case_test_cases = [
        ('\x1b[97;5u', 'KEY_CTRL_A'),   # lowercase 'a' -> 'KEY_CTRL_A'
        ('\x1b[65;5u', 'KEY_CTRL_A'),   # uppercase 'A' -> 'KEY_CTRL_A'
        ('\x1b[122;3u', 'KEY_ALT_Z'),   # lowercase 'z' -> 'KEY_ALT_Z'
        ('\x1b[90;3u', 'KEY_ALT_Z'),    # uppercase 'Z' -> 'KEY_ALT_Z'
    ]

    for sequence, expected_name in case_test_cases:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        assert ks.name == expected_name


def test_kitty_letter_name_synthesis_modifier_ordering():
    """Test that modifier ordering in names follows legacy pattern: CTRL_ALT_SHIFT."""
    # Test various combinations to ensure consistent ordering
    ordering_test_cases = [
        ('\x1b[97;6u', 'KEY_CTRL_SHIFT_A'),     # ctrl+shift (1+4+1=6)
        ('\x1b[97;4u', 'KEY_ALT_SHIFT_A'),       # alt+shift (1+2+1=4)
        ('\x1b[97;8u', 'KEY_CTRL_ALT_SHIFT_A'),  # all three (1+4+2+1=8)
    ]

    for sequence, expected_name in ordering_test_cases:
        ks = _match_kitty_key(sequence)
        assert ks.name == expected_name


def test_disambiguate_f1_f4_csi_sequences():
    """Test that F1-F4 are recognized in disambiguate mode (CSI format)."""
    @as_subprocess
    def child():
        term = Terminal(force_styling=True)

        # Get keyboard sequences and codes for resolution
        mapper = term._keymap
        codes = term._keycodes
        prefixes = set()

        # Test F1-F4 in disambiguate CSI format (not SS3)
        test_cases = [
            ('\x1b[P', 'KEY_F1', 'F1'),
            ('\x1b[Q', 'KEY_F2', 'F2'),
            ('\x1b[13~', 'KEY_F3', 'F3'),  # F3 uses tilde format
            ('\x1b[S', 'KEY_F4', 'F4'),
        ]

        for sequence, expected_name, description in test_cases:
            ks = resolve_sequence(sequence, mapper, codes, prefixes, final=True)
            assert ks is not None
            assert ks.name == expected_name
            assert str(ks) == sequence

    child()


def test_disambiguate_f1_f4_via_inkey():
    """Test that F1-F4 disambiguate sequences work through Terminal.inkey()."""
    @as_subprocess
    def child():
        term = Terminal(stream=io.StringIO(), force_styling=True)

        # Test F1-F4 in disambiguate CSI format
        test_cases = [
            ('\x1b[P', 'KEY_F1'),
            ('\x1b[Q', 'KEY_F2'),
            ('\x1b[13~', 'KEY_F3'),
            ('\x1b[S', 'KEY_F4'),
        ]

        for sequence, expected_name in test_cases:
            term.ungetch(sequence)
            ks = term.inkey(timeout=0)

            assert ks == sequence
            assert ks.name == expected_name

    child()


def test_disambiguate_f1_f4_not_confused_with_alt():
    """Test that disambiguate F1-F4 are not confused with ALT+[ sequences."""
    @as_subprocess
    def child():
        term = Terminal(stream=io.StringIO(), force_styling=True)

        # F1 should be \x1b[P, not confused with ALT+[ followed by P
        term.ungetch('\x1b[P')
        ks = term.inkey(timeout=0)

        # Should be recognized as F1, not as two separate keys
        assert ks.name == 'KEY_F1'
        assert str(ks) == '\x1b[P'
        assert len(ks) == 3

        # Verify no leftover input
        remaining = term.inkey(timeout=0)
        assert remaining == ''

    child()


def test_kitty_letter_name_synthesis_boundary_conditions():
    """Test boundary conditions for letter detection."""
    # Test edge cases around ASCII letter ranges
    boundary_cases = [
        ('\x1b[91;5u', 'CSI', '['),          # ASCII 91, just after 'Z' (90) - SPECIAL CASE
        ('\x1b[64;5u', None, '@'),           # ASCII 64, just before 'A' (65)
        ('\x1b[96;5u', None, '`'),           # ASCII 96, just before 'a' (97)
        ('\x1b[123;5u', None, '{'),          # ASCII 123, just after 'z' (122)
        ('\x1b[65;5u', 'KEY_CTRL_A', 'A'),   # ASCII 65, 'A'
        ('\x1b[90;5u', 'KEY_CTRL_Z', 'Z'),   # ASCII 90, 'Z'
        ('\x1b[97;5u', 'KEY_CTRL_A', 'a'),   # ASCII 97, 'a'
        ('\x1b[122;5u', 'KEY_CTRL_Z', 'z'),  # ASCII 122, 'z
    ]
    for sequence, expected_name, description in boundary_cases:
        ks = _match_kitty_key(sequence)
        assert ks.name == expected_name


@pytest.mark.parametrize("initial_value,flag_name,bit_position", [
    (0, 'disambiguate', 0),
    (0, 'report_events', 1),
    (0, 'report_alternates', 2),
    (0, 'report_all_keys', 3),
    (0, 'report_text', 4),
    (31, 'disambiguate', 0),  # Test with all flags initially set
    (31, 'report_events', 1),
    (31, 'report_alternates', 2),
    (31, 'report_all_keys', 3),
    (31, 'report_text', 4),
])
def test_kitty_keyboard_protocol_individual_setters(initial_value, flag_name, bit_position):
    """Test individual setter operations with parameterized values."""
    protocol = KittyKeyboardProtocol(initial_value)
    initial_flag_state = getattr(protocol, flag_name)

    # Toggle the flag
    setattr(protocol, flag_name, not initial_flag_state)
    new_flag_state = getattr(protocol, flag_name)

    # Verify the flag changed
    assert new_flag_state == (not initial_flag_state)

    # Verify the bit manipulation worked correctly
    bit_value = 2 ** bit_position
    if new_flag_state:
        # Flag was turned on, bit should be set
        assert protocol.value & bit_value == bit_value
        expected_value = initial_value | bit_value
    else:
        # Flag was turned off, bit should be clear
        assert protocol.value & bit_value == 0
        expected_value = initial_value & ~bit_value

    assert protocol.value == expected_value


# PUA Modifier Keys Tests


@pytest.mark.parametrize("sequence,expected_key,expected_mods", [
    ('\x1b[57442;5u', KEY_LEFT_CONTROL, 5),
    ('\x1b[57441;6u', KEY_LEFT_SHIFT, 6),
    ('\x1b[57449;3u', KEY_RIGHT_ALT, 3),
    ('\x1b[57441;2u', KEY_LEFT_SHIFT, 2),
    ('\x1b[57442;1u', KEY_LEFT_CONTROL, 1),
])
def test_kitty_pua_modifier_keys(sequence, expected_key, expected_mods):
    """Test Kitty PUA modifier key sequences."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._mode == DecPrivateMode.SpecialInternalKitty
    assert ks._match.unicode_key == expected_key
    assert ks.modifiers == expected_mods
    assert ks.value == ''


# Super/Hyper/Meta Modifier Tests

@pytest.mark.parametrize("modifier,mod_value,char", [
    ('super', 9, 97),
    ('hyper', 17, 97),
    ('meta', 33, 97),
])
def test_kitty_advanced_modifiers(modifier, mod_value, char):
    """Test super/hyper/meta modifiers."""
    sequence = f'\x1b[{char};{mod_value}u'
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert getattr(ks, f'_{modifier}') is True
    assert ks._ctrl is False
    assert ks._alt is False
    expected_name = f'KEY_{modifier.upper()}_{chr(char).upper()}'
    assert ks.name == expected_name


@pytest.mark.parametrize("sequence,expected_name", [
    ('\x1b[97;13u', 'KEY_CTRL_SUPER_A'),
    ('\x1b[122;11u', 'KEY_ALT_SUPER_Z'),
    ('\x1b[97;21u', 'KEY_CTRL_HYPER_A'),
    ('\x1b[97;37u', 'KEY_CTRL_META_A'),
    ('\x1b[97;57u', 'KEY_SUPER_HYPER_META_A'),
])
def test_kitty_compound_advanced_modifiers(sequence, expected_name):
    """Test compound modifier combinations."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks.name == expected_name


# Report Text and Empty Modifiers Tests

@pytest.mark.parametrize("sequence,expected_key,expected_text", [
    ('\x1b[97;;97u', 97, (97,)),
    ('\x1b[97;u', 97, ()),
    ('\x1b[98;:1;98u', 98, (98,)),
    ('\x1b[122;;122:65u', 122, (122, 65)),
])
def test_kitty_empty_modifiers(sequence, expected_key, expected_text):
    """Test Kitty empty modifiers support."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._match.unicode_key == expected_key
    assert ks._match.modifiers == 1
    assert ks._match.int_codepoints == expected_text


# Event Type Tests

@pytest.mark.parametrize("sequence,is_press,is_repeat,is_release", [
    ('\x1b[97u', True, False, False),
    ('\x1b[97;1:1u', True, False, False),
    ('\x1b[97;1:2u', False, True, False),
    ('\x1b[97;1:3u', False, False, True),
])
def test_event_types_kitty(sequence, is_press, is_repeat, is_release):
    """Test event type properties for Kitty protocol."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks.pressed == is_press
    assert ks.repeated == is_repeat
    assert ks.released == is_release


@pytest.mark.parametrize("sequence,is_press,is_repeat,is_release", [
    ('\x1b[1;2Q', True, False, False),
    ('\x1b[1;2:1Q', True, False, False),
    ('\x1b[1;2:2Q', False, True, False),
    ('\x1b[1;2:3Q', False, False, True),
])
def test_event_types_legacy_csi(sequence, is_press, is_repeat, is_release):
    """Test event type properties for legacy CSI."""
    ks = _match_legacy_csi_modifiers(sequence)
    assert ks is not None
    assert ks.pressed == is_press
    assert ks.repeated == is_repeat
    assert ks.released == is_release


@pytest.mark.parametrize("sequence,expected_name,expected_value", [
    ('\x1b[1;2:3Q', 'KEY_SHIFT_F2_RELEASED', ''),
    ('\x1b[1;2:2Q', 'KEY_SHIFT_F2_REPEATED', ''),
    ('\x1b[1;2Q', 'KEY_SHIFT_F2', ''),
])
def test_event_type_name_suffixes(sequence, expected_name, expected_value):
    """Test name suffixes for event types."""
    ks = _match_legacy_csi_modifiers(sequence)
    assert ks is not None
    assert ks.name == expected_name
    assert ks.value == expected_value


def test_event_type_dynamic_predicates():
    """Test dynamic predicates with event types."""
    ks_release = _match_legacy_csi_modifiers('\x1b[1;2:3Q')
    assert ks_release.is_key_shift_f2_released() is True
    assert ks_release.is_key_shift_f2_pressed() is False

    ks_press = _match_legacy_csi_modifiers('\x1b[1;2Q')
    assert ks_press.is_key_shift_f2_pressed() is True
    assert ks_press.is_key_shift_f2_released() is False


def test_plain_keystroke_defaults_to_pressed():
    """Test plain keystrokes default to pressed."""
    ks = Keystroke('a')
    assert ks.pressed is True
    assert ks.repeated is False
    assert ks.released is False
