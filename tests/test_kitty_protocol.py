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
    event = ks._match
    assert event.unicode_key == 97
    assert event.shifted_key == 65
    assert event.base_key == 99
    assert event.modifiers == 6
    assert event.event_type == 2
    assert event.int_codepoints == (65, 66)


@pytest.mark.parametrize("sequence", [
    'a',
    '\x1b[A',
    '\x1b[97',
    '\x1b]97u',
    '\x1b[97v',
])
def test_match_kitty_non_matching(sequence):
    """Test non-Kitty sequences return None."""
    assert _match_kitty_key(sequence) is None


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


@pytest.mark.parametrize("value,dis,events,alt,all_keys,text", [
    (0, False, False, False, False, False),
    (1, True, False, False, False, False),
    (2, False, True, False, False, False),
    (4, False, False, True, False, False),
    (8, False, False, False, True, False),
    (16, False, False, False, False, True),
    (31, True, True, True, True, True),
    (5, True, False, True, False, False),
    (9, True, False, False, True, False),
    (18, False, True, False, False, True),
])
def test_kitty_keyboard_protocol_properties(
        # pylint: disable=too-many-positional-arguments
        value, dis, events, alt, all_keys, text):
    """Test KittyKeyboardProtocol flag parsing, make_arguments, repr, and equality."""
    proto = KittyKeyboardProtocol(value)
    assert proto.value == value
    assert proto.disambiguate == dis
    assert proto.report_events == events
    assert proto.report_alternates == alt
    assert proto.report_all_keys == all_keys
    assert proto.report_text == text

    expected_args = {
        'disambiguate': dis,
        'report_events': events,
        'report_alternates': alt,
        'report_all_keys': all_keys,
        'report_text': text
    }
    assert proto.make_arguments() == expected_args

    repr_str = repr(proto)
    assert f'KittyKeyboardProtocol(value={value}' in repr_str
    if value == 0:
        assert 'flags=[]' in repr_str

    proto_copy = KittyKeyboardProtocol(value)
    assert proto == proto_copy
    assert proto == value
    if value != 10:
        assert proto != 10


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

        # Test with styling disabled, still works when is_a_tty is True
        term = TestTerminal(stream=io.StringIO(), force_styling=False)
        term._is_a_tty = True
        term.ungetch('\x1b[?15u\x1b[?64c')
        flags = term.get_kitty_keyboard_state(timeout=0.01)
        assert flags is not None
        assert flags.value == 15
        assert flags.disambiguate is True
        assert flags.report_events is True
        assert flags.report_alternates is True
        assert flags.report_all_keys is True
        assert flags.report_text is False
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


def test_enable_kitty_keyboard_all_flag_operations():
    """Test all flag bit operations in enable_kitty_keyboard."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        given_flags_response = '\x1b[?0u'  # flags 0 (no flags currently set)
        expected_enable_seq = '\x1b[=31;1u'  # flags 31 (1+2+4+8+16: all 5 flags), mode 1 (push)
        term.ungetch(given_flags_response)
        with term.enable_kitty_keyboard(
            disambiguate=True,
            report_events=True,
            report_alternates=True,
            report_all_keys=True,
            report_text=True,
            timeout=0.01,
            force=True
        ):
            pass
        output = stream.getvalue()
        assert expected_enable_seq in output
    child()


def test_enable_kitty_keyboard_sequence_emission():
    """Test sequence emission and flush in enable_kitty_keyboard."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        given_flags_response = '\x1b[?5u'  # flags 5 (1+4: disambiguate+report_alternates)
        expected_enable_seq = '\x1b[=1;1u'  # flags 1 (disambiguate), mode 1 (push)
        expected_restore_seq = '\x1b[=5;1u'  # flags 5 (restore previous), mode 1
        term.ungetch(given_flags_response)
        with term.enable_kitty_keyboard(disambiguate=True, timeout=0.01, force=True):
            output_during = stream.getvalue()
            assert expected_enable_seq in output_during
        output_after = stream.getvalue()
        assert expected_restore_seq in output_after
    child()


def test_enable_kitty_keyboard_restoration_with_previous_flags():
    """Test restoration logic when previous flags exist."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        given_flags_response = '\x1b[?9u'  # flags 9 (1+8: disambiguate+report_all_keys)
        expected_restore_seq = '\x1b[=9;1u'  # flags 9 (restore previous), mode 1
        term.ungetch(given_flags_response)
        with term.enable_kitty_keyboard(disambiguate=True, report_all_keys=True,
                                        timeout=0.01, force=True):
            pass
        output = stream.getvalue()
        assert expected_restore_seq in output
    child()


def test_enable_kitty_keyboard_sticky_failure():
    """Test enable_kitty_keyboard skips when first query failed."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._kitty_kb_first_query_failed = True
        with term.enable_kitty_keyboard(disambiguate=True, timeout=0.01):
            pass
        assert stream.getvalue() == ''
    child()


