"""Tests for XTGETTCAP (DCS +q) terminal capability queries."""
# std imports
import io
import os
import select
import termios
import time

# 3rd party
import pytest
from unittest import mock

# local
from blessed._capabilities import Decrqss
from blessed._capabilities import TermcapResponse, ITerm2Capabilities
from blessed.terminal import Terminal
from blessed.xtgettcap import query_xtgettcap
from .conftest import IS_WINDOWS
from .accessories import TestTerminal, as_subprocess, pty_test


class TestTermcapResponseParsing:
    """TermcapResponse hex encoding/decoding and construction."""

    def test_hex_encode(self):
        """Hex-encode ASCII strings."""
        assert TermcapResponse.hex_encode('TN') == '544e'
        assert TermcapResponse.hex_encode('colors') == '636f6c6f7273'

    def test_hex_decode(self):
        """Hex-decode valid hex strings."""
        assert TermcapResponse.hex_decode('544e') == 'TN'
        assert TermcapResponse.hex_decode('636f6c6f7273') == 'colors'

    def test_hex_decode_invalid(self):
        """Hex-decode returns empty string on invalid hex."""
        assert TermcapResponse.hex_decode('zzzz') == ''

    def test_hex_decode_non_ascii(self):
        """Hex-decode returns empty string on non-ASCII bytes."""
        assert TermcapResponse.hex_decode('c0c1') == ''

    def test_supported_with_capabilities(self):
        """Supported response exposes capabilities via dict-like API."""
        caps = {'TN': 'xterm-256color', 'colors': '256'}
        resp = TermcapResponse(supported=True, capabilities=caps)
        assert resp.supported is True
        assert resp.terminal_name == 'xterm-256color'
        assert resp.num_colors == 256
        assert len(resp) == 2
        assert 'TN' in resp
        assert resp['TN'] == 'xterm-256color'
        assert resp.get('missing') is None
        assert resp.get('missing', 'default') == 'default'

    def test_unsupported(self):
        """Unsupported response returns None for all properties."""
        resp = TermcapResponse(supported=False)
        assert resp.supported is False
        assert resp.terminal_name is None
        assert resp.num_colors is None
        assert len(resp) == 0

    def test_num_colors_non_integer(self):
        """Non-integer colors value returns None."""
        resp = TermcapResponse(supported=True, capabilities={'colors': 'abc'})
        assert resp.num_colors is None

    def test_repr(self):
        """String representation includes key attributes."""
        resp = TermcapResponse(supported=True, capabilities={'TN': 'xterm'})
        assert 'supported=True' in repr(resp)
        assert 'TN' in repr(resp)

    def test_getitem_keyerror(self):
        """Missing key raises KeyError."""
        resp = TermcapResponse(supported=True, capabilities={})
        with pytest.raises(KeyError):
            _ = resp['nonexistent']

    def test_defaults_empty_capabilities(self):
        """Default capabilities is empty dict."""
        resp = TermcapResponse(supported=True)
        assert resp.capabilities == {}
        assert len(resp) == 0

    # unescape_terminfo tests

    @pytest.mark.parametrize('value,expected', [
        (r'\E', '\x1b'),
        (r'\n', '\n'),
        (r'\t', '\t'),
        (r'\r', '\r'),
        (r'\b', '\b'),
        (r'\f', '\f'),
        (r'\\', '\\'),
        (r'\^', '^'),
        (r'\:', ':'),
    ])
    def test_unescape_terminfo_backslash_escapes(self, value, expected):
        r"""Backslash escapes (\E, \n, \t, \r, \b, \f, \\, \^, \:) are unescaped."""
        assert TermcapResponse.unescape_terminfo(value) == expected

    @pytest.mark.parametrize('value,expected', [
        (r'\033', '\x1b'),
        (r'\101\102', 'AB'),
        (r'\000', '\x00'),
        (r'\141', 'a'),
    ])
    def test_unescape_terminfo_octal_escapes(self, value, expected):
        r"""Octal \NNN escapes are decoded."""
        assert TermcapResponse.unescape_terminfo(value) == expected

    @pytest.mark.parametrize('value,expected', [
        ('^A', '\x01'),
        ('^Z', '\x1a'),
        ('^?', '\x7f'),
        ('^_', '\x1f'),
    ])
    def test_unescape_terminfo_control_notation(self, value, expected):
        """^X control-character and ^? DEL notation."""
        assert TermcapResponse.unescape_terminfo(value) == expected

    def test_unescape_terminfo_mixed(self):
        """Mixed escape sequences."""
        result = TermcapResponse.unescape_terminfo(r'\E[5m\E[m')
        assert result == '\x1b[5m\x1b[m'

    def test_unescape_terminfo_no_escapes(self):
        """String without escapes is unchanged."""
        assert TermcapResponse.unescape_terminfo('hello') == 'hello'



