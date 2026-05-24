"""Tests for XTGETTCAP (DCS +q) terminal capability queries."""
# std imports
import io
import os
import select
import sys
import time

# 3rd party
import pytest
from unittest import mock

# local
from blessed._capabilities import TermcapResponse, ITerm2Capabilities
from blessed.terminal import Terminal
from .conftest import IS_WINDOWS
from .accessories import TestTerminal, pty_test, NO_XTGETTCAP_DATA


def test_hex_encode():
    """Hex-encode ASCII strings."""
    assert TermcapResponse.hex_encode('TN') == '544e'
    assert TermcapResponse.hex_encode('colors') == '636f6c6f7273'


def test_hex_decode():
    """Hex-decode valid hex strings."""
    assert TermcapResponse.hex_decode('544e') == 'TN'
    assert TermcapResponse.hex_decode('636f6c6f7273') == 'colors'


def test_hex_decode_invalid():
    """Hex-decode returns empty string on invalid hex."""
    assert TermcapResponse.hex_decode('zzzz') == ''


def test_hex_decode_non_ascii():
    """Hex-decode returns empty string on non-ASCII bytes."""
    assert TermcapResponse.hex_decode('c0c1') == ''


def test_supported_with_capabilities():
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


def test_unsupported():
    """Unsupported response returns None for all properties."""
    resp = TermcapResponse(supported=False)
    assert resp.supported is False
    assert resp.terminal_name is None
    assert resp.num_colors is None
    assert len(resp) == 0


def test_num_colors_non_integer():
    """Non-integer colors value returns None."""
    resp = TermcapResponse(supported=True, capabilities={'colors': 'abc'})
    assert resp.num_colors is None


def test_repr():
    """String representation includes key attributes."""
    resp = TermcapResponse(supported=True, capabilities={'TN': 'xterm'})
    assert 'supported=True' in repr(resp)
    assert 'TN' in repr(resp)


def test_getitem_keyerror():
    """Missing key raises KeyError."""
    resp = TermcapResponse(supported=True, capabilities={})
    with pytest.raises(KeyError):
        _ = resp['nonexistent']


def test_defaults_empty_capabilities():
    """Default capabilities is empty dict."""
    resp = TermcapResponse(supported=True)
    assert resp.capabilities == {}
    assert len(resp) == 0


def test_make_jinxed_capabilities_classifies_by_type():
    """Bool, num, and str caps are routed to correct output dicts."""
    resp = TermcapResponse(supported=True, capabilities={
        'am': '',          # empty value + in BOOL_CAPS -> bool_caps
        'colors': '256',   # digit value + in NUM_CAPS -> num_caps
        'TN': 'xterm',     # non-empty + not in NUM_CAPS -> str_caps
    })
    result = resp.make_jinxed_capabilities()
    assert 'am' in result['bool_caps']
    assert result['num_caps'] == {'colors': 256}
    assert result['str_caps'] == {'TN': 'xterm'}


def test_make_jinxed_capabilities_non_digit_num_value():
    """Non-digit NUM_CAPS value is skipped."""
    resp = TermcapResponse(supported=True, capabilities={
        'colors': 'not_a_number',
    })
    result = resp.make_jinxed_capabilities()
    assert 'colors' not in result['num_caps']


def test_make_jinxed_capabilities_skips_rgb():
    """RGB capability is excluded from num_caps."""
    resp = TermcapResponse(supported=True, capabilities={
        'RGB': '8',
    })
    result = resp.make_jinxed_capabilities()
    assert 'RGB' not in result['num_caps']


def test_xtgettcap_probe_oserror():
    """XTGETTCAP probe OSError is recorded in errors list."""
    with mock.patch('os.isatty', return_value=True), \
        mock.patch.object(Terminal, '_xtgettcap_batch',
                          side_effect=OSError('broken pipe')):
        t = Terminal(stream=sys.__stdout__, force_styling=True)
        assert any('OSError' in err for err in t.errors)


