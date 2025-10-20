r"""Tests for SoftwareVersion class and Terminal.get_software_version().

XTVERSION Query Format
======================

The XTVERSION query (CSI > q or ESC [ > q) requests the terminal software
name and version. Supported by modern terminal emulators including xterm,
mintty, iTerm2, tmux, kitty, WezTerm, foot, and VTE-based terminals.

Terminal response: DCS > | text ST  (ESC P > | text ESC \)

Text format varies by terminal:
  - XTerm(367)
  - kitty(0.24.2)
  - tmux 3.2a
  - WezTerm 20220207-230252-0826fb06
  - X.Org 7.7.0(370)
"""
# std
import time
import re

# 3rd party
import pytest

# local
from .conftest import TEST_KEYBOARD, IS_WINDOWS
from .accessories import (
    TestTerminal,
    pty_test,
    as_subprocess,
)
from blessed.keyboard import SoftwareVersion

pytestmark = pytest.mark.skipif(
    not TEST_KEYBOARD or IS_WINDOWS,
    reason="Timing-sensitive tests please do not run on build farms.")


def test_software_version_from_string_parentheses_format():
    """Test SoftwareVersion.from_match() with parentheses format."""
    pattern = re.compile(r'\x1bP>\|(.+?)\x1b\\')
    match = pattern.match('\x1bP>|kitty(0.24.2)\x1b\\')
    sv = SoftwareVersion.from_match(match)
    assert sv is not None
    assert sv.name == 'kitty'
    assert sv.version == '0.24.2'
    assert sv.raw == '\x1bP>|kitty(0.24.2)\x1b\\'


def test_software_version_from_string_space_format():
    """Test SoftwareVersion.from_match() with space-separated format."""
    pattern = re.compile(r'\x1bP>\|(.+?)\x1b\\')
    match = pattern.match('\x1bP>|tmux 3.2a\x1b\\')
    sv = SoftwareVersion.from_match(match)
    assert sv is not None
    assert sv.name == 'tmux'
    assert sv.version == '3.2a'
    assert sv.raw == '\x1bP>|tmux 3.2a\x1b\\'


def test_software_version_from_string_name_only():
    """Test SoftwareVersion.from_match() with name-only format."""
    pattern = re.compile(r'\x1bP>\|(.+?)\x1b\\')
    match = pattern.match('\x1bP>|foot\x1b\\')
    sv = SoftwareVersion.from_match(match)
    assert sv is not None
    assert sv.name == 'foot'
    assert sv.version == ''
    assert sv.raw == '\x1bP>|foot\x1b\\'


def test_software_version_from_string_complex_version():
    """Test SoftwareVersion.from_match() with complex version string."""
    pattern = re.compile(r'\x1bP>\|(.+?)\x1b\\')
    match = pattern.match('\x1bP>|WezTerm 20220207-230252-0826fb06\x1b\\')
    sv = SoftwareVersion.from_match(match)
    assert sv is not None
    assert sv.name == 'WezTerm'
    assert sv.version == '20220207-230252-0826fb06'


def test_software_version_from_string_xterm_format():
    """Test SoftwareVersion.from_match() with XTerm format."""
    pattern = re.compile(r'\x1bP>\|(.+?)\x1b\\')
    match = pattern.match('\x1bP>|XTerm(367)\x1b\\')
    sv = SoftwareVersion.from_match(match)
    assert sv is not None
    assert sv.name == 'XTerm'
    assert sv.version == '367'


def test_software_version_from_string_xorg_format():
    """Test SoftwareVersion.from_match() with X.Org complex format."""
    pattern = re.compile(r'\x1bP>\|(.+?)\x1b\\')
    match = pattern.match('\x1bP>|X.Org 7.7.0(370)\x1b\\')
    sv = SoftwareVersion.from_match(match)
    assert sv is not None
    assert sv.name == 'X.Org'
    assert sv.version == '7.7.0(370)'


def test_software_version_from_string_invalid():
    """Test SoftwareVersion.from_match() with invalid input."""
    pattern = re.compile(r'\x1bP>\|(.+?)\x1b\\')
    match = pattern.match('invalid')
    assert match is None
    match = pattern.match('')
    assert match is None


def test_software_version_repr():
    """Test SoftwareVersion.__repr__()."""
    sv = SoftwareVersion('\x1bP>|kitty(0.24.2)\x1b\\', 'kitty', '0.24.2')
    repr_str = repr(sv)
    assert 'SoftwareVersion' in repr_str
    assert "name='kitty'" in repr_str
    assert "version='0.24.2'" in repr_str


def test_software_version_parse_text_parentheses():
    """Test SoftwareVersion._parse_text() with parentheses format."""
    name, version = SoftwareVersion._parse_text('kitty(0.24.2)')
    assert name == 'kitty'
    assert version == '0.24.2'


