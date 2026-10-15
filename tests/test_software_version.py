r"""Tests for SoftwareVersion class and Terminal.get_software_version().

XTVERSION Query Format
======================

The XTVERSION query (CSI > q or ESC [ > q) requests the terminal software
name and version. Supported by modern terminal emulators including xterm,
mintty, iTerm2, tmux, kitty, WezTerm, foot, and VTE-based terminals.

Terminal response: DCS > | text ST  (ESC P > | text ESC \\)

Text format varies by terminal:
  - XTerm(367)
  - kitty(0.24.2)
  - tmux 3.2a
  - WezTerm 20220207-230252-0826fb06
  - X.Org 7.7.0(370)
"""
# std
import io
import time
from unittest import mock

# 3rd party
import pytest

# local
from .conftest import TEST_KEYBOARD, IS_WINDOWS
from .accessories import (
    TestTerminal,
    pty_test,
)
from blessed.keyboard import (SoftwareVersion,
                              resolve_sequence,
                              get_keyboard_codes,
                              get_keyboard_sequences)
from blessed.terminal import Terminal

pytestmark = pytest.mark.skipif(
    not TEST_KEYBOARD or IS_WINDOWS,
    reason="Timing-sensitive tests please do not run on build farms.")


@pytest.mark.parametrize("response,expected_name,expected_version", [
    ('\x1bP>|kitty(0.24.2)\x1b\\', 'kitty', '0.24.2'),
    ('\x1bP>|tmux 3.2a\x1b\\', 'tmux', '3.2a'),
    ('\x1bP>|foot\x1b\\', 'foot', ''),
    ('\x1bP>|WezTerm 20220207-230252-0826fb06\x1b\\', 'WezTerm', '20220207-230252-0826fb06'),
    ('\x1bP>|XTerm(367)\x1b\\', 'XTerm', '367'),
    ('\x1bP>|X.Org 7.7.0(370)\x1b\\', 'X.Org', '7.7.0(370)'),
])
def test_software_version_from_match(response, expected_name, expected_version):
    """Test SoftwareVersion.from_match() with various response formats."""
    match = SoftwareVersion.RE_RESPONSE.match(response)
    sv = SoftwareVersion.from_match(match)
    assert sv is not None
    assert sv.name == expected_name
    assert sv.version == expected_version
    assert sv.raw == response


@pytest.mark.parametrize("invalid_input", ['invalid', ''])
def test_software_version_from_match_invalid(invalid_input):
    """Test SoftwareVersion.from_match() with invalid input."""
    match = SoftwareVersion.RE_RESPONSE.match(invalid_input)
    assert match is None


def test_software_version_repr():
    """Test SoftwareVersion.__repr__()."""
    sv = SoftwareVersion('\x1bP>|kitty(0.24.2)\x1b\\', 'kitty', '0.24.2')
    repr_str = repr(sv)
    assert 'SoftwareVersion' in repr_str
    assert "name='kitty'" in repr_str
    assert "version='0.24.2'" in repr_str


@pytest.mark.parametrize("text,expected_name,expected_version", [
    ('kitty(0.24.2)', 'kitty', '0.24.2'),
    ('tmux 3.2a', 'tmux', '3.2a'),
    ('foot', 'foot', ''),
    ('WezTerm 20220207-230252-0826fb06', 'WezTerm', '20220207-230252-0826fb06'),
])
def test_software_version_parse_text(text, expected_name, expected_version):
    """Test SoftwareVersion._parse_text() with various formats."""
    name, version = SoftwareVersion._parse_text(text)
    assert name == expected_name
    assert version == expected_version