def test_init_descriptor_stdout_valueerror():
    """ValueError from sys.__stdout__.fileno() is recorded in errors."""
    mock_term = mock.MagicMock()
    mock_term.tigetnum.return_value = 0
    with mock.patch.object(sys.__stdout__, 'fileno',
                           side_effect=ValueError('detached stdout')), \
            mock.patch('blessed.terminal.jinxed.Terminal', return_value=mock_term):
        t = Terminal(stream=io.StringIO(), force_styling=True)
        assert any('stdout may be detached or closed' in err for err in t.errors)
        assert t.number_of_colors == 0


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
def test_unescape_terminfo_backslash_escapes(value, expected):
    r"""Backslash escapes are unescaped."""
    assert TermcapResponse.unescape_terminfo(value) == expected


@pytest.mark.parametrize('value,expected', [
    (r'\033', '\x1b'),
    (r'\101\102', 'AB'),
    (r'\000', '\x00'),
    (r'\141', 'a'),
])
def test_unescape_terminfo_octal_escapes(value, expected):
    r"""Octal \NNN escapes are decoded."""
    assert TermcapResponse.unescape_terminfo(value) == expected


@pytest.mark.parametrize('value,expected', [
    ('^A', '\x01'),
    ('^Z', '\x1a'),
    ('^?', '\x7f'),
    ('^_', '\x1f'),
])
def test_unescape_terminfo_control_notation(value, expected):
    """^X control-character and ^? DEL notation."""
    assert TermcapResponse.unescape_terminfo(value) == expected


def test_unescape_terminfo_mixed():
    """Mixed escape sequences."""
    result = TermcapResponse.unescape_terminfo(r'\E[5m\E[m')
    assert result == '\x1b[5m\x1b[m'


def test_unescape_terminfo_no_escapes():
    """String without escapes is unchanged."""
    assert TermcapResponse.unescape_terminfo('hello') == 'hello'


@pytest.mark.parametrize('value,expected', [
    (r'\9', r'\9'),
    ('^0', '^0'),
])
def test_unescape_terminfo_pass_through(value, expected):
    """Escape-like sequences that are not valid escapes pass through unchanged."""
    assert TermcapResponse.unescape_terminfo(value) == expected


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
def test_parse_feature_string(feature_str, expected):
    """Parse iTerm2 feature string into dict."""
    result = ITerm2Capabilities.parse_feature_string(feature_str)
    assert result == expected


def test_iterm2_supported_capabilities_response():
    """Supported response with features."""
    features = {'truecolor': 2, 'sixel': True}
    caps = ITerm2Capabilities(supported=True, features=features)
    assert caps.supported is True
    assert caps.features == features


def test_iterm2_unsupported():
    """Unsupported response has empty features."""
    caps = ITerm2Capabilities(supported=False)
    assert caps.supported is False
    assert caps.features == {}


def test_iterm2_repr():
    """String representation includes key attributes."""
    caps = ITerm2Capabilities(
        supported=True, features={'truecolor': 2})
    r = repr(caps)
    assert 'supported=True' in r
    assert 'truecolor' in r


def test_get_xtgettcap_not_a_tty():
    """Returns None when not a TTY."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        is_a_tty=False)
    assert term.get_xtgettcap(timeout=0.01) is None


def test_does_xtgettcap_not_a_tty():
    """does_xtgettcap returns False when not a TTY."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        is_a_tty=False)
    assert term.does_xtgettcap(timeout=0.01) is False


def test_get_xtgettcap_cached_result():
    """Returns cached result without re-querying."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True

    cached = TermcapResponse(supported=True,
                             capabilities={'TN': 'test'})
    term._xtgettcap_cache = cached

    result = term.get_xtgettcap(caps=['TN'])
    assert result is not cached
    assert result.supported is True
    assert result['TN'] == 'test'


def test_get_xtgettcap_sticky_failure():
    """Returns None after first query failure."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(supported=False)

    result = term.get_xtgettcap()
    assert result is None


