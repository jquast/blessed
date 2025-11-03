"""Tests for DEC Private Modes and related functionality (mouse, focus, bracketed paste)."""
# std imports
import io
import re
from unittest import mock

# 3rd party
import pytest

# local
import blessed.terminal as terminal_module
from blessed import Terminal
from blessed.dec_modes import DecModeResponse
from blessed.dec_modes import DecPrivateMode as _DPM
from blessed.keyboard import (
    Keystroke,
    _match_dec_event,
    BracketedPasteEvent,
    FocusEvent,
    ResizeEvent,
    RE_PATTERN_BRACKETED_PASTE,
    resolve_sequence,
    OrderedDict,
    get_leading_prefixes,
    DeviceAttribute,
)
from .accessories import TestTerminal, as_subprocess, make_enabled_dec_cache

# For backwards compatibility and convenience in tests
DecPrivateMode = Terminal.DecPrivateMode

EXPECTED_DECTCEM_DESC = "Text Cursor Enable Mode"


def test_dec_private_mode_known_construction():
    """Known DEC mode construction."""
    mode = DecPrivateMode(_DPM.DECTCEM)
    assert mode.value == _DPM.DECTCEM
    assert mode.name == "DECTCEM"
    assert mode.long_description == EXPECTED_DECTCEM_DESC
    assert int(mode) == _DPM.DECTCEM
    assert mode.__index__() == _DPM.DECTCEM


def test_dec_private_mode_unknown_construction():
    """Unknown DEC mode construction."""
    mode = DecPrivateMode(99999)
    assert mode.value == 99999
    assert mode.name == "UNKNOWN"
    assert mode.long_description == "Unknown mode"
    assert int(mode) == 99999


def test_dec_private_mode_equality():
    """Mode equality comparisons."""
    mode_same_a = DecPrivateMode(_DPM.DECTCEM)
    mode_same_b = DecPrivateMode(_DPM.DECTCEM)
    mode_other = DecPrivateMode(_DPM.MOUSE_REPORT_CLICK)

    assert mode_same_a == mode_same_b
    assert mode_same_a != mode_other
    assert mode_same_a != _DPM.MOUSE_REPORT_CLICK
    assert mode_same_a == _DPM.DECTCEM
    assert mode_other != _DPM.DECTCEM


def test_dec_private_mode_hashing():
    """Modes work as dict keys and in sets."""
    mode_same_a = DecPrivateMode(_DPM.DECTCEM)
    mode_same_b = DecPrivateMode(_DPM.DECTCEM)
    mode_other = DecPrivateMode(_DPM.MOUSE_REPORT_CLICK)

    mode_set = {mode_same_a, mode_other, mode_same_b}
    assert len(mode_set) == 2

    mode_dict = {mode_same_a: "same-value", mode_other: "other-value"}
    assert mode_dict[mode_same_b] == "same-value"


def test_dec_private_mode_repr():
    """Mode string representation."""
    known_mode = DecPrivateMode(_DPM.DECTCEM)
    unknown_mode = DecPrivateMode(99999)

    assert repr(known_mode) == str(known_mode) == "DECTCEM(25)"
    assert repr(unknown_mode) == str(unknown_mode) == "UNKNOWN(99999)"


@pytest.mark.parametrize("value,expected_name,expected_desc", [
    (_DPM.DECCKM, "DECCKM", "Cursor Keys Mode"),
    (99999, "UNKNOWN", "Unknown mode"),
])
def test_dec_private_mode_types(value, expected_name, expected_desc):
    """Test different kinds of modes for correct values and descriptions."""
    mode = DecPrivateMode(value)
    assert mode.name == expected_name
    assert mode.long_description == expected_desc


def test_dec_private_mode_equality_with_non_standard_types():
    """Test DecPrivateMode equality with non-int, non-DecPrivateMode types."""
    mode = DecPrivateMode(_DPM.DECTCEM)

    assert (mode == "string") is False
    assert (mode is None) is False
    assert (mode == [_DPM.DECTCEM]) is False
    assert (mode == {"value": _DPM.DECTCEM}) is False
    assert (mode == 25.0) is False


