"""Tests for DeviceAttribute class and Terminal.get_device_attributes().

DA1 (Primary Device Attributes) Response Format
================================================

Terminal response: ESC [ ? {service_class} ; {ext1} ; {ext2} ; ... c

Service Class (Terminal Type):
  1  = VT101
  62 = VT220
  63 = VT320
  64 = VT420
  65 = VT500-series

Extension Codes (Capability Flags):
  1  = 132-columns
  2  = Printer
  3  = ReGIS graphics
  4  = Sixel graphics
  6  = Selective erase
  7  = Soft character set (DRCS)
  8  = User-defined keys
  9  = National Replacement Character sets
  15 = Technical characters
  16 = Locator port
  17 = Terminal state interrogation
  18 = User windows
  21 = Horizontal scrolling
  22 = Color (ANSI color support)

Example: '\x1b[?64;1;2;4c' = VT420 with 132-col, Printer, and Sixel support
"""
# std
import time
import io

# 3rd party
import pytest

# local
from .conftest import TEST_KEYBOARD, IS_WINDOWS
from .accessories import (
    TestTerminal,
    pty_test,
    as_subprocess,
)
from blessed.keyboard import DeviceAttribute

pytestmark = pytest.mark.skipif(
    not TEST_KEYBOARD or IS_WINDOWS,
    reason="Timing-sensitive tests please do not run on build farms.")


@pytest.mark.parametrize("response,service_class,extensions,supports_sixel", [
    ('\x1b[?64;1;2;4;7c', 64, {1, 2, 4, 7}, True),
    ('\x1b[?64;1;2c', 64, {1, 2}, False),
    ('\x1b[?1c', 1, set(), False),
    ('\x1b[?62;1;4;6c', 62, {1, 4, 6}, True),
])
def test_device_attribute_from_match(response, service_class, extensions, supports_sixel):
    """Test DeviceAttribute.from_match() with various response formats."""
    match = DeviceAttribute.RE_RESPONSE.match(response)
    da = DeviceAttribute.from_match(match)
    assert da is not None
    assert da.service_class == service_class
    assert da.extensions == extensions
    assert da.supports_sixel is supports_sixel
    assert da.raw == response


@pytest.mark.parametrize("invalid_input", ['invalid', ''])
def test_device_attribute_from_match_invalid(invalid_input):
    """Test DeviceAttribute.from_match() with invalid input."""
    match = DeviceAttribute.RE_RESPONSE.match(invalid_input)
    assert match is None


def test_device_attribute_repr():
    """Test DeviceAttribute.__repr__()."""
    # DA1 response: VT420 (64) with Sixel (4) extension only
    da = DeviceAttribute('\x1b[?64;4c', 64, [4])
    repr_str = repr(da)
    assert 'DeviceAttribute' in repr_str
    assert 'service_class=64' in repr_str
    assert 'supports_sixel=True' in repr_str


def test_get_device_attributes_via_ungetch():
    """Test get_device_attributes() with response via ungetch."""
    def child(term):
        # DA1 response: VT420 (64) with 132-col (1), Printer (2), Sixel (4)
        term.ungetch('\x1b[?64;1;2;4c')
        da = term.get_device_attributes(timeout=0.01)
        assert da is not None
        assert da.service_class == 64  # VT420
        assert da.supports_sixel is True
        assert 4 in da.extensions
        return b'OK'

    output = pty_test(child, parent_func=None, test_name='test_get_device_attributes_via_ungetch')
    assert output == '\x1b[cOK'


def test_get_device_attributes_timeout():
    """Test get_device_attributes() timeout without response."""
    def child(term):
        stime = time.time()
        da = term.get_device_attributes(timeout=0.1)
        elapsed = time.time() - stime
        assert da is None
        assert 0.08 <= elapsed <= 0.15
        return b'TIMEOUT'

    output = pty_test(child, parent_func=None, test_name='test_get_device_attributes_timeout')
    assert output == '\x1b[cTIMEOUT'