def test_get_xtgettcap_force_bypasses_cache():
    """force=True bypasses both cache and sticky failure."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True

    cached = TermcapResponse(supported=True,
                             capabilities={'TN': 'old'})
    term._xtgettcap_cache = cached

    result = term.get_xtgettcap(timeout=0.01, force=True)
    assert result is not None
    assert result.supported


def test_parse_xtgettcap_responses():
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


def test_parse_xtgettcap_boolean_capability():
    """Parse DCS +r boolean capability."""
    raw = '\x1bP1+r626365\x1b\\'
    capabilities = TermcapResponse.parse_capabilities(raw)
    assert capabilities['bce'] == ''


def test_parse_xtgettcap_malformed_empty_name():
    """Parse malformed DCS +r response with empty capability name (VTE/GNOME Terminal)."""
    raw = '\x1bP0+r\x1b\\'
    # parse_capabilities skips valid=0 responses.
    assert not TermcapResponse.parse_capabilities(raw)
    # The regex must match; sub() must consume the entire string.
    assert TermcapResponse._RE_XTGETTCAP_RESPONSE.sub('', raw) == ''
    # The regex must NOT consume unrelated text around the malformed response.
    mixed = 'abc\x1bP0+r\x1b\\def'
    assert TermcapResponse._RE_XTGETTCAP_RESPONSE.sub('', mixed) == 'abcdef'


def test_does_xtgettcap_with_cached():
    """does_xtgettcap returns True with cached supported result."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        supported=True, capabilities={'TN': 'test'})

    assert term.does_xtgettcap(timeout=0.1) is True


def test_does_xtgettcap_unsupported():
    """does_xtgettcap returns False after probe failure."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(supported=False)

    assert term.does_xtgettcap() is False


def test_get_xtgettcap_caps_all_in_cache():
    """caps= with all names already in cache returns filtered copy."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    cached = TermcapResponse(supported=True,
                             capabilities={'TN': 'xterm', 'FAKE_CAP': 'FAKE_VAL'})
    term._xtgettcap_cache = cached
    result = term.get_xtgettcap(caps=['FAKE_CAP'])
    assert result is not cached
    assert result['FAKE_CAP'] == 'FAKE_VAL'


def test_get_xtgettcap_caps_incremental_queries_missing():
    """caps= with names absent from cache queries only missing ones."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        supported=True, capabilities={'TN': 'xterm'})
    hex_fake = TermcapResponse.hex_encode('FAKE_CAP')
    term.ungetch(
        f'\x1bP1+r{hex_fake}=46414b455f56414c\x1b\\'
        '\x1b[10;20R')
    result = term.get_xtgettcap(caps=['FAKE_CAP'], timeout=0.1)
    assert result['FAKE_CAP'] == 'FAKE_VAL'
    assert 'TN' not in result.capabilities
    assert 'FAKE_CAP' in term._xtgettcap_cache.capabilities
    assert term._xtgettcap_cache.capabilities['TN'] == 'xterm'


def test_get_xtgettcap_caps_force_queries_all():
    """force=True with caps= queries only the specified caps."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        supported=True, capabilities={'TN': 'old'})
    hex_fake = TermcapResponse.hex_encode('FAKE_CAP')
    term.ungetch(
        f'\x1bP1+r{hex_fake}=46414b455f56414c\x1b\\'
        '\x1b[10;20R')
    result = term.get_xtgettcap(timeout=0.1, force=True, caps=['FAKE_CAP'])
    assert result['FAKE_CAP'] == 'FAKE_VAL'


def test_get_xtgettcap_caps_ignores_sticky_failure():
    """caps= with sticky failure still attempts query."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    hex_fake = TermcapResponse.hex_encode('FAKE_CAP')
    term.ungetch(
        f'\x1bP1+r{hex_fake}=46414b455f56414c\x1b\\'
        '\x1b[10;20R')
    result = term.get_xtgettcap(timeout=0.1, caps=['FAKE_CAP'])
    assert result is not None


def test_get_xtgettcap_batch_non_line_buffered():
    """_xtgettcap_batch with _line_buffered=False skips cbreak context manager."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._line_buffered = False
    hex_fake = TermcapResponse.hex_encode('FAKE_CAP')
    term.ungetch(
        f'\x1bP1+r{hex_fake}=46414b455f56414c\x1b\\'
        '\x1b[10;20R')
    result = term.get_xtgettcap(timeout=0.1, force=True, caps=['FAKE_CAP'])
    assert result is not None
    assert result['FAKE_CAP'] == 'FAKE_VAL'


