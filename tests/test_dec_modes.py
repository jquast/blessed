# -*- coding: utf-8 -*-
"""Tests for DEC Private Modes functionality."""
# std imports
import io
import re

# 3rd party
import pytest

# local
from blessed import Terminal
from blessed.dec_modes import DecPrivateMode, DecModeResponse
from .accessories import TestTerminal, as_subprocess

try:
    from unittest import mock
except ImportError:
    import mock


# Shared format variable for common stream output expectations
EXPECTED_EMPTY_STREAM = ''
EXPECTED_DECTCEM_DESC = "Text Cursor Enable Mode"


def test_dec_private_mode_known_construction():
    """Known DEC mode construction."""
    mode = DecPrivateMode(25)
    assert mode.value == 25
    assert mode.name == "DECTCEM"
    assert mode.long_description == EXPECTED_DECTCEM_DESC
    assert int(mode) == 25
    assert mode.__index__() == 25


def test_dec_private_mode_unknown_construction():
    """Unknown DEC mode construction."""
    mode = DecPrivateMode(99999)
    assert mode.value == 99999
    assert mode.name == "UNKNOWN"
    assert mode.long_description == "Unknown mode"
    assert int(mode) == 99999


def test_dec_private_mode_equality():
    """Mode equality comparisons."""
    mode_same_a = DecPrivateMode(25)
    mode_same_b = DecPrivateMode(25)
    mode_other = DecPrivateMode(1000)

    assert mode_same_a == mode_same_b
    assert mode_same_a != mode_other
    assert mode_same_a != 1000
    assert mode_same_a == 25
    assert mode_other != 25


def test_dec_private_mode_hashing():
    """Modes work as dict keys and in sets."""
    mode_same_a = DecPrivateMode(25)
    mode_same_b = DecPrivateMode(25)
    mode_other = DecPrivateMode(1000)

    mode_set = {mode_same_a, mode_other, mode_same_b}
    assert len(mode_set) == 2

    mode_dict = {mode_same_a: "same-value", mode_other: "other-value"}
    assert mode_dict[mode_same_b] == "same-value"


def test_dec_private_mode_repr():
    """Mode string representation."""
    known_mode = DecPrivateMode(25)
    unknown_mode = DecPrivateMode(99999)

    assert repr(known_mode) == str(known_mode) == "DECTCEM(25)"
    assert repr(unknown_mode) == str(unknown_mode) == "UNKNOWN(99999)"


@pytest.mark.parametrize("value,expected_name,expected_desc", [
    (1, "DECCKM", "Cursor Keys Mode"),
    (DecPrivateMode.DECCKM, "DECCKM", "Cursor Keys Mode"),
    (99999, "UNKNOWN", "Unknown mode"),
])
def test_dec_private_mode_types(value, expected_name, expected_desc):
    """Test a different kinds of modes for correct values and descriptions."""
    mode = DecPrivateMode(value)
    assert mode.value == value
    assert mode.name == expected_name
    assert mode.long_description == expected_desc


def test_dec_mode_response_construction():
    """Test construction of DecModeResponse objects."""
    # using constants that evaluate to ints,
    mode = DecPrivateMode(DecPrivateMode.DECTCEM)
    response_a = DecModeResponse(mode, DecModeResponse.SET)
    response_b = DecModeResponse(25, 1)

    assert response_a.mode == response_b.mode == mode == 25
    assert response_b.mode.name == response_a.mode.name == "DECTCEM"
    assert response_a.value == response_b.value == DecModeResponse.SET == 1
    responses_a_b = (response_a.description, response_b.description)
    assert (EXPECTED_DECTCEM_DESC,) * 2 == responses_a_b


def test_dec_mode_response_construction_invalid_mode():
    """Test that invalid mode types raise TypeError."""
    with pytest.raises(TypeError):
        DecModeResponse("invalid", 1)


