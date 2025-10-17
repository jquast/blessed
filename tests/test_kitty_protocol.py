# -*- coding: utf-8 -*-
"""Tests specific to Kitty keyboard protocol features."""
import io
import os
import sys
import time
import math
import pytest
import platform

from blessed import Terminal
from blessed.keyboard import (
    KEY_TAB, KEY_LEFT_SHIFT, KEY_LEFT_CONTROL, KEY_RIGHT_ALT,
    _match_kitty_key, KittyKeyEvent, Keystroke, KittyKeyboardProtocol, resolve_sequence,
    _match_legacy_csi_letter_form,
)
from tests.accessories import (as_subprocess, SEMAPHORE, TestTerminal,
                               read_until_semaphore, pty_test)
from tests.conftest import IS_WINDOWS, TEST_KEYBOARD

# isort: off
# curses
if platform.system() == 'Windows':
    # pylint: disable=import-error
    from jinxed import KEY_EXIT, KEY_ENTER, KEY_BACKSPACE
else:
    from curses import KEY_EXIT, KEY_ENTER, KEY_BACKSPACE

# Skip PTY tests on Windows and build farms
pytestmark = pytest.mark.skipif(
    IS_WINDOWS,
    reason="PTY tests not supported on Windows")


@pytest.mark.parametrize(
    "sequence,unicode_key,shifted_key,base_key,modifiers,event_type,codepoints",
    [('\x1b[97u', 97, None, None, 1, 1, ()),
     ('\x1b[97;5u', 97, None, None, 5, 1, ()),
     ('\x1b[97:65;2u', 97, 65, None, 2, 1, ()),
     ('\x1b[1089::99;5u', 1089, None, 99, 5, 1, ()),
     ('\x1b[97;1:3u', 97, None, None, 1, 3, ()),
     ('\x1b[97;2;65u', 97, None, None, 2, 1, (65,))])
def test_match_kitty_basic_forms(
        # pylint: disable=too-many-positional-arguments
        sequence, unicode_key, shifted_key, base_key, modifiers, event_type, codepoints):
    """Test basic Kitty protocol sequence parsing."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._mode == -1
    assert isinstance(ks._match, KittyKeyEvent)
    event = ks._match
    assert event.unicode_key == unicode_key
    assert event.shifted_key == shifted_key
    assert event.base_key == base_key
    assert event.modifiers == modifiers
    assert event.event_type == event_type
    assert event.int_codepoints == codepoints


def test_match_kitty_complex():
    """Test complex Kitty protocol sequence with all fields."""
    ks = _match_kitty_key('\x1b[97:65:99;6:2;65:66u')
    assert ks is not None
    event = ks._match
    assert event.unicode_key == 97
    assert event.shifted_key == 65
    assert event.base_key == 99
    assert event.modifiers == 6
    assert event.event_type == 2
    assert event.int_codepoints == (65, 66)


def test_match_kitty_non_matching():
    """Test non-Kitty sequences return None."""
    assert _match_kitty_key('a') is None
    assert _match_kitty_key('\x1b[A') is None
    assert _match_kitty_key('\x1b[97') is None
    assert _match_kitty_key('\x1b]97u') is None
    assert _match_kitty_key('\x1b[97v') is None


def test_kitty_modifier_encoding():
    """Test Kitty protocol modifier value encoding."""
    modifiers = {
        'shift': 2,
        'alt': 3,
        'ctrl': 5,
        'super': 9,
        'hyper': 17,
        'meta': 33,
        'caps_lock': 65,
        'num_lock': 129,
        'ctrl+shift': 6,
        'ctrl+alt': 7,
    }

    for mod_value in modifiers.values():
        ks = _match_kitty_key(f'\x1b[97;{mod_value}u')
        assert ks is not None
        assert ks._match.modifiers == mod_value


def test_kitty_sequence_properties():
    """Test Kitty keystroke properties."""
    ks = _match_kitty_key('\x1b[97;5u')
    assert str(ks) == '\x1b[97;5u'
    assert ks.is_sequence is True
    assert ks._mode == -1
    assert ks._code is None


def test_terminal_inkey_kitty_protocol():
    """Test Terminal.inkey() with Kitty protocol sequences."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=True)

        term.ungetch('\x1b[97;5u')
        ks = term.inkey(timeout=0)
        assert ks == '\x1b[97;5u'
        assert ks._mode == -1
        assert isinstance(ks._match, KittyKeyEvent)
        assert ks._match.unicode_key == 97
        assert ks._match.modifiers == 5

        term.ungetch('\x1b[65u')
        ks = term.inkey(timeout=0)
        assert ks._mode == -1
        assert ks._match.unicode_key == 65

        term.ungetch('\x1b[97;5uextra')
        ks = term.inkey(timeout=0)
        assert ks == '\x1b[97;5u'
        assert ks._mode == -1
        remaining = term.flushinp()
        assert remaining == 'extra'

        term.ungetch('\x1b[97;8u')
        ks = term.inkey(timeout=0)
        assert ks._mode == -1
        assert isinstance(ks._match, KittyKeyEvent)
        assert ks._match.unicode_key == 97
        assert ks._match.modifiers == 8

        assert stream.getvalue() == ''
    child()


def test_kitty_protocol_modifier_properties():
    """Test Kitty protocol modifier properties."""
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

    # Test with num lock
    ks = _match_kitty_key('\x1b[97;129u')  # 1 + 128 = 129 (a w/num_lock)
    assert ks._num_lock is True
    assert ks._ctrl is False
    assert ks._alt is False
    assert ks.value == 'a'


def test_kitty_protocol_is_ctrl_is_alt():
    """Test is_ctrl() and is_alt() with Kitty protocol."""
    # Matching Ctrl+a
    ks = _match_kitty_key('\x1b[97;5u')  # Ctrl+a
    assert ks.is_ctrl('a') is True
    assert ks.is_ctrl('A') is True  # Ctrl is Case insensitive
    assert ks.is_ctrl('b') is False
    assert ks.is_ctrl() is False

    # Matching Alt+a
    ks = _match_kitty_key('\x1b[97;3u')  # Alt+a
    assert ks.is_alt('a') is True
    assert ks.is_alt('A') is True  # Alt is also Case insensitive
    assert ks.is_alt('b') is False

    # Ctrl+Alt+a should NOT match exact is_ctrl('a') or is_alt('a')
    ks = _match_kitty_key('\x1b[97;7u')  # Ctrl+Alt+a
    assert ks.is_ctrl('a') is False  # Not exactly ctrl
    assert ks.is_alt('a') is False   # Not exactly alt


