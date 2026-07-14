"""Test font glyph support detection (does_font_have_codepoints)."""
import io

import pytest

from .conftest import IS_WINDOWS
from .accessories import TestTerminal, pty_test

pytestmark = pytest.mark.skipif(
    IS_WINDOWS, reason="PTY testing not supported on Windows")

_MINTTY_PROBE_REPLY = '\x1b]7771;!;98;108;101;115;100\x07\x1b[99;99R'


def test_not_a_tty():
    """does_font_have_codepoints returns None when not a TTY."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        result = term.does_font_have_codepoints('abc', timeout=0.01)
        assert result is None
    child()


def test_no_styling():
    """does_font_have_codepoints returns None when does_styling is False."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=False)
        result = term.does_font_have_codepoints('abc', timeout=0.01)
        assert result is None
    child()


def test_empty_string():
    """does_font_have_codepoints returns empty tuple for empty input."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = True
        result = term.does_font_have_codepoints('', timeout=0.01)
        assert result == ()
    child()


def test_mintty_all_supported():
    """Mintty reply lists all codepoints -> all in result string."""
    def child(term):
        term.ungetch(
            _MINTTY_PROBE_REPLY +
            '\x1b]7771;!;65;66;67\x07\x1b[10;20R')
        result = term.does_font_have_codepoints('ABC', timeout=0.01)
        assert result == 'ABC'
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_mintty_all_supported')
    assert 'OK' in output


def test_mintty_partial_support():
    """Mintty reply omits unsupported codepoints from result."""
    def child(term):
        term.ungetch(
            _MINTTY_PROBE_REPLY +
            '\x1b]7771;!;65;67\x07\x1b[10;20R')
        result = term.does_font_have_codepoints('ABC', timeout=0.01)
        assert result == 'AC'
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_mintty_partial_support')
    assert 'OK' in output


def test_mintty_none_supported():
    """Mintty reply with empty cp list -> empty result string."""
    def child(term):
        term.ungetch(
            _MINTTY_PROBE_REPLY +
            '\x1b]7771;!\x07\x1b[10;20R')
        result = term.does_font_have_codepoints('AB', timeout=0.01)
        assert result == ''
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_mintty_none_supported')
    assert 'OK' in output


def test_unsupported_protocol():
    """No protocol probe succeeds -> None."""
    def child(term):
        result = term.does_font_have_codepoints('A', timeout=0.01)
        assert result is None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_unsupported_protocol')
    assert 'OK' in output


def test_chunking():
    """Queries larger than _FONT_QUERY_CHUNK_SIZE are chunked."""
    def child(term):
        count = 257
        chars = 'A' * count
        supported_chunk1 = ''.join(f';{ord(c)}' for c in chars[:256])
        supported_chunk2 = f';{ord(chars[256])}'
        term.ungetch(
            _MINTTY_PROBE_REPLY +
            f'\x1b]7771;!{supported_chunk1}\x07\x1b[10;20R' +
            f'\x1b]7771;!{supported_chunk2}\x07\x1b[30;40R')
        result = term.does_font_have_codepoints(chars, timeout=0.01)
        assert result == chars
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_chunking')
    assert 'OK' in output


def test_beyond_bmp():
    """Codepoints beyond the Basic Multilingual Plane are handled."""
    def child(term):
        cps = '\U0001f600\U0001f601'
        term.ungetch(
            _MINTTY_PROBE_REPLY +
            f'\x1b]7771;!;{ord(cps[0])};{ord(cps[1])}\x07\x1b[10;20R')
        result = term.does_font_have_codepoints(cps, timeout=0.01)
        assert result == cps
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_beyond_bmp')
    assert 'OK' in output


def test_mintty_regex_parsing():
    """_RE_MINTTY_FONT_RESPONSE parses supported codepoint list."""
    from blessed.terminal import _RE_MINTTY_FONT_RESPONSE

    match = _RE_MINTTY_FONT_RESPONSE.search('\x1b]7771;!;65;66;67\x07')
    assert match is not None
    assert match.group(1) == ';65;66;67'

    match = _RE_MINTTY_FONT_RESPONSE.search('\x1b]7771;!\x07')
    assert match is not None
    assert match.group(1) == ''

    match = _RE_MINTTY_FONT_RESPONSE.search('\x1b]7771;!;128512\x1b\\')
    assert match is not None
    assert match.group(1) == ';128512'


def test_glyph_font_regex_parsing():
    """_RE_GLYPH_PROTOCOL_Q_RESPONSE parses cp and status fields."""
    from blessed.terminal import _RE_GLYPH_PROTOCOL_Q_RESPONSE

    matches = list(_RE_GLYPH_PROTOCOL_Q_RESPONSE.finditer(
        '\x1b_25a1;q;cp=41;status=system\x1b\\'
        '\x1b_25a1;q;cp=42;status=\x1b\\'
        '\x1b_25a1;q;cp=43;status=system,glossary\x1b\\'))
    assert len(matches) == 3
    assert int(matches[0].group(1), 16) == 0x41
    assert matches[0].group(2) == 'system'
    assert int(matches[1].group(1), 16) == 0x42
    assert matches[1].group(2) == ''
    assert int(matches[2].group(1), 16) == 0x43
    assert matches[2].group(2) == 'system,glossary'


def test_glyph_protocol_support_regex():
    """_RE_GLYPH_PROTOCOL_S_RESPONSE matches s verb response with capturing group."""
    from blessed.terminal import _RE_GLYPH_PROTOCOL_S_RESPONSE

    match = _RE_GLYPH_PROTOCOL_S_RESPONSE.search('\x1b_25a1;s;fmt=glyf,colrv0\x1b\\')
    assert match is not None
    assert match.group(1) == ';fmt=glyf,colrv0'

    match = _RE_GLYPH_PROTOCOL_S_RESPONSE.search('\x1b_25a1;s;fmt=glyf\x1b\\')
    assert match is not None
    assert match.group(1) == ';fmt=glyf'

    match = _RE_GLYPH_PROTOCOL_S_RESPONSE.search('\x1b_25a1;s;fmt=\x1b\\')
    assert match is not None
    assert match.group(1) == ';fmt='

    assert _RE_GLYPH_PROTOCOL_S_RESPONSE.search('\x1b_25a1;s\x1b\\') is None
    assert _RE_GLYPH_PROTOCOL_S_RESPONSE.search(
        '\x1b_25a1;q;cp=41;status=system\x1b\\') is None