def test_dec_private_mode_descriptions_consistency():
    """Test that all capitalized mode constants have descriptions in _LONG_DESCRIPTIONS."""
    # Get all capitalized attributes from DecPrivateMode that are integers (mode values)
    mode_constants = {}
    for attr_name in dir(DecPrivateMode):
        if attr_name.isupper() and not attr_name.startswith('_'):
            attr_value = getattr(DecPrivateMode, attr_name)
            if isinstance(attr_value, int):
                mode_constants[attr_name] = attr_value

    # Check that every mode constant has a description
    missing_descriptions = []
    for constant_name, mode_value in mode_constants.items():
        if mode_value not in DecPrivateMode._LONG_DESCRIPTIONS:
            missing_descriptions.append(f"{constant_name}({mode_value})")
    assert missing_descriptions == []

    # Check for extra descriptions (descriptions for non-existent constants)
    extra_descriptions = []
    defined_mode_values = set(mode_constants.values())
    for mode_value in DecPrivateMode._LONG_DESCRIPTIONS:
        if mode_value >= 0 and mode_value not in defined_mode_values:
            extra_descriptions.append(f"mode {mode_value}")
    assert extra_descriptions == []

    # Verify each description is a non-empty string
    for mode_value, description in DecPrivateMode._LONG_DESCRIPTIONS.items():
        assert isinstance(description, str)
        assert len(description.strip()) > 0


@pytest.mark.parametrize("value,expected", [
    (DecModeResponse.SET, {
        "supported": True,
        "enabled": True,
        "disabled": False,
        "permanent": False,
        "changeable": True,
        "failed": False
    }),
    (DecModeResponse.RESET, {
        "supported": True,
        "enabled": False,
        "disabled": True,
        "permanent": False,
        "changeable": True,
        "failed": False
    }),
    (DecModeResponse.PERMANENTLY_SET, {
        "supported": True,
        "enabled": True,
        "disabled": False,
        "permanent": True,
        "changeable": False,
        "failed": False
    }),
    (DecModeResponse.PERMANENTLY_RESET, {
        "supported": True,
        "enabled": False,
        "disabled": True,
        "permanent": True,
        "changeable": False,
        "failed": False
    }),
    (DecModeResponse.NOT_RECOGNIZED, {
        "supported": False,
        "enabled": False,
        "disabled": False,
        "permanent": False,
        "changeable": False,
        "failed": False
    }),
    (DecModeResponse.NO_RESPONSE, {
        "supported": False,
        "enabled": False,
        "disabled": False,
        "permanent": False,
        "changeable": False,
        "failed": True
    }),
    (DecModeResponse.NOT_QUERIED, {
        "supported": False,
        "enabled": False,
        "disabled": False,
        "permanent": False,
        "changeable": False,
        "failed": True
    }),
])
def test_dec_mode_response_predicates(value, expected):
    """Test predicates for all possible response values (-2 through 4)."""
    response = DecModeResponse(25, value)

    assert response.is_supported() is expected["supported"]
    assert response.is_recognized() is expected["supported"]  # Alias for is_supported
    assert response.is_enabled() is expected["enabled"]
    assert response.is_disabled() is expected["disabled"]
    assert response.is_permanent() is expected["permanent"]
    assert response.is_changeable() is expected["changeable"]
    assert response.is_failed() is expected["failed"]


@pytest.mark.parametrize("value,expected_str", [
    (DecModeResponse.NOT_QUERIED, "NOT_QUERIED"),
    (DecModeResponse.NO_RESPONSE, "NO_RESPONSE"),
    (DecModeResponse.NOT_RECOGNIZED, "NOT_RECOGNIZED"),
    (DecModeResponse.SET, "SET"),
    (DecModeResponse.RESET, "RESET"),
    (DecModeResponse.PERMANENTLY_SET, "PERMANENTLY_SET"),
    (DecModeResponse.PERMANENTLY_RESET, "PERMANENTLY_RESET"),
    (999, "UNKNOWN"),  # Unknown value
])
def test_dec_mode_response_str_representation(value, expected_str):
    """Test string representation of response values."""
    response = DecModeResponse(25, value)
    assert str(response) == expected_str