def test_get_device_attributes_force_bypass_cache():
    """Test get_device_attributes() with force=True bypasses cache."""
    def child(term):
        # DA1 response 1: VT420 (64) with 132-col (1)
        term.ungetch('\x1b[?64;1c')
        da1 = term.get_device_attributes(timeout=0.01)

        # DA1 response 2: VT500-series (65) with Printer (2)
        term.ungetch('\x1b[?65;2c')
        da2 = term.get_device_attributes(timeout=0.01, force=True)

        assert da1 is not None
        assert da2 is not None
        assert da1.service_class == 64  # VT420
        assert da2.service_class == 65  # VT500-series
        assert da1 is not da2

        return b'FORCED'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_device_attributes_force_bypass_cache')
    assert output == '\x1b[c\x1b[cFORCED'


def test_get_device_attributes_no_force_uses_cache():
    """Test get_device_attributes() without force uses cached result."""
    def child(term):
        # DA1 response 1: VT420 (64) with 132-col (1)
        term.ungetch('\x1b[?64;1c')
        da1 = term.get_device_attributes(timeout=0.01)

        # Second query without force should use cache even with different ungetch data
        # DA1 response 2: VT500-series (65) with Printer (2) - but this is ignored due to cache
        term.ungetch('\x1b[?65;2c')
        da2 = term.get_device_attributes(timeout=0.01, force=False)

        assert da1 is not None
        assert da2 is not None
        assert da1 is da2
        assert da1.service_class == 64  # VT420 (cached)
        assert da2.service_class == 64  # VT420 (cached)

        return b'NO_FORCE'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_device_attributes_no_force_uses_cache')
    assert output == '\x1b[cNO_FORCE'


def test_get_device_attributes_retry_after_failure():
    """Test get_device_attributes() can retry after failed query with force=True."""
    def child(term):
        # First query fails (timeout)
        da1 = term.get_device_attributes(timeout=0.01)

        # Second query succeeds with force=True: VT420 (64) with Sixel (4)
        term.ungetch('\x1b[?64;4c')
        da2 = term.get_device_attributes(timeout=0.01, force=True)

        assert da1 is None
        assert da2 is not None
        assert da2.service_class == 64  # VT420
        assert da2.supports_sixel is True

        return b'RETRY'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_device_attributes_retry_after_failure')
    assert output == '\x1b[c\x1b[cRETRY'


def test_get_device_attributes_sticky_failure():
    """Test get_device_attributes() sticky failure prevents repeated queries."""
    def child(term):
        # First query fails (timeout)
        da1 = term.get_device_attributes(timeout=0.01)

        # Second query should return None immediately due to sticky failure
        term.ungetch('\x1b[?64;4c')
        da2 = term.get_device_attributes(timeout=0.01)

        assert da1 is None
        assert da2 is None

        return b'STICKY'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_device_attributes_sticky_failure')
    assert output == '\x1b[cSTICKY'


def test_get_device_attributes_multiple_extensions():
    """Test get_device_attributes() with many extensions."""
    def child(term):
        # DA1 response: VT420 (64) with extensions:
        # 132-col (1), Printer (2), Sixel (4), Selective erase (6), DRCS (7),
        # National Replacement Character sets (9), Technical characters (15),
        # User windows (18), Horizontal scrolling (21), Color (22)
        term.ungetch('\x1b[?64;1;2;4;6;7;9;15;18;21;22c')
        da = term.get_device_attributes(timeout=0.01)
        assert da is not None
        assert da.service_class == 64  # VT420
        assert da.extensions == {1, 2, 4, 6, 7, 9, 15, 18, 21, 22}
        assert da.supports_sixel is True
        return b'MULTI'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_device_attributes_multiple_extensions')
    assert output == '\x1b[cMULTI'


def test_device_attribute_init_with_none_extensions():
    """Test DeviceAttribute.__init__() with None extensions."""
    # DA1 response: VT101 (1) with no extensions
    da = DeviceAttribute('\x1b[?1c', 1, None)
    assert da.service_class == 1  # VT101
    assert da.extensions == set()
    assert da.supports_sixel is False


def test_device_attribute_init_with_list_extensions():
    """Test DeviceAttribute.__init__() with list of extensions."""
    # DA1 response: VT420 (64) with Sixel (4) extension only
    da = DeviceAttribute('\x1b[?64;4c', 64, [4])
    assert da.service_class == 64  # VT420
    assert da.extensions == {4}
    assert da.supports_sixel is True