def test_kitty_keyboard_protocol_parsing_flags_response():
    """Test Kitty keyboard flags response parsing."""
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


def test_kitty_keyboard_protocol_methods():
    """Test KittyKeyboardProtocol make_arguments, repr, and equality."""
    proto_zero = KittyKeyboardProtocol(0)
    proto_all = KittyKeyboardProtocol(31)

    assert proto_zero.make_arguments() == {
        'disambiguate': False,
        'report_events': False,
        'report_alternates': False,
        'report_all_keys': False,
        'report_text': False
    }
    assert proto_all.make_arguments() == {
        'disambiguate': True,
        'report_events': True,
        'report_alternates': True,
        'report_all_keys': True,
        'report_text': True
    }

    repr_zero = repr(proto_zero)
    assert 'KittyKeyboardProtocol(value=0' in repr_zero
    assert 'flags=[]' in repr_zero

    repr_all = repr(proto_all)
    assert 'KittyKeyboardProtocol(value=31' in repr_all
    for flag in [
        'disambiguate',
        'report_events',
        'report_alternates',
        'report_all_keys',
            'report_text']:
        assert flag in repr_all

    proto_five_a = KittyKeyboardProtocol(5)
    proto_five_b = KittyKeyboardProtocol(5)
    proto_ten = KittyKeyboardProtocol(10)
    assert proto_five_a == proto_five_b
    assert proto_five_a == 5
    assert proto_five_a != proto_ten
    assert proto_five_a != 10
    assert proto_five_a != "not an int"


@pytest.mark.skipif(not TEST_KEYBOARD, reason="TEST_KEYBOARD not specified")
def test_get_kitty_keyboard_state_pty_success():
    """PTY test: get_kitty_keyboard_state with successful terminal response."""
    def child(term):
        # Signal readiness and query Kitty state
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        flags = term.get_kitty_keyboard_state(timeout=0.1)

        # Write result to stdout for parent verification
        if flags is not None:
            os.write(sys.__stdout__.fileno(), str(flags.value).encode('ascii'))
        else:
            os.write(sys.__stdout__.fileno(), b'None')

    def parent(master_fd):
        # Wait for child readiness
        read_until_semaphore(master_fd)
        # Send both Kitty protocol flags response and DA1 response for boundary detection
        # flags=27: all basic flags set, and a DA1 response indicating VT terminal
        os.write(master_fd, b'\x1b[?27u\x1b[?64c')

    output = pty_test(child, parent, 'test_get_kitty_keyboard_state_pty_success')
    # first call to get_kitty_keyboard_state causes both kitty and dec
    # parameters query to output, we faked a "response" by writing to our master pty side
    assert output == '\x1b[?u\x1b[c' + '27'  # Should have parsed flags value 27


@pytest.mark.skipif(not TEST_KEYBOARD, reason="TEST_KEYBOARD not specified")
def test_enable_kitty_keyboard_pty_success():
    """PTY test: enable_kitty_keyboard with set and restore sequences."""
    def child(term):
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

    def parent(master_fd):
        # Wait for child readiness
        read_until_semaphore(master_fd)
        # Send initial state response when child queries current flags (9 =
        # disambiguate + report_all_keys)
        os.write(master_fd, b'\x1b[?9u')

    output = pty_test(child, parent, 'test_enable_kitty_keyboard_pty_success')
    # Verify child completed successfully
    assert 'INSIDE' in output
    assert 'COMPLETE' in output


def test_kitty_state_0s_reply_via_ungetch():
    """0-second get_kitty_keyboard_state call with response via ungetch."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = True  # Force TTY behavior for testing
        stime = time.time()
        # Simulate Kitty keyboard state response - flags value 9 (disambiguate + report_all_keys)
        # Need both Kitty and DA response for boundary approach on first call
        term.ungetch('\x1b[?9u\x1b[?64c')

        flags = term.get_kitty_keyboard_state(timeout=0.01)
        assert math.floor(time.time() - stime) == 0.0
        assert flags is not None
        assert flags.value == 9
        assert flags.disambiguate is True
        assert flags.report_all_keys is True
        assert flags.report_events is False
    child()


def test_kitty_state_styling_indifferent():
    """Test get_kitty_keyboard_state with styling enabled and disabled."""
    @as_subprocess
    def child():
        # Test with styling enabled
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = True  # Force TTY behavior for testing
        # Need both Kitty and DA response for boundary approach on first call
        term.ungetch('\x1b[?15u\x1b[?64c')  # flags value 15 (multiple flags)
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
        term.ungetch('\x1b[?15u')
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
    """Test get_kitty_keyboard_state buffer management."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = True  # Force TTY behavior for testing
        # Buffer unrelated data before and after the kitty state response
        term.ungetch('abc' + '\x1b[?13u' + 'xyz')

        # get_kitty_keyboard_state should parse and consume only the response
        # Use force=True to bypass boundary approach for this buffer management test
        flags = term.get_kitty_keyboard_state(timeout=0.01, force=True)
        assert flags is not None
        assert flags.value == 13

        # Remaining data should still be available for subsequent input
        remaining = term.flushinp()
        assert remaining == 'abcxyz'
    child()


@pytest.mark.parametrize("force_styling,expected_sticky_flag", [
    (False, False),  # styling disabled -> no sticky flag
    (True, False),   # not a TTY -> no sticky flag
])
def test_get_kitty_keyboard_state_no_tty_or_disabled(force_styling, expected_sticky_flag):
    """Test get_kitty_keyboard_state returns None when unsupported."""
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