@pytest.mark.parametrize("response,expected_name,expected_version,test_suffix", [
    ('\x1bP>|kitty(0.24.2)\x1b\\', 'kitty', '0.24.2', 'OK'),
    ('\x1bP>|XTerm(367)\x1b\\', 'XTerm', '367', 'XTERM'),
    ('\x1bP>|tmux 3.2a\x1b\\', 'tmux', '3.2a', 'TMUX'),
    ('\x1bP>|WezTerm 20220207-230252-0826fb06\x1b\\',
     'WezTerm', '20220207-230252-0826fb06', 'WEZTERM'),
])
def test_get_software_version_via_ungetch(response, expected_name, expected_version, test_suffix):
    """Test get_software_version() with various terminal responses via ungetch."""
    def child(term):
        term.ungetch(response)
        sv = term.get_software_version(timeout=0.01)
        assert sv is not None
        assert sv.name == expected_name
        assert sv.version == expected_version
        return test_suffix.encode('ascii')

    output = pty_test(child, parent_func=None,
                      test_name=f'test_get_software_version_{test_suffix.lower()}')
    assert output == f'\x1b[>q\x1b[6n{test_suffix}'


def test_get_software_version_timeout():
    """Test get_software_version() timeout without response."""
    def child(term):
        stime = time.time()
        sv = term.get_software_version(timeout=0.1)
        elapsed = time.time() - stime
        assert sv is None
        assert 0.08 <= elapsed <= 0.15
        return b'TIMEOUT'

    output = pty_test(child, parent_func=None, test_name='test_get_software_version_timeout')
    assert output == '\x1b[>q\x1b[6nTIMEOUT'


def test_get_software_version_force_bypass_cache():
    """Test get_software_version() with force=True bypasses cache."""
    def child(term):
        # First response: kitty 0.24.2
        term.ungetch('\x1bP>|kitty(0.24.2)\x1b\\')
        sv1 = term.get_software_version(timeout=0.01)

        # Second response: XTerm 367 with force=True
        term.ungetch('\x1bP>|XTerm(367)\x1b\\')
        sv2 = term.get_software_version(timeout=0.01, force=True)

        assert sv1 is not None
        assert sv2 is not None
        assert sv1.name == 'kitty'
        assert sv2.name == 'XTerm'
        assert sv1 is not sv2

        return b'FORCED'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_software_version_force_bypass_cache')
    assert output == '\x1b[>q\x1b[6n\x1b[>q\x1b[6nFORCED'


def test_get_software_version_no_force_uses_cache():
    """Test get_software_version() without force uses cached result."""
    def child(term):
        # First response: kitty 0.24.2
        term.ungetch('\x1bP>|kitty(0.24.2)\x1b\\')
        sv1 = term.get_software_version(timeout=0.01)

        # Second query without force should use cache even with different ungetch data
        # Response: XTerm 367 - but this is ignored due to cache
        term.ungetch('\x1bP>|XTerm(367)\x1b\\')
        sv2 = term.get_software_version(timeout=0.01, force=False)

        assert sv1 is not None
        assert sv2 is not None
        assert sv1 is sv2
        assert sv1.name == 'kitty'
        assert sv2.name == 'kitty'

        return b'NO_FORCE'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_software_version_no_force_uses_cache')
    assert output == '\x1b[>q\x1b[6nNO_FORCE'


def test_get_software_version_retry_after_timeout():
    """Test get_software_version() can retry after timeout."""
    def child(term):
        # First query fails (timeout)
        sv1 = term.get_software_version(timeout=0.01)

        # Second query succeeds: kitty 0.24.2
        term.ungetch('\x1bP>|kitty(0.24.2)\x1b\\')
        sv2 = term.get_software_version(timeout=0.01)

        assert sv1 is None
        assert sv2 is not None
        assert sv2.name == 'kitty'
        assert sv2.version == '0.24.2'

        return b'RETRY'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_software_version_retry_after_timeout')
    assert output == '\x1b[>q\x1b[6n\x1b[>q\x1b[6nRETRY'


