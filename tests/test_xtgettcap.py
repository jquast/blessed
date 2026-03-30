"""Tests for XTGETTCAP (DCS +q) terminal capability queries."""
# std imports
import io

# 3rd party
import pytest

# local
from blessed._capabilities import Decrqss
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


class TestStyledUnderlines:
    """Terminal.does_styled_underlines() and does_colored_underlines()."""

    def test_styled_underlines_supported(self):
        """Returns True when Smulx is in XTGETTCAP capabilities."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._xtgettcap_cache = TermcapResponse(
                supported=True,
                capabilities={'TN': 'xterm', 'Smulx': '\x1b[4:%p1%dm'})
            assert term.does_styled_underlines() is True
        child()

    def test_styled_underlines_unsupported(self):
        """Returns False when Smulx is not in capabilities."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._xtgettcap_cache = TermcapResponse(
                supported=True, capabilities={'TN': 'xterm'})
            assert term.does_styled_underlines() is False
        child()

    def test_styled_underlines_no_xtgettcap(self):
        """Returns False when XTGETTCAP is not supported."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._xtgettcap_first_query_failed = True
            assert term.does_styled_underlines() is False
        child()

    def test_colored_underlines_supported(self):
        """Returns True when Setulc is in XTGETTCAP capabilities."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._xtgettcap_cache = TermcapResponse(
                supported=True,
                capabilities={'Setulc': '\x1b[58;2;%p1%d;%p2%d;%p3%dm'})
            assert term.does_colored_underlines() is True
        child()

    def test_colored_underlines_unsupported(self):
        """Returns False when Setulc is not in capabilities."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._xtgettcap_cache = TermcapResponse(
                supported=True, capabilities={'TN': 'xterm'})
            assert term.does_colored_underlines() is False
        child()


class TestOsc52Clipboard:
    """Terminal.does_osc52_clipboard() detection."""

    def test_not_a_tty(self):
        """Returns False when not a TTY."""
        @as_subprocess
        def child():
            term = TestTerminal(stream=io.StringIO(), force_styling=True,
                                is_a_tty=False)
            assert term.does_osc52_clipboard(timeout=0.01) is False
        child()

    def test_cached_result(self):
        """Returns cached result without re-querying."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._osc52_clipboard_supported = True
            assert term.does_osc52_clipboard() is True
        child()

    def test_force_bypasses_cache(self):
        """force=True bypasses cached result."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._osc52_clipboard_supported = True
            result = term.does_osc52_clipboard(timeout=0.01, force=True)
            assert result is False
        child()


class TestColorScheme:
    """Terminal.get_color_scheme() detection."""

    def test_not_a_tty(self):
        """Returns None when not a TTY."""
        @as_subprocess
        def child():
            term = TestTerminal(stream=io.StringIO(), force_styling=True,
                                is_a_tty=False)
            assert term.get_color_scheme(timeout=0.01) is None
        child()

    def test_negative_cache(self):
        """Returns None immediately when previously unsupported."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._color_scheme_supported = False
            assert term.get_color_scheme() is None
        child()

    def test_force_bypasses_negative_cache(self):
        """force=True bypasses negative cache."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._color_scheme_supported = False
            result = term.get_color_scheme(timeout=0.01, force=True)
            assert result is None
        child()


class TestKittyQuery:
    """Terminal.does_kitty_query() detection."""

    def test_not_a_tty(self):
        """Returns False when not a TTY."""
        @as_subprocess
        def child():
            term = TestTerminal(stream=io.StringIO(), force_styling=True,
                                is_a_tty=False)
            assert term.does_kitty_query(timeout=0.01) is False
        child()

    def test_cached_result(self):
        """Returns cached result without re-querying."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._kitty_query_supported = True
            assert term.does_kitty_query() is True
        child()

    def test_force_bypasses_cache(self):
        """force=True bypasses cached result."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._kitty_query_supported = True
            result = term.does_kitty_query(timeout=0.01, force=True)
            assert result is False
        child()


class TestDecrqss:
    """Terminal.does_decrqss() detection."""

    def test_not_a_tty(self):
        """Returns False when not a TTY."""
        @as_subprocess
        def child():
            term = TestTerminal(stream=io.StringIO(), force_styling=True,
                                is_a_tty=False)
            assert term.does_decrqss(timeout=0.01) is False
        child()

    def test_cached_result(self):
        """Returns cached result without re-querying."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._decrqss_supported = True
            assert term.does_decrqss() is True
        child()

    def test_force_bypasses_cache(self):
        """force=True bypasses cached result."""
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._decrqss_supported = True
            result = term.does_decrqss(timeout=0.01, force=True)
            assert result is False
        child()


class TestGetDecrqss:
    """Terminal.get_decrqss() state queries."""

    def test_not_a_tty(self):
        """Returns None when not a TTY."""
        @as_subprocess
        def child():
            term = TestTerminal(stream=io.StringIO(), force_styling=True,
                                is_a_tty=False)
            assert term.get_decrqss(timeout=0.01) is None
        child()

    def test_default_setting_is_sgr(self):
        """Default setting_id is SGR ('m')."""
        @as_subprocess
        def child():
            term = TestTerminal(stream=io.StringIO(), force_styling=True,
                                is_a_tty=False)
            assert Decrqss.SGR == 'm'
            assert term.get_decrqss() is None
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


@pytestmark_pty
def test_does_osc52_clipboard_via_da1():
    """OSC 52 detected via DA1 extension 52."""
    def child(term):
        # DA1 with extension 52 (OSC 52 support)
        da1_resp = '\x1b[?64;1;4;52c'
        cpr = '\x1b[10;20R'
        term.ungetch(da1_resp + cpr)
        result = term.does_osc52_clipboard(timeout=1)
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
        result = term.does_osc52_clipboard(timeout=1)
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
        result = term.does_osc52_clipboard(timeout=1)
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
        result = term.clipboard_paste(timeout=1)
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
        result = term.clipboard_paste(timeout=1)
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
        result = term.clipboard_paste(timeout=1)
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
        result = term.get_color_scheme(timeout=1)
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
        result = term.get_color_scheme(timeout=1)
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
        result = term.get_color_scheme(timeout=1)
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
        result = term.does_kitty_query(timeout=1)
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
        result = term.does_kitty_query(timeout=1)
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
        result = term.does_kitty_query(timeout=1)
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
        result = term.does_decrqss(timeout=1)
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
        result = term.does_decrqss(timeout=1)
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
        result = term.does_decrqss(timeout=1)
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
        result = term.get_decrqss(Decrqss.SGR, timeout=1)
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
        result = term.get_decrqss(Decrqss.SGR, timeout=1)
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
        result = term.get_decrqss(Decrqss.DECSCUSR, timeout=1)
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
        result = term.get_decrqss(Decrqss.DECSTBM, timeout=1)
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
        result = term.get_decrqss(Decrqss.SGR, timeout=1)
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
        result = term.get_decrqss(Decrqss.SGR, timeout=1)
        assert result is None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_decrqss_invalid')
    assert 'OK' in output