@pytest.mark.parametrize("force_styling,force,flags,mode,expected_output", [
    (False, False, {'disambiguate': True}, 1, ''),  # No styling, no output
    (True, False, {'disambiguate': True}, 1, ''),  # Not TTY, no force, no output
    (True, True, {'disambiguate': True}, 1, '\x1b[=1;1u'),  # Not TTY but forced
    (True, True, {'disambiguate': False, 'report_events': True,
     'report_alternates': True}, 2, '\x1b[=6;2u'),  # Multi-flag
    (True,
     True,
     {'disambiguate': True,
      'report_events': True,
      'report_all_keys': True,
      'report_text': True},
     1,
     '\x1b[=27;1u'),
    # Comprehensive
])
def test_enable_kitty_keyboard(force_styling, force, flags, mode, expected_output):
    """Test enable_kitty_keyboard with various flag combinations and conditions."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = Terminal(stream=stream, force_styling=force_styling)

        with term.enable_kitty_keyboard(**flags, mode=mode, force=force, timeout=0.01):
            pass
        assert stream.getvalue() == expected_output
    child()


def test_kitty_keyboard_protocol_setters():
    """Test KittyKeyboardProtocol property setters."""
    # Test 1: Setting flags sequentially from 0
    protocol = KittyKeyboardProtocol(0)
    assert protocol.value == 0
    protocol.disambiguate = True
    assert protocol.value == 1
    protocol.report_events = True
    assert protocol.value == 3
    assert protocol.disambiguate is True
    protocol.report_alternates = True
    assert protocol.value == 7
    protocol.report_all_keys = True
    assert protocol.value == 15
    protocol.report_text = True
    assert protocol.value == 31

    # Test 2: Clearing flags sequentially from 31
    protocol = KittyKeyboardProtocol(31)
    assert protocol.value == 31
    protocol.disambiguate = False
    assert protocol.value == 30
    assert protocol.report_events is True
    protocol.report_events = False
    assert protocol.value == 28
    protocol.report_alternates = False
    assert protocol.value == 24
    protocol.report_all_keys = False
    assert protocol.value == 16
    protocol.report_text = False
    assert protocol.value == 0

    # Test 3: Independence - setting non-adjacent flags
    protocol = KittyKeyboardProtocol(0)
    protocol.disambiguate = True
    protocol.report_alternates = True
    protocol.report_text = True
    assert protocol.value == 21
    assert protocol.report_events is False
    assert protocol.report_all_keys is False

    # Test 4: Modifying a single flag with existing values
    protocol = KittyKeyboardProtocol(15)
    protocol.report_alternates = False
    assert protocol.value == 11
    assert protocol.disambiguate is True
    assert protocol.report_events is True
    assert protocol.report_alternates is False
    assert protocol.report_all_keys is True
    assert protocol.report_text is False


def test_get_kitty_keyboard_state_boundary_approach():
    """Test boundary approach for detecting Kitty keyboard support."""
    @as_subprocess
    def child():
        stream = io.StringIO()

        # Test 1: Successful first call with Kitty and DA responses
        term = Terminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term.ungetch('\x1b[?9u\x1b[?64;1;2;4c')
        flags = term.get_kitty_keyboard_state(timeout=0.01)
        assert flags is not None
        assert flags.value == 9
        assert term._kitty_kb_first_query_attempted is True
        assert term._kitty_kb_first_query_failed is False

        # Test 2: First call with only DA response (no Kitty support)
        term = Terminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term.ungetch('\x1b[?64;1;2c')
        flags = term.get_kitty_keyboard_state(timeout=0.01)
        assert flags is None
        assert term._kitty_kb_first_query_attempted is True
        assert term._kitty_kb_first_query_failed is True
        flags2 = term.get_kitty_keyboard_state(timeout=1.0)
        assert flags2 is None

        # Test 3: First call timeout (no response)
        term = Terminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        flags = term.get_kitty_keyboard_state(timeout=0.001)
        assert flags is None
        assert term._kitty_kb_first_query_attempted is True
        assert term._kitty_kb_first_query_failed is True
        flags2 = term.get_kitty_keyboard_state(timeout=1.0)
        assert flags2 is None

        # Test 4: Subsequent call uses normal query
        term = Terminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term.ungetch('\x1b[?15u\x1b[?64c')
        flags1 = term.get_kitty_keyboard_state(timeout=0.01)
        assert flags1 is not None
        assert flags1.value == 15
        term.ungetch('\x1b[?7u')
        flags2 = term.get_kitty_keyboard_state(timeout=0.01)
        assert flags2 is not None
        assert flags2.value == 7

        # Test 5: force=True bypasses boundary approach
        term = Terminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term.ungetch('\x1b[?13u')
        flags = term.get_kitty_keyboard_state(timeout=0.01, force=True)
        assert flags is not None
        assert flags.value == 13
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
    """Test digit name synthesis with modifiers."""
    # Test digit name synthesis for Kitty sequences
    digit_test_cases = [
        ('\x1b[49;3u', 'KEY_ALT_1'),       # ASCII '1' = 49
        ('\x1b[49;5u', 'KEY_CTRL_1'),
        ('\x1b[49;4u', 'KEY_ALT_SHIFT_1'),  # Alt(2) + Shift(1) + base(1) = 4
        ('\x1b[50;3u', 'KEY_ALT_2'),       # ASCII '2' = 50
        ('\x1b[57;5u', 'KEY_CTRL_9'),      # ASCII '9' = 57
        ('\x1b[48;7u', 'KEY_CTRL_ALT_0'),  # ASCII '0' = 48, modifiers=7 (1+2+4)
    ]

    for sequence, expected_name in digit_test_cases:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        assert ks._mode == -1  # Kitty protocol mode
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
    """Test letter name synthesis with basic modifiers."""
    # Test basic modifier combinations for letter 'a' (unicode_key=97)
    test_cases = [
        ('\x1b[97;5u', 'KEY_CTRL_A'),
        ('\x1b[97;3u', 'KEY_ALT_A'),
        ('\x1b[97;7u', 'KEY_CTRL_ALT_A'),
        ('\x1b[97;2u', 'KEY_SHIFT_A'),
        ('\x1b[97;6u', 'KEY_CTRL_SHIFT_A'),
        ('\x1b[97;4u', 'KEY_ALT_SHIFT_A'),
        ('\x1b[97;8u', 'KEY_CTRL_ALT_SHIFT_A'),
    ]

    for sequence, expected_name in test_cases:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        assert ks.name == expected_name
        assert ks._mode == -1  # Kitty protocol mode


def test_kitty_letter_name_synthesis_different_letters():
    """Test letter name synthesis for different letters."""
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
        assert ks.value == letter


def test_kitty_letter_name_synthesis_base_key_preference():
    """Test base_key preference in letter naming."""
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
    """Test name synthesis for keypress events only."""
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
    """Test non-letter, non-digit keys have no synthesized names."""
    # Test symbols and space - should not get names even with modifiers
    # (digits now DO get names with modifiers, so they're excluded from this test)
    # Special case: '[' always gets 'CSI' name
    non_letter_non_digit_cases = [
        ('\x1b[32;5u', None),     # space
        ('\x1b[33;3u', None),     # exclamation
        ('\x1b[59;5u', None),     # semicolon
        ('\x1b[46;3u', None),     # period
        ('\x1b[64;5u', None),     # @ symbol
        ('\x1b[91;3u', 'CSI'),    # bracket - special case
    ]

    for sequence, expected_name in non_letter_non_digit_cases:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        if expected_name is None:
            assert ks.name is None
        else:
            assert ks.name == expected_name


def test_kitty_letter_name_synthesis_no_modifiers_no_name():
    """Test plain letters have no synthesized names."""
    # Test plain letters (modifiers=1, meaning no modifiers) - should not get names
    plain_letter_cases = [
        ('\x1b[97;1u', 'a'),   # plain 'a'
        ('\x1b[65;1u', 'A'),   # plain 'A'
        ('\x1b[122;1u', 'z'),  # plain 'z'
        ('\x1b[90;1u', 'Z'),   # plain 'Z'
        ('\x1b[97u', 'a'),     # plain 'a' (default modifiers=1)
    ]

    for sequence, value in plain_letter_cases:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        assert ks.name is None
        assert ks.value == value


def test_kitty_letter_name_synthesis_supports_advanced_modifiers():
    """Test advanced modifier support in letter naming."""
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
    """Test explicitly set names are preserved."""
    # Create a Kitty keystroke with explicit name - should preserve it
    kitty_event = KittyKeyEvent(unicode_key=97, shifted_key=None, base_key=None,
                                modifiers=5, event_type=1, int_codepoints=())
    ks = Keystroke('\x1b[97;5u', name='CUSTOM_NAME',
                   mode=-1, match=kitty_event)  # Kitty protocol mode

    assert ks.name == 'CUSTOM_NAME'


def test_kitty_letter_name_synthesis_integration():
    """Test letter name synthesis with Terminal.inkey()."""
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
            assert ks._mode == -1  # Kitty protocol mode

    child()


def test_kitty_letter_name_synthesis_case_normalization():
    """Test letter names normalized to uppercase."""
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
    """Test modifier ordering in names."""
    # Test various combinations to ensure consistent ordering
    ordering_test_cases = [
        ('\x1b[97;6u', 'KEY_CTRL_SHIFT_A'),     # ctrl+shift (1+4+1=6)
        ('\x1b[97;4u', 'KEY_ALT_SHIFT_A'),       # alt+shift (1+2+1=4)
        ('\x1b[97;8u', 'KEY_CTRL_ALT_SHIFT_A'),  # all three (1+4+2+1=8)
    ]

    for sequence, expected_name in ordering_test_cases:
        ks = _match_kitty_key(sequence)
        assert ks.name == expected_name


@pytest.mark.parametrize("sequence,expected_name", [
    ('\x1b[P', 'KEY_F1'),
    ('\x1b[Q', 'KEY_F2'),
    ('\x1b[13~', 'KEY_F3'),
    ('\x1b[S', 'KEY_F4'),
])
def test_disambiguate_f1_f4_csi_sequences(sequence, expected_name):
    """Test F1-F4 recognition in disambiguate mode."""
    @as_subprocess
    def child():
        term = Terminal(force_styling=True)
        mapper = term._keymap
        codes = term._keycodes
        prefixes = set()

        ks = resolve_sequence(sequence, mapper, codes, prefixes, final=True)
        assert ks is not None
        assert ks.name == expected_name
        assert str(ks) == sequence

    child()


@pytest.mark.parametrize("sequence,expected_name", [
    ('\x1b[P', 'KEY_F1'),
    ('\x1b[Q', 'KEY_F2'),
    ('\x1b[13~', 'KEY_F3'),
    ('\x1b[S', 'KEY_F4'),
])
def test_disambiguate_f1_f4_via_inkey(sequence, expected_name):
    """Test F1-F4 disambiguate sequences with Terminal.inkey()."""
    @as_subprocess
    def child():
        term = Terminal(stream=io.StringIO(), force_styling=True)
        term.ungetch(sequence)
        ks = term.inkey(timeout=0)
        assert ks == sequence
        assert ks.name == expected_name

    child()


def test_disambiguate_f1_f4_not_confused_with_alt():
    """Test F1-F4 not confused with ALT+[ sequences."""
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
        ('\x1b[91;5u', 'CSI'),          # ASCII 91, just after 'Z' (90) - SPECIAL CASE
        ('\x1b[64;5u', None),           # ASCII 64, just before 'A' (65)
        ('\x1b[96;5u', None),           # ASCII 96, just before 'a' (97)
        ('\x1b[123;5u', None),          # ASCII 123, just after 'z' (122)
        ('\x1b[65;5u', 'KEY_CTRL_A'),   # ASCII 65, 'A'
        ('\x1b[90;5u', 'KEY_CTRL_Z'),   # ASCII 90, 'Z'
        ('\x1b[97;5u', 'KEY_CTRL_A'),   # ASCII 97, 'a'
        ('\x1b[122;5u', 'KEY_CTRL_Z'),  # ASCII 122, 'z
    ]
    for sequence, expected_name in boundary_cases:
        ks = _match_kitty_key(sequence)
        assert ks.name == expected_name


@pytest.mark.parametrize("initial_value,flag_name,bit_position", [
    (0, 'disambiguate', 0),
    (0, 'report_events', 1),
    (0, 'report_alternates', 2),
    (0, 'report_all_keys', 3),
    (0, 'report_text', 4),
    (31, 'disambiguate', 0),
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
    assert ks._mode == -1  # Kitty protocol mode
    assert ks._match.unicode_key == expected_key
    assert ks.modifiers == expected_mods
    assert ks.value == ''


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


@pytest.mark.parametrize("sequence,expected_value", [
    ('\x1b[97;;97u', 'a'),
    ('\x1b[97;;97:98u', 'ab'),
    ('\x1b[122;;122:120:121u', 'zxy'),
])
def test_kitty_int_codepoints_value(sequence, expected_value):
    """Test int_codepoints conversion to value string."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._mode == -1
    assert ks._match.int_codepoints is not None
    assert len(ks._match.int_codepoints) > 0
    assert ks.value == expected_value


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
    ks = _match_legacy_csi_letter_form(sequence)
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
    ks = _match_legacy_csi_letter_form(sequence)
    assert ks is not None
    assert ks.name == expected_name
    assert ks.value == expected_value


def test_event_type_dynamic_predicates():
    """Test dynamic predicates with event types."""
    ks_release = _match_legacy_csi_letter_form('\x1b[1;2:3Q')
    # These predicates would require event type suffix support
    assert ks_release.is_shift_f2_released() is True
    assert ks_release.is_shift_f2_pressed() is False

    ks_press = _match_legacy_csi_letter_form('\x1b[1;2Q')
    assert ks_press.is_shift_f2_pressed() is True
    assert ks_press.is_shift_f2_released() is False


def test_plain_keystroke_defaults_to_pressed():
    """Test plain keystrokes default to pressed."""
    ks = Keystroke('a')
    assert ks.pressed is True
    assert ks.repeated is False
    assert ks.released is False


@pytest.mark.parametrize("sequence,expected_code,expected_name", [
    ('\x1b[57399u', 57399, 'KEY_KP_0'),
    ('\x1b[57400u', 57400, 'KEY_KP_1'),
    ('\x1b[57401u', 57401, 'KEY_KP_2'),
    ('\x1b[57402u', 57402, 'KEY_KP_3'),
    ('\x1b[57403u', 57403, 'KEY_KP_4'),
    ('\x1b[57404u', 57404, 'KEY_KP_5'),
    ('\x1b[57405u', 57405, 'KEY_KP_6'),
    ('\x1b[57406u', 57406, 'KEY_KP_7'),
    ('\x1b[57407u', 57407, 'KEY_KP_8'),
    ('\x1b[57408u', 57408, 'KEY_KP_9'),
    ('\x1b[57409u', 57409, 'KEY_KP_DECIMAL'),
    ('\x1b[57410u', 57410, 'KEY_KP_DIVIDE'),
    ('\x1b[57411u', 57411, 'KEY_KP_MULTIPLY'),
    ('\x1b[57412u', 57412, 'KEY_KP_SUBTRACT'),
    ('\x1b[57413u', 57413, 'KEY_KP_ADD'),
    ('\x1b[57414u', 57414, 'KEY_KP_ENTER'),
    ('\x1b[57415u', 57415, 'KEY_KP_EQUAL'),
    ('\x1b[57416u', 57416, 'KEY_KP_SEPARATOR'),
    ('\x1b[57417u', 57417, 'KEY_KP_LEFT'),
    ('\x1b[57418u', 57418, 'KEY_KP_RIGHT'),
    ('\x1b[57419u', 57419, 'KEY_KP_UP'),
    ('\x1b[57420u', 57420, 'KEY_KP_DOWN'),
    ('\x1b[57421u', 57421, 'KEY_KP_PAGE_UP'),
    ('\x1b[57422u', 57422, 'KEY_KP_PAGE_DOWN'),
    ('\x1b[57423u', 57423, 'KEY_KP_HOME'),
    ('\x1b[57424u', 57424, 'KEY_KP_END'),
    ('\x1b[57425u', 57425, 'KEY_KP_INSERT'),
    ('\x1b[57426u', 57426, 'KEY_KP_DELETE'),
    ('\x1b[57427u', 57427, 'KEY_KP_BEGIN'),
])
def test_kitty_all_keypad_keys(sequence, expected_code, expected_name):
    """Test all Kitty protocol keypad keys."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._mode == -1  # Kitty protocol mode
    assert ks._match.unicode_key == expected_code
    assert ks.code == expected_code
    assert ks.name == expected_name
    assert ks.value == ''


@pytest.mark.parametrize("sequence,expected_code,modifier", [
    ('\x1b[57424;5u', 57424, 5),    # Ctrl+KP_END
    ('\x1b[57424;3u', 57424, 3),    # Alt+KP_END
    ('\x1b[57424;7u', 57424, 7),    # Ctrl+Alt+KP_END
    ('\x1b[57399;6u', 57399, 6),    # Ctrl+Shift+KP_0
])
def test_kitty_keypad_with_modifiers(sequence, expected_code, modifier):
    """Test keypad keys with modifiers."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._mode == -1  # Kitty protocol mode
    assert ks._match.unicode_key == expected_code
    assert ks._match.modifiers == modifier
    assert ks.code == expected_code


@pytest.mark.parametrize("sequence,event_type", [
    ('\x1b[57424u', 1),           # press (default)
    ('\x1b[57424;1:1u', 1),       # press (explicit)
    ('\x1b[57424;1:2u', 2),       # repeat
    ('\x1b[57424;1:3u', 3),       # release
])
def test_kitty_keypad_event_types(sequence, event_type):
    """Test keypad keys with different event types."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._match.event_type == event_type
    assert ks.pressed == (event_type == 1)
    assert ks.repeated == (event_type == 2)
    assert ks.released == (event_type == 3)


def test_kitty_keypad_inkey_integration():
    """Test keypad integration with Terminal.inkey()."""
    @as_subprocess
    def child():
        term = Terminal(stream=io.StringIO(), force_styling=True)

        # Basic keypad keys
        term.ungetch('\x1b[57424u')
        ks = term.inkey(timeout=0)
        assert ks == '\x1b[57424u'
        assert ks.name == 'KEY_KP_END'
        assert ks.code == 57424

        term.ungetch('\x1b[57399u')
        ks = term.inkey(timeout=0)
        assert ks == '\x1b[57399u'
        assert ks.name == 'KEY_KP_0'
        assert ks.code == 57399

        term.ungetch('\x1b[57414u')
        ks = term.inkey(timeout=0)
        assert ks == '\x1b[57414u'
        assert ks.name == 'KEY_KP_ENTER'
        assert ks.code == 57414

        # Keypad with Ctrl modifier
        term.ungetch('\x1b[57424;5u')
        ks = term.inkey(timeout=0)
        assert ks._ctrl is True
        assert ks._alt is False
        assert ks.name == 'KEY_CTRL_KP_END'

        # Keypad with multiple modifiers
        term.ungetch('\x1b[57424;7u')
        ks = term.inkey(timeout=0)
        assert ks._ctrl is True
        assert ks._alt is True
        assert ks.name == 'KEY_CTRL_ALT_KP_END'

        # Keypad release event
        term.ungetch('\x1b[57424;1:3u')
        ks = term.inkey(timeout=0)
        assert ks.released is True
        assert ks.pressed is False
        assert ks.name == 'KEY_KP_END_RELEASED'

        # Keypad repeat event
        term.ungetch('\x1b[57424;1:2u')
        ks = term.inkey(timeout=0)
        assert ks.repeated is True
        assert ks.pressed is False
        assert ks.name == 'KEY_KP_END_REPEATED'

    child()


def test_kitty_keypad_value_property():
    """Test keypad keys have empty value."""
    ks = _match_kitty_key('\x1b[57424u')
    assert ks.value == ''

    ks = _match_kitty_key('\x1b[57399u')
    assert ks.value == ''


@pytest.mark.parametrize("sequence,expected_name", [
    ('\x1b[57417u', 'KEY_KP_LEFT'),
    ('\x1b[57418u', 'KEY_KP_RIGHT'),
    ('\x1b[57419u', 'KEY_KP_UP'),
    ('\x1b[57420u', 'KEY_KP_DOWN'),
    ('\x1b[57421u', 'KEY_KP_PAGE_UP'),
    ('\x1b[57422u', 'KEY_KP_PAGE_DOWN'),
    ('\x1b[57423u', 'KEY_KP_HOME'),
    ('\x1b[57424u', 'KEY_KP_END'),
])
def test_kitty_keypad_navigation_keys(sequence, expected_name):
    """Test keypad navigation keys."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks.name == expected_name


@pytest.mark.parametrize("sequence,expected_name", [
    ('\x1b[57410u', 'KEY_KP_DIVIDE'),
    ('\x1b[57411u', 'KEY_KP_MULTIPLY'),
    ('\x1b[57412u', 'KEY_KP_SUBTRACT'),
    ('\x1b[57413u', 'KEY_KP_ADD'),
    ('\x1b[57415u', 'KEY_KP_EQUAL'),
])
def test_kitty_keypad_arithmetic_keys(sequence, expected_name):
    """Test keypad arithmetic operation keys."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks.name == expected_name


@pytest.mark.parametrize("digit", range(10))
def test_kitty_keypad_digit_keys(digit):
    """Test keypad digit keys 0-9."""
    code = 57399 + digit
    sequence = f'\x1b[{code}u'
    expected_name = f'KEY_KP_{digit}'

    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks.code == code
    assert ks.name == expected_name


@pytest.mark.parametrize("sequence,expected_code,expected_name", [
    # Lock and special function keys (57358-57363)
    ('\x1b[57358u', 57358, 'KEY_CAPS_LOCK'),
    ('\x1b[57359u', 57359, 'KEY_SCROLL_LOCK'),
    ('\x1b[57360u', 57360, 'KEY_NUM_LOCK'),
    ('\x1b[57361u', 57361, 'KEY_PRINT_SCREEN'),
    ('\x1b[57362u', 57362, 'KEY_PAUSE'),
    ('\x1b[57363u', 57363, 'KEY_MENU'),
])
def test_kitty_lock_and_special_keys(sequence, expected_code, expected_name):
    """Test lock and special function keys."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._mode == -1  # Kitty protocol mode
    assert ks._match.unicode_key == expected_code
    assert ks.code == expected_code
    assert ks.name == expected_name
    assert ks.value == ''  # Functional keys don't produce text


@pytest.mark.parametrize("sequence,expected_code,expected_name", [
    # Extended function keys F13-F35 (57376-57398)
    ('\x1b[57376u', 57376, 'KEY_F13'),
    ('\x1b[57377u', 57377, 'KEY_F14'),
    ('\x1b[57378u', 57378, 'KEY_F15'),
    ('\x1b[57379u', 57379, 'KEY_F16'),
    ('\x1b[57380u', 57380, 'KEY_F17'),
    ('\x1b[57381u', 57381, 'KEY_F18'),
    ('\x1b[57382u', 57382, 'KEY_F19'),
    ('\x1b[57383u', 57383, 'KEY_F20'),
    ('\x1b[57384u', 57384, 'KEY_F21'),
    ('\x1b[57385u', 57385, 'KEY_F22'),
    ('\x1b[57386u', 57386, 'KEY_F23'),
    ('\x1b[57387u', 57387, 'KEY_F24'),
    ('\x1b[57388u', 57388, 'KEY_F25'),
    ('\x1b[57389u', 57389, 'KEY_F26'),
    ('\x1b[57390u', 57390, 'KEY_F27'),
    ('\x1b[57391u', 57391, 'KEY_F28'),
    ('\x1b[57392u', 57392, 'KEY_F29'),
    ('\x1b[57393u', 57393, 'KEY_F30'),
    ('\x1b[57394u', 57394, 'KEY_F31'),
    ('\x1b[57395u', 57395, 'KEY_F32'),
    ('\x1b[57396u', 57396, 'KEY_F33'),
    ('\x1b[57397u', 57397, 'KEY_F34'),
    ('\x1b[57398u', 57398, 'KEY_F35'),
])
def test_kitty_extended_f_keys(sequence, expected_code, expected_name):
    """Test extended function keys F13-F35."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._mode == -1  # Kitty protocol mode
    assert ks._match.unicode_key == expected_code
    assert ks.code == expected_code
    assert ks.name == expected_name
    # Functional keys don't produce text
    assert ks.value == ''


@pytest.mark.parametrize("sequence,expected_code,expected_name", [
    # Media control keys (57428-57440)
    ('\x1b[57428u', 57428, 'KEY_MEDIA_PLAY'),
    ('\x1b[57429u', 57429, 'KEY_MEDIA_PAUSE'),
    ('\x1b[57430u', 57430, 'KEY_MEDIA_PLAY_PAUSE'),
    ('\x1b[57431u', 57431, 'KEY_MEDIA_REVERSE'),
    ('\x1b[57432u', 57432, 'KEY_MEDIA_STOP'),
    ('\x1b[57433u', 57433, 'KEY_MEDIA_FAST_FORWARD'),
    ('\x1b[57434u', 57434, 'KEY_MEDIA_REWIND'),
    ('\x1b[57435u', 57435, 'KEY_MEDIA_TRACK_NEXT'),
    ('\x1b[57436u', 57436, 'KEY_MEDIA_TRACK_PREVIOUS'),
    ('\x1b[57437u', 57437, 'KEY_MEDIA_RECORD'),
    ('\x1b[57438u', 57438, 'KEY_LOWER_VOLUME'),
    ('\x1b[57439u', 57439, 'KEY_RAISE_VOLUME'),
    ('\x1b[57440u', 57440, 'KEY_MUTE_VOLUME'),
])
def test_kitty_media_keys(sequence, expected_code, expected_name):
    """Test media control and volume keys."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._mode == -1  # Kitty protocol mode
    assert ks._match.unicode_key == expected_code
    assert ks.code == expected_code
    assert ks.name == expected_name
    assert ks.value == ''  # Functional keys don't produce text


@pytest.mark.parametrize("sequence,expected_code,expected_name", [
    # ISO level shift keys (57453-57454)
    ('\x1b[57453u', 57453, 'KEY_ISO_LEVEL3_SHIFT'),
    ('\x1b[57454u', 57454, 'KEY_ISO_LEVEL5_SHIFT'),
])
def test_kitty_iso_level_shift_keys(sequence, expected_code, expected_name):
    """Test ISO level shift keys."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._mode == -1  # Kitty protocol mode
    assert ks._match.unicode_key == expected_code
    assert ks.code == expected_code
    assert ks.name == expected_name
    assert ks.value == ''  # Functional keys don't produce text


@pytest.mark.parametrize("sequence,expected_code,expected_name_part", [
    ('\x1b[57358;5u', 57358, 'KEY_CTRL_CAPS_LOCK'),  # Ctrl+CapsLock
    ('\x1b[57376;3u', 57376, 'KEY_ALT_F13'),  # Alt+F13
    ('\x1b[57428;2u', 57428, 'KEY_SHIFT_MEDIA_PLAY'),  # Shift+MediaPlay
    ('\x1b[57438;7u', 57438, 'KEY_CTRL_ALT_LOWER_VOLUME'),  # Ctrl+Alt+LowerVolume
])
def test_kitty_functional_keys_with_modifiers(sequence, expected_code, expected_name_part):
    """Test functional keys with various modifiers."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._mode == -1  # Kitty protocol mode
    assert ks._match.unicode_key == expected_code
    assert ks.code == expected_code
    assert ks.name == expected_name_part
    assert ks.value == ''  # Functional keys don't produce text


@pytest.mark.parametrize("sequence,expected_code,event_type", [
    ('\x1b[57361u', 57361, 1),  # PrintScreen press (default)
    ('\x1b[57361;1:1u', 57361, 1),  # PrintScreen press (explicit)
    ('\x1b[57361;1:2u', 57361, 2),  # PrintScreen repeat
    ('\x1b[57361;1:3u', 57361, 3),  # PrintScreen release
])
def test_kitty_functional_keys_event_types(sequence, expected_code, event_type):
    """Test functional keys with different event types."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._match.unicode_key == expected_code
    assert ks._match.event_type == event_type
    assert ks.pressed == (event_type == 1)
    assert ks.repeated == (event_type == 2)
    assert ks.released == (event_type == 3)


@pytest.mark.parametrize("sequence,expected_code,expected_name", [
    # Keypad digits with Ctrl
    ('\x1b[57399;5u', 57399, 'KEY_CTRL_KP_0'),
    ('\x1b[57400;5u', 57400, 'KEY_CTRL_KP_1'),
    ('\x1b[57408;5u', 57408, 'KEY_CTRL_KP_9'),
    # Keypad digits with Alt
    ('\x1b[57399;3u', 57399, 'KEY_ALT_KP_0'),
    ('\x1b[57405;3u', 57405, 'KEY_ALT_KP_6'),
    # Keypad digits with Shift
    ('\x1b[57399;2u', 57399, 'KEY_SHIFT_KP_0'),
    ('\x1b[57407;2u', 57407, 'KEY_SHIFT_KP_8'),
    # Keypad digits with Ctrl+Alt
    ('\x1b[57399;7u', 57399, 'KEY_CTRL_ALT_KP_0'),
    ('\x1b[57404;7u', 57404, 'KEY_CTRL_ALT_KP_5'),
    # Keypad digits with Ctrl+Shift
    ('\x1b[57399;6u', 57399, 'KEY_CTRL_SHIFT_KP_0'),
    ('\x1b[57403;6u', 57403, 'KEY_CTRL_SHIFT_KP_4'),
    # Keypad operators with Ctrl
    ('\x1b[57411;5u', 57411, 'KEY_CTRL_KP_MULTIPLY'),
    ('\x1b[57413;5u', 57413, 'KEY_CTRL_KP_ADD'),
    ('\x1b[57410;5u', 57410, 'KEY_CTRL_KP_DIVIDE'),
    ('\x1b[57412;5u', 57412, 'KEY_CTRL_KP_SUBTRACT'),
    # Keypad operators with Alt
    ('\x1b[57411;3u', 57411, 'KEY_ALT_KP_MULTIPLY'),
    ('\x1b[57413;3u', 57413, 'KEY_ALT_KP_ADD'),
    # Keypad operators with Ctrl+Alt
    ('\x1b[57409;7u', 57409, 'KEY_CTRL_ALT_KP_DECIMAL'),
    ('\x1b[57415;7u', 57415, 'KEY_CTRL_ALT_KP_EQUAL'),
])
def test_kitty_pua_keypad_with_modifiers(sequence, expected_code, expected_name):
    """Test PUA keypad keys with modifiers."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._mode == -1  # Kitty protocol mode
    assert ks._match.unicode_key == expected_code
    assert ks.code == expected_code
    assert ks.name == expected_name
    assert ks.value == ''  # Keypad keys don't produce text
    # Verify modifier flags
    if 'CTRL' in expected_name:
        assert ks._ctrl
    if 'ALT' in expected_name:
        assert ks._alt
    if 'SHIFT' in expected_name:
        assert ks._shift


def test_kitty_control_chars():
    """Test control character keys via Kitty protocol."""
    test_cases = [
        ('\x1b[27u', 27, KEY_EXIT, 'KEY_ESCAPE', '\x1b'),
        ('\x1b[9u', 9, KEY_TAB, 'KEY_TAB', '\t'),
        ('\x1b[13u', 13, KEY_ENTER, 'KEY_ENTER', '\n'),
        ('\x1b[127u', 127, KEY_BACKSPACE, 'KEY_BACKSPACE', '\x08'),
    ]

    for sequence, unicode_key, expected_code, expected_name, expected_value in test_cases:
        ks = _match_kitty_key(sequence)
        assert ks is not None
        assert ks._mode == -1
        assert ks._match.unicode_key == unicode_key
        assert ks.code == expected_code
        assert ks.name == expected_name
        assert ks.value == expected_value


@pytest.mark.parametrize("sequence,unicode_key,expected_code,expected_name", [
    ('\x1b[27;5u', 27, KEY_EXIT, 'KEY_CTRL_ESCAPE'),
    ('\x1b[27;3u', 27, KEY_EXIT, 'KEY_ALT_ESCAPE'),
    ('\x1b[27;7u', 27, KEY_EXIT, 'KEY_CTRL_ALT_ESCAPE'),
    ('\x1b[9;5u', 9, KEY_TAB, 'KEY_CTRL_TAB'),
    ('\x1b[9;3u', 9, KEY_TAB, 'KEY_ALT_TAB'),
    ('\x1b[13;5u', 13, KEY_ENTER, 'KEY_CTRL_ENTER'),
    ('\x1b[13;3u', 13, KEY_ENTER, 'KEY_ALT_ENTER'),
    ('\x1b[127;5u', 127, KEY_BACKSPACE, 'KEY_CTRL_BACKSPACE'),
    ('\x1b[127;3u', 127, KEY_BACKSPACE, 'KEY_ALT_BACKSPACE'),
])
def test_kitty_control_chars_with_modifiers(sequence, unicode_key, expected_code, expected_name):
    """Test control character keys with modifiers."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._mode == -1
    assert ks._match.unicode_key == unicode_key
    assert ks.code == expected_code
    assert ks.name == expected_name


@pytest.mark.parametrize("sequence,event_type", [
    ('\x1b[27u', 1),
    ('\x1b[27;1:1u', 1),
    ('\x1b[27;1:2u', 2),
    ('\x1b[27;1:3u', 3),
])
def test_kitty_control_chars_event_types(sequence, event_type):
    """Test control character event types."""
    ks = _match_kitty_key(sequence)
    assert ks is not None
    assert ks._match.event_type == event_type
    assert ks.pressed == (event_type == 1)
    assert ks.repeated == (event_type == 2)
    assert ks.released == (event_type == 3)


def test_kitty_escape_key_fallback_without_protocol():
    """Test that Kitty escape sequences fall back to CSI without protocol enabled."""
    @as_subprocess
    def child():
        term = Terminal(stream=io.StringIO(), force_styling=True)

        # Without Kitty protocol enabled, Kitty sequences are not in keymap
        # and fall back to CSI (\x1b[), leaving the rest unread

        term.ungetch('\x1b[27u')
        ks = term.inkey(timeout=0)
        assert ks == '\x1b['
        assert ks.name == 'CSI'
        assert ks.value == '['
        remaining = term.flushinp(timeout=0)
        assert remaining == '27u'

        term.ungetch('\x1b[27;5u')
        ks = term.inkey(timeout=0)
        assert ks == '\x1b['
        assert ks.name == 'CSI'
        remaining = term.flushinp(timeout=0)
        assert remaining == '27;5u'

        term.ungetch('\x1b[27;1:3u')
        ks = term.inkey(timeout=0)
        assert ks == '\x1b['
        assert ks.name == 'CSI'
        remaining = term.flushinp(timeout=0)
        assert remaining == '27;1:3u'

    child()


def test_kitty_escape_key_with_protocol_enabled():
    """Test Escape key with Kitty protocol explicitly enabled."""
    @as_subprocess
    def child():
        term = Terminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = True

        # Test plain ESC (without modifiers)
        ks = _match_kitty_key('\x1b[27u')
        assert ks is not None
        assert ks.name == 'KEY_ESCAPE'
        assert ks.code == KEY_EXIT
        assert ks.value == '\x1b'

        # Test Ctrl+ESC
        ks = _match_kitty_key('\x1b[27;5u')
        assert ks is not None
        assert ks.name == 'KEY_CTRL_ESCAPE'
        assert ks._ctrl is True

        # Test ESC release event
        ks = _match_kitty_key('\x1b[27;1:3u')
        assert ks is not None
        assert ks.released is True
        assert ks.name == 'KEY_ESCAPE_RELEASED'

    child()


def test_kitty_tab_key_integration():
    """Test Tab key integration with Terminal.inkey()."""
    @as_subprocess
    def child():
        term = Terminal(stream=io.StringIO(), force_styling=True)

        term.ungetch('\x1b[9u')
        ks = term.inkey(timeout=0)
        assert ks == '\x1b[9u'
        assert ks.name == 'KEY_TAB'
        assert ks.code == KEY_TAB  # 512, not 9
        assert ks.value == '\t'

        term.ungetch('\x1b[9;3u')
        ks = term.inkey(timeout=0)
        assert ks.name == 'KEY_ALT_TAB'
        assert ks._alt is True

    child()


def test_kitty_enter_backspace_integration():
    """Test Enter and Backspace integration."""
    @as_subprocess
    def child():
        term = Terminal(stream=io.StringIO(), force_styling=True)

        term.ungetch('\x1b[13u')
        ks = term.inkey(timeout=0)
        assert ks.name == 'KEY_ENTER'
        assert ks.value == '\n'

        term.ungetch('\x1b[127u')
        ks = term.inkey(timeout=0)
        assert ks.name == 'KEY_BACKSPACE'
        assert ks.value == '\x08'

    child()


@pytest.mark.skipif(not TEST_KEYBOARD, reason="TEST_KEYBOARD not specified")
def test_kitty_negotiation_timing_cached_failure():
    """Test timing of cached failure returns immediately."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = True

        stime = time.time()
        flags1 = term.get_kitty_keyboard_state(timeout=0.025)
        assert flags1 is None
        assert term._kitty_kb_first_query_failed is True
        elapsed_ms = (time.time() - stime) * 1000
        assert 24 <= elapsed_ms <= 35

        # any subsequent calls return immediately (as failed)
        stime = time.time()
        flags2 = term.get_kitty_keyboard_state(timeout=1.0)
        elapsed_ms = (time.time() - stime) * 1000
        assert flags2 is None
        assert elapsed_ms < 5

    child()


@pytest.mark.skipif(not TEST_KEYBOARD, reason="TEST_KEYBOARD not specified")
def test_kitty_negotiation_force_True_incurs_second_timeout():
    """Test timing of force=True incurs timeout again."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = True

        flags1 = term.get_kitty_keyboard_state(timeout=0.025)
        assert flags1 is None
        assert term._kitty_kb_first_query_failed is True

        # demonstrate that the 'force=True' argument works as designed by its
        # side-effect of exceeding our timeout (again).
        stime = time.time()
        flags2 = term.get_kitty_keyboard_state(timeout=0.025, force=True)
        elapsed_ms = (time.time() - stime) * 1000

        assert flags2 is None
        assert 20 <= elapsed_ms <= 35

    child()