def test_dec_mode_response_construction():
    """Test construction of DecModeResponse objects."""
    mode = DecPrivateMode(_DPM.DECTCEM)
    response_a = DecModeResponse(mode, DecModeResponse.SET)
    response_b = DecModeResponse(_DPM.DECTCEM, 1)

    assert response_a.mode == response_b.mode == mode == _DPM.DECTCEM
    assert response_b.mode.name == response_a.mode.name == "DECTCEM"
    assert response_a.value == response_b.value == DecModeResponse.SET == 1
    assert response_a.description == EXPECTED_DECTCEM_DESC
    assert response_b.description == EXPECTED_DECTCEM_DESC


def test_dec_mode_response_construction_invalid_mode():
    """Test that invalid mode types raise TypeError."""
    with pytest.raises(TypeError):
        DecModeResponse("invalid", 1)


def test_dec_private_mode_descriptions_consistency():
    """Test that all capitalized mode constants have descriptions in _LONG_DESCRIPTIONS."""
    mode_constants = {}
    for attr_name in dir(DecPrivateMode):
        if attr_name.isupper() and not attr_name.startswith('_'):
            attr_value = getattr(DecPrivateMode, attr_name)
            if isinstance(attr_value, int):
                mode_constants[attr_name] = attr_value

    missing_descriptions = []
    for constant_name, mode_value in mode_constants.items():
        if mode_value not in DecPrivateMode._LONG_DESCRIPTIONS:
            missing_descriptions.append(f"{constant_name}({mode_value})")
    assert not missing_descriptions

    extra_descriptions = []
    defined_mode_values = set(mode_constants.values())
    for mode_value in DecPrivateMode._LONG_DESCRIPTIONS:
        if mode_value >= 0 and mode_value not in defined_mode_values:
            extra_descriptions.append(f"mode {mode_value}")
    assert not extra_descriptions

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
    response = DecModeResponse(_DPM.DECTCEM, value)

    assert response.supported is expected["supported"]
    assert response.enabled is expected["enabled"]
    assert response.disabled is expected["disabled"]
    assert response.permanent is expected["permanent"]
    assert response.changeable is expected["changeable"]
    assert response.failed is expected["failed"]


@pytest.mark.parametrize("value,expected_str", [
    (DecModeResponse.NOT_QUERIED, "NOT_QUERIED"),
    (DecModeResponse.NO_RESPONSE, "NO_RESPONSE"),
    (DecModeResponse.NOT_RECOGNIZED, "NOT_RECOGNIZED"),
    (DecModeResponse.SET, "SET"),
    (DecModeResponse.RESET, "RESET"),
    (DecModeResponse.PERMANENTLY_SET, "PERMANENTLY_SET"),
    (DecModeResponse.PERMANENTLY_RESET, "PERMANENTLY_RESET"),
    (999, "UNKNOWN"),
])
def test_dec_mode_response_str_representation(value, expected_str):
    """Test string representation of response values."""
    response = DecModeResponse(_DPM.DECTCEM, value)
    assert str(response) == expected_str


def test_dec_mode_response_repr():
    """Test full representation of response objects."""
    response = DecModeResponse(_DPM.DECTCEM, DecModeResponse.SET)
    expected = "DECTCEM(25) is SET(1)"
    assert repr(response) == expected

    response_unknown = DecModeResponse(99999, DecModeResponse.NOT_RECOGNIZED)
    expected_unknown = "UNKNOWN(99999) is NOT_RECOGNIZED(0)"
    assert repr(response_unknown) == expected_unknown


def test_dec_mode_response_description_fallback():
    """Test DecModeResponse.description returns fallback for edge cases."""
    response = DecModeResponse(_DPM.DECTCEM, DecModeResponse.SET)

    with mock.patch.object(type(response), 'mode', new_callable=mock.PropertyMock) as mock_mode:
        mock_mode.return_value = "not a DecPrivateMode"
        assert response.description == "Unknown mode"


