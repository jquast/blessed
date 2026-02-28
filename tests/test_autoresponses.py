"""Tests for terminal auto-response detection methods."""
# std imports
import io

# 3rd party
import pytest

# local
from blessed._capabilities import ITerm2Capabilities, TextSizingResult
from .conftest import IS_WINDOWS
from .accessories import TestTerminal, as_subprocess, pty_test

pytestmark = pytest.mark.skipif(
    IS_WINDOWS, reason="ungetch and PTY testing not supported on Windows")


@pytest.mark.parametrize('method_name,expected', [
    ('does_kitty_graphics', False),
    ('does_iterm2', False),
    ('does_iterm2_graphics', False),
    ('does_kitty_notifications', False),
    ('does_kitty_clipboard', False),
    ('does_kitty_pointer_shapes', None),
    ('get_iterm2_capabilities', None),
    ('does_text_sizing', TextSizingResult()),
])
def test_detection_not_a_tty(method_name, expected):
    """Detection methods return falsy default when not a TTY."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        result = getattr(term, method_name)(timeout=0.01)
        assert result == expected
    child()


@pytest.mark.parametrize('method_name,expected', [
    ('does_kitty_graphics', False),
    ('does_kitty_notifications', False),
    ('does_kitty_clipboard', False),
    ('does_kitty_pointer_shapes', None),
    ('get_iterm2_capabilities', None),
    ('does_text_sizing', TextSizingResult()),
])
def test_detection_no_styling(method_name, expected):
    """Detection methods return falsy default when does_styling is False."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=False)
        result = getattr(term, method_name)(timeout=0.01)
        assert result == expected
    child()


@pytest.mark.parametrize('method_name,cache_attr,cached_value,expected', [
    ('does_kitty_graphics', '_kitty_graphics_supported', True, True),
    ('does_kitty_graphics', '_kitty_graphics_supported', False, False),
    ('does_kitty_notifications', '_kitty_notifications_supported', True, True),
    ('does_kitty_notifications', '_kitty_notifications_supported', False, False),
    ('does_kitty_clipboard', '_kitty_clipboard_supported', True, True),
    ('does_kitty_clipboard', '_kitty_clipboard_supported', False, False),
])
def test_detection_cached_bool(method_name, cache_attr, cached_value, expected):
    """Boolean detection methods return cached value."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        setattr(term, cache_attr, cached_value)
        assert getattr(term, method_name)() is expected
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


def test_does_kitty_pointer_shapes_cached_supported():
    """does_kitty_pointer_shapes returns cached shape string."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._kitty_pointer_shapes_result = (True, 'beam')
        assert term.does_kitty_pointer_shapes() == 'beam'
    child()


def test_does_kitty_pointer_shapes_cached_unsupported():
    """does_kitty_pointer_shapes returns None when cached unsupported."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._kitty_pointer_shapes_result = (False, '')
        assert term.does_kitty_pointer_shapes() is None
    child()


@pytest.mark.parametrize('method_name,cache_attr,cached_value', [
    ('does_kitty_graphics', '_kitty_graphics_supported', True),
    ('does_kitty_notifications', '_kitty_notifications_supported', True),
    ('does_kitty_clipboard', '_kitty_clipboard_supported', True),
])
def test_detection_force_bypass(method_name, cache_attr, cached_value):
    """force=True bypasses detection cache."""
    def child(term):
        setattr(term, cache_attr, cached_value)
        result = getattr(term, method_name)(timeout=0.01, force=True)
        assert result is False
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name=f'test_detection_force_bypass_{method_name}')
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


def test_does_text_sizing_cached():
    """does_text_sizing returns cached result."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        cached = TextSizingResult(width=True, scale=True)
        term._text_sizing_cache = cached
        assert term.does_text_sizing() is cached
    child()


def test_does_text_sizing_force_bypass():
    """force=True bypasses text sizing cache."""
    def child(term):
        cached = TextSizingResult(width=True, scale=True)
        term._text_sizing_cache = cached
        result = term.does_text_sizing(timeout=0.01, force=True)
        assert result is not cached
        assert not result
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_text_sizing_force_bypass')
    assert 'OK' in output


def test_does_kitty_pointer_shapes_force_bypass():
    """force=True bypasses kitty pointer shapes cache."""
    def child(term):
        term._kitty_pointer_shapes_result = (True, 'beam')
        result = term.does_kitty_pointer_shapes(timeout=0.01, force=True)
        assert result is None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_pointer_shapes_force_bypass')
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


@pytest.mark.parametrize('method_name,expected', [
    ('does_kitty_graphics', False),
    ('does_kitty_notifications', False),
    ('does_kitty_clipboard', False),
    ('does_kitty_pointer_shapes', None),
])
def test_detection_timeout(method_name, expected):
    """Detection methods return falsy default on timeout."""
    def child(term):
        result = getattr(term, method_name)(timeout=0.01)
        assert result == expected
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name=f'test_detection_timeout_{method_name}')
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