def test_get_software_version_raw_stored():
    """Test SoftwareVersion stores raw response string."""
    raw = '\x1bP>|kitty(0.24.2)\x1b\\'
    match = SoftwareVersion.RE_RESPONSE.match(raw)
    sv = SoftwareVersion.from_match(match)
    assert sv is not None
    assert sv.raw == raw


def test_get_software_version_not_a_tty():
    """Test get_software_version() returns None when not a TTY and no env vars."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = False

        sv = term.get_software_version(timeout=0.01)
        assert sv is None
    child()


def test_get_software_version_env_fallback():
    """Test get_software_version() uses TERM_PROGRAM env vars, without inquiry."""
    def child(term):
        import os
        os.environ['TERM_PROGRAM'] = 'iTerm.app'
        os.environ['TERM_PROGRAM_VERSION'] = '3.5.0'
        try:
            sv = term.get_software_version(timeout=0.01)
            assert sv is not None
            assert sv.name == 'iTerm.app'
            assert sv.version == '3.5.0'
            assert sv.raw == 'iTerm.app 3.5.0'
        finally:
            del os.environ['TERM_PROGRAM']
            del os.environ['TERM_PROGRAM_VERSION']
        return b'ENV_FALLBACK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_software_version_env_fallback')
    assert output == 'ENV_FALLBACK'


def test_get_software_version_env_fallback_no_version():
    """Test env fallback works when TERM_PROGRAM_VERSION is unset."""
    def child(term):
        import os
        os.environ['TERM_PROGRAM'] = 'Apple_Terminal'
        try:
            sv = term.get_software_version(timeout=0.01)
            assert sv is not None
            assert sv.name == 'Apple_Terminal'
            assert sv.version == ''
            assert sv.raw == 'Apple_Terminal'
        finally:
            del os.environ['TERM_PROGRAM']
        return b'ENV_NO_VER'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_software_version_env_fallback_no_version')
    assert output == 'ENV_NO_VER'


def test_get_software_version_env_fallback_version_only():
    """An empty TERM_PROGRAM is treated as unset, so a query is still made."""
    def child(term):
        import os
        os.environ['TERM_PROGRAM_VERSION'] = '1.2.3'
        try:
            sv = term.get_software_version(timeout=0.01)
            assert sv is None
        finally:
            del os.environ['TERM_PROGRAM_VERSION']
        return b'ENV_VER_ONLY'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_software_version_env_fallback_version_only')
    assert output == '\x1b[>q\x1b[6nENV_VER_ONLY'


def test_get_software_version_no_env_no_response():
    """Test get_software_version() returns None with no XTVERSION and no env vars."""
    def child(term):
        sv = term.get_software_version(timeout=0.01)
        assert sv is None
        return b'NO_ENV'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_software_version_no_env_no_response')
    assert output == '\x1b[>q\x1b[6nNO_ENV'


def test_software_version_init():
    """Test SoftwareVersion.__init__() stores all parameters."""
    sv = SoftwareVersion('\x1bP>|kitty(0.24.2)\x1b\\', 'kitty', '0.24.2')
    assert sv.raw == '\x1bP>|kitty(0.24.2)\x1b\\'
    assert sv.name == 'kitty'
    assert sv.version == '0.24.2'


def test_xtversion_response_resolves_as_a_named_response():
    """A complete XTVERSION reply is a named response, not keys."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True)
    ks = resolve_sequence('\x1bP>|kitty(0.24.2)\x1b\\',
                          get_keyboard_sequences(term), get_keyboard_codes(),
                          term._keymap_prefixes)
    assert ks.name == 'XTVERSION_RESPONSE'
    assert str(ks) == '\x1bP>|kitty(0.24.2)\x1b\\'