def test_dec_mode_calls_with_no_styling():
    """Test _dec_mode_set_enabled does nothing when does_styling is False."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=False)

        term._dec_mode_set_enabled(DecPrivateMode.DECTCEM)
        term._dec_mode_set_enabled(DecPrivateMode.DECTCEM)

        assert stream.getvalue() == ''

        response = term.get_dec_mode(DecPrivateMode.DECTCEM)

        assert response.value == DecModeResponse.NOT_QUERIED
        assert response.failed is True
        assert not response.supported
        assert stream.getvalue() == ''
    child()


def test_get_dec_mode_invalid_mode_type():
    """Test get_dec_mode raises TypeError for invalid mode types."""
    @as_subprocess
    def child():
        term = TestTerminal()
        with pytest.raises(TypeError):
            term.get_dec_mode("invalid")
    child()


def test_get_dec_mode_successful_query():
    """Test successful DEC mode query with mocked response."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_match = mock.Mock()
        mock_match.group.return_value = '1'

        with mock.patch.object(term, '_is_a_tty', True), \
                mock.patch.object(term, '_query_response', return_value=mock_match) as mock_query:
            response = term.get_dec_mode(DecPrivateMode.DECTCEM, timeout=0.5)

            mock_query.assert_called_once()
            assert response.value == DecModeResponse.SET
            assert response.supported is True
            assert response.enabled is True
            assert term._dec_mode_cache[_DPM.DECTCEM] == DecModeResponse.SET
        assert stream.getvalue() == ''
    child()


def test_get_dec_mode_timeout():
    """Test DEC mode query timeout handling."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        with mock.patch.object(term, '_is_a_tty', True), \
                mock.patch.object(term, '_query_response', return_value=None):
            response = term.get_dec_mode(DecPrivateMode.DECTCEM, timeout=0.1)

            assert response.value == DecModeResponse.NO_RESPONSE
            assert response.failed is True
            assert term._dec_first_query_failed is True
        assert stream.getvalue() == ''
    child()


def test_get_dec_mode_cached_response():
    """Test that cached responses are returned without re-querying."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        term._dec_mode_cache[_DPM.DECTCEM] = DecModeResponse.SET

        with mock.patch.object(term, '_is_a_tty', True), \
                mock.patch.object(term, '_query_response') as mock_query:
            response = term.get_dec_mode(DecPrivateMode.DECTCEM)

            mock_query.assert_not_called()
            assert response.value == DecModeResponse.SET
        assert stream.getvalue() == ''
    child()


def test_get_dec_mode_force_bypass_cache():
    """Test force=True bypasses cache and re-queries."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        term._dec_mode_cache[_DPM.DECTCEM] = DecModeResponse.SET

        mock_match = mock.Mock()
        mock_match.group.return_value = '2'

        with mock.patch.object(term, '_is_a_tty', True), \
                mock.patch.object(term, '_query_response', return_value=mock_match) as mock_query:
            response = term.get_dec_mode(DecPrivateMode.DECTCEM, force=True)

            mock_query.assert_called_once()
            assert response.value == DecModeResponse.RESET
        assert stream.getvalue() == ''
    child()


def test_get_dec_mode_sticky_failure():
    """Test get_dec_mode returns NOT_QUERIED after first query fails."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        with mock.patch.object(term, '_is_a_tty', True), \
                mock.patch.object(term, '_query_response', return_value=None):

            first_response = term.get_dec_mode(DecPrivateMode.DECTCEM, timeout=0.1)
            assert first_response.value == DecModeResponse.NO_RESPONSE
            assert term._dec_first_query_failed is True

            second_response = term.get_dec_mode(DecPrivateMode.BRACKETED_PASTE)
            assert second_response.value == DecModeResponse.NOT_QUERIED
            assert second_response.failed is True

        assert stream.getvalue() == ''
    child()


def test_get_dec_mode_no_response_after_success():
    """Test get_dec_mode returns NO_RESPONSE when query fails after previous success."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_match_success = mock.Mock()
        mock_match_success.group.return_value = '1'

        with mock.patch.object(term, '_is_a_tty', True):
            with mock.patch.object(term, '_query_response', return_value=mock_match_success):
                first_response = term.get_dec_mode(DecPrivateMode.DECTCEM, timeout=0.1)
                assert first_response.value == DecModeResponse.SET
                assert term._dec_any_query_succeeded is True

            with mock.patch.object(term, '_query_response', return_value=None):
                second_response = term.get_dec_mode(DecPrivateMode.BRACKETED_PASTE, timeout=0.1)
                assert second_response.value == DecModeResponse.NO_RESPONSE
                assert second_response.failed is True
                assert term._dec_any_query_succeeded is True

        assert stream.getvalue() == ''
    child()


def test_dec_mode_set_enabled_with_styling():
    """Test _dec_mode_set_enabled writes correct sequence."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        term._dec_mode_set_enabled(DecPrivateMode.DECTCEM, DecPrivateMode.BRACKETED_PASTE)
        assert stream.getvalue() == '\x1b[?25;2004h'
        assert term._dec_mode_cache[_DPM.DECTCEM] == DecModeResponse.SET
        assert term._dec_mode_cache[_DPM.BRACKETED_PASTE] == DecModeResponse.SET
    child()