def test_software_version_parse_text_space():
    """Test SoftwareVersion._parse_text() with space-separated format."""
    name, version = SoftwareVersion._parse_text('tmux 3.2a')
    assert name == 'tmux'
    assert version == '3.2a'


def test_software_version_parse_text_name_only():
    """Test SoftwareVersion._parse_text() with name-only format."""
    name, version = SoftwareVersion._parse_text('foot')
    assert name == 'foot'
    assert version == ''


def test_software_version_parse_text_complex():
    """Test SoftwareVersion._parse_text() with complex version."""
    name, version = SoftwareVersion._parse_text('WezTerm 20220207-230252-0826fb06')
    assert name == 'WezTerm'
    assert version == '20220207-230252-0826fb06'


def test_get_software_version_via_ungetch_kitty():
    """Test get_software_version() with kitty response via ungetch."""
    def child(term):
        term.ungetch('\x1bP>|kitty(0.24.2)\x1b\\')
        sv = term.get_software_version(timeout=0.01)
        assert sv is not None
        assert sv.name == 'kitty'
        assert sv.version == '0.24.2'
        return b'OK'

    output = pty_test(child, parent_func=None, test_name='test_get_software_version_kitty')
    assert output == '\x1b[>qOK'


def test_get_software_version_via_ungetch_xterm():
    """Test get_software_version() with XTerm response via ungetch."""
    def child(term):
        term.ungetch('\x1bP>|XTerm(367)\x1b\\')
        sv = term.get_software_version(timeout=0.01)
        assert sv is not None
        assert sv.name == 'XTerm'
        assert sv.version == '367'
        return b'XTERM'

    output = pty_test(child, parent_func=None, test_name='test_get_software_version_xterm')
    assert output == '\x1b[>qXTERM'


def test_get_software_version_via_ungetch_tmux():
    """Test get_software_version() with tmux response via ungetch."""
    def child(term):
        term.ungetch('\x1bP>|tmux 3.2a\x1b\\')
        sv = term.get_software_version(timeout=0.01)
        assert sv is not None
        assert sv.name == 'tmux'
        assert sv.version == '3.2a'
        return b'TMUX'

    output = pty_test(child, parent_func=None, test_name='test_get_software_version_tmux')
    assert output == '\x1b[>qTMUX'


def test_get_software_version_via_ungetch_wezterm():
    """Test get_software_version() with WezTerm response via ungetch."""
    def child(term):
        term.ungetch('\x1bP>|WezTerm 20220207-230252-0826fb06\x1b\\')
        sv = term.get_software_version(timeout=0.01)
        assert sv is not None
        assert sv.name == 'WezTerm'
        assert sv.version == '20220207-230252-0826fb06'
        return b'WEZTERM'

    output = pty_test(child, parent_func=None, test_name='test_get_software_version_wezterm')
    assert output == '\x1b[>qWEZTERM'


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
    assert output == '\x1b[>qTIMEOUT'


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
    assert output == '\x1b[>q\x1b[>qFORCED'


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
    assert output == '\x1b[>qNO_FORCE'


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
    assert output == '\x1b[>q\x1b[>qRETRY'


def test_get_software_version_raw_stored():
    """Test SoftwareVersion stores raw response string."""
    raw = '\x1bP>|kitty(0.24.2)\x1b\\'
    pattern = re.compile(r'\x1bP>\|(.+?)\x1b\\')
    match = pattern.match(raw)
    sv = SoftwareVersion.from_match(match)
    assert sv is not None
    assert sv.raw == raw


def test_get_software_version_not_a_tty():
    """Test get_software_version() returns None when not a TTY."""
    @as_subprocess
    def child():
        import io
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = False

        sv = term.get_software_version(timeout=0.01)
        assert sv is None
    child()


def test_software_version_init():
    """Test SoftwareVersion.__init__() stores all parameters."""
    sv = SoftwareVersion('\x1bP>|kitty(0.24.2)\x1b\\', 'kitty', '0.24.2')
    assert sv.raw == '\x1bP>|kitty(0.24.2)\x1b\\'
    assert sv.name == 'kitty'
    assert sv.version == '0.24.2'


def test_software_version_from_match():
    """Test SoftwareVersion.from_match() method."""
    pattern = re.compile(r'\x1bP>\|(.+?)\x1b\\')
    match = pattern.match('\x1bP>|kitty(0.24.2)\x1b\\')

    sv = SoftwareVersion.from_match(match)
    assert sv is not None
    assert sv.name == 'kitty'
    assert sv.version == '0.24.2'


def test_software_version_from_match_space_format():
    """Test SoftwareVersion.from_match() with space-separated format."""
    pattern = re.compile(r'\x1bP>\|(.+?)\x1b\\')
    match = pattern.match('\x1bP>|tmux 3.2a\x1b\\')

    sv = SoftwareVersion.from_match(match)
    assert sv is not None
    assert sv.name == 'tmux'
    assert sv.version == '3.2a'