def test_dec_mode_response_repr():
    """Test full representation of response objects."""
    response = DecModeResponse(25, DecModeResponse.SET)
    expected = "DECTCEM(25) is SET(1)"
    assert repr(response) == expected

    response_unknown = DecModeResponse(99999, DecModeResponse.NOT_RECOGNIZED)
    expected_unknown = "UNKNOWN(99999) is NOT_RECOGNIZED(0)"
    assert repr(response_unknown) == expected_unknown


def test_get_dec_mode_no_styling():
    """Test get_dec_mode returns NOT_QUERIED when does_styling is False."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)
    response = term.get_dec_mode(DecPrivateMode.DECTCEM)

    assert response.value == DecModeResponse.NOT_QUERIED
    assert response.is_failed() is True
    assert not response.is_supported()
    assert stream.getvalue() == EXPECTED_EMPTY_STREAM


def test_get_dec_mode_invalid_mode_type():
    """Test get_dec_mode raises TypeError for invalid mode types."""
    term = TestTerminal()
    with pytest.raises(TypeError):
        term.get_dec_mode("invalid")


def test_get_dec_mode_successful_query():
    """Test successful DEC mode query with mocked response."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        # Mock successful DECRQM response for mode 25 (DECTCEM) with value 1 (SET)
        mock_match = mock.Mock()
        mock_match.group.return_value = '1'

        # Mock _is_a_tty to return True so the query actually happens
        with mock.patch.object(term, '_is_a_tty', True), \
                mock.patch.object(term, '_query_response', return_value=mock_match) as mock_query:
            response = term.get_dec_mode(DecPrivateMode.DECTCEM, timeout=0.5)

            # Verify query was called with correct parameters
            mock_query.assert_called_once()

            # Verify response
            assert response.value == DecModeResponse.SET
            assert response.is_supported() is True
            assert response.is_enabled() is True

            # Verify caching
            assert term._dec_mode_cache[25] == DecModeResponse.SET
        assert stream.getvalue() == EXPECTED_EMPTY_STREAM
    child()


def test_get_dec_mode_timeout():
    """Test DEC mode query timeout handling."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        # Mock _is_a_tty to return True so the query actually happens
        with mock.patch.object(term, '_is_a_tty', True), \
                mock.patch.object(term, '_query_response', return_value=None):
            response = term.get_dec_mode(DecPrivateMode.DECTCEM, timeout=0.1)

            # First query failure should set _dec_first_query_failed
            assert response.value == DecModeResponse.NO_RESPONSE
            assert response.is_failed() is True
            assert term._dec_first_query_failed is True
        assert stream.getvalue() == EXPECTED_EMPTY_STREAM
    child()


def test_get_dec_mode_cached_response():
    """Test that cached responses are returned without re-querying."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        # Pre-populate cache
        term._dec_mode_cache[25] = DecModeResponse.SET

        # Mock _is_a_tty to return True so the method doesn't return NOT_QUERIED
        with mock.patch.object(term, '_is_a_tty', True), \
                mock.patch.object(term, '_query_response') as mock_query:
            response = term.get_dec_mode(DecPrivateMode.DECTCEM)

            # Should not call _query_response due to cache
            mock_query.assert_not_called()
            assert response.value == DecModeResponse.SET
        assert stream.getvalue() == EXPECTED_EMPTY_STREAM
    child()


def test_get_dec_mode_force_bypass_cache():
    """Test force=True bypasses cache and re-queries."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        # Pre-populate cache
        term._dec_mode_cache[25] = DecModeResponse.SET

        # Mock different response for forced query
        mock_match = mock.Mock()
        mock_match.group.return_value = '2'  # RESET

        # Mock _is_a_tty to return True so the query actually happens
        with mock.patch.object(term, '_is_a_tty', True), \
                mock.patch.object(term, '_query_response', return_value=mock_match) as mock_query:
            response = term.get_dec_mode(DecPrivateMode.DECTCEM, force=True)

            # Should call _query_response despite cache
            mock_query.assert_called_once()
            assert response.value == DecModeResponse.RESET
        assert stream.getvalue() == EXPECTED_EMPTY_STREAM
    child()


def test_dec_mode_set_enabled_no_styling():
    """Test _dec_mode_set_enabled does nothing when does_styling is False."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)

    term._dec_mode_set_enabled(DecPrivateMode.DECTCEM)
    term._dec_mode_set_enabled(DecPrivateMode.DECTCEM)

    assert stream.getvalue() == EXPECTED_EMPTY_STREAM