def test_dec_mode_set_disabled_with_styling():
    """Test _dec_mode_set_disabled writes correct sequence."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        term._dec_mode_set_disabled(DecPrivateMode.DECTCEM, DecPrivateMode.BRACKETED_PASTE)
        assert stream.getvalue() == '\x1b[?25;2004l'
        assert term._dec_mode_cache[_DPM.DECTCEM] == DecModeResponse.RESET
        assert term._dec_mode_cache[_DPM.BRACKETED_PASTE] == DecModeResponse.RESET
    child()


def test_dec_mode_set_enabled_invalid_mode_type():
    """Test _dec_mode_set_enabled raises TypeError for invalid mode types."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=False)
        with pytest.raises(TypeError):
            term._dec_mode_set_enabled("invalid")
        assert stream.getvalue() == ''
    child()


def test_dec_mode_set_disabled_invalid_mode_type():
    """Test _dec_mode_set_disabled raises TypeError for invalid mode types."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=False)
        with pytest.raises(TypeError):
            term._dec_mode_set_disabled("invalid")
        assert stream.getvalue() == ''
    child()


@pytest.mark.parametrize("method_name,suffix", [
    ('_dec_mode_set_enabled', 'h'),
    ('_dec_mode_set_disabled', 'l'),
])
def test_dec_mode_set_with_dec_private_mode_enum(method_name, suffix):
    """Test _dec_mode_set_enabled/disabled with DecPrivateMode instance values."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        method = getattr(term, method_name)
        method(_DPM(2004), _DPM(1006))

        output = stream.getvalue()
        assert f'\x1b[?2004;1006{suffix}' in output
    child()


def test_dec_modes_enabled_with_invalid_type():
    """Test dec_modes_enabled raises TypeError with invalid mode type."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True

        term.get_dec_mode = lambda mode_num, timeout=None, force=False: DecModeResponse(
            mode_num, DecModeResponse.RESET)

        with pytest.raises(TypeError, match="Invalid mode argument number 0"):
            with term.dec_modes_enabled("invalid_mode"):
                pass
        child()


def test_dec_modes_disabled_with_invalid_type():
    """Test dec_modes_disabled raises TypeError with invalid mode type."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True

        term.get_dec_mode = lambda mode_num, timeout=None, force=False: DecModeResponse(
            mode_num, DecModeResponse.SET)

        # Test with invalid *type*: list [2004] instead of int 2004 or DecPrivateMode(2004)
        # The value 2004 (BRACKETED_PASTE) is valid, but passing it in a list is not accepted
        with pytest.raises(TypeError, match="Invalid mode argument number 0"):
            with term.dec_modes_disabled([_DPM.BRACKETED_PASTE]):
                pass
        child()


def test_dec_modes_enabled_context_manager():
    """Test dec_modes_enabled context manager behavior."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True
        mock_response.enabled = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.dec_modes_enabled(DecPrivateMode.DECTCEM, timeout=0.5):
                mock_set_enabled.assert_called_once_with(DecPrivateMode.DECTCEM)
                mock_set_enabled.reset_mock()

            mock_set_disabled.assert_called_once_with(DecPrivateMode.DECTCEM)
    child()


def test_dec_modes_enabled_already_enabled():
    """Test dec_modes_enabled skips already enabled modes."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True
        mock_response.enabled = True

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.dec_modes_enabled(DecPrivateMode.DECTCEM, timeout=0.5):
                mock_set_enabled.assert_called_once_with()
                mock_set_enabled.reset_mock()

            mock_set_disabled.assert_called_once_with()
    child()