def test_xtgettcap_batch_empty_caps():
    """_xtgettcap_batch returns None when caps list is empty."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True)
    result = term._xtgettcap_batch([], timeout=0.01)
    assert result is None


def test_get_xtgettcap_all_parameter():
    """No caps specified queries all standard XTGETTCAP capabilities."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    hex_tn = TermcapResponse.hex_encode('TN')
    hex_co = TermcapResponse.hex_encode('colors')
    term.ungetch(
        f'\x1bP1+r{hex_tn}=787465726d\x1b\\'
        f'\x1bP1+r{hex_co}=323536\x1b\\'
        '\x1b[10;20R'
        '\x1b[11;21R')
    result = term.get_xtgettcap(timeout=0.1)
    assert result is not None
    assert result['TN'] == 'xterm'
    assert result['colors'] == '256'


def test_get_xtgettcap_none_sentinel_not_in_returned_response():
    """None-valued caps in cache are filtered from returned response."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        supported=True,
        capabilities={'TN': 'xterm', 'FAKE_CAP': None})
    result = term.get_xtgettcap(caps=['TN', 'FAKE_CAP'])
    assert 'TN' in result.capabilities
    assert 'FAKE_CAP' not in result.capabilities


def test_get_xtgettcap_none_sentinel_internal_cache_retains_none():
    """Internal cache retains None sentinel for absent caps."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        supported=True,
        capabilities={'TN': 'xterm'})
    hex_fake = TermcapResponse.hex_encode('FAKE_CAP')
    term.ungetch(
        f'\x1bP1+r{hex_fake}=\x1b\\'
        '\x1b[10;20R')
    result = term.get_xtgettcap(caps=['FAKE_CAP'], timeout=0.1)
    assert 'FAKE_CAP' in result.capabilities


def test_get_xtgettcap_absent_cap_not_requeried():
    """Absent caps are not re-queried on subsequent calls."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        supported=True,
        capabilities={'TN': 'xterm', 'Ms': None})
    result = term.get_xtgettcap(caps=['Ms'], timeout=0.01)
    assert result is not None
    assert result.supported
    assert 'Ms' not in result.capabilities
    assert term._xtgettcap_cache.capabilities['Ms'] is None


def test_get_xtgettcap_no_args():
    """get_xtgettcap() with no caps queries all standard caps."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    hex_tn = TermcapResponse.hex_encode('TN')
    hex_co = TermcapResponse.hex_encode('colors')
    term.ungetch(
        f'\x1bP1+r{hex_tn}=787465726d\x1b\\'
        f'\x1bP1+r{hex_co}=323536\x1b\\'
        '\x1b[10;20R'
        '\x1b[11;21R')
    result = term.get_xtgettcap(timeout=0.1)
    assert result is not None
    assert result['TN'] == 'xterm'
    assert result['colors'] == '256'


def test_filter_xtgettcap_response_removes_none_values():
    """_filter_xtgettcap_response removes None-valued caps."""
    tc = TermcapResponse(
        supported=True,
        capabilities={'TN': 'xterm', 'RGB': None, 'colors': '256'})
    result = Terminal._filter_xtgettcap_response(tc)
    assert 'TN' in result.capabilities
    assert 'colors' in result.capabilities
    assert 'RGB' not in result.capabilities
    assert result.supported is True


def test_styled_underlines_supported():
    """Returns True when Smulx is in XTGETTCAP capabilities."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        supported=True,
        capabilities={'TN': 'xterm', 'Smulx': '\x1b[4:%p1%dm'})
    assert term.does_styled_underlines() is True


def test_styled_underlines_unsupported():
    """Returns False when Smulx is not in capabilities."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        supported=True, capabilities={'TN': 'xterm'})
    assert term.does_styled_underlines(timeout=0.1) is False