class TestITerm2Capabilities:
    """ITerm2Capabilities parsing and construction."""

    @pytest.mark.parametrize('feature_str,expected', [
        ('T2CwBF', {
            'truecolor': 2,
            'clipboard_writable': True,
            'bracketed_paste': True,
            'focus_reporting': True,
        }),
        ('', {}),
        ('ZZZ', {}),
        ('Sc', {'decscusr': 0}),
        ('Sc3', {'decscusr': 3}),
        ('MSxNo', {
            'mouse': True,
            'sixel': True,
            'notifications': True,
        }),
        ('UAwUw6', {
            'unicode_basic': True,
            'ambiguous_wide': True,
            'unicode_widths': 6,
        }),
        ('LrGsGoSyH', {
            'decslrm': True,
            'strikethrough': True,
            'overline': True,
            'sync': True,
            'hyperlinks': True,
        }),
        ('Ts2', {'titles': 2}),
    ])
    def test_parse_feature_string(self, feature_str, expected):
        """Parse iTerm2 feature string into dict."""
        result = ITerm2Capabilities.parse_feature_string(feature_str)
        assert result == expected

    def test_supported_capabilities_response(self):
        """Supported response with features."""
        features = {'truecolor': 2, 'sixel': True}
        caps = ITerm2Capabilities(supported=True, features=features)
        assert caps.supported is True
        assert caps.features == features

    def test_unsupported(self):
        """Unsupported response has empty features."""
        caps = ITerm2Capabilities(supported=False)
        assert caps.supported is False
        assert caps.features == {}

    def test_repr(self):
        """String representation includes key attributes."""
        caps = ITerm2Capabilities(
            supported=True, features={'truecolor': 2})
        r = repr(caps)
        assert 'supported=True' in r
        assert 'truecolor' in r