def test_dec_modes_enabled_unsupported_mode():
    """Test dec_modes_enabled skips unsupported modes."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.dec_modes_enabled(DecPrivateMode.DECTCEM, timeout=0.5):
                mock_set_enabled.assert_called_once_with()
                mock_set_enabled.reset_mock()

            mock_set_disabled.assert_called_once_with()
    child()


def test_dec_modes_disabled_context_manager():
    """Test dec_modes_disabled context manager behavior."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True
        mock_response.enabled = True

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.dec_modes_disabled(DecPrivateMode.DECTCEM, timeout=0.5):
                mock_set_disabled.assert_called_once_with(DecPrivateMode.DECTCEM)
                mock_set_disabled.reset_mock()

            mock_set_enabled.assert_called_once_with(DecPrivateMode.DECTCEM)
    child()


def test_dec_modes_disabled_already_disabled():
    """Test dec_modes_disabled skips already disabled modes."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True
        mock_response.enabled = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.dec_modes_disabled(DecPrivateMode.DECTCEM, timeout=0.5):
                mock_set_disabled.assert_called_once_with()
                mock_set_disabled.reset_mock()

            mock_set_enabled.assert_called_once_with()
    child()


def test_context_manager_no_styling_and_invalid_args():
    """Test context managers do nothing when does_styling is False."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)
    with term.dec_modes_enabled(DecPrivateMode.DECTCEM):
        pass
    with term.dec_modes_disabled(DecPrivateMode.DECTCEM):
        pass
    with term.dec_modes_enabled(Terminal.DecPrivateMode.BRACKETED_PASTE):
        pass
    with term.dec_modes_enabled(Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR):
        pass
    with pytest.raises(TypeError):
        with term.dec_modes_enabled("invalid"):
            pass
    with pytest.raises(TypeError):
        with term.dec_modes_disabled("invalid"):
            pass
    assert stream.getvalue() == ""


def test_context_manager_exception_handling():
    """Test context managers properly restore state on exception."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True
        mock_response.enabled = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with pytest.raises(ValueError):
                with term.dec_modes_enabled(DecPrivateMode.DECTCEM):
                    mock_set_enabled.assert_called_once_with(DecPrivateMode.DECTCEM)
                    raise ValueError("Test exception")

            mock_set_disabled.assert_called_once_with(DecPrivateMode.DECTCEM)
        assert stream.getvalue() == ''
    child()


def test_multiple_modes_context_manager():
    """Test context managers work with multiple modes."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True
        mock_response.enabled = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.dec_modes_enabled(DecPrivateMode.DECTCEM, DecPrivateMode.BRACKETED_PASTE):
                mock_set_enabled.assert_called_once_with(
                    DecPrivateMode.DECTCEM, DecPrivateMode.BRACKETED_PASTE)
                mock_set_enabled.reset_mock()

            mock_set_disabled.assert_called_once_with(
                DecPrivateMode.DECTCEM, DecPrivateMode.BRACKETED_PASTE)
        assert stream.getvalue() == ''
    child()


@pytest.mark.parametrize("method_name,mock_response", [
    ('dec_modes_enabled', 'RESET'),
    ('dec_modes_disabled', 'SET'),
])
def test_dec_modes_context_with_dec_private_mode_enum(method_name, mock_response):
    """Test dec_modes_enabled/disabled with DecPrivateMode instance values."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True

        response_value = getattr(DecModeResponse, mock_response)
        term.get_dec_mode = lambda mode_num, timeout=None, force=False: DecModeResponse(
            mode_num, response_value)

        context_manager = getattr(term, method_name)
        with context_manager(_DPM(2004), timeout=0.01):
            pass

        output = stream.getvalue()
        assert '\x1b[?2004' in output
    child()


def test_int_mode_parameters():
    """Test that integer mode parameters work correctly."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)
    response = term.get_dec_mode(_DPM.DECTCEM)
    assert response.value == DecModeResponse.NOT_QUERIED
    with term.dec_modes_enabled(_DPM.DECTCEM, _DPM.BRACKETED_PASTE):
        pass
    with term.dec_modes_disabled(_DPM.DECTCEM, _DPM.BRACKETED_PASTE):
        pass
    assert stream.getvalue() == ""