def test_incomplete_xtversion_is_not_alt_shift_p():
    """A split reply holds for esc_delay rather than resolving as Alt+Shift+P."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True)
    keymap, codes = get_keyboard_sequences(term), get_keyboard_codes()
    assert resolve_sequence('\x1bP', keymap, codes, term._keymap_prefixes,
                            final=False).name == 'KEY_ESCAPE'
    assert resolve_sequence('\x1bP', keymap, codes, term._keymap_prefixes,
                            final=True).name == 'KEY_ALT_SHIFT_P'


def test_late_xtversion_response_is_not_a_keystroke():
    """A reply arriving after its query timed out is recorded, not applied."""
    def child(term):
        term._software_version_cache = None  # pylint: disable=protected-access
        term.term_program = True  # unknown, as after a timed-out query
        term.ungetch('\x1bP>|kitty(0.24.2)\x1b\\')
        term.ungetch('Z')

        ks = term.inkey(timeout=0.1)

        assert str(ks) == 'Z', repr(ks)
        assert term.term_program is True
        assert term._software_version_cache is None
        assert any('XTVERSION_RESPONSE' in err for err in term.errors), term.errors
        return b'LATE_XTV'

    output = pty_test(child, parent_func=None,
                      test_name='test_late_xtversion_response_is_not_a_keystroke')
    assert output == 'LATE_XTV'


def test_empty_term_program_still_queries(monkeypatch):
    """An empty TERM_PROGRAM is unset, so XTVERSION is queried for a name."""
    monkeypatch.setenv('TERM_PROGRAM', '')
    monkeypatch.delenv('TERM', raising=False)
    term = TestTerminal(force_styling=True)
    term._is_a_tty = True  # pylint: disable=protected-access
    term._keyboard_fd = 0  # pylint: disable=protected-access
    response = SoftwareVersion('\x1bP>|kitty(0.24.2)\x1b\\', 'kitty', '0.24.2')

    with mock.patch.object(Terminal, 'get_software_version', return_value=response) as query:
        assert term._Terminal__init_term_program() == 'kitty'

    assert query.called


@pytest.mark.parametrize('term', ['xterm-kitty', 'foot'])
def test_resolvable_term_skips_the_query(monkeypatch, term):
    """A TERM that names its terminal is left to wcwidth's own environment lookup."""
    monkeypatch.setenv('TERM_PROGRAM', '')
    monkeypatch.setenv('TERM', term)
    terminal = TestTerminal(force_styling=True)
    terminal._is_a_tty = True  # pylint: disable=protected-access
    terminal._keyboard_fd = 0  # pylint: disable=protected-access

    with mock.patch.object(Terminal, 'get_software_version') as query:
        assert terminal._Terminal__init_term_program() == ''

    assert not query.called


def test_claimed_term_still_queries(monkeypatch):
    """TERM=xterm resolves in wcwidth, but terminals claim it without being it."""
    monkeypatch.setenv('TERM_PROGRAM', '')
    monkeypatch.setenv('TERM', 'xterm')
    terminal = TestTerminal(force_styling=True)
    terminal._is_a_tty = True  # pylint: disable=protected-access
    terminal._keyboard_fd = 0  # pylint: disable=protected-access
    response = SoftwareVersion('\x1bP>|mlterm(3.9.4)\x1b\\', 'mlterm', '3.9.4')

    with mock.patch.object(Terminal, 'get_software_version', return_value=response) as query:
        assert terminal._Terminal__init_term_program() == 'mlterm'

    assert query.called


def test_generic_term_still_queries(monkeypatch):
    """A TERM that wcwidth does not resolve is named by XTVERSION instead."""
    monkeypatch.setenv('TERM_PROGRAM', '')
    monkeypatch.setenv('TERM', 'xterm-256color')
    terminal = TestTerminal(force_styling=True)
    terminal._is_a_tty = True  # pylint: disable=protected-access
    terminal._keyboard_fd = 0  # pylint: disable=protected-access
    response = SoftwareVersion('\x1bP>|foot(1.20.1)\x1b\\', 'foot', '1.20.1')

    with mock.patch.object(Terminal, 'get_software_version', return_value=response) as query:
        assert terminal._Terminal__init_term_program() == 'foot'

    assert query.called
