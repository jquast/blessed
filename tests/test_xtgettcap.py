"""Tests for XTGETTCAP (DCS +q) terminal capability queries."""
# std imports
import io

# 3rd party
import pytest

# local
from blessed._capabilities import TermcapResponse, ITerm2Capabilities
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
        @as_subprocess
        def child():
            term = TestTerminal(stream=io.StringIO(), force_styling=True,
                                is_a_tty=False)
            assert term.get_xtgettcap(timeout=0.01) is None
        child()

    def test_does_xtgettcap_not_a_tty(self):
        """does_xtgettcap returns False when not a TTY."""
        @as_subprocess
        def child():
            term = TestTerminal(stream=io.StringIO(), force_styling=True,
                                is_a_tty=False)
            assert term.does_xtgettcap(timeout=0.01) is False
        child()

    def test_cached_result(self):
        """Returns cached result without re-querying."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True

            cached = TermcapResponse(supported=True,
                                     capabilities={'TN': 'test'})
            term._xtgettcap_cache = cached

            result = term.get_xtgettcap()
            assert result is cached
        child()

    def test_sticky_failure(self):
        """Returns None after first query failure."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._xtgettcap_first_query_failed = True

            result = term.get_xtgettcap()
            assert result is None
        child()

    def test_force_bypasses_cache(self):
        """force=True bypasses both cache and sticky failure."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True

            cached = TermcapResponse(supported=True,
                                     capabilities={'TN': 'old'})
            term._xtgettcap_cache = cached
            term._xtgettcap_first_query_failed = True

            result = term.get_xtgettcap(timeout=0.01, force=True)
            assert result is None
        child()

    def test_parse_xtgettcap_responses(self):
        """Parse multiple DCS +r responses."""
        from blessed.terminal import Terminal
        raw = (
            '\x1bP1+r544e=787465726d\x1b\\'
            '\x1bP1+r636f6c6f7273=323536\x1b\\'
            '\x1bP0+r626365\x1b\\'
        )
        capabilities: dict = {}
        Terminal._parse_xtgettcap_responses(raw, capabilities)
        assert capabilities['TN'] == 'xterm'
        assert capabilities['colors'] == '256'
        assert 'bce' not in capabilities

    def test_parse_xtgettcap_boolean_capability(self):
        """Parse DCS +r boolean capability (no value)."""
        from blessed.terminal import Terminal
        raw = '\x1bP1+r626365\x1b\\'
        capabilities: dict = {}
        Terminal._parse_xtgettcap_responses(raw, capabilities)
        assert capabilities['bce'] == ''

    def test_does_xtgettcap_with_cached(self):
        """does_xtgettcap returns True with cached supported result."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._xtgettcap_cache = TermcapResponse(
                supported=True, capabilities={'TN': 'test'})

            assert term.does_xtgettcap() is True
        child()

    def test_does_xtgettcap_unsupported(self):
        """does_xtgettcap returns False after probe failure."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._xtgettcap_first_query_failed = True

            assert term.does_xtgettcap() is False
        child()


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
        result = term.get_xtgettcap(timeout=1)
        assert result is not None
        assert result.supported is True
        assert result['TN'] == 'xterm'
        assert result['Co'] == '256'
        assert term._xtgettcap_cache is result
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_xtgettcap_full_success')
    assert 'OK' in output


@pytestmark_pty
def test_get_xtgettcap_probe_failure():
    """Phase 1 probe failure sets sticky flag and writes clear_eol."""
    def child(term):
        # Only CPR, no DCS response -- probe fails
        term.ungetch('\x1b[10;20R')
        result = term.get_xtgettcap(timeout=1)
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
        result = term.get_xtgettcap(timeout=1)
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
        result = term.get_xtgettcap(timeout=0.01)
        assert result is not None
        assert result.supported is True
        assert result['TN'] == 'xterm'
        assert len(result) == 1
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_xtgettcap_batch_empty_flushinp')
    assert 'OK' in output