@pytest.mark.parametrize("method_name,expected_mode", [
    ("bracketed_paste", DecPrivateMode.BRACKETED_PASTE),
    ("synchronized_output", DecPrivateMode.SYNCHRONIZED_OUTPUT),
    ("focus_events", DecPrivateMode.FOCUS_IN_OUT_EVENTS),
])
def test_sugary_context_managers(method_name, expected_mode):
    """Test sugary context managers enable correct modes."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True
        mock_response.enabled = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            method = getattr(term, method_name)
            with method():
                mock_set_enabled.assert_called_once_with(expected_mode)
                mock_set_enabled.reset_mock()

            mock_set_disabled.assert_called_once_with(expected_mode)
    child()


@pytest.mark.parametrize("method_name", [
    "bracketed_paste",
    "synchronized_output",
    "focus_events",
])
def test_sugary_context_managers_no_styling(method_name):
    """Test sugary context managers do nothing when does_styling is False."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=False)

        method = getattr(term, method_name)
        with method():
            pass

        assert stream.getvalue() == ""
    child()


@pytest.mark.parametrize("sequence", [
    'hello',
    'abc123',
    '',
    '\x1b[9999z',
    '\x1b[unknown'
])
def test_match_dec_event_invalid(sequence):
    """Test that invalid sequences return None."""
    assert _match_dec_event(sequence) is None


def test_bracketed_paste_detection():
    """Test bracketed paste sequence detection."""
    sequence = '\x1b[200~hello world\x1b[201~'
    ks = _match_dec_event(sequence, dec_mode_cache=make_enabled_dec_cache())

    assert ks is not None
    assert ks == sequence
    assert ks.mode == Terminal.DecPrivateMode.BRACKETED_PASTE
    assert ks._mode == _DPM.BRACKETED_PASTE

    values = ks._mode_values
    assert isinstance(values, BracketedPasteEvent)
    assert values.text == 'hello world'


def test_bracketed_paste_multiline():
    """Test bracketed paste with multiline content."""
    sequence = '\x1b[200~line1\nline2\tindented\x1b[201~'
    ks = _match_dec_event(sequence, dec_mode_cache=make_enabled_dec_cache())

    assert ks is not None
    values = ks._mode_values
    assert values.text == 'line1\nline2\tindented'


@pytest.mark.parametrize("sequence,expected_gained", [
    ('\x1b[I', True),
    ('\x1b[O', False),
])
def test_focus_events(sequence, expected_gained):
    """Test focus events for gained and lost."""
    ks = _match_dec_event(sequence, dec_mode_cache=make_enabled_dec_cache())
    assert ks.mode == Terminal.DecPrivateMode.FOCUS_IN_OUT_EVENTS

    values = ks._mode_values
    assert isinstance(values, FocusEvent)
    assert values.gained is expected_gained


@pytest.mark.parametrize("mode,match_obj", [
    (None, None),
    (9999, re.compile(r'\x1b\[test'))
])
def test_mode_values_returns_none(mode, match_obj):
    """Test mode_values returns None for unsupported modes."""
    match = None
    if match_obj:
        match = match_obj.match('\x1b[test')

    ks = Keystroke('xxxxxxxxx', mode=mode, match=match)

    assert ks._mode_values is None


def test_keystroke_with_dec_mode():
    """Test keystroke with DEC mode - minimal test."""
    match = RE_PATTERN_BRACKETED_PASTE.match('\x1b[200~test\x1b[201~')
    ks = Keystroke('\x1b[200~test\x1b[201~', mode=_DPM.BRACKETED_PASTE, match=match)
    assert ks.mode == Terminal.DecPrivateMode.BRACKETED_PASTE
    assert ks.is_sequence


def test_resolve_sequence():
    """Test that DEC events don't interfere with regular sequence resolution."""
    keymap = OrderedDict([('\x1b[A', 100)])
    prefixes = get_leading_prefixes(keymap)
    codes = {100: 'KEY_UP'}

    ks = resolve_sequence('\x1b[A', keymap, codes, prefixes)
    assert ks.code == 100
    assert ks.name == 'KEY_UP'

    dec_sequence = '\x1b[200~test\x1b[201~'
    ks_dec = resolve_sequence(dec_sequence, keymap, codes, prefixes,
                              dec_mode_cache=make_enabled_dec_cache())
    event_value = ks_dec._mode_values
    assert isinstance(event_value, BracketedPasteEvent)
    assert event_value.text == 'test'
    assert ks_dec.mode == Terminal.DecPrivateMode.BRACKETED_PASTE