@pytest.mark.parametrize('method_name,cached_supported', [
    ('does_iterm2', True),
    ('does_iterm2', False),
    ('does_iterm2_graphics', True),
    ('does_iterm2_graphics', False),
])
def test_does_iterm2_delegates_cached(method_name, cached_supported):
    """does_iterm2 and does_iterm2_graphics return cached result."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        term._iterm2_capabilities_cache = ITerm2Capabilities(
            supported=cached_supported)
        assert getattr(term, method_name)() is cached_supported
    child()


@pytest.mark.parametrize('ps,expected', [
    (1, True),
    (2, True),
    (3, True),
    (0, False),
    (4, False),
])
def test_does_kitty_clipboard_decrqm_values(ps, expected):
    """does_kitty_clipboard interprets DECRQM response values."""
    def child(term):
        term.ungetch(f'\x1b[?5522;{ps}$y\x1b[10;20R')
        result = term.does_kitty_clipboard(timeout=0.01)
        assert result is expected
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name=f'test_does_kitty_clipboard_decrqm_{ps}')
    assert 'OK' in output


def test_does_kitty_pointer_shapes_supported():
    """does_kitty_pointer_shapes returns shape name with OSC 22 response."""
    def child(term):
        term.ungetch('\x1b]22;default\x07\x1b[10;20R')
        result = term.does_kitty_pointer_shapes(timeout=0.01)
        assert result == 'default'
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_kitty_pointer_shapes_supported')
    assert 'OK' in output


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


def test_query_with_boundary_requires_styling():
    """_query_with_boundary returns None when requires_styling and not styling."""
    import re

    def child(term):
        feature_re = re.compile(r'\x1b_Gi=31;(.+?)\x1b\\')
        term._does_styling = False
        match = term._query_with_boundary(
            '\x1b_Gi=31,s=1,v=1,a=q,t=d,f=24;AAAA\x1b\\',
            feature_re, timeout=0.5, requires_styling=True)
        assert match is None
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_query_with_boundary_requires_styling')
    assert 'OK' in output


def test_text_sizing_result_eq_non_text_sizing():
    """TextSizingResult.__eq__ returns NotImplemented for other types."""
    result = TextSizingResult(width=True, scale=False)
    assert result != (True, False)
    assert result != "TextSizingResult(width=True, scale=False)"


def test_text_sizing_result_repr():
    """TextSizingResult.__repr__ includes width and scale."""
    assert repr(TextSizingResult()) == "TextSizingResult(width=False, scale=False)"
    assert repr(TextSizingResult(width=True, scale=True)) == "TextSizingResult(width=True, scale=True)"


def test_does_text_sizing_both_supported():
    """does_text_sizing returns (True, True) when both width and scale detected."""
    def child(term):
        term.ungetch('\x1b[1;11R\x1b[1;13R\x1b[1;15R')
        result = term.does_text_sizing(timeout=0.1)
        assert result == TextSizingResult(width=True, scale=True)
        assert result
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_text_sizing_both_supported')
    assert 'OK' in output


def test_does_text_sizing_width_only():
    """does_text_sizing returns (True, False) when only width detected."""
    def child(term):
        term.ungetch('\x1b[1;11R\x1b[1;13R\x1b[1;14R')
        result = term.does_text_sizing(timeout=0.1)
        assert result == TextSizingResult(width=True, scale=False)
        assert result
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_text_sizing_width_only')
    assert 'OK' in output


def test_does_text_sizing_neither_supported():
    """does_text_sizing returns falsy result when no sizing detected."""
    def child(term):
        term.ungetch('\x1b[1;11R\x1b[1;11R\x1b[1;11R')
        result = term.does_text_sizing(timeout=0.1)
        assert result == TextSizingResult()
        assert not result
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_text_sizing_neither_supported')
    assert 'OK' in output


def test_does_text_sizing_initial_location_timeout():
    """does_text_sizing returns falsy result when first get_location times out."""
    def child(term):
        result = term.does_text_sizing(timeout=0.01)
        assert result == TextSizingResult()
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_text_sizing_initial_location_timeout')
    assert 'OK' in output


def test_does_text_sizing_width_location_timeout():
    """does_text_sizing returns falsy result when second get_location times out."""
    def child(term):
        term.ungetch('\x1b[1;11R')
        result = term.does_text_sizing(timeout=0.01)
        assert result == TextSizingResult()
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_text_sizing_width_location_timeout')
    assert 'OK' in output


def test_does_text_sizing_scale_location_timeout():
    """does_text_sizing returns falsy result when third get_location times out."""
    def child(term):
        term.ungetch('\x1b[1;11R\x1b[1;13R')
        result = term.does_text_sizing(timeout=0.01)
        assert result == TextSizingResult()
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_does_text_sizing_scale_location_timeout')
    assert 'OK' in output
