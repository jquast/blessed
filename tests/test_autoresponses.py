"""Tests for terminal auto-response detection methods."""
# std imports
import io

# 3rd party
import pytest

# local
from blessed._capabilities import ITerm2Capabilities
from .conftest import IS_WINDOWS
from .accessories import TestTerminal, as_subprocess, pty_test

pytestmark = pytest.mark.skipif(
    IS_WINDOWS, reason="ungetch and PTY testing not supported on Windows")


@pytest.mark.parametrize('method_name,expected', [
    ('does_kitty_graphics', False),
    ('does_iterm2', False),
    ('does_iterm2_graphics', False),
    ('does_kitty_notifications', False),
])
def test_detection_not_a_tty(method_name, expected):
    """Boolean detection methods return False when not a TTY."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        result = getattr(term, method_name)(timeout=0.01)
        assert result is expected
    child()


def test_get_iterm2_capabilities_not_a_tty():
    """get_iterm2_capabilities returns None when not a TTY."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        result = term.get_iterm2_capabilities(timeout=0.01)
        assert result is None
    child()


def test_does_kitty_graphics_no_styling():
    """does_kitty_graphics returns False when does_styling is False."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=False)
        result = term.does_kitty_graphics(timeout=0.01)
        assert result is False
    child()


def test_get_iterm2_capabilities_no_styling():
    """get_iterm2_capabilities returns None when does_styling is False."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=False)
        result = term.get_iterm2_capabilities(timeout=0.01)
        assert result is None
    child()


def test_does_kitty_graphics_cached_true():
    """does_kitty_graphics returns cached True."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._kitty_graphics_supported = True
        assert term.does_kitty_graphics() is True
    child()


def test_does_kitty_graphics_cached_false():
    """does_kitty_graphics returns cached False."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._kitty_graphics_supported = False
        assert term.does_kitty_graphics() is False
    child()


def test_get_iterm2_capabilities_cached():
    """get_iterm2_capabilities returns cached result."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        cached = ITerm2Capabilities(supported=True, features={'truecolor': 2})
        term._iterm2_capabilities_cache = cached
        result = term.get_iterm2_capabilities()
        assert result is cached
    child()


def test_does_kitty_notifications_cached_true():
    """does_kitty_notifications returns cached True."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._kitty_notifications_supported = True
        assert term.does_kitty_notifications() is True
    child()


def test_does_kitty_notifications_cached_false():
    """does_kitty_notifications returns cached False."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._kitty_notifications_supported = False
        assert term.does_kitty_notifications() is False
    child()


def test_does_kitty_graphics_force_bypass():
    """force=True bypasses kitty graphics cache."""
    def child(term):
        term._kitty_graphics_supported = True
        result = term.does_kitty_graphics(timeout=0.01, force=True)
        assert result is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_graphics_force_bypass')
    assert 'OK' in output


def test_get_iterm2_capabilities_force_bypass():
    """force=True bypasses iterm2 capabilities cache."""
    def child(term):
        cached = ITerm2Capabilities(supported=True, features={'truecolor': 2})
        term._iterm2_capabilities_cache = cached
        result = term.get_iterm2_capabilities(timeout=0.01, force=True)
        assert result is not cached
        assert result.supported is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_iterm2_capabilities_force_bypass')
    assert 'OK' in output


def test_does_kitty_notifications_force_bypass():
    """force=True bypasses kitty notifications cache."""
    def child(term):
        term._kitty_notifications_supported = True
        result = term.does_kitty_notifications(timeout=0.01, force=True)
        assert result is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_notifications_force_bypass')
    assert 'OK' in output


def test_does_kitty_graphics_supported():
    """does_kitty_graphics returns True with OK response."""
    def child(term):
        term.ungetch('\x1b_Gi=31;OK\x1b\\\x1b[10;20R')
        result = term.does_kitty_graphics(timeout=0.01)
        assert result is True
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_graphics_supported')
    assert 'OK' in output


def test_does_kitty_graphics_error_response():
    """does_kitty_graphics returns False with error response."""
    def child(term):
        term.ungetch('\x1b_Gi=31;ENOENT\x1b\\\x1b[10;20R')
        result = term.does_kitty_graphics(timeout=0.01)
        assert result is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_graphics_error_response')
    assert 'OK' in output


def test_does_kitty_graphics_timeout():
    """does_kitty_graphics returns False on timeout."""
    def child(term):
        result = term.does_kitty_graphics(timeout=0.01)
        assert result is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_graphics_timeout')
    assert 'OK' in output


def test_get_iterm2_capabilities_full():
    """get_iterm2_capabilities parses Capabilities response."""
    def child(term):
        term.ungetch('\x1b]1337;Capabilities=T2CwBF\x07\x1b[10;20R')
        result = term.get_iterm2_capabilities(timeout=0.01)
        assert result is not None
        assert result.supported is True
        assert result.features['truecolor'] == 2
        assert result.features['clipboard_writable'] is True
        assert result.features['bracketed_paste'] is True
        assert result.features['focus_reporting'] is True
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_iterm2_capabilities_full')
    assert 'OK' in output


def test_get_iterm2_capabilities_timeout():
    """get_iterm2_capabilities returns unsupported on timeout."""
    def child(term):
        result = term.get_iterm2_capabilities(timeout=0.01)
        assert result is not None
        assert result.supported is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_iterm2_capabilities_timeout')
    assert 'OK' in output


def test_does_kitty_notifications_supported():
    """does_kitty_notifications returns True with OSC 99 response."""
    def child(term):
        term.ungetch('\x1b]99;i=blessed\x1b\\\x1b[10;20R')
        result = term.does_kitty_notifications(timeout=0.01)
        assert result is True
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_notifications_supported')
    assert 'OK' in output


def test_does_kitty_notifications_timeout():
    """does_kitty_notifications returns False on timeout."""
    def child(term):
        result = term.does_kitty_notifications(timeout=0.01)
        assert result is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_notifications_timeout')
    assert 'OK' in output


def test_does_iterm2_with_cached_supported():
    """does_iterm2 returns True with cached supported result."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._iterm2_capabilities_cache = ITerm2Capabilities(supported=True)
        assert term.does_iterm2() is True
    child()