def test_dec_mode_set_enabled_with_styling():
    """Test _dec_mode_set_enabled writes correct sequence."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        term._dec_mode_set_enabled(DecPrivateMode.DECTCEM, DecPrivateMode.BRACKETED_PASTE)
        assert stream.getvalue() == '\x1b[?25;2004h'

        # Verify cache updates
        assert term._dec_mode_cache[25] == DecModeResponse.SET
        assert term._dec_mode_cache[2004] == DecModeResponse.SET
    child()


def test_dec_mode_set_disabled_with_styling():
    """Test _dec_mode_set_disabled writes correct sequence."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        term._dec_mode_set_disabled(DecPrivateMode.DECTCEM, DecPrivateMode.BRACKETED_PASTE)

        assert stream.getvalue() == '\x1b[?25;2004l'

        # Verify cache updates
        assert term._dec_mode_cache[25] == DecModeResponse.RESET
        assert term._dec_mode_cache[2004] == DecModeResponse.RESET
    child()


def test_dec_mode_set_enabled_invalid_mode_type():
    """Test _dec_mode_set_enabled raises TypeError for invalid mode types."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)
    with pytest.raises(TypeError):
        term._dec_mode_set_enabled("invalid")
    assert stream.getvalue() == EXPECTED_EMPTY_STREAM


def test_dec_mode_set_disabled_invalid_mode_type():
    """Test _dec_mode_set_disabled raises TypeError for invalid mode types."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)
    with pytest.raises(TypeError):
        term._dec_mode_set_disabled("invalid")
    assert stream.getvalue() == EXPECTED_EMPTY_STREAM


def test_context_manager_invalid_mode_type():
    """Test context managers raise TypeError for invalid mode types."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)
    with pytest.raises(TypeError):
        with term.dec_modes_enabled("invalid"):
            pass
    with pytest.raises(TypeError):
        with term.dec_modes_disabled("invalid"):
            pass
    assert stream.getvalue() == EXPECTED_EMPTY_STREAM


def test_dec_modes_enabled_context_manager():
    """Test dec_modes_enabled context manager behavior."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        # Mock get_dec_mode to return supported but disabled mode
        mock_response = mock.Mock()
        mock_response.is_supported.return_value = True
        mock_response.is_enabled.return_value = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.dec_modes_enabled(DecPrivateMode.DECTCEM, timeout=0.5):
                # Verify mode was enabled on entry
                mock_set_enabled.assert_called_once_with(DecPrivateMode.DECTCEM)
                mock_set_enabled.reset_mock()

            # Verify mode was disabled on exit
            mock_set_disabled.assert_called_once_with(DecPrivateMode.DECTCEM)
    child()


def test_dec_modes_enabled_already_enabled():
    """Test dec_modes_enabled skips already enabled modes."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        # Mock get_dec_mode to return supported and already enabled mode
        mock_response = mock.Mock()
        mock_response.is_supported.return_value = True
        mock_response.is_enabled.return_value = True

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.dec_modes_enabled(DecPrivateMode.DECTCEM, timeout=0.5):
                # Should not enable already enabled mode - called with empty args since no
                # modes to enable
                mock_set_enabled.assert_called_once_with()
                mock_set_enabled.reset_mock()

            # Should not disable mode that wasn't enabled by us - called with empty
            # args since no modes to disable
            mock_set_disabled.assert_called_once_with()
    child()


def test_dec_modes_enabled_unsupported_mode():
    """Test dec_modes_enabled skips unsupported modes."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        # Mock get_dec_mode to return unsupported mode
        mock_response = mock.Mock()
        mock_response.is_supported.return_value = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.dec_modes_enabled(DecPrivateMode.DECTCEM, timeout=0.5):
                # Should not enable unsupported mode
                mock_set_enabled.assert_called_once_with()  # Called with empty args since no modes to enable
                mock_set_enabled.reset_mock()

            # Should not disable unsupported mode
            mock_set_disabled.assert_called_once_with()  # Called with empty args since no modes to disable
    child()