def test_styled_underlines_no_xtgettcap():
    """Returns False when XTGETTCAP is not supported."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(supported=False)
    assert term.does_styled_underlines(timeout=0.1) is False


def test_colored_underlines_supported():
    """Returns True when Setulc is in XTGETTCAP capabilities."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        supported=True,
        capabilities={'Setulc': '\x1b[58;2;%p1%d;%p2%d;%p3%dm'})
    assert term.does_colored_underlines() is True


def test_colored_underlines_unsupported():
    """Returns False when Setulc is not in capabilities."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        supported=True, capabilities={'TN': 'xterm'})
    assert term.does_colored_underlines(timeout=0.1) is False


def test_osc52_clipboard_not_a_tty():
    """Returns False when not a TTY."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        is_a_tty=False)
    assert term.does_osc52_clipboard(timeout=0.01) is False


def test_osc52_clipboard_cached_result():
    """Returns cached result without re-querying."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._osc52_clipboard_supported = True
    assert term.does_osc52_clipboard() is True


def test_osc52_clipboard_force_bypasses_cache():
    """force=True bypasses cached result."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._osc52_clipboard_supported = True
    result = term.does_osc52_clipboard(timeout=0.01, force=True)
    assert result is False


def test_color_scheme_not_a_tty():
    """Returns None when not a TTY."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        is_a_tty=False)
    assert term.get_color_scheme(timeout=0.01) is None


def test_color_scheme_negative_cache():
    """Returns None immediately when previously unsupported."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._color_scheme_supported = False
    assert term.get_color_scheme() is None


def test_color_scheme_force_bypasses_negative_cache():
    """force=True bypasses negative cache."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._color_scheme_supported = False
    result = term.get_color_scheme(timeout=0.01, force=True)
    assert result is None


def test_kitty_query_not_a_tty():
    """Returns False when not a TTY."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        is_a_tty=False)
    assert term.does_kitty_query(timeout=0.01) is False


def test_kitty_query_cached_result():
    """Returns cached result without re-querying."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        capabilities={'kitty-query-name': 'kitty'},
        supported=True)
    assert term.does_kitty_query() is True


def test_kitty_query_force_bypasses_cache():
    """force=True bypasses cached result."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._xtgettcap_cache = TermcapResponse(
        capabilities={'kitty-query-name': 'kitty'},
        supported=True)
    result = term.does_kitty_query(timeout=0.01, force=True)
    assert result is True


pytestmark_pty = pytest.mark.skipif(
    IS_WINDOWS, reason="ungetch and PTY testing not supported on Windows")


@pytestmark_pty
def test_get_xtgettcap_full_success():
    """Phase 1 probe + Phase 2 batch query returns parsed capabilities."""
    def child(term):
        probe_resp = '\x1bP1+r544e=787465726d\x1b\\'
        cpr = '\x1b[10;20R'
        batch_resp = '\x1bP1+r636f6c6f7273=323536\x1b\\'
        term.ungetch(probe_resp + cpr + batch_resp)
        result = term.get_xtgettcap(timeout=0.1, force=True)
        assert result is not None
        assert result.supported is True
        assert result['TN'] == 'xterm'
        assert result['colors'] == '256'
        assert term._xtgettcap_cache is not None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_xtgettcap_full_success')
    assert 'OK' in output


@pytestmark_pty
def test_get_xtgettcap_batch_empty():
    """Batch with CPR-only response returns supported=False."""
    def child(term):
        term._xtgettcap_cache = TermcapResponse(supported=False)
        term.ungetch('\x1b[10;20R')
        result = term.get_xtgettcap(timeout=0.1)
        assert result is None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_xtgettcap_batch_empty')
    assert 'OK' in output