@pytest.mark.parametrize("flags,expected_value", [
    ({'disambiguate': True}, 1),
    ({'report_events': True}, 2),
    ({'report_alternates': True}, 4),
    ({'report_all_keys': True}, 8),
    ({'report_text': True}, 16),
    ({'disambiguate': True, 'report_events': True}, 3),
    ({'disambiguate': True, 'report_alternates': True}, 5),
    ({'report_events': True, 'report_all_keys': True}, 10),
    ({'report_alternates': True, 'report_text': True}, 20),
    ({'disambiguate': True, 'report_events': True, 'report_alternates': True}, 7),
    ({'report_all_keys': True, 'report_text': True, 'disambiguate': True}, 25),
])
def test_kitty_keyboard_protocol_setters(flags, expected_value):
    """Test KittyKeyboardProtocol property setters with various combinations."""
    protocol = KittyKeyboardProtocol(0)
    for flag_name, flag_value in flags.items():
        setattr(protocol, flag_name, flag_value)
    assert protocol.value == expected_value
    for flag_name, expected_flag_value in flags.items():
        assert getattr(protocol, flag_name) == expected_flag_value


def test_get_kitty_state_boundary_no_response():
    """Test boundary approach when neither Kitty nor DA1 response found."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term.ungetch('garbage response')
        expected_kitty_query = '\x1b[?u'  # query current flags
        expected_da1_query = '\x1b[c'  # device attributes query
        flags = term.get_kitty_keyboard_state(timeout=0.01)
        assert flags is None
        assert term._kitty_kb_first_query_failed is True
        output = stream.getvalue()
        assert expected_kitty_query in output
        assert expected_da1_query in output
    child()


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


@pytest.mark.parametrize("sequence,expected_name,expected_value", [
    ('\x1b[49;3u', 'KEY_ALT_1', '1'),
    ('\x1b[49;5u', 'KEY_CTRL_1', '1'),
    ('\x1b[49;4u', 'KEY_ALT_SHIFT_1', '1'),
    ('\x1b[50;3u', 'KEY_ALT_2', '2'),
    ('\x1b[57;5u', 'KEY_CTRL_9', '9'),
    ('\x1b[48;7u', 'KEY_CTRL_ALT_0', '0'),
    ('\x1b[97;5u', 'KEY_CTRL_A', 'a'),
    ('\x1b[97;3u', 'KEY_ALT_A', 'a'),
    ('\x1b[97;7u', 'KEY_CTRL_ALT_A', 'a'),
    ('\x1b[97;2u', 'KEY_SHIFT_A', 'a'),
    ('\x1b[97;6u', 'KEY_CTRL_SHIFT_A', 'a'),
    ('\x1b[97;4u', 'KEY_ALT_SHIFT_A', 'a'),
    ('\x1b[97;8u', 'KEY_CTRL_ALT_SHIFT_A', 'a'),
    ('\x1b[65;5u', 'KEY_CTRL_A', 'A'),
    ('\x1b[90;5u', 'KEY_CTRL_Z', 'Z'),
    ('\x1b[122;5u', 'KEY_CTRL_Z', 'z'),
    ('\x1b[77;3u', 'KEY_ALT_M', 'M'),
    ('\x1b[109;3u', 'KEY_ALT_M', 'm'),
    ('\x1b[97;9u', 'KEY_SUPER_A', 'a'),
    ('\x1b[97;17u', 'KEY_HYPER_A', 'a'),
    ('\x1b[97;33u', 'KEY_META_A', 'a'),
    ('\x1b[97;13u', 'KEY_CTRL_SUPER_A', 'a'),
    ('\x1b[97;11u', 'KEY_ALT_SUPER_A', 'a'),
])
def test_kitty_letter_digit_name_synthesis(sequence, expected_name, expected_value):
    """Test letter and digit name synthesis with modifiers."""
    ks = _match_kitty_key(sequence)
    assert ks.name == expected_name
    assert ks.value == expected_value


@pytest.mark.parametrize("sequence,expected_name,expected_value", [
    ('\x1b[49u', None, '1'),
    ('\x1b[97;1u', None, 'a'),
    ('\x1b[65;1u', None, 'A'),
    ('\x1b[122;1u', None, 'z'),
    ('\x1b[97u', None, 'a'),
    ('\x1b[32;5u', None, ' '),
    ('\x1b[33;3u', None, '!'),
    ('\x1b[59;5u', None, ';'),
    ('\x1b[46;3u', None, '.'),
    ('\x1b[64;5u', None, '@'),
    ('\x1b[91;3u', 'CSI', '['),
])
def test_kitty_name_synthesis_edge_cases(sequence, expected_name, expected_value):
    """Test name synthesis edge cases."""
    ks = _match_kitty_key(sequence)
    assert ks.name == expected_name
    assert ks.value == expected_value


@pytest.mark.parametrize("sequence,expected_name", [
    # Base key usage: unicode_key=1089, base_key=99 ('c'), modifiers=5 (Ctrl)
    ('\x1b[1089::99;5u', 'KEY_CTRL_C'),

    # Press event: unicode_key=97 ('a'), modifiers=5 (Ctrl), event_type=1 (press)
    ('\x1b[97;5:1u', 'KEY_CTRL_A'),

    # Release event: unicode_key=97 ('a'), modifiers=5 (Ctrl), event_type=3 (release)
    ('\x1b[97;5:3u', 'KEY_CTRL_A_RELEASED'),

    # Repeat event: unicode_key=97 ('a'), modifiers=5 (Ctrl), event_type=2 (repeat)
    ('\x1b[97;5:2u', 'KEY_CTRL_A_REPEATED'),

    # Additional release event tests - text keys with modifiers
    ('\x1b[106;5:3u', 'KEY_CTRL_J_RELEASED'),
    ('\x1b[106;5u', 'KEY_CTRL_J'),
    ('\x1b[97;3:3u', 'KEY_ALT_A_RELEASED'),
    ('\x1b[122;7:3u', 'KEY_CTRL_ALT_Z_RELEASED'),
    ('\x1b[49;5:3u', 'KEY_CTRL_1_RELEASED'),

    # Repeat event tests
    ('\x1b[106;5:2u', 'KEY_CTRL_J_REPEATED'),
    ('\x1b[97;3:2u', 'KEY_ALT_A_REPEATED'),
])
def test_kitty_name_synthesis_special_cases(sequence, expected_name):
    """Test special cases in Kitty protocol name synthesis including event types."""
    ks = _match_kitty_key(sequence)
    assert ks.name == expected_name


def test_kitty_name_synthesis_custom_name():
    """Test custom name override in name synthesis."""
    kitty_event = KittyKeyEvent(unicode_key=97, shifted_key=None, base_key=None,
                                modifiers=5, event_type=1, int_codepoints=())
    ks = Keystroke('\x1b[97;5u', name='CUSTOM_NAME', mode=-1, match=kitty_event)
    assert ks.name == 'CUSTOM_NAME'


@pytest.mark.parametrize("sequence,expected_name", [
    ('\x1b[97;5u', 'KEY_CTRL_A'),
    ('\x1b[122;3u', 'KEY_ALT_Z'),
    ('\x1b[77;7u', 'KEY_CTRL_ALT_M'),
    ('\x1b[98;6u', 'KEY_CTRL_SHIFT_B'),
])
def test_kitty_letter_name_synthesis_integration(sequence, expected_name):
    """Test letter name synthesis with Terminal.inkey()."""
    @as_subprocess
    def child():
        term = Terminal(force_styling=True)
        term.ungetch(sequence)
        ks = term.inkey(timeout=0)
        assert ks == sequence
        assert ks.name == expected_name
    child()


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


@pytest.mark.parametrize("sequence,expected_name", [
    ('\x1b[91;5u', 'CSI'),
    ('\x1b[64;5u', None),
    ('\x1b[96;5u', None),
    ('\x1b[123;5u', None),
    ('\x1b[65;5u', 'KEY_CTRL_A'),
    ('\x1b[90;5u', 'KEY_CTRL_Z'),
    ('\x1b[97;5u', 'KEY_CTRL_A'),
    ('\x1b[122;5u', 'KEY_CTRL_Z'),
])
def test_kitty_letter_name_synthesis_boundary_conditions(sequence, expected_name):
    """Test boundary conditions for letter detection."""
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
    # removed redundant assertion
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
    assert ks._match.event_type == event_type
    assert ks.pressed == (event_type == 1)
    assert ks.repeated == (event_type == 2)
    assert ks.released == (event_type == 3)


@pytest.mark.parametrize("sequence,expected_code,expected_name,ctrl,alt,released,repeated", [
    ('\x1b[57424u', 57424, 'KEY_KP_END', False, False, False, False),
    ('\x1b[57399u', 57399, 'KEY_KP_0', False, False, False, False),
    ('\x1b[57414u', 57414, 'KEY_KP_ENTER', False, False, False, False),
    ('\x1b[57424;5u', 57424, 'KEY_CTRL_KP_END', True, False, False, False),
    ('\x1b[57424;7u', 57424, 'KEY_CTRL_ALT_KP_END', True, True, False, False),
    ('\x1b[57424;1:3u', 57424, 'KEY_KP_END_RELEASED', False, False, True, False),
    ('\x1b[57424;1:2u', 57424, 'KEY_KP_END_REPEATED', False, False, False, True),
])
def test_kitty_keypad_inkey_integration(
        # pylint: disable=too-many-positional-arguments
        sequence, expected_code, expected_name, ctrl, alt, released, repeated):
    """Test keypad integration with Terminal.inkey()."""
    @as_subprocess
    def child():
        term = Terminal(stream=io.StringIO(), force_styling=True)
        term.ungetch(sequence)
        ks = term.inkey(timeout=0)
        if not released and not repeated:
            assert ks == sequence
            assert ks.code == expected_code
        assert ks.name == expected_name
        assert ks._ctrl == ctrl
        assert ks._alt == alt
        assert ks.released == released
        assert ks.repeated == repeated
    child()


@pytest.mark.parametrize("digit", range(10))
def test_kitty_keypad_digit_keys(digit):
    """Test keypad digit keys 0-9."""
    code = 57399 + digit
    sequence = f'\x1b[{code}u'
    expected_name = f'KEY_KP_{digit}'

    ks = _match_kitty_key(sequence)
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
    assert ks._match.unicode_key == expected_code
    assert ks.code == expected_code
    assert ks.name == expected_name

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


@pytest.mark.parametrize("sequence,unicode_key,expected_code,expected_name,expected_value", [
    ('\x1b[27u', 27, KEY_EXIT, 'KEY_ESCAPE', '\x1b'),
    ('\x1b[9u', 9, KEY_TAB, 'KEY_TAB', '\t'),
    ('\x1b[13u', 13, KEY_ENTER, 'KEY_ENTER', '\n'),
    ('\x1b[127u', 127, KEY_BACKSPACE, 'KEY_BACKSPACE', '\x08'),
])
def test_kitty_control_chars(sequence, unicode_key, expected_code, expected_name, expected_value):
    """Test control character keys via Kitty protocol."""
    ks = _match_kitty_key(sequence)
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
    assert ks._match.event_type == event_type
    assert ks.pressed == (event_type == 1)
    assert ks.repeated == (event_type == 2)
    assert ks.released == (event_type == 3)


@pytest.mark.parametrize(
    "sequence,expected_name,expected_code,expected_value,is_ctrl,is_released",
    [
        ('\x1b[27u', 'KEY_ESCAPE', KEY_EXIT, '\x1b', False, False),
        ('\x1b[27;5u', 'KEY_CTRL_ESCAPE', KEY_EXIT, None, True, False),
        ('\x1b[27;1:3u', 'KEY_ESCAPE_RELEASED', KEY_EXIT, None, False, True),
    ])
def test_kitty_escape_key_with_protocol_enabled(
        # pylint: disable=too-many-positional-arguments
        sequence, expected_name, expected_code, expected_value, is_ctrl, is_released):
    """Test Escape key with Kitty protocol explicitly enabled."""
    ks = _match_kitty_key(sequence)
    assert ks.name == expected_name
    assert ks.code == expected_code
    if expected_value is not None:
        assert ks.value == expected_value
    if is_ctrl:
        assert ks._ctrl is True
    if is_released:
        assert ks.released is True


@pytest.mark.parametrize("sequence,expected_name,expected_code,ctrl,alt,released,repeated", [
    ('\x1b[27u', 'KEY_ESCAPE', KEY_EXIT, False, False, False, False),
    ('\x1b[27;1:1u', 'KEY_ESCAPE', KEY_EXIT, False, False, False, False),
    ('\x1b[27;1:3u', 'KEY_ESCAPE_RELEASED', KEY_EXIT, False, False, True, False),
    ('\x1b[27;1:2u', 'KEY_ESCAPE_REPEATED', KEY_EXIT, False, False, False, True),
    ('\x1b[27;5u', 'KEY_CTRL_ESCAPE', KEY_EXIT, True, False, False, False),
    ('\x1b[27;3u', 'KEY_ALT_ESCAPE', KEY_EXIT, False, True, False, False),
    ('\x1b[27;7u', 'KEY_CTRL_ALT_ESCAPE', KEY_EXIT, True, True, False, False),
])
def test_kitty_escape_key_integration(
        # pylint: disable=too-many-positional-arguments
        sequence, expected_name, expected_code, ctrl, alt, released, repeated):
    """Test ESC key sequences via Terminal.inkey() integration."""
    @as_subprocess
    def child():
        term = Terminal(stream=io.StringIO(), force_styling=True)
        term.ungetch(sequence)
        ks = term.inkey(timeout=0)
        assert ks == sequence
        assert ks.name == expected_name
        assert ks.code == expected_code
        assert ks._ctrl == ctrl
        assert ks._alt == alt
        assert ks.released == released
        assert ks.repeated == repeated
        if released:
            assert ks.value == ''
        else:
            assert ks.value == '\x1b'
    child()


@pytest.mark.parametrize("sequence,expected_name,expected_code,expected_value,alt", [
    ('\x1b[9u', 'KEY_TAB', KEY_TAB, '\t', False),
    ('\x1b[9;3u', 'KEY_ALT_TAB', KEY_TAB, '\t', True),
    ('\x1b[13u', 'KEY_ENTER', KEY_ENTER, '\n', False),
    ('\x1b[127u', 'KEY_BACKSPACE', KEY_BACKSPACE, '\x08', False),
])
def test_kitty_control_key_integration(sequence, expected_name, expected_code, expected_value, alt):
    """Test control key integration with Terminal.inkey()."""
    @as_subprocess
    def child():
        term = Terminal(stream=io.StringIO(), force_styling=True)
        term.ungetch(sequence)
        ks = term.inkey(timeout=0)
        assert ks.name == expected_name
        assert ks.code == expected_code
        assert ks.value == expected_value
        assert ks._alt == alt
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


def test_kitty_keyboard_protocol_report_all_keys_setter_false():
    """Test report_all_keys setter with False value."""
    protocol = KittyKeyboardProtocol(31)
    assert protocol.report_all_keys is True
    protocol.report_all_keys = False
    assert protocol.report_all_keys is False
    assert protocol.value == 23


def test_kitty_keyboard_protocol_report_text_getter_setter():
    """Test report_text property getter and setter."""
    protocol = KittyKeyboardProtocol(0)
    assert protocol.report_text is False
    protocol.report_text = True
    assert protocol.report_text is True
    assert protocol.value == 16
    protocol.report_text = False
    assert protocol.report_text is False
    assert protocol.value == 0


@pytest.mark.parametrize("value,expected_flags", [
    (0, []),
    (1, ['disambiguate']),
    (2, ['report_events']),
    (4, ['report_alternates']),
    (8, ['report_all_keys']),
    (16, ['report_text']),
    (3, ['disambiguate', 'report_events']),
    (12, ['report_alternates', 'report_all_keys']),
    (31, ['disambiguate', 'report_events', 'report_alternates', 'report_all_keys', 'report_text']),
])
def test_kitty_keyboard_protocol_repr_all_combinations(value, expected_flags):
    """Test __repr__ with all flag combinations."""
    protocol = KittyKeyboardProtocol(value)
    repr_str = repr(protocol)
    assert f'KittyKeyboardProtocol(value={value}' in repr_str
    for flag in expected_flags:
        assert flag in repr_str
    if not expected_flags:
        assert 'flags=[]' in repr_str


def test_kitty_keyboard_protocol_equality_with_protocol():
    """Test __eq__ with another KittyKeyboardProtocol instance."""
    proto1 = KittyKeyboardProtocol(15)
    proto2 = KittyKeyboardProtocol(15)
    proto3 = KittyKeyboardProtocol(7)
    assert proto1 == proto2
    assert proto1 != proto3


def test_kitty_keyboard_protocol_equality_with_int():
    """Test __eq__ with int values."""
    protocol = KittyKeyboardProtocol(15)
    assert protocol == 15
    assert protocol != 7


def test_kitty_keyboard_protocol_equality_with_other_types():
    """Test __eq__ with types that are neither KittyKeyboardProtocol nor int."""
    protocol = KittyKeyboardProtocol(15)
    assert protocol != "15"
    assert protocol != 15.0
    assert protocol is not None
    assert protocol != [15]
    assert protocol != {'value': 15}