class TestGetXtgettcap:
    """Terminal.get_xtgettcap() method."""

    def test_not_a_tty_returns_none(self):
        """Returns None when not a TTY."""
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        assert term.get_xtgettcap(timeout=0.01) is None

    def test_does_xtgettcap_not_a_tty(self):
        """does_xtgettcap returns False when not a TTY."""
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        assert term.does_xtgettcap(timeout=0.01) is False

    def test_cached_result(self):
        """Returns cached result without re-querying (caps= restricts request)."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True

        cached = TermcapResponse(supported=True,
                                 capabilities={'TN': 'test'})
        term._xtgettcap_cache = cached

        result = term.get_xtgettcap(caps=['TN'])
        assert result is not cached  # filtered copy, not same object
        assert result.supported is True
        assert result['TN'] == 'test'

    def test_sticky_failure(self):
        """Returns None after first query failure."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._xtgettcap_cache = None
        term._xtgettcap_first_query_failed = True

        result = term.get_xtgettcap()
        assert result is None

    def test_force_bypasses_cache(self):
        """force=True bypasses both cache and sticky failure."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True

        cached = TermcapResponse(supported=True,
                                 capabilities={'TN': 'old'})
        term._xtgettcap_cache = cached
        term._xtgettcap_first_query_failed = True

        result = term.get_xtgettcap(timeout=0.01, force=True)
        assert result is None

    def test_parse_xtgettcap_responses(self):
        """Parse multiple DCS +r responses."""
        raw = (
            '\x1bP1+r544e=787465726d\x1b\\'
            '\x1bP1+r636f6c6f7273=323536\x1b\\'
            '\x1bP0+r626365\x1b\\'
        )
        capabilities = TermcapResponse.parse_capabilities(raw)
        assert capabilities['TN'] == 'xterm'
        assert capabilities['colors'] == '256'
        assert 'bce' not in capabilities

    def test_parse_xtgettcap_boolean_capability(self):
        """Parse DCS +r boolean capability (no value)."""
        raw = '\x1bP1+r626365\x1b\\'
        capabilities = TermcapResponse.parse_capabilities(raw)
        assert capabilities['bce'] == ''

    def test_does_xtgettcap_with_cached(self):
        """does_xtgettcap returns True with cached supported result."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._xtgettcap_cache = TermcapResponse(
            supported=True, capabilities={'TN': 'test'})

        assert term.does_xtgettcap() is True

    def test_does_xtgettcap_unsupported(self):
        """does_xtgettcap returns False after probe failure."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._xtgettcap_cache = None
        term._xtgettcap_first_query_failed = True

        assert term.does_xtgettcap() is False

    def test_caps_all_in_cache_returns_cached(self):
        """caps= with all names already in cache returns filtered copy."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        cached = TermcapResponse(supported=True,
                                 capabilities={'TN': 'xterm', 'RV': '1.0'})
        term._xtgettcap_cache = cached
        result = term.get_xtgettcap(caps=['RV'])
        assert result is not cached  # filtering creates new object
        assert result['RV'] == '1.0'

    def test_caps_incremental_queries_missing(self):
        """caps= with names absent from cache queries only missing ones."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._xtgettcap_cache = TermcapResponse(
            supported=True, capabilities={'TN': 'xterm'})
        old_cache = term._xtgettcap_cache
        # Inject response for the missing cap: RV=1.0 + CPR fence
        hex_rv = TermcapResponse.hex_encode('RV')
        term.ungetch(
            f'\x1bP1+r{hex_rv}=312e30\x1b\\'
            '\x1b[10;20R')
        result = term.get_xtgettcap(caps=['RV'], timeout=0.1)
        assert 'RV' not in old_cache.capabilities     # wasn't there before
        assert result['TN'] == 'xterm'                # preserved from cache
        assert result['RV'] == '1.0'                  # newly queried
        assert 'RV' in term._xtgettcap_cache.capabilities  # cache updated

    def test_caps_force_queries_all(self):
        """force=True with caps= queries only the specified caps."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._xtgettcap_cache = TermcapResponse(
            supported=True, capabilities={'TN': 'old'})
        # caps=['RV'] queries only RV (not standard set)
        hex_rv = TermcapResponse.hex_encode('RV')
        term.ungetch(
            f'\x1bP1+r{hex_rv}=312e30\x1b\\'
            '\x1b[10;20R')
        result = term.get_xtgettcap(timeout=0.1, force=True, caps=['RV'])
        assert result['RV'] == '1.0'

    def test_caps_ignores_sticky_failure(self):
        """caps= with sticky failure still attempts query."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._xtgettcap_cache = None
        term._xtgettcap_first_query_failed = True
        # caps=['RV'] probes with RV (first requested cap), then
        # no remaining caps to batch.  Inject RV probe response + CPR.
        hex_rv = TermcapResponse.hex_encode('RV')
        term.ungetch(
            f'\x1bP1+r{hex_rv}=312e30\x1b\\'
            '\x1b[10;20R')
        result = term.get_xtgettcap(timeout=0.1, caps=['RV'])
        assert result is not None
        assert result['RV'] == '1.0'


    def test_all_parameter_queries_all_standard_caps(self):
        """all=True queries all standard XTGETTCAP capabilities."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        # Inject response for TN (probe) + Co (batch) + CPR
        hex_tn = TermcapResponse.hex_encode('TN')
        hex_co = TermcapResponse.hex_encode('Co')
        term.ungetch(
            f'\x1bP1+r{hex_tn}=787465726d\x1b\\'
            f'\x1bP1+r{hex_co}=323536\x1b\\'
            '\x1b[10;20R'
            '\x1b[11;21R')
        result = term.get_xtgettcap(timeout=0.1, all=True)
        assert result is not None
        assert result['TN'] == 'xterm'
        assert result['Co'] == '256'

    def test_none_sentinel_not_in_returned_response(self):
        """None-valued caps in cache are filtered from returned response."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        # Internal cache has None for an absent cap
        term._xtgettcap_cache = TermcapResponse(
            supported=True,
            capabilities={'TN': 'xterm', 'RV': None})
        result = term.get_xtgettcap(caps=['TN', 'RV'])
        assert 'TN' in result.capabilities
        assert 'RV' not in result.capabilities  # filtered out

    def test_none_sentinel_internal_cache_retains_none(self):
        """Internal cache retains None sentinel for absent caps."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._xtgettcap_cache = TermcapResponse(
            supported=True,
            capabilities={'TN': 'xterm'})
        # Query RV; no response injected, so it becomes None in cache
        hex_rv = TermcapResponse.hex_encode('RV')
        term.ungetch(
            f'\x1bP1+r{hex_rv}=\x1b\\'  # empty value for RV
            '\x1b[10;20R')
        result = term.get_xtgettcap(caps=['RV'], timeout=0.1)
        # RV was answered (even with empty value), so it should be present
        assert 'RV' in result.capabilities

    def test_absent_cap_not_requeried(self):
        """Absent caps (None sentinel) are not re-queried on subsequent calls."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        # Pre-populate cache with a None sentinel for Ms
        term._xtgettcap_cache = TermcapResponse(
            supported=True,
            capabilities={'TN': 'xterm', 'Ms': None})
        # Clear any injected input to verify no query is sent
        result = term.get_xtgettcap(caps=['Ms'], timeout=0.01)
        assert result is not None
        assert 'Ms' not in result.capabilities  # filtered from response
        assert term._xtgettcap_cache.capabilities['Ms'] is None  # retained in cache

    def test_get_xtgettcap_no_args_queries_all_standard_caps(self):
        """get_xtgettcap() with no caps or all queries all standard caps."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        # Inject TN probe + batch response with Co
        hex_tn = TermcapResponse.hex_encode('TN')
        hex_co = TermcapResponse.hex_encode('Co')
        term.ungetch(
            f'\x1bP1+r{hex_tn}=787465726d\x1b\\'
            f'\x1bP1+r{hex_co}=323536\x1b\\'
            '\x1b[10;20R'
            '\x1b[11;21R')
        result = term.get_xtgettcap(timeout=0.1)
        assert result is not None
        assert result['TN'] == 'xterm'
        assert result['Co'] == '256'

    def test_filter_response_none(self):
        """_filter_xtgettcap_response returns None for None input."""
        assert Terminal._filter_xtgettcap_response(None) is None

    def test_filter_response_removes_none_values(self):
        """_filter_xtgettcap_response removes None-valued caps."""
        tc = TermcapResponse(
            supported=True,
            capabilities={'TN': 'xterm', 'RGB': None, 'Co': '256'})
        result = Terminal._filter_xtgettcap_response(tc)
        assert 'TN' in result.capabilities
        assert 'Co' in result.capabilities
        assert 'RGB' not in result.capabilities
        assert result.supported is True