@pytestmark_pty
def test_get_xtgettcap_batch_with_remaining_input():
    """Keyboard data interleaved with batch responses is re-buffered."""
    def child(term):
        probe_resp = '\x1bP1+r544e=787465726d\x1b\\'
        cpr = '\x1b[10;20R'
        batch_resp = '\x1bP1+r636f6c6f7273=323536\x1b\\'
        keyboard_data = 'x'
        term.ungetch(probe_resp + cpr + batch_resp + keyboard_data)
        result = term.get_xtgettcap(timeout=0.1, force=True)
        assert result is not None
        assert result['TN'] == 'xterm'
        assert result['colors'] == '256'
        with term.cbreak():
            inp = term.inkey(timeout=0)
            assert inp == 'x'
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_xtgettcap_batch_with_remaining_input')
    assert 'OK' in output


@pytestmark_pty
def test_get_xtgettcap_batch_empty_flushinp():
    """Phase 2 flushinp returns empty."""
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
        da1_resp = '\x1b[?64;1;4c'
        da1_cpr = '\x1b[10;20R'
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
        da1_resp = '\x1b[?64;1;4c'
        da1_cpr = '\x1b[10;20R'
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
        assert result is True, (term._xtgettcap_cache, term.does_styling)
        assert term._xtgettcap_cache is not None
        assert term._xtgettcap_cache.capabilities.get('kitty-query-name') == 'kitty'
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_query_supported',
                      _xtgettcap_data=TermcapResponse(supported=True),
                      )
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
    """Kitty query returns False on DCS 0+r."""
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
def test_terminal_init_xtgettcap_success():
    """Terminal() init with real XTGETTCAP probe and batch succeeds."""
    def parent(master_fd):
        # Wait for child to emit queries (indicates it's past
        # read_until_semaphore).  No need to drain stdout -- child's
        # _read_until reads from stdin (what we write to master_fd),
        # not stdout (what we read from master_fd).
        stime = time.time()
        while time.time() - stime < 0.5:
            ready, _, _ = select.select([master_fd], [], [], 0.05)
            if ready:
                break
        os.write(master_fd, b'\x1bP1+r636f6c6f7273=323536\x1b\\')
        os.write(master_fd, b'\x1bP1+r524742=38\x1b\\')
        os.write(master_fd, b'\x1bP1+r544e=787465726d\x1b\\')
        os.write(master_fd, b'\x1b[10;20R')

    def child(term):
        assert term._xtgettcap_cache is not None
        assert term._xtgettcap_cache.supported is True
        assert term._xtgettcap_cache['TN'] == 'xterm'
        assert term._xtgettcap_cache['colors'] == '256'
        assert term._xtgettcap_cache['RGB'] == '8'
        with term.cbreak():
            leaked = term.inkey(timeout=0)
            assert not leaked
        return b'OK'

    output = pty_test(child, parent,
                      test_name='test_terminal_init_xtgettcap_success',
                      _xtgettcap_data=NO_XTGETTCAP_DATA)
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
                      _xtgettcap_data=NO_XTGETTCAP_DATA,
                      _xtgettcap_timeout=0.01)
    assert 'OK' in output


@pytestmark_pty
def test_terminal_init_xtgettcap_unsupported():
    """Terminal() init with XTGETTCAP probe that gets CPR-only response."""
    def parent(master_fd):
        data = b''
        stime = time.time()
        while b'\x1b[6n' not in data:
            remaining = 2.0 - (time.time() - stime)
            if remaining <= 0:
                break
            ready, _, _ = select.select([master_fd], [], [], remaining)
            if ready:
                data += os.read(master_fd, 4096)
        # Send only CPR, no XTGETTCAP responses -- terminal does not support it.
        os.write(master_fd, b'\x1b[10;20R')

    def child(term):
        assert term._xtgettcap_cache is not None
        assert term._xtgettcap_cache.supported is False
        return b'OK'

    output = pty_test(child, parent,
                      test_name='test_terminal_init_xtgettcap_unsupported',
                      _xtgettcap_data=NO_XTGETTCAP_DATA)
    assert 'OK' in output


def test_init_cache_populated_from_xtgettcap_data():
    """Injected XTGETTCAP data populates _xtgettcap_cache."""
    xt_data = TermcapResponse(
        supported=True, capabilities={'TN': 'xterm', 'colors': '256'})
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        kind=None, _xtgettcap_data=xt_data)
    assert term._xtgettcap_cache is not None
    assert term._xtgettcap_cache.capabilities['colors'] == '256'