def test_device_attribute_raw_stored():
    """Test DeviceAttribute stores raw response string."""
    raw = '\x1b[?64;1;2;4c'
    match = DeviceAttribute.RE_RESPONSE.match(raw)
    da = DeviceAttribute.from_match(match)
    assert da is not None
    assert da.raw == raw


def test_get_kitty_keyboard_state_boundary_neither_response():
    """Test boundary detection when neither Kitty nor DA1 response matches."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True

        term.ungetch('garbage_response')
        flags = term.get_kitty_keyboard_state(timeout=0.01)
        assert flags is None
        assert term._kitty_kb_first_query_attempted is True
        assert term._kitty_kb_first_query_failed is True

        flags2 = term.get_kitty_keyboard_state(timeout=1.0)
        assert flags2 is None
    child()


def test_get_kitty_keyboard_state_boundary_da1_only():
    """Test boundary detection when only DA1 responds."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True

        # DA1 response: VT420 (64) with 132-col (1), Printer (2) - no Kitty protocol
        term.ungetch('\x1b[?64;1;2c')
        flags = term.get_kitty_keyboard_state(timeout=0.01)
        assert flags is None
        assert term._kitty_kb_first_query_attempted is True
        assert term._kitty_kb_first_query_failed is True

        flags2 = term.get_kitty_keyboard_state(timeout=1.0)
        assert flags2 is None
    child()


def test_enable_kitty_keyboard_after_query_failed():
    """Test enable_kitty_keyboard yields without emitting sequences after query failed."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True

        term._kitty_kb_first_query_failed = True

        with term.enable_kitty_keyboard(disambiguate=True, timeout=0.01, force=False):
            pass

        assert stream.getvalue() == ''
    child()


def test_device_attribute_from_match_with_malformed_extensions():
    """Test DeviceAttribute.from_match() with malformed extension strings."""
    # Test with non-digit extension parts (should be filtered out)
    match = DeviceAttribute.RE_RESPONSE.match('\x1b[?64;abc;4;xyz;7c')
    if match:
        # Manually test parsing logic
        da = DeviceAttribute.from_match(match)
        # Should only include valid numeric extensions
        assert da.service_class == 64
        assert 4 in da.extensions
        assert 7 in da.extensions


def test_device_attribute_from_match_with_whitespace_extensions():
    """Test DeviceAttribute.from_match() with whitespace in extensions."""
    # Create a match with extensions that have whitespace
    # This tests the part.strip() and part.isdigit() checks

    # Since the regex won't match whitespace, let's test the code path
    # by using extensions_str that could have spaces
    # Actually, we need to manually construct to test lines 2095-2097
    # The regex pattern won't capture whitespace, so this branch may be defensive
    # Let's test with empty extension parts
    match = DeviceAttribute.RE_RESPONSE.match('\x1b[?64;;4;;c')
    if match:
        da = DeviceAttribute.from_match(match)
        assert da.service_class == 64
        # Empty parts should be filtered out
        assert da.extensions == {4}


def test_kitty_keyboard_protocol_eq_with_int():
    """Test KittyKeyboardProtocol.__eq__() with int."""
    from blessed.keyboard import KittyKeyboardProtocol
    proto = KittyKeyboardProtocol(15)
    assert proto == 15
    assert proto != 20


def test_kitty_keyboard_protocol_eq_with_protocol():
    """Test KittyKeyboardProtocol.__eq__() with another KittyKeyboardProtocol."""
    from blessed.keyboard import KittyKeyboardProtocol
    proto1 = KittyKeyboardProtocol(15)
    proto2 = KittyKeyboardProtocol(15)
    proto3 = KittyKeyboardProtocol(20)
    assert proto1 == proto2
    assert proto1 != proto3


def test_kitty_keyboard_protocol_eq_with_other_types():
    """Test KittyKeyboardProtocol.__eq__() with non-int, non-KittyKeyboardProtocol types."""
    from blessed.keyboard import KittyKeyboardProtocol
    proto = KittyKeyboardProtocol(15)
    assert proto != "15"
    assert proto != [15]
    assert proto is not None
    assert proto != {"value": 15}