def test_focus_event_names():
    """Test that focus events have correct names."""
    cache = make_enabled_dec_cache()

    ks_focus_in = _match_dec_event('\x1b[I', dec_mode_cache=cache)
    assert ks_focus_in.name == "FOCUS_IN"

    ks_focus_out = _match_dec_event('\x1b[O', dec_mode_cache=cache)
    assert ks_focus_out.name == "FOCUS_OUT"

    ks_regular = Keystroke('I')
    assert ks_regular.name != "FOCUS_IN"


def test_bracketed_paste_name_and_text():
    """Test that bracketed paste events have correct name and text property."""
    cache = make_enabled_dec_cache()

    ks_paste = _match_dec_event('\x1b[200~hello world\x1b[201~', dec_mode_cache=cache)
    assert ks_paste.name == "BRACKETED_PASTE"
    assert ks_paste.text == "hello world"

    ks_multiline = _match_dec_event('\x1b[200~line1\nline2\x1b[201~', dec_mode_cache=cache)
    assert ks_multiline.name == "BRACKETED_PASTE"
    assert ks_multiline.text == "line1\nline2"

    ks_empty = _match_dec_event('\x1b[200~\x1b[201~', dec_mode_cache=cache)
    assert ks_empty.name == "BRACKETED_PASTE"
    assert ks_empty.text == ""

    ks_regular = Keystroke('a')
    assert ks_regular.text is None


def test_focus_event_name_with_no_match():
    """Test _get_focus_event_name() returns None when match has no io group."""
    ks = Keystroke('test', mode=_DPM.FOCUS_IN_OUT_EVENTS, match=None)
    assert ks._get_focus_event_name() is None


def test_mouse_event_name_with_non_mouse_mode():
    """Test _get_mouse_event_name() returns None when mode_values is not MouseEvent."""
    ks = Keystroke('test', mode=_DPM.MOUSE_EXTENDED_SGR, match=None)
    assert ks._get_mouse_event_name() is None


def test_query_response_with_line_buffered_mode():
    """Test _query_response with line buffering disabled."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._line_buffered = False
        term._keyboard_fd = None

        mock_match = mock.Mock()
        mock_match.start.return_value = 0
        mock_match.end.return_value = 999

        with mock.patch.object(term, 'ungetch') as mock_ungetch, \
                mock.patch.object(terminal_module, '_read_until',
                                  return_value=(mock_match, '')) as mock_read_until:

            match = term._query_response(
                '\x1b[c', DeviceAttribute.RE_RESPONSE, timeout=0.01
            )

            mock_read_until.assert_called_once_with(
                term=term, pattern=DeviceAttribute.RE_RESPONSE, timeout=0.01
            )
            mock_ungetch.assert_called_once_with('')
            assert match is mock_match

        assert stream.getvalue() == '\x1b[c'
    child()


@pytest.mark.parametrize("sequence,h_chars,w_chars,h_pix,w_pix", [
    ('\x1b[48;24;80;480;1600t', 24, 80, 480, 1600),
    ('\x1b[48;30;120;0;0t', 30, 120, 0, 0),
    ('\x1b[48;50;100;500;2000t', 50, 100, 500, 2000),
])
def test_resize_events(sequence, h_chars, w_chars, h_pix, w_pix):
    """Test resize event detection and value extraction."""
    cache = make_enabled_dec_cache()
    ks = _match_dec_event(sequence, dec_mode_cache=cache)

    assert ks is not None
    assert ks.name == 'RESIZE_EVENT'
    assert ks.mode == Terminal.DecPrivateMode.IN_BAND_WINDOW_RESIZE

    values = ks._mode_values
    assert isinstance(values, ResizeEvent)
    assert values.height_chars == h_chars
    assert values.width_chars == w_chars
    assert values.height_pixels == h_pix
    assert values.width_pixels == w_pix


def test_notify_on_resize_context_manager():
    """Test notify_on_resize enables and disables mode correctly."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True
        mock_response.enabled = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.notify_on_resize():
                mock_set_enabled.assert_called_once_with(DecPrivateMode.IN_BAND_WINDOW_RESIZE)
                mock_set_enabled.reset_mock()

            mock_set_disabled.assert_called_once_with(DecPrivateMode.IN_BAND_WINDOW_RESIZE)
    child()


