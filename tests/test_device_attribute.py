"""Tests for DeviceAttribute class and Terminal.get_device_attributes()."""

import os
import sys
import time
import math

import pytest

from .conftest import TEST_KEYBOARD, IS_WINDOWS
from .accessories import (
    TestTerminal,
    pty_test,
    read_until_semaphore,
    read_until_eof,
    echo_off,
    init_subproc_coverage,
    SEMAPHORE,
    SEND_SEMAPHORE,
)

pytestmark = pytest.mark.skipif(
    not TEST_KEYBOARD or IS_WINDOWS,
    reason="Timing-sensitive tests please do not run on build farms.")


def test_device_attribute_from_string_with_sixel():
    """Test DeviceAttribute.from_string() with sixel support."""
    from blessed.keyboard import DeviceAttribute

    da = DeviceAttribute.from_string('\x1b[?64;1;2;4;7c')
    assert da is not None
    assert da.service_class == 64
    assert da.extensions == {1, 2, 4, 7}
    assert da.supports_sixel is True


def test_device_attribute_from_string_without_sixel():
    """Test DeviceAttribute.from_string() without sixel support."""
    from blessed.keyboard import DeviceAttribute

    da = DeviceAttribute.from_string('\x1b[?64;1;2c')
    assert da is not None
    assert da.service_class == 64
    assert da.extensions == {1, 2}
    assert da.supports_sixel is False


def test_device_attribute_from_string_no_extensions():
    """Test DeviceAttribute.from_string() with no extensions."""
    from blessed.keyboard import DeviceAttribute

    da = DeviceAttribute.from_string('\x1b[?1c')
    assert da is not None
    assert da.service_class == 1
    assert da.extensions == set()
    assert da.supports_sixel is False


def test_device_attribute_from_string_invalid():
    """Test DeviceAttribute.from_string() with invalid input."""
    from blessed.keyboard import DeviceAttribute

    da = DeviceAttribute.from_string('invalid')
    assert da is None


def test_device_attribute_from_string_empty():
    """Test DeviceAttribute.from_string() with empty string."""
    from blessed.keyboard import DeviceAttribute

    da = DeviceAttribute.from_string('')
    assert da is None


def test_device_attribute_repr():
    """Test DeviceAttribute.__repr__()."""
    from blessed.keyboard import DeviceAttribute

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

    output = pty_test(child, parent_func=None, test_name='test_get_device_attributes_force_bypass_cache')
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

    output = pty_test(child, parent_func=None, test_name='test_get_device_attributes_no_force_uses_cache')
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

    output = pty_test(child, parent_func=None, test_name='test_get_device_attributes_retry_after_failure')
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

    output = pty_test(child, parent_func=None, test_name='test_get_device_attributes_multiple_extensions')
    assert output == '\x1b[cMULTI'


def test_device_attribute_from_match():
    """Test DeviceAttribute.from_match() method."""
    import re
    from blessed.keyboard import DeviceAttribute

    pattern = re.compile(r'\x1b\[\?([0-9]+)((?:;[0-9]+)*)c')
    match = pattern.match('\x1b[?62;1;4;6c')

    da = DeviceAttribute.from_match(match)
    assert da is not None
    assert da.service_class == 62
    assert da.extensions == {1, 4, 6}
    assert da.supports_sixel is True


def test_device_attribute_from_match_no_extensions():
    """Test DeviceAttribute.from_match() with no extensions."""
    import re
    from blessed.keyboard import DeviceAttribute

    pattern = re.compile(r'\x1b\[\?([0-9]+)((?:;[0-9]+)*)c')
    match = pattern.match('\x1b[?1c')

    da = DeviceAttribute.from_match(match)
    assert da is not None
    assert da.service_class == 1
    assert da.extensions == set()
    assert da.supports_sixel is False


def test_device_attribute_init_with_none_extensions():
    """Test DeviceAttribute.__init__() with None extensions."""
    from blessed.keyboard import DeviceAttribute

    da = DeviceAttribute('\x1b[?1c', 1, None)
    assert da.service_class == 1
    assert da.extensions == set()
    assert da.supports_sixel is False


def test_device_attribute_init_with_list_extensions():
    """Test DeviceAttribute.__init__() with list of extensions."""
    from blessed.keyboard import DeviceAttribute

    da = DeviceAttribute('\x1b[?64;4c', 64, [4])
    assert da.service_class == 64
    assert da.extensions == {4}
    assert da.supports_sixel is True


def test_device_attribute_raw_stored():
    """Test DeviceAttribute stores raw response string."""
    from blessed.keyboard import DeviceAttribute

    raw = '\x1b[?64;1;2;4c'
    da = DeviceAttribute.from_string(raw)
    assert da is not None
    assert da.raw == raw