def test_does_iterm2_with_cached_unsupported():
    """does_iterm2 returns False with cached unsupported result."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._iterm2_capabilities_cache = ITerm2Capabilities(supported=False)
        assert term.does_iterm2() is False
    child()


def test_does_iterm2_graphics_delegates():
    """does_iterm2_graphics delegates to does_iterm2."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._iterm2_capabilities_cache = ITerm2Capabilities(supported=True)
        assert term.does_iterm2_graphics() is True
    child()


def test_does_iterm2_graphics_delegates_false():
    """does_iterm2_graphics returns False when iterm2 unsupported."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._iterm2_capabilities_cache = ITerm2Capabilities(supported=False)
        assert term.does_iterm2_graphics() is False
    child()


def test_query_with_boundary_feature_supported():
    """_query_with_boundary returns feature match when feature responds."""
    import re

    def child(term):
        feature_re = re.compile(r'\x1b_Gi=31;(.+?)\x1b\\')
        term.ungetch('\x1b_Gi=31;OK\x1b\\\x1b[10;20R')
        match = term._query_with_boundary(
            '\x1b_Gi=31,s=1,v=1,a=q,t=d,f=24;AAAA\x1b\\',
            feature_re, timeout=0.5)
        assert match is not None
        assert match.group(1) == 'OK'
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_query_with_boundary_feature_supported')
    assert 'OK' in output


def test_query_with_boundary_fast_negative():
    """_query_with_boundary returns None when only CPR responds."""
    import re

    def child(term):
        feature_re = re.compile(r'\x1b_Gi=31;(.+?)\x1b\\')
        term.ungetch('\x1b[10;20R')
        match = term._query_with_boundary(
            '\x1b_Gi=31,s=1,v=1,a=q,t=d,f=24;AAAA\x1b\\',
            feature_re, timeout=0.5)
        assert match is None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_query_with_boundary_fast_negative')
    assert 'OK' in output


def test_query_with_boundary_timeout():
    """_query_with_boundary returns None on timeout."""
    import re

    def child(term):
        feature_re = re.compile(r'\x1b_Gi=31;(.+?)\x1b\\')
        match = term._query_with_boundary(
            '\x1b_Gi=31,s=1,v=1,a=q,t=d,f=24;AAAA\x1b\\',
            feature_re, timeout=0.01)
        assert match is None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_query_with_boundary_timeout')
    assert 'OK' in output