def test_notify_on_resize_cache_cleared_on_exit():
    """Test preferred size cache is cleared when exiting context."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True
        mock_response.enabled = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled'), \
                mock.patch.object(term, '_dec_mode_set_disabled'):

            # Set cache inside context
            with term.notify_on_resize():
                from blessed.terminal import WINSZ
                term._preferred_size_cache = WINSZ(ws_row=50, ws_col=100,
                                                   ws_xpixel=500, ws_ypixel=1000)
                assert term._preferred_size_cache is not None

            # Cache should be cleared after exit
            assert term._preferred_size_cache is None
    child()


def test_height_width_use_preferred_cache():
    """Test height and width properties use preferred cache."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        from blessed.terminal import WINSZ
        term._preferred_size_cache = WINSZ(ws_row=42, ws_col=123,
                                           ws_xpixel=2460, ws_ypixel=840)

        assert term.height == 42
        assert term.width == 123
        assert term.pixel_height == 840
        assert term.pixel_width == 2460
    child()


def test_sixel_uses_preferred_cache():
    """Test get_sixel_height_and_width uses pixel dimensions from cache."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        from blessed.terminal import WINSZ
        term._preferred_size_cache = WINSZ(ws_row=40, ws_col=100,
                                           ws_xpixel=2000, ws_ypixel=800)

        height, width = term.get_sixel_height_and_width()
        assert height == 800
        assert width == 2000
    child()


def test_sixel_ignores_zero_pixel_cache():
    """Test get_sixel_height_and_width falls back when pixel dimensions are zero."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        from blessed.terminal import WINSZ
        term._preferred_size_cache = WINSZ(ws_row=40, ws_col=100,
                                           ws_xpixel=0, ws_ypixel=0)

        # Set XTSMGRAPHICS cache to verify fallback
        term._xtsmgraphics_cache = (1000, 2500)
        term._xtwinops_cache = (1000, 2500)

        height, width = term.get_sixel_height_and_width()
        # Should use xtsmgraphics cache instead of preferred cache with zeros
        assert height == 1000
        assert width == 2500
    child()


@pytest.mark.parametrize("response_value,expected", [
    (DecModeResponse.SET, True),
    (DecModeResponse.NOT_RECOGNIZED, False),
])
def test_does_inband_resize(response_value, expected):
    """Test does_inband_resize returns expected value based on mode support."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True

        term.get_dec_mode = lambda mode_num, timeout: DecModeResponse(
            mode_num, response_value)

        result = term.does_inband_resize()
        assert result is expected
        assert stream.getvalue() == ''
    child()


def test_does_inband_resize_not_a_tty():
    """Test does_inband_resize returns False when not a TTY."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True, is_a_tty=False)

        result = term.does_inband_resize(timeout=0.01)
        assert result is False
    child()


def test_inkey_updates_preferred_cache_on_resize_event():
    """Test inkey() updates preferred size cache when receiving resize event."""
    from .accessories import pty_test

    def child(term):
        # Ungetch a resize event sequence
        term.ungetch('\x1b[48;30;120;600;1920t')

        # Enable resize notifications in cache
        term._dec_mode_cache = make_enabled_dec_cache()

        # Call inkey() to receive the resize event
        ks = term.inkey(timeout=0.01)

        # Verify it's a resize event
        assert ks.name == 'RESIZE_EVENT'

        # Verify the preferred cache was updated
        from blessed.terminal import WINSZ
        assert term._preferred_size_cache is not None
        expected = WINSZ(ws_row=30, ws_col=120, ws_xpixel=1920, ws_ypixel=600)
        assert term._preferred_size_cache == expected

        # Verify the cached dimensions are returned by properties
        assert term.height == 30
        assert term.width == 120
        assert term.pixel_height == 600
        assert term.pixel_width == 1920

        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_inkey_updates_preferred_cache_on_resize_event')
    assert 'OK' in output


def test_does_inband_resize_no_styling():
    """Test does_inband_resize returns False when does_styling is False."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)

    result = term.does_inband_resize()
    assert result is False
    assert stream.getvalue() == ""