class TestStyledUnderlines:
    """Terminal.does_styled_underlines() and does_colored_underlines()."""

    def test_styled_underlines_supported(self):
        """Returns True when Smulx is in XTGETTCAP capabilities."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._xtgettcap_cache = TermcapResponse(
            supported=True,
            capabilities={'TN': 'xterm', 'Smulx': '\x1b[4:%p1%dm'})
        assert term.does_styled_underlines() is True

    def test_styled_underlines_unsupported(self):
        """Returns False when Smulx is not in capabilities."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._xtgettcap_cache = TermcapResponse(
            supported=True, capabilities={'TN': 'xterm'})
        assert term.does_styled_underlines() is False

    def test_styled_underlines_no_xtgettcap(self):
        """Returns False when XTGETTCAP is not supported."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._xtgettcap_first_query_failed = True
        assert term.does_styled_underlines() is False

    def test_colored_underlines_supported(self):
        """Returns True when Setulc is in XTGETTCAP capabilities."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._xtgettcap_cache = TermcapResponse(
            supported=True,
            capabilities={'Setulc': '\x1b[58;2;%p1%d;%p2%d;%p3%dm'})
        assert term.does_colored_underlines() is True

    def test_colored_underlines_unsupported(self):
        """Returns False when Setulc is not in capabilities."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._xtgettcap_cache = TermcapResponse(
            supported=True, capabilities={'TN': 'xterm'})
        assert term.does_colored_underlines() is False


class TestOsc52Clipboard:
    """Terminal.does_osc52_clipboard() detection."""

    def test_not_a_tty(self):
        """Returns False when not a TTY."""
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        assert term.does_osc52_clipboard(timeout=0.01) is False

    def test_cached_result(self):
        """Returns cached result without re-querying."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._osc52_clipboard_supported = True
        assert term.does_osc52_clipboard() is True

    def test_force_bypasses_cache(self):
        """force=True bypasses cached result."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._osc52_clipboard_supported = True
        result = term.does_osc52_clipboard(timeout=0.01, force=True)
        assert result is False


class TestColorScheme:
    """Terminal.get_color_scheme() detection."""

    def test_not_a_tty(self):
        """Returns None when not a TTY."""
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        assert term.get_color_scheme(timeout=0.01) is None

    def test_negative_cache(self):
        """Returns None immediately when previously unsupported."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._color_scheme_supported = False
        assert term.get_color_scheme() is None

    def test_force_bypasses_negative_cache(self):
        """force=True bypasses negative cache."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._color_scheme_supported = False
        result = term.get_color_scheme(timeout=0.01, force=True)
        assert result is None


class TestKittyQuery:
    """Terminal.does_kitty_query() detection."""

    def test_not_a_tty(self):
        """Returns False when not a TTY."""
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        assert term.does_kitty_query(timeout=0.01) is False

    def test_cached_result(self):
        """Returns cached result without re-querying."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._kitty_query_supported = True
        assert term.does_kitty_query() is True

    def test_force_bypasses_cache(self):
        """force=True bypasses cached result."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._kitty_query_supported = True
        result = term.does_kitty_query(timeout=0.01, force=True)
        assert result is False


class TestDecrqss:
    """Terminal.does_decrqss() detection."""

    def test_not_a_tty(self):
        """Returns False when not a TTY."""
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        assert term.does_decrqss(timeout=0.01) is False

    def test_cached_result(self):
        """Returns cached result without re-querying."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._decrqss_supported = True
        assert term.does_decrqss() is True

    def test_force_bypasses_cache(self):
        """force=True bypasses cached result."""
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._decrqss_supported = True
        result = term.does_decrqss(timeout=0.01, force=True)
        assert result is False


class TestGetDecrqss:
    """Terminal.get_decrqss() state queries."""

    def test_not_a_tty(self):
        """Returns None when not a TTY."""
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        assert term.get_decrqss(timeout=0.01) is None

    def test_default_setting_is_sgr(self):
        """Default setting_id is SGR ('m')."""
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        assert Decrqss.SGR == 'm'
        assert term.get_decrqss() is None


pytestmark_pty = pytest.mark.skipif(
    IS_WINDOWS, reason="ungetch and PTY testing not supported on Windows")


@pytestmark_pty
def test_get_xtgettcap_full_success():
    """Phase 1 probe + Phase 2 batch query returns parsed capabilities."""
    def child(term):
        # Phase 1: DCS +r response for probe cap "TN" + CPR boundary
        # Phase 2: DCS +r response for "Co" (colors=256), read by flushinp
        probe_resp = '\x1bP1+r544e=787465726d\x1b\\'
        cpr = '\x1b[10;20R'
        batch_resp = '\x1bP1+r436f=323536\x1b\\'
        term.ungetch(probe_resp + cpr + batch_resp)
        result = term.get_xtgettcap(timeout=0.1, force=True)
        assert result is not None
        assert result.supported is True
        assert result['TN'] == 'xterm'
        assert result['Co'] == '256'
        assert term._xtgettcap_cache is not None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_xtgettcap_full_success')
    assert 'OK' in output


@pytestmark_pty
def test_get_xtgettcap_probe_failure():
    """Phase 1 probe failure sets sticky flag."""
    def child(term):
        # Clear the injected cache so we exercise the real probe path
        term._xtgettcap_cache = None
        term._xtgettcap_first_query_failed = False
        # Inject only CPR, no DCS response: probe fails
        term.ungetch('\x1b[10;20R')
        result = term.get_xtgettcap(timeout=0.1)
        assert result is None
        assert term._xtgettcap_first_query_failed is True
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_xtgettcap_probe_failure')
    assert 'OK' in output