def test_init_kind_set_from_xtgettcap_tn():
    """XTGETTCAP TN capability updates terminal kind."""
    xt_data = TermcapResponse(
        supported=True, capabilities={'TN': 'foot'})
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        kind=None, _xtgettcap_data=xt_data)
    assert term.kind == 'foot'


def test_init_cache_unsupported_from_data():
    """Injected unsupported TermcapResponse stored in cache."""
    xt_data = TermcapResponse(supported=False)
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        kind=None, _xtgettcap_data=xt_data)
    assert term._xtgettcap_cache is not None
    assert term._xtgettcap_cache.supported is False


def test_init_cache_unsupported_from_probe_timeout():
    """XTGETTCAP probe timeout sets supported=False in cache."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        kind=None, _xtgettcap_data=None, is_a_tty=True)
    assert term._xtgettcap_cache is not None
    assert term._xtgettcap_cache.supported is False


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
    assert result is True


@pytest.mark.parametrize('capabilities,expected_colors', [
    ({'RGB': '8'}, 1 << 24),
    ({'RGB': '8/8/8'}, 1 << 24),
    ({}, 256),
    ({'RGB': '4'}, 256),
])
def test_rgb_truecolor_detection(capabilities, expected_colors):
    """XTGETTCAP RGB=8 sets number_of_colors to 1<<24."""
    xt_data = TermcapResponse(supported=True, capabilities=capabilities)
    with mock.patch.dict(os.environ, {}, clear=True):
        term = Terminal(
            kind='xterm-256color', force_styling=True,
            _xtgettcap_data=xt_data)
        assert term.number_of_colors == expected_colors


def test_get_xtgettcap_applies_overlay_to_jinxed():
    """get_xtgettcap() applies discovered caps to jinxed for property access."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, kind='vt220', force_styling=True)
    term._is_a_tty = True
    assert term.dim == ''

    hex_dim = TermcapResponse.hex_encode('dim')
    term.ungetch(
        '\x1bP1+r' + hex_dim + '=1b5b326d\x1b\\'
        '\x1b[10;20R')
    result = term.get_xtgettcap(timeout=0.1, force=True, caps=['dim'])
    assert result is not None
    assert result['dim'] == '\x1b[2m'


def test_xtgettcap_skip_ansicon_env():
    """XTGETTCAP init probe skipped when ANSICON env var is set."""
    with mock.patch.dict(os.environ, {'ANSICON': '1'}), \
            mock.patch('os.isatty', return_value=True), \
            mock.patch.object(Terminal, '_xtgettcap_batch') as mock_batch:
        t = Terminal(stream=sys.__stdout__, force_styling=True)
        mock_batch.assert_not_called()
        assert any('ansicon' in err for err in t.errors)
        assert t._xtgettcap_cache.supported is False


def test_xtgettcap_skip_conemuansi_env():
    """XTGETTCAP init probe skipped when ConEmuANSI env var is set."""
    with mock.patch.dict(os.environ, {'ConEmuANSI': 'ON'}), \
            mock.patch('os.isatty', return_value=True), \
            mock.patch.object(Terminal, '_xtgettcap_batch') as mock_batch:
        t = Terminal(stream=sys.__stdout__, force_styling=True)
        mock_batch.assert_not_called()
        assert any('ansicon' in err for err in t.errors)
        assert t._xtgettcap_cache.supported is False


def test_xtgettcap_skip_Terminal_app():
    """XTGETTCAP init probe skipped when TERM_PROGRAM is 'Apple_Terminal'."""
    with mock.patch.dict(os.environ, {'TERM_PROGRAM': 'Apple_Terminal'}), \
            mock.patch('os.isatty', return_value=True), \
            mock.patch.object(Terminal, '_xtgettcap_batch') as mock_batch:
        t = Terminal(stream=sys.__stdout__, force_styling=True)
        mock_batch.assert_not_called()
        assert any('Terminal.app' in err for err in t.errors)
        assert t._xtgettcap_cache.supported is False
