# -*- coding: utf-8 -*-
"""Tests specific to Kitty keyboard protocol features."""
import io
import os
import sys
import time
import math
import pytest

from blessed.keyboard import (_match_kitty_key, KittyKeyEvent, Keystroke, KittyKeyboardProtocol)
from blessed import Terminal
from tests.accessories import (as_subprocess, SEMAPHORE, SEND_SEMAPHORE, TestTerminal, 
                               echo_off, read_until_eof, read_until_semaphore, 
                               init_subproc_coverage)
from tests.conftest import IS_WINDOWS, TEST_KEYBOARD

# Skip PTY tests on Windows and build farms
pytestmark = pytest.mark.skipif(
    IS_WINDOWS,
    reason="PTY tests not supported on Windows")

# kitty keyboard sequence tests

def test_match_kitty_basic():
    """Test basic Kitty keyboard protocol sequences."""
    # Basic form: ESC [ key u
    ks = _match_kitty_key('\x1b[97u')  # 'a' key
    assert ks is not None
    assert ks._mode == -1  # Kitty mode indicator
    assert isinstance(ks._match, KittyKeyEvent)
    
    event = ks._match
    assert event.unicode_key == 97  # ASCII 'a'
    assert event.shifted_key is None
    assert event.base_key is None
    assert event.modifiers == 1  # default (no modifiers)
    assert event.event_type == 1  # press event (default)
    assert event.text_codepoints == []


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


def test_match_kitty_with_text_codepoints():
    """Test Kitty protocol with text codepoints."""
    # ESC [ key ; modifiers : event_type ; text_codepoints u
    ks = _match_kitty_key('\x1b[97;2;65u')  # Shift+a with text 'A'
    assert ks is not None
    event = ks._match
    assert event.unicode_key == 97
    assert event.modifiers == 2
    assert event.text_codepoints == [65]  # ASCII 'A'


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
    assert event.text_codepoints == [65, 66]  # 'AB'


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
        'caps_lock': 65, # 1 + 64
        'num_lock': 129, # 1 + 128
        'ctrl+shift': 6, # 1 + 1 + 4
        'ctrl+alt': 7,   # 1 + 2 + 4
    }
    
    for name, mod_value in modifiers.items():
        ks = _match_kitty_key(f'\x1b[97;{mod_value}u')  # 'a' with modifier
        assert ks is not None, f"Failed to match {name} modifier"
        assert ks._match.modifiers == mod_value, f"Wrong modifier value for {name}"


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
    assert ks._mode == -1
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
        assert ks._mode == -1  # Kitty mode indicator
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
        assert ks._mode == -1  # Kitty mode
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
        assert ks._mode == -1
        
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
    
    for sequence, expected_key in functional_keys.items():
        ks = _match_kitty_key(sequence)
        assert ks is not None, f"Failed to match {expected_key}"
        assert ks._mode == -1
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
    
    for sequence, expected_key in f_keys.items():
        ks = _match_kitty_key(sequence)
        assert ks is not None, f"Failed to match {expected_key}"
        assert ks._mode == -1
        expected_code = int(sequence.split('[')[1].split('u')[0])
        assert ks._match.unicode_key == expected_code


def test_kitty_keypad_keys():
    """Test Kitty protocol with keypad keys."""
    # Test keypad keys that are specific to Kitty protocol
    keypad_keys = {
        '\x1b[57399u': 'KP_0',      # 57399 u
        '\x1b[57409u': 'KP_DECIMAL', # 57409 u
        '\x1b[57414u': 'KP_ENTER',  # 57414 u
    }
    
    for sequence, expected_key in keypad_keys.items():
        ks = _match_kitty_key(sequence)
        assert ks is not None, f"Failed to match {expected_key}"
        assert ks._mode == -1
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
    assert ks.is_ctrl() is True  # Any ctrl
    
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
    import pty
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
    import pty
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
        
        # Send initial state response when child queries current flags (9 = disambiguate + report_all_keys)
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
        term._is_a_tty = True  # Force TTY behavior for testing
        term.ungetch(u'\x1b[?15u')  # Same response buffered but won't be used
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
        
        # Test comprehensive mode (should set disambiguate + report_events + report_all_keys + report_text)
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
        
        assert protocol.value == expected, f"Failed for case {case}, got {protocol.value}, expected {expected}"
        
        # Verify individual flag values
        for flag_name, expected_flag_value in case.items():
            actual_flag_value = getattr(protocol, flag_name)
            assert actual_flag_value == expected_flag_value, f"Flag {flag_name} should be {expected_flag_value}, got {actual_flag_value}"


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