@pytestmark_pty
def test_get_xtgettcap_batch_with_remaining_input():
    """Keyboard data interleaved with batch responses is re-buffered."""
    def child(term):
        probe_resp = '\x1bP1+r544e=787465726d\x1b\\'
        cpr = '\x1b[10;20R'
        batch_resp = '\x1bP1+r436f=323536\x1b\\'
        keyboard_data = 'x'
        term.ungetch(probe_resp + cpr + batch_resp + keyboard_data)
        result = term.get_xtgettcap(timeout=0.1, force=True)
        assert result is not None
        assert result['TN'] == 'xterm'
        assert result['Co'] == '256'
        with term.cbreak():
            inp = term.inkey(timeout=0)
            assert inp == 'x'
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_xtgettcap_batch_with_remaining_input')
    assert 'OK' in output


@pytestmark_pty
def test_get_xtgettcap_batch_empty_flushinp():
    """Phase 2 flushinp returns empty -- result has only probe capability."""
    def child(term):
        probe_resp = '\x1bP1+r544e=787465726d\x1b\\'
        cpr = '\x1b[10;20R'
        term.ungetch(probe_resp + cpr)
        result = term.get_xtgettcap(timeout=0.01, force=True)
        assert result is not None
        assert result.supported is True
        assert result['TN'] == 'xterm'
        assert len(result) == 1
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_xtgettcap_batch_empty_flushinp')
    assert 'OK' in output


@pytestmark_pty
def test_does_osc52_clipboard_via_da1():
    """OSC 52 detected via DA1 extension 52."""
    def child(term):
        # DA1 with extension 52 (OSC 52 support)
        da1_resp = '\x1b[?64;1;4;52c'
        cpr = '\x1b[10;20R'
        term.ungetch(da1_resp + cpr)
        result = term.does_osc52_clipboard(timeout=0.1)
        assert result is True
        assert term._osc52_clipboard_supported is True
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_osc52_clipboard_via_da1')
    assert 'OK' in output


@pytestmark_pty
def test_does_osc52_clipboard_via_xtgettcap():
    """OSC 52 detected via XTGETTCAP Ms capability."""
    def child(term):
        hex_tn = TermcapResponse.hex_encode('TN')
        hex_ms = TermcapResponse.hex_encode('Ms')
        ms_val = TermcapResponse.hex_encode(r'\e]52;%p1%s;%p2%s\007')
        # DA1 without extension 52, so DA1 path returns False
        da1_resp = '\x1b[?64;1;4c'
        da1_cpr = '\x1b[10;20R'
        # XTGETTCAP probe + batch with Ms
        probe_resp = f'\x1bP1+r{hex_tn}=787465726d\x1b\\'
        tcap_cpr = '\x1b[11;21R'
        batch_resp = f'\x1bP1+r{hex_ms}={ms_val}\x1b\\'
        term.ungetch(da1_resp + da1_cpr + probe_resp + tcap_cpr + batch_resp)
        result = term.does_osc52_clipboard(timeout=0.1, force=True)
        assert result is True
        assert term._osc52_clipboard_supported is True
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_osc52_clipboard_via_xtgettcap')
    assert 'OK' in output


@pytestmark_pty
def test_does_osc52_clipboard_unsupported():
    """OSC 52 not detected when neither DA1 nor XTGETTCAP report it."""
    def child(term):
        # DA1 without extension 52
        da1_resp = '\x1b[?64;1;4c'
        da1_cpr = '\x1b[10;20R'
        # XTGETTCAP probe fails (no DCS response)
        tcap_cpr = '\x1b[11;21R'
        term.ungetch(da1_resp + da1_cpr + tcap_cpr)
        result = term.does_osc52_clipboard(timeout=0.1)
        assert result is False
        assert term._osc52_clipboard_supported is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_osc52_clipboard_unsupported')
    assert 'OK' in output


@pytestmark_pty
def test_clipboard_copy():
    """clipboard_copy writes base64-encoded OSC 52 set sequence."""
    def child(term):
        term.clipboard_copy('Hello')
        return b''

    output = pty_test(child, parent_func=None,
                      test_name='test_clipboard_copy')
    assert '\x1b]52;c;SGVsbG8=\x07' in output


@pytestmark_pty
def test_clipboard_copy_primary_selection():
    """clipboard_copy with selection='p' uses primary selection."""
    def child(term):
        term.clipboard_copy('test', selection='p')
        return b''

    output = pty_test(child, parent_func=None,
                      test_name='test_clipboard_copy_primary_selection')
    assert '\x1b]52;p;dGVzdA==\x07' in output


@pytestmark_pty
def test_clipboard_copy_nostyling():
    """clipboard_copy is a no-op without styling."""
    def child(term):
        term._does_styling = False
        term.clipboard_copy('Hello')
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_clipboard_copy_nostyling')
    assert '\x1b]52' not in output


@pytestmark_pty
@pytest.mark.parametrize("terminator", ['\x07', '\x1b\\'])
def test_clipboard_paste_success(terminator):
    """clipboard_paste decodes base64 clipboard response."""
    def child(term):
        osc52_resp = '\x1b]52;c;SGVsbG8=' + terminator
        term.ungetch(osc52_resp)
        result = term.clipboard_paste(timeout=0.1)
        assert result == 'Hello'
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_clipboard_paste_success')
    assert 'OK' in output


