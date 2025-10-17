"""Tests for DeviceAttribute class and Terminal.get_device_attributes()."""
# std
import time
import re
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


def test_device_attribute_from_string_with_sixel():
    """Test DeviceAttribute.from_string() with sixel support."""
    da = DeviceAttribute.from_string('\x1b[?64;1;2;4;7c')
    assert da is not None
    assert da.service_class == 64
    assert da.extensions == {1, 2, 4, 7}
    assert da.supports_sixel is True


def test_device_attribute_from_string_without_sixel():
    """Test DeviceAttribute.from_string() without sixel support."""
    da = DeviceAttribute.from_string('\x1b[?64;1;2c')
    assert da is not None
    assert da.service_class == 64
    assert da.extensions == {1, 2}
    assert da.supports_sixel is False


def test_device_attribute_from_string_no_extensions():
    """Test DeviceAttribute.from_string() with no extensions."""
    da = DeviceAttribute.from_string('\x1b[?1c')
    assert da is not None
    assert da.service_class == 1
    assert da.extensions == set()
    assert da.supports_sixel is False


def test_device_attribute_from_string_invalid():
    """Test DeviceAttribute.from_string() with invalid input."""
    da = DeviceAttribute.from_string('invalid')
    assert da is None
    da = DeviceAttribute.from_string('')
    assert da is None


def test_device_attribute_repr():
    """Test DeviceAttribute.__repr__()."""
    da = DeviceAttribute('\x1b[?64;4c', 64, [4])
    repr_str = repr(da)
    assert 'DeviceAttribute' in repr_str
    assert 'service_class=64' in repr_str
    assert 'supports_sixel=True' in repr_str


def test_get_device_attributes_via_ungetch():
    """Test get_device_attributes() with response via ungetch."""
    def child(term):
        term.ungetch('\x1b[?64;1;2;4c')
        da = term.get_device_attributes(timeout=0.01)
        assert da is not None
        assert da.service_class == 64
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
        # Set up two different responses
        term.ungetch('\x1b[?64;1c')
        da1 = term.get_device_attributes(timeout=0.01)

        # Now force a new query with different response
        term.ungetch('\x1b[?65;2c')
        da2 = term.get_device_attributes(timeout=0.01, force=True)

        assert da1 is not None
        assert da2 is not None
        assert da1.service_class == 64
        assert da2.service_class == 65
        assert da1 is not da2

        return b'FORCED'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_device_attributes_force_bypass_cache')
    assert output == '\x1b[c\x1b[cFORCED'


def test_get_device_attributes_no_force_uses_cache():
    """Test get_device_attributes() without force uses cached result."""
    def child(term):
        # First query
        term.ungetch('\x1b[?64;1c')
        da1 = term.get_device_attributes(timeout=0.01)

        # Second query without force should use cache even with different ungetch data
        term.ungetch('\x1b[?65;2c')
        da2 = term.get_device_attributes(timeout=0.01, force=False)

        assert da1 is not None
        assert da2 is not None
        assert da1 is da2
        assert da1.service_class == 64
        assert da2.service_class == 64

        return b'NO_FORCE'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_device_attributes_no_force_uses_cache')
    assert output == '\x1b[cNO_FORCE'


def test_get_device_attributes_retry_after_failure():
    """Test get_device_attributes() can retry after failed query."""
    def child(term):
        # First query fails (timeout)
        da1 = term.get_device_attributes(timeout=0.01)

        # Second query succeeds
        term.ungetch('\x1b[?64;4c')
        da2 = term.get_device_attributes(timeout=0.01)

        assert da1 is None
        assert da2 is not None
        assert da2.service_class == 64
        assert da2.supports_sixel is True

        return b'RETRY'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_device_attributes_retry_after_failure')
    assert output == '\x1b[c\x1b[cRETRY'


