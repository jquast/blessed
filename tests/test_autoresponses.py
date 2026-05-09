"""Tests for terminal auto-response detection methods."""
# std imports
import io

# 3rd party
import pytest

try:
    from unittest import mock
except ImportError:
    import mock

# local
from blessed._capabilities import Decrqss, ITerm2Capabilities, TextSizingResult
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
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        is_a_tty=False)
    result = getattr(term, method_name)(timeout=0.01)
    assert result == expected


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
    term = TestTerminal(stream=io.StringIO(), force_styling=False)
    result = getattr(term, method_name)(timeout=0.01)
    assert result == expected


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
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    setattr(term, cache_attr, cached_value)
    assert getattr(term, method_name)() is expected


def test_get_iterm2_capabilities_cached():
    """get_iterm2_capabilities returns cached result."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    cached = ITerm2Capabilities(supported=True, features={'truecolor': 2})
    term._iterm2_capabilities_cache = cached
    result = term.get_iterm2_capabilities()
    assert result is cached


def test_does_kitty_pointer_shapes_cached_supported():
    """does_kitty_pointer_shapes returns cached shape string."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._kitty_pointer_shapes_result = (True, 'beam')
    assert term.does_kitty_pointer_shapes() == 'beam'


def test_does_kitty_pointer_shapes_cached_unsupported():
    """does_kitty_pointer_shapes returns None when cached unsupported."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._kitty_pointer_shapes_result = (False, '')
    assert term.does_kitty_pointer_shapes() is None


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
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    cached = TextSizingResult(width=True, scale=True)
    term._text_sizing_cache = cached
    assert term.does_text_sizing() is cached


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


@pytest.mark.parametrize("terminator", ['\x07', '\x1b\\'])
def test_get_iterm2_capabilities_full(terminator):
    """get_iterm2_capabilities parses Capabilities response."""
    def child(term):
        term.ungetch('\x1b]1337;Capabilities=T2CwBF' + terminator + '\x1b[10;20R')
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


@pytest.mark.parametrize("terminator", ['\x07', '\x1b\\'])
def test_does_kitty_notifications_supported(terminator):
    """does_kitty_notifications returns True with OSC 99 response."""
    def child(term):
        term.ungetch('\x1b]99;i=blessed' + terminator + '\x1b[10;20R')
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
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._iterm2_capabilities_cache = ITerm2Capabilities(
        supported=cached_supported)
    assert getattr(term, method_name)() is cached_supported


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


@pytest.mark.parametrize("terminator", ['\x07', '\x1b\\'])
def test_does_kitty_pointer_shapes_supported(terminator):
    """does_kitty_pointer_shapes returns shape name with OSC 22 response."""
    def child(term):
        term.ungetch('\x1b]22;default' + terminator + '\x1b[10;20R')
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
    assert repr(TextSizingResult(width=True, scale=True)
                ) == "TextSizingResult(width=True, scale=True)"


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


def test_does_text_sizing_cleanup_side_effect():
    """does_text_sizing writes cleanup (backspace+space+backspace) to erase probes."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    with mock.patch.object(term, 'get_location', side_effect=[
        (5, 10),  # initial: col0=10
        (5, 12),  # after width probe: col1=12
        (5, 14),  # after scale probe: col2=14
    ]):
        result = term.does_text_sizing(timeout=0.1)
    assert result == TextSizingResult(width=True, scale=True)
    output = stream.getvalue()
    # cleanup: _movement=4 backspaces, 4 spaces, 4 backspaces
    assert '\b' * 4 + ' ' * 4 + '\b' * 4 in output


def test_does_text_sizing_no_cleanup_when_cached():
    """does_text_sizing does not write probes/cleanup when cached result exists."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._text_sizing_cache = TextSizingResult(width=True, scale=True)
    stream.truncate(0)
    stream.seek(0)
    result = term.does_text_sizing()
    assert result == TextSizingResult(width=True, scale=True)
    assert stream.getvalue() == ''


def _sizing_term(supported):
    term = TestTerminal(stream=io.StringIO(), force_styling=True)
    term._is_a_tty = True
    term._text_sizing_cache = (
        TextSizingResult(width=True, scale=True) if supported
        else TextSizingResult())
    return term


@pytest.mark.parametrize('supported,kwargs,expected,measured', [
    (False, {}, 'abc', len('abc')),
    (False, {'scale': 2}, 'abc', len('abc')),
    (True, {'scale': 2}, '\x1b]66;s=2;abc\x07', len('abc') * 2),
    (True, {}, '\x1b]66;;abc\x07', len('abc')),
    (True, {
        'scale': 2, 'width': 3, 'numerator': 1, 'denominator': 2,
        'vertical_align': 1, 'horizontal_align': 2},
     '\x1b]66;s=2:w=3:n=1:d=2:v=1:h=2;abc\x07', 6),
    (True, {'scale': 3}, '\x1b]66;s=3;abc\x07', len('abc') * 3),
    (True, {'scale': 4}, '\x1b]66;s=4;abc\x07', len('abc') * 4),
    (True, {'scale': 5}, '\x1b]66;s=5;abc\x07', len('abc') * 5),

])
def test_text_sized(supported, kwargs, expected, measured):
    """text_sized returns OSC 66-wrapped text when supported, as-is otherwise."""
    from wcwidth import width as wcwidth_width
    term = _sizing_term(supported)
    result = term.text_sized('abc', **kwargs)
    assert result == expected
    assert wcwidth_width(result) == measured


def test_text_sized_ValueError():
    """text_sized raises ValueError for text exceeding 4096 length limit."""
    term = _sizing_term(True)
    with pytest.raises(ValueError):
        term.text_sized('X' * 4097, scale=2)


# Decrqss tests (moved from test_xtgettcap.py)

def test_decrqss_not_a_tty():
    """Returns False when not a TTY."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        is_a_tty=False)
    assert term.does_decrqss(timeout=0.01) is False


def test_decrqss_cached_result():
    """Returns cached result without re-querying."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._decrqss_supported = True
    assert term.does_decrqss() is True


def test_decrqss_force_bypasses_cache():
    """force=True bypasses cached result."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True
    term._decrqss_supported = True
    result = term.does_decrqss(timeout=0.01, force=True)
    assert result is False


def test_get_decrqss_not_a_tty():
    """Returns None when not a TTY."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        is_a_tty=False)
    assert term.get_decrqss(timeout=0.01) is None


def test_get_decrqss_default_setting_is_sgr():
    """Default setting_id is SGR."""
    term = TestTerminal(stream=io.StringIO(), force_styling=True,
                        is_a_tty=False)
    assert Decrqss.SGR == 'm'
    assert term.get_decrqss() is None


@pytestmark
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


@pytestmark
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


@pytestmark
def test_does_decrqss_invalid():
    """DECRQSS returns False on DCS 0 $ r."""
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


@pytestmark
def test_get_decrqss_sgr():
    """get_decrqss returns SGR parameter value."""
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


@pytestmark
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


@pytestmark
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


@pytestmark
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


@pytestmark
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


@pytestmark
def test_get_decrqss_invalid():
    """get_decrqss returns None on DCS 0 $ r."""
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