@pytestmark_pty
@pytest.mark.parametrize("terminator", ['\x07', '\x1b\\'])
def test_clipboard_paste_empty(terminator):
    """clipboard_paste returns empty string for empty clipboard."""
    def child(term):
        osc52_resp = '\x1b]52;c;' + terminator
        term.ungetch(osc52_resp)
        result = term.clipboard_paste(timeout=0.1)
        assert result == ''
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_clipboard_paste_empty')
    assert 'OK' in output


@pytestmark_pty
def test_clipboard_paste_no_response():
    """clipboard_paste returns None when terminal does not respond."""
    def child(term):
        result = term.clipboard_paste(timeout=0.1)
        assert result is None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_clipboard_paste_no_response')
    assert 'OK' in output


@pytestmark_pty
@pytest.mark.parametrize("terminator", ['\x07', '\x1b\\'])
def test_clipboard_paste_invalid_base64(terminator):
    """clipboard_paste returns None for invalid base64 data."""
    def child(term):
        osc52_resp = '\x1b]52;c;!!!not-base64!!!' + terminator
        term.ungetch(osc52_resp)
        result = term.clipboard_paste(timeout=0.1)
        assert result is None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_clipboard_paste_invalid_base64')
    assert 'OK' in output


@pytestmark_pty
def test_get_color_scheme_dark():
    """Dark mode detected from CSI ? 997 ; 1 n response."""
    def child(term):
        resp = '\x1b[?997;1n'
        cpr = '\x1b[10;20R'
        term.ungetch(resp + cpr)
        result = term.get_color_scheme(timeout=0.1)
        assert result == 'dark'
        assert term._color_scheme_supported is True
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_color_scheme_dark')
    assert 'OK' in output


@pytestmark_pty
def test_get_color_scheme_light():
    """Light mode detected from CSI ? 997 ; 2 n response."""
    def child(term):
        resp = '\x1b[?997;2n'
        cpr = '\x1b[10;20R'
        term.ungetch(resp + cpr)
        result = term.get_color_scheme(timeout=0.1)
        assert result == 'light'
        assert term._color_scheme_supported is True
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_color_scheme_light')
    assert 'OK' in output


@pytestmark_pty
def test_get_color_scheme_unsupported():
    """Returns None when terminal does not respond to CSI ? 996 n."""
    def child(term):
        cpr = '\x1b[10;20R'
        term.ungetch(cpr)
        result = term.get_color_scheme(timeout=0.1)
        assert result is None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_color_scheme_unsupported')
    assert 'OK' in output


@pytestmark_pty
def test_does_kitty_query_supported():
    """Kitty query extensions detected from DCS 1+r response."""
    def child(term):
        capname = 'kitty-query-name'
        hex_cap = TermcapResponse.hex_encode(capname)
        hex_val = TermcapResponse.hex_encode('kitty')
        resp = f'\x1bP1+r{hex_cap}={hex_val}\x1b\\'
        cpr = '\x1b[10;20R'
        term.ungetch(resp + cpr)
        result = term.does_kitty_query(timeout=0.1)
        assert result is True
        assert term._kitty_query_supported is True
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_query_supported')
    assert 'OK' in output


@pytestmark_pty
def test_does_kitty_query_unsupported():
    """Kitty query not detected when only CPR arrives."""
    def child(term):
        cpr = '\x1b[10;20R'
        term.ungetch(cpr)
        result = term.does_kitty_query(timeout=0.1)
        assert result is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_query_unsupported')
    assert 'OK' in output


@pytestmark_pty
def test_does_kitty_query_rejected():
    """Kitty query returns False on DCS 0+r (not recognized)."""
    def child(term):
        capname = 'kitty-query-name'
        hex_cap = TermcapResponse.hex_encode(capname)
        resp = f'\x1bP0+r{hex_cap}\x1b\\'
        cpr = '\x1b[10;20R'
        term.ungetch(resp + cpr)
        result = term.does_kitty_query(timeout=0.1)
        assert result is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_query_rejected')
    assert 'OK' in output


@pytestmark_pty
def test_does_decrqss_supported():
    """DECRQSS detected from DCS 1 $ r response."""
    def child(term):
        resp = '\x1bP1$r0m\x1b\\'
        cpr = '\x1b[10;20R'
        term.ungetch(resp + cpr)
        result = term.does_decrqss(timeout=0.1)
        assert result is True
        assert term._decrqss_supported is True
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_decrqss_supported')
    assert 'OK' in output


@pytestmark_pty
def test_does_decrqss_unsupported():
    """DECRQSS not detected when only CPR arrives."""
    def child(term):
        cpr = '\x1b[10;20R'
        term.ungetch(cpr)
        result = term.does_decrqss(timeout=0.1)
        assert result is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_decrqss_unsupported')
    assert 'OK' in output


@pytestmark_pty
def test_does_decrqss_invalid():
    """DECRQSS returns False on DCS 0 $ r (invalid request)."""
    def child(term):
        resp = '\x1bP0$r\x1b\\'
        cpr = '\x1b[10;20R'
        term.ungetch(resp + cpr)
        result = term.does_decrqss(timeout=0.1)
        assert result is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_decrqss_invalid')
    assert 'OK' in output


@pytestmark_pty
def test_get_decrqss_sgr():
    """get_decrqss returns SGR parameter value with setting_id stripped."""
    def child(term):
        resp = '\x1bP1$r0m\x1b\\'
        cpr = '\x1b[10;20R'
        term.ungetch(resp + cpr)
        result = term.get_decrqss(Decrqss.SGR, timeout=0.1)
        assert result == '0'
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_decrqss_sgr')
    assert 'OK' in output