def test_get_device_attributes_multiple_extensions():
    """Test get_device_attributes() with many extensions."""
    def child(term):
        term.ungetch('\x1b[?64;1;2;4;6;7;9;15;18;21;22c')
        da = term.get_device_attributes(timeout=0.01)
        assert da is not None
        assert da.service_class == 64
        assert da.extensions == {1, 2, 4, 6, 7, 9, 15, 18, 21, 22}
        assert da.supports_sixel is True
        return b'MULTI'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_device_attributes_multiple_extensions')
    assert output == '\x1b[cMULTI'


def test_device_attribute_from_match():
    """Test DeviceAttribute.from_match() method."""
    pattern = re.compile(r'\x1b\[\?([0-9]+)((?:;[0-9]+)*)c')
    match = pattern.match('\x1b[?62;1;4;6c')

    da = DeviceAttribute.from_match(match)
    assert da is not None
    assert da.service_class == 62
    assert da.extensions == {1, 4, 6}
    assert da.supports_sixel is True


def test_device_attribute_from_match_no_extensions():
    """Test DeviceAttribute.from_match() with no extensions."""
    pattern = re.compile(r'\x1b\[\?([0-9]+)((?:;[0-9]+)*)c')
    match = pattern.match('\x1b[?1c')

    da = DeviceAttribute.from_match(match)
    assert da is not None
    assert da.service_class == 1
    assert da.extensions == set()
    assert da.supports_sixel is False


def test_device_attribute_init_with_none_extensions():
    """Test DeviceAttribute.__init__() with None extensions."""
    da = DeviceAttribute('\x1b[?1c', 1, None)
    assert da.service_class == 1
    assert da.extensions == set()
    assert da.supports_sixel is False


def test_device_attribute_init_with_list_extensions():
    """Test DeviceAttribute.__init__() with list of extensions."""
    da = DeviceAttribute('\x1b[?64;4c', 64, [4])
    assert da.service_class == 64
    assert da.extensions == {4}
    assert da.supports_sixel is True


def test_device_attribute_raw_stored():
    """Test DeviceAttribute stores raw response string."""
    raw = '\x1b[?64;1;2;4c'
    da = DeviceAttribute.from_string(raw)
    assert da is not None
    assert da.raw == raw


def test_does_sixel_returns_true_with_support():
    """Test does_sixel() returns True when terminal supports sixel."""
    def child(term):
        term.ungetch('\x1b[?64;1;2;4c')
        result = term.does_sixel(timeout=0.01)
        assert result is True
        return b'SIXEL_YES'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_sixel_returns_true_with_support')
    assert output == '\x1b[cSIXEL_YES'


def test_does_sixel_returns_false_without_support():
    """Test does_sixel() returns False when terminal doesn't support sixel."""
    def child(term):
        term.ungetch('\x1b[?64;1;2c')
        result = term.does_sixel(timeout=0.01)
        assert result is False
        return b'SIXEL_NO'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_sixel_returns_false_without_support')
    assert output == '\x1b[cSIXEL_NO'


def test_does_sixel_returns_false_on_timeout():
    """Test does_sixel() returns False when timeout occurs."""
    def child(term):
        stime = time.time()
        result = term.does_sixel(timeout=0.1)
        elapsed = time.time() - stime
        assert result is False
        assert 0.08 <= elapsed <= 0.15
        return b'SIXEL_TIMEOUT'

    output = pty_test(child, parent_func=None, test_name='test_does_sixel_returns_false_on_timeout')
    assert output == '\x1b[cSIXEL_TIMEOUT'


def test_does_sixel_uses_cache():
    """Test does_sixel() uses cached device attributes."""
    def child(term):
        term.ungetch('\x1b[?64;1;2;4c')
        result1 = term.does_sixel(timeout=0.01)

        result2 = term.does_sixel(timeout=0.01)

        assert result1 is True
        assert result2 is True
        return b'SIXEL_CACHE'

    output = pty_test(child, parent_func=None, test_name='test_does_sixel_uses_cache')
    assert output == '\x1b[cSIXEL_CACHE'


def test_does_sixel_not_a_tty():
    """Test does_sixel() returns False when not a TTY."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = False

        result = term.does_sixel(timeout=0.01)
        assert result is False
    child()


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