def test_dec_modes_disabled_context_manager():
    """Test dec_modes_disabled context manager behavior."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        # Mock get_dec_mode to return supported and enabled mode
        mock_response = mock.Mock()
        mock_response.is_supported.return_value = True
        mock_response.is_enabled.return_value = True

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.dec_modes_disabled(DecPrivateMode.DECTCEM, timeout=0.5):
                # Verify mode was disabled on entry
                mock_set_disabled.assert_called_once_with(DecPrivateMode.DECTCEM)
                mock_set_disabled.reset_mock()

            # Verify mode was enabled on exit
            mock_set_enabled.assert_called_once_with(DecPrivateMode.DECTCEM)
    child()


def test_dec_modes_disabled_already_disabled():
    """Test dec_modes_disabled skips already disabled modes."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        # Mock get_dec_mode to return supported but already disabled mode
        mock_response = mock.Mock()
        mock_response.is_supported.return_value = True
        mock_response.is_enabled.return_value = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.dec_modes_disabled(DecPrivateMode.DECTCEM, timeout=0.5):
                # Should not disable already disabled mode
                mock_set_disabled.assert_called_once_with()  # Called with empty args since no modes to disable
                mock_set_disabled.reset_mock()

            # Should not enable mode that wasn't disabled by us
            mock_set_enabled.assert_called_once_with()  # Called with empty args since no modes to enable
    child()


def test_context_manager_no_styling():
    """Test context managers do nothing when does_styling is False."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)

    with term.dec_modes_enabled(DecPrivateMode.DECTCEM):
        pass

    with term.dec_modes_disabled(DecPrivateMode.DECTCEM):
        pass

    # No sequences should be written
    assert stream.getvalue() == ""


def test_context_manager_exception_handling():
    """Test context managers properly restore state on exception."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        # Mock get_dec_mode to return supported but disabled mode
        mock_response = mock.Mock()
        mock_response.is_supported.return_value = True
        mock_response.is_enabled.return_value = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with pytest.raises(ValueError):
                with term.dec_modes_enabled(DecPrivateMode.DECTCEM):
                    mock_set_enabled.assert_called_once_with(DecPrivateMode.DECTCEM)
                    raise ValueError("Test exception")

            # Should still restore state despite exception
            mock_set_disabled.assert_called_once_with(DecPrivateMode.DECTCEM)
        assert stream.getvalue() == EXPECTED_EMPTY_STREAM
    child()


def test_multiple_modes_context_manager():
    """Test context managers work with multiple modes."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        # Mock get_dec_mode to return supported but disabled modes
        mock_response = mock.Mock()
        mock_response.is_supported.return_value = True
        mock_response.is_enabled.return_value = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.dec_modes_enabled(DecPrivateMode.DECTCEM, DecPrivateMode.BRACKETED_PASTE):
                # Both modes should be enabled
                mock_set_enabled.assert_called_once_with(
                    DecPrivateMode.DECTCEM, DecPrivateMode.BRACKETED_PASTE)
                mock_set_enabled.reset_mock()

            # Both modes should be disabled on exit
            mock_set_disabled.assert_called_once_with(
                DecPrivateMode.DECTCEM, DecPrivateMode.BRACKETED_PASTE)
        assert stream.getvalue() == EXPECTED_EMPTY_STREAM
    child()


def test_int_mode_parameters():
    """Test that integer mode parameters work correctly."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)

    # Test with integer mode parameter
    response = term.get_dec_mode(25)  # DECTCEM as int
    assert response.value == DecModeResponse.NOT_QUERIED  # No styling, so not queried

    # Test context managers with int parameters
    with term.dec_modes_enabled(25, 2004):  # DECTCEM and BRACKETED_PASTE as ints
        pass

    with term.dec_modes_disabled(25, 2004):
        pass

    # Should not crash and should handle int parameters correctly
    assert stream.getvalue() == ""  # No styling, so no output