@pytestmark_pty
def test_get_decrqss_sgr_with_attrs():
    """get_decrqss returns compound SGR values."""
    def child(term):
        resp = '\x1bP1$r1;4;38;5;12m\x1b\\'
        cpr = '\x1b[10;20R'
        term.ungetch(resp + cpr)
        result = term.get_decrqss(Decrqss.SGR, timeout=0.1)
        assert result == '1;4;38;5;12'
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_decrqss_sgr_with_attrs')
    assert 'OK' in output


@pytestmark_pty
def test_get_decrqss_cursor_style():
    """get_decrqss returns cursor style value for DECSCUSR."""
    def child(term):
        resp = '\x1bP1$r2 q\x1b\\'
        cpr = '\x1b[10;20R'
        term.ungetch(resp + cpr)
        result = term.get_decrqss(Decrqss.DECSCUSR, timeout=0.1)
        assert result == '2'
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_decrqss_cursor_style')
    assert 'OK' in output


@pytestmark_pty
def test_get_decrqss_scroll_region():
    """get_decrqss returns top/bottom margins for DECSTBM."""
    def child(term):
        resp = '\x1bP1$r1;24r\x1b\\'
        cpr = '\x1b[10;20R'
        term.ungetch(resp + cpr)
        result = term.get_decrqss(Decrqss.DECSTBM, timeout=0.1)
        assert result == '1;24'
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_decrqss_scroll_region')
    assert 'OK' in output


@pytestmark_pty
def test_get_decrqss_unsupported():
    """get_decrqss returns None when terminal does not respond."""
    def child(term):
        cpr = '\x1b[10;20R'
        term.ungetch(cpr)
        result = term.get_decrqss(Decrqss.SGR, timeout=0.1)
        assert result is None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_decrqss_unsupported')
    assert 'OK' in output


@pytestmark_pty
def test_get_decrqss_invalid():
    """get_decrqss returns None on DCS 0 $ r (invalid request)."""
    def child(term):
        resp = '\x1bP0$r\x1b\\'
        cpr = '\x1b[10;20R'
        term.ungetch(resp + cpr)
        result = term.get_decrqss(Decrqss.SGR, timeout=0.1)
        assert result is None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_decrqss_invalid')
    assert 'OK' in output


# -- init-time XTGETTCAP PTY integration tests ---------------------------------------


@pytestmark_pty
def test_terminal_init_xtgettcap_success():
    """Terminal() init with real XTGETTCAP probe and batch succeeds."""
    def parent(master_fd):
        # Phase 1: wait for probe DCS +q and CPR, then respond
        data = b''
        stime = time.time()
        while b'\x1b[6n' not in data:
            remaining = 2.0 - (time.time() - stime)
            if remaining <= 0:
                break
            ready, _, _ = select.select([master_fd], [], [], remaining)
            if ready:
                data += os.read(master_fd, 4096)
        os.write(master_fd, b'\x1bP1+r436f=323536\x1b\\')
        os.write(master_fd, b'\x1b[10;20R')
        # Phase 2: wait for batch queries + CPR, then respond
        data = b''
        stime = time.time()
        while b'\x1b[6n' not in data:
            remaining = 2.0 - (time.time() - stime)
            if remaining <= 0:
                break
            ready, _, _ = select.select([master_fd], [], [], remaining)
            if ready:
                data += os.read(master_fd, 4096)
        os.write(master_fd, b'\x1bP1+r524742=38\x1b\\')
        os.write(master_fd, b'\x1bP1+r544e=787465726d\x1b\\')
        os.write(master_fd, b'\x1b[11;21R')

    def child(term):
        assert term._xtgettcap_cache is not None
        assert term._xtgettcap_cache.supported is True
        assert term._xtgettcap_cache['TN'] == 'xterm'
        assert term._xtgettcap_cache['Co'] == '256'
        assert term._xtgettcap_cache['RGB'] == '8'
        # Verify no stray input leaked after probe
        with term.cbreak():
            leaked = term.inkey(timeout=0)
            assert not leaked
        return b'OK'

    output = pty_test(child, parent,
                      test_name='test_terminal_init_xtgettcap_success',
                      _xtgettcap_data=None)
    assert 'OK' in output


@pytestmark_pty
def test_terminal_init_xtgettcap_timeout():
    """Terminal() init with XTGETTCAP probe that times out."""

    def child(term):
        assert term._xtgettcap_cache is not None
        assert term._xtgettcap_cache.supported is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_terminal_init_xtgettcap_timeout',
                      _xtgettcap_data=None)
    assert 'OK' in output


@pytest.mark.parametrize('init_descriptor,query_side_effect,expected', [
    (999, None, None),
    (999, OSError, None),
    (999, TermcapResponse(supported=True,
                          capabilities={'TN': 'xterm', 'colors': '256'}), 'supported'),
    (999, TermcapResponse(supported=False), 'unsupported'),
])
def test_init_xtgettcap_probe(init_descriptor, query_side_effect, expected):
    """XTGETTCAP probe during init populates _xtgettcap_cache correctly."""
    def mock_init_streams(term_self):
        term_self._is_a_tty = True
        term_self._init_descriptor = init_descriptor
        term_self._keyboard_fd = None
        term_self.errors = term_self.errors or []
        term_self._encoding = 'UTF-8'

    if isinstance(query_side_effect, TermcapResponse):
        patcher = mock.patch('blessed.terminal.query_xtgettcap',
                             return_value=query_side_effect)
    elif query_side_effect is None:
        patcher = mock.patch('blessed.terminal.query_xtgettcap',
                             return_value=None)
    else:
        patcher = mock.patch('blessed.terminal.query_xtgettcap',
                             side_effect=query_side_effect)
    with patcher, \
         mock.patch.object(Terminal, '_Terminal__init__streams',
                           mock_init_streams):
        term = TestTerminal(
            stream=io.StringIO(), force_styling=True,
            _xtgettcap_data=None)
    cache = term._xtgettcap_cache
    if expected is None:
        assert cache is None
    elif expected == 'supported':
        assert cache is not None
        assert cache.supported is True
        assert cache.capabilities['TN'] == 'xterm'
    elif expected == 'unsupported':
        assert cache is not None
        assert cache.supported is False


# -- init-time XTGETTCAP cache population --------------------------------------------


@pytest.mark.parametrize('xtgettcap_data,assertions', [
    (TermcapResponse(supported=True,
                     capabilities={'TN': 'xterm', 'colors': '256'}),
     [('cache', 'not_none'),
      ('_xtgettcap_cache.capabilities["colors"]', '256')]),
    (TermcapResponse(supported=True,
                     capabilities={'TN': 'foot'}),
     [('term.kind', 'foot')]),
    (TermcapResponse(supported=False),
     [('cache', 'not_none'),
      ('_xtgettcap_cache.supported', False)]),
    (None,
     [('cache', 'is_none')]),
])
def test_init_cache_population(xtgettcap_data, assertions):
    """__init__ cache integration with injected or probed XTGETTCAP results."""
    kwargs: dict = {}
    if xtgettcap_data is not None:
        kwargs['_xtgettcap_data'] = xtgettcap_data
    else:
        kwargs['_xtgettcap_data'] = None
        kwargs['is_a_tty'] = True
    term = TestTerminal(stream=io.StringIO(), force_styling=True, **kwargs)
    for attr, expected_val in assertions:
        if attr == 'cache':
            if expected_val == 'not_none':
                assert term._xtgettcap_cache is not None
            elif expected_val == 'is_none':
                assert term._xtgettcap_cache is None
        elif attr == 'term.kind':
            assert term.kind == expected_val
        elif attr.startswith('_xtgettcap_cache.'):
            _, rest = attr.split('.', 1)
            if rest == 'supported':
                assert term._xtgettcap_cache.supported == expected_val
            elif rest.startswith('capabilities['):
                cap_name = rest.split('"')[1]
                assert term._xtgettcap_cache.capabilities[cap_name] == expected_val


@pytest.mark.parametrize('method,capabilities', [
    ('does_styled_underlines', {'Smulx': '\x1b[4:%p1%dm'}),
    ('does_colored_underlines', {'Setulc': '\x1b[58;2;%p1%d;%p2%d;%p3%dm'}),
    ('does_xtgettcap', {'TN': 'xterm'}),
])
def test_force_bypasses_cache(method, capabilities):
    """force=True causes re-query even with populated cache, returns False."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        supported=True, capabilities=capabilities)
    result = getattr(term, method)(timeout=0.01, force=True)
    assert result is False


def test_query_xtgettcap_input_fd_fallback():
    """query_xtgettcap defaults input_fd to stream_fd when not provided."""
    rfd, wfd = os.pipe()
    try:
        result = query_xtgettcap(stream_fd=wfd, timeout=0.01)
        assert result.supported is False
    finally:
        os.close(rfd)
        os.close(wfd)


def test_query_xtgettcap_termios_error():
    """query_xtgettcap survives termios.error on input_fd."""
    rfd, wfd = os.pipe()
    try:
        with mock.patch('blessed.xtgettcap.termios.tcgetattr',
                        side_effect=termios.error):
            result = query_xtgettcap(stream_fd=wfd, input_fd=rfd, timeout=0.01)
            assert result.supported is False
    finally:
        os.close(rfd)
        os.close(wfd)

@pytest.mark.parametrize('capabilities,expected_colors', [
    ({'RGB': '8'}, 1 << 24),
    ({'RGB': '8/8/8'}, 1 << 24),
    ({}, 256),
    ({'RGB': '4'}, 256),
])
def test_rgb_truecolor_detection(capabilities, expected_colors):
    """XTGETTCAP RGB=8 sets number_of_colors to 1<<24, otherwise uses terminfo."""
    xt_data = TermcapResponse(supported=True, capabilities=capabilities)
    with mock.patch.dict(os.environ, {}, clear=True):
        term = Terminal(
            kind='xterm-256color', force_styling=True,
            _xtgettcap_data=xt_data)
        assert term.number_of_colors == expected_colors


def test_make_jinxed_capabilities_parses_binary_numeric():
    """make_jinxed_capabilities decodes binary-encoded numeric values."""
    caps = {'colors': '\x01\x00', 'pairs': '\x7f\xff', 'TN': 'test'}
    xt_data = TermcapResponse(supported=True, capabilities=caps)
    result = xt_data.make_jinxed_capabilities()
    assert result['num_caps']['colors'] == 256
    assert result['num_caps']['pairs'] == 32767
