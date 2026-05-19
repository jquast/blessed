"""Core blessed Terminal() tests."""

# std imports
import base64
import io
import os
import sys
import math
import time
import platform
import warnings
import importlib
from io import StringIO
from unittest import mock

# 3rd party
import jinxed
import pytest

# local
from .conftest import IS_WINDOWS
from .accessories import TestTerminal, unicode_cap, pty_test, NO_XTGETTCAP_DATA, as_subprocess
from blessed._capabilities import TermcapResponse


def test_export_only_Terminal():
    "Ensure only expected names are exported for import * statements."

    import blessed
    assert blessed.__all__ == ('Terminal', 'LineEditor', 'LineHistory')


def test_null_location(any_term):
    """Make sure ``location()`` with no args just does position restoration."""
    def child(kind):
        t = TestTerminal(kind=kind, stream=StringIO(), force_styling=True)
        with t.location():
            pass
        expected_output = ''.join(
            (unicode_cap('sc', t), unicode_cap('rc', t)))
        assert t.stream.getvalue() == expected_output

    child(any_term)


def test_location_to_move_xy(any_term):
    """``location()`` and ``move_xy()`` receive complimentary arguments."""
    def child(kind):
        buf = StringIO()
        t = TestTerminal(stream=buf, force_styling=True)
        x, y = 12, 34
        with t.location(x, y):
            xy_val_from_move_xy = t.move_xy(x, y)
            xy_val_from_location = buf.getvalue()[len(t.sc):]
            assert xy_val_from_move_xy == xy_val_from_location

    child(any_term)


def test_yield_keypad():
    """Ensure ``keypad()`` writes keyboard_xmit and keyboard_local."""
    def child(kind):

        t = TestTerminal(stream=StringIO(), force_styling=True)
        expected_output = ''.join((t.smkx, t.rmkx))

        with t.keypad():
            pass

        assert t.stream.getvalue() == expected_output

    child(kind='xterm')


def test_null_fileno():
    """Make sure ``Terminal`` works when ``fileno`` is ``None``."""
    def child():

        out = StringIO()
        out.fileno = None
        t = TestTerminal(stream=out)
        assert t.save == ''

    child()


@pytest.mark.skipif(IS_WINDOWS, reason="requires more than 1 tty")
def test_number_of_colors_without_tty():
    """``number_of_colors`` should return 0 when there's no tty."""
    if 'COLORTERM' in os.environ:
        del os.environ['COLORTERM']

    def child_256_nostyle():
        t = TestTerminal(stream=StringIO(), _xtgettcap_data=TermcapResponse(supported=False))
        assert t.number_of_colors == 0

    def child_256_forcestyle():
        t = TestTerminal(stream=StringIO(), force_styling=True,
                         _xtgettcap_data=TermcapResponse(supported=False))
        assert t.number_of_colors == 256

    def child_8_forcestyle():
        # 'ansi' on freebsd returns 0 colors. We use 'cons25', compatible with its kernel tty.c
        kind = 'cons25' if platform.system().lower() == 'freebsd' else 'ansi'
        t = TestTerminal(kind=kind, stream=StringIO(),
                         force_styling=True,
                         _xtgettcap_data=TermcapResponse(supported=False))
        assert t.number_of_colors == 8

    def child_0_forcestyle():
        t = TestTerminal(kind='vt220', stream=StringIO(), force_styling=True,
                         _xtgettcap_data=TermcapResponse(supported=False))
        assert t.number_of_colors == 0

    child_0_forcestyle()
    child_8_forcestyle()
    child_256_forcestyle()
    child_256_nostyle()


def test_multiple_terminal_kinds():
    """Multiple Terminal instances with different kinds retain correct capabilities."""
    term_a = TestTerminal(kind='xterm-256color', force_styling=True,
                          _xtgettcap_data=TermcapResponse(supported=False))
    colors_a = term_a.number_of_colors
    assert colors_a == 256

    term_b = TestTerminal(kind='vt220', force_styling=True,
                          _xtgettcap_data=TermcapResponse(supported=False))
    colors_b = term_b.number_of_colors
    assert colors_b == 0

    assert term_a.number_of_colors == 256
    assert term_b.number_of_colors == 0


@pytest.mark.parametrize('colorterm_value', ['truecolor', '24bit'])
def test_number_of_colors_colorterm(colorterm_value):
    """COLORTERM=truecolor|24bit yields 1<<24 colors."""
    os.environ['COLORTERM'] = colorterm_value
    try:
        t = TestTerminal(force_styling=True,
                         _xtgettcap_data=TermcapResponse(supported=False))
        assert t.number_of_colors == 1 << 24
    finally:
        del os.environ['COLORTERM']


def test_number_of_colors_bad_rgb_value():
    """Bad RGB value (non-numeric) is handled gracefully."""
    t = TestTerminal(kind='xterm-256color', force_styling=True, stream=StringIO(),
                     _xtgettcap_data=TermcapResponse(
                         supported=True,
                         capabilities={'RGB': 'not_a_number'}))
    assert t.number_of_colors == 256


@pytest.mark.skipif(IS_WINDOWS, reason="requires more than 1 tty")
def test_number_of_colors_with_tty():
    """test ``number_of_colors`` 0, 8, and 256."""
    def child_256():
        t = TestTerminal(force_styling=True, _xtgettcap_data=NO_XTGETTCAP_DATA)
        assert t.number_of_colors == 256

    def child_8():
        kind = 'cons25' if platform.system().lower() == 'freebsd' else 'ansi'
        t = TestTerminal(kind=kind, force_styling=True, _xtgettcap_data=NO_XTGETTCAP_DATA)
        assert t.number_of_colors == 8

    def child_0():
        t = TestTerminal(kind='vt220', force_styling=True, _xtgettcap_data=NO_XTGETTCAP_DATA)
        assert t.number_of_colors == 0

    child_0()
    child_8()
    child_256()


def test_init_descriptor_always_initted(any_term):
    """Test height and width with non-tty Terminals."""
    def child(kind):
        t = TestTerminal(kind=kind, stream=StringIO())
        assert t._init_descriptor == sys.__stdout__.fileno()
        assert isinstance(t.height, int)
        assert isinstance(t.width, int)
        assert t.height == t._height_and_width()[0]
        assert t.width == t._height_and_width()[1]

    child(any_term)


def test_force_styling_none(any_term):
    """If ``force_styling=None`` is used, don't ever do styling."""
    def child(kind):
        t = TestTerminal(force_styling=None)
        assert not t.does_styling

    child(any_term)


def test_force_styling_none_but_FORCE_COLOR(any_term):
    """``force_styling=None``, but FORCE_COLOR or CLICOLOR_FORCE is non-empty, does styling."""
    def child(envkey):
        os.environ[envkey] = '1'
        t = TestTerminal(force_styling=None)
        assert t.does_styling
        del os.environ[envkey]

    child('FORCE_COLOR')
    child('CLICOLOR_FORCE')


def test_force_styling_none_and_unset_FORCE_COLOR(any_term):
    """
    ``force_styling=None``, but FORCE_COLOR/CLICOLOR_FORCE is set, but empty, do not style.
    """
    def child(envkey):
        os.environ[envkey] = ''
        t = TestTerminal(force_styling=None)
        assert not t.does_styling
        del os.environ[envkey]

    child('FORCE_COLOR')
    child('CLICOLOR_FORCE')


def test_force_styling_False_but_FORCE_COLOR():
    """``force_styling=False``, but FORCE_COLOR or CLICOLOR_FORCE is non-empty, do styling."""
    def child(envkey):
        os.environ[envkey] = '1'
        t = TestTerminal(force_styling=False)
        assert t.does_styling
        del os.environ[envkey]

    child('FORCE_COLOR')
    child('CLICOLOR_FORCE')


def test_force_styling_True_but_NO_COLOR():
    """``force_styling=True``, but NO_COLOR is non-empty, do not style."""
    def child(envkey):
        os.environ[envkey] = '1'
        t = TestTerminal(force_styling=True)
        assert not t.does_styling
        del os.environ[envkey]

    child('NO_COLOR')


def test_setupterm_singleton_issue_33():
    """Multiple Terminal instances with different kinds are supported."""
    def child():
        warnings.filterwarnings("error", category=UserWarning)

        term = TestTerminal(force_styling=True)
        next_kind = 'xterm'

        term = TestTerminal(kind=next_kind, force_styling=True)
        assert term.kind == next_kind

    child()


def test_kind_resolution_kind_preferred():
    """kind= takes priority over TN, TERM, and kind_fallback."""
    term = TestTerminal(kind='vt220', force_styling=True)
    assert term.kind == 'vt220'


def test_kind_resolution_tn_via_xtgettcap():
    """TN from XTGETTCAP used when kind is not specified."""
    _xtgettcap_data = TermcapResponse(
        supported=True, capabilities={'TN': 'ansi'})
    term = TestTerminal(kind=None, force_styling=True,
                        _xtgettcap_data=_xtgettcap_data)
    assert term.kind == 'ansi'


def test_kind_resolution_term_kind():
    """kind_fallback used when kind is invalid and TERM is unset (xtgettcap path)."""
    assert 'TERM' not in os.environ, (
        'TERM is expected unset, check: tox.ini and conftest.py:pytest_configure')
    term = TestTerminal(kind='unknown', force_styling=True, _xtgettcap_data=None)
    if IS_WINDOWS:
        assert term.kind == 'vtwin10'
    else:
        assert term.kind == 'xterm-256color'


def test_kind_resolution_kind_fallback():
    """kind_fallback used when kind is invalid and TERM is unset."""
    assert 'TERM' not in os.environ, (
        'TERM is expected unset, check: tox.ini and conftest.py:pytest_configure')
    term = TestTerminal(kind='unknown', force_styling=True)
    if IS_WINDOWS:
        assert term.kind == 'vtwin10'
    else:
        assert term.kind == 'xterm-256color'


def test_kind_resolution_all_fail():
    """jinxed.error raised when kind, TERM, and kind_fallback all fail."""
    assert 'TERM' not in os.environ, (
        'TERM is expected unset, check: tox.ini and conftest.py:pytest_configure')
    with pytest.raises(jinxed.error, match='xxBadFallbackXx'):
        TestTerminal(
            kind='xxUnknownXx', force_styling=True,
            kind_fallback='xxBadFallbackXx',
            _xtgettcap_data=TermcapResponse(supported=False))


def test_IOUnsupportedOperation():
    """Ensure stream that throws IOUnsupportedOperation results in non-tty."""
    def child():

        def side_effect():
            raise io.UnsupportedOperation

        mock_stream = mock.Mock()
        mock_stream.fileno = side_effect

        term = TestTerminal(stream=mock_stream)
        assert term.stream == mock_stream
        assert not term.does_styling
        assert not term.is_a_tty
        assert term.number_of_colors == 0

    child()


def test_stream_no_fileno():
    """Handle custom stream objects gracefully"""
    def child():
        stream = object()
        term = TestTerminal(stream=stream)
        assert term._stream is stream
        assert 'stream has no fileno method' in term.errors
        assert 'Output stream is not a default stream' in term.errors
        assert term._init_descriptor is sys.__stdout__.fileno()
        assert term._keyboard_fd is None
        assert term.is_a_tty is False

    child()


@pytest.mark.skipif(IS_WINDOWS, reason="has process-wide side-effects")
def test_winsize_IOError_returns_environ():
    """When _winsize raises IOError, defaults from os.environ given."""
    def child():
        def side_effect(fd):
            raise OSError

        term = TestTerminal()
        term._winsize = side_effect
        save_cols = os.environ.get('COLUMNS')
        save_lines = os.environ.get('LINES')
        try:
            os.environ['COLUMNS'] = '1984'
            os.environ['LINES'] = '1888'
            assert term._height_and_width() == (1888, 1984, None, None)
        finally:
            if save_cols is not None:
                os.environ['COLUMNS'] = save_cols
            else:
                del os.environ['COLUMNS']
            if save_lines is not None:
                os.environ['LINES'] = save_lines
            else:
                del os.environ['LINES']

    child()


def test_yield_fullscreen(any_term):
    """Ensure ``fullscreen()`` writes enter_fullscreen and exit_fullscreen."""
    def child(kind):
        t = TestTerminal(stream=StringIO(), force_styling=True)
        t.enter_fullscreen = 'BEGIN'
        t.exit_fullscreen = 'END'
        with t.fullscreen():
            pass
        expected_output = ''.join((t.enter_fullscreen, t.exit_fullscreen))
        assert t.stream.getvalue() == expected_output

    child(any_term)


def test_yield_hidden_cursor(any_term):
    """Ensure ``hidden_cursor()`` writes hide_cursor and normal_cursor."""
    def child(kind):
        t = TestTerminal(stream=StringIO(), force_styling=True)
        t.hide_cursor = 'BEGIN'
        t.normal_cursor = 'END'
        with t.hidden_cursor():
            pass
        expected_output = ''.join((t.hide_cursor, t.normal_cursor))
        assert t.stream.getvalue() == expected_output

    child(any_term)


@pytest.mark.skipif(IS_WINDOWS, reason="windows lacks disable_line_wrap capability")
# see https://github.com/Rockhopper-Technologies/jinxed/blob/main/jinxed/terminfo/vtwin10.py
# "Removed - These do not appear to be supported" for rmam + smam
def test_yield_no_line_wrap():
    """Ensure ``no_line_wrap()`` writes disable and enable VT100 line wrap sequence."""
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.no_line_wrap():
            pass
        result = t.stream.getvalue()
        assert t.disable_line_wrap and t.enable_line_wrap
        assert result == t.disable_line_wrap + t.enable_line_wrap
        assert result == t.rmam + t.smam
        assert result == '\x1b[?7l' + '\x1b[?7h'

    child()


@pytest.mark.skipif(IS_WINDOWS, reason="windows doesn't work like this")
def test_no_preferredencoding_fallback():
    """Ensure empty preferredencoding value defaults to ascii."""
    def child():
        with mock.patch('locale.getpreferredencoding') as get_enc:
            get_enc.return_value = ''
            t = TestTerminal(force_styling=True)
            assert t._encoding == 'UTF-8'

    child()


@pytest.mark.skipif(IS_WINDOWS, reason="requires fcntl")
def test_unknown_preferredencoding_warned_and_fallback():
    """Ensure a locale without a codec emits a warning."""
    @as_subprocess
    def child():
        with mock.patch('locale.getpreferredencoding') as get_enc:
            get_enc.return_value = 'unknown'
            with pytest.warns(UserWarning, match=(
                    'LookupError: unknown encoding: unknown, '
                    'defaulting to UTF-8 for keyboard.')):
                t = TestTerminal(force_styling=True)
                assert t._encoding == 'UTF-8'

    child()


@pytest.mark.skipif(IS_WINDOWS, reason="requires fcntl")
def test_win32_missing_tty_modules(monkeypatch):
    """Ensure dummy exception is used when io is without UnsupportedOperation."""
    def child():
        OLD_STYLE = False
        try:
            original_import = getattr(__builtins__, '__import__')
            OLD_STYLE = True
        except AttributeError:
            original_import = __builtins__['__import__']

        tty_modules = ('termios', 'fcntl', 'tty')

        def __import__(name, *args, **kwargs):  # pylint: disable=redefined-builtin
            if name in tty_modules:
                raise ImportError
            return original_import(name, *args, **kwargs)

        for module in tty_modules:
            sys.modules.pop(module, None)

        warnings.filterwarnings("error", category=UserWarning)
        try:
            if OLD_STYLE:
                __builtins__.__import__ = __import__
            else:
                __builtins__['__import__'] = __import__
            try:

                import blessed.terminal
                importlib.reload(blessed.terminal)
            except UserWarning as err:
                assert err.args[0] == blessed.terminal._MSG_NOSUPPORT

            warnings.filterwarnings("ignore", category=UserWarning)

            import blessed.terminal
            importlib.reload(blessed.terminal)
            assert not blessed.terminal.HAS_TTY
            term = blessed.terminal.Terminal('ansi')

            assert term.height == 25
            assert term.width == 80

        finally:
            if OLD_STYLE:
                setattr(__builtins__, '__import__', original_import)
            else:
                __builtins__['__import__'] = original_import
            warnings.resetwarnings()

            import blessed.terminal
            importlib.reload(blessed.terminal)

    child()


def test_time_left():
    """test '_time_left' routine returns correct positive delta difference."""

    from blessed.keyboard import _time_left

    stime = time.time() - 10

    timeout = 15
    result = _time_left(stime=stime, timeout=timeout)

    assert math.ceil(result) == 5.0


def test_time_left_infinite_None():
    """keyboard '_time_left' routine returns None when given None."""

    from blessed.keyboard import _time_left
    assert _time_left(stime=time.time(), timeout=None) is None


def test_termcap_repr():
    """Ensure Termcap repr includes escaped pattern string."""

    given_ttype = 'vt220'
    given_capname = 'cursor_up'
    expected = r"<Termcap cursor_up:'\x1b\\[A'>"

    def child():
        term = TestTerminal(kind=given_ttype, force_styling=True)
        given = repr(term.caps[given_capname])
        assert given == expected

    child()


@pytest.mark.parametrize("force_styling,is_a_tty", [
    (False, True),
    (True, False),
])
def test_query_methods_respect_does_styling_and_is_a_tty(force_styling, is_a_tty):
    """Test that all query methods respect does_styling and is_a_tty guardrails."""
    def child():
        stream = StringIO()
        term = TestTerminal(stream=stream, force_styling=force_styling)
        if not is_a_tty:
            term._is_a_tty = False

        result_location = term.get_location(timeout=0.01)
        assert result_location == (-1, -1)

        result_fgcolor = term.get_fgcolor(timeout=0.01)
        assert result_fgcolor == (-1, -1, -1)

        result_bgcolor = term.get_bgcolor(timeout=0.01)
        assert result_bgcolor == (-1, -1, -1)

        result_device_attributes = term.get_device_attributes(timeout=0.01)
        assert result_device_attributes is None

        result_does_sixel = term.does_sixel(timeout=0.01)
        assert result_does_sixel is False

        result_sixel_hw = term.get_sixel_height_and_width(timeout=0.01)
        assert result_sixel_hw == (-1, -1)

        result_sixel_colors = term.get_sixel_colors(timeout=0.01)
        assert result_sixel_colors == -1

        result_cell_hw = term.get_cell_height_and_width(timeout=0.01)
        assert result_cell_hw == (-1, -1)

        assert stream.getvalue() == ''

    child()


@pytest.mark.skipif(IS_WINDOWS, reason="PTY tests not supported on Windows")
def test_scroll_region_context_manager():
    """Test scroll_region context manager sets and resets scroll region."""
    def child(term):
        stream = io.StringIO()
        term._stream = stream
        with term.scroll_region(top=5, height=10):
            pass
        return stream.getvalue()

    output = pty_test(
        child, rows=24, cols=80,)
    assert output == '\x1b[6;15r\x1b[1;24r'


@pytest.mark.skipif(IS_WINDOWS, reason="PTY tests not supported on Windows")
def test_scroll_region_context_manager_defaults():
    """Test scroll_region context manager with default arguments."""
    def child(term):
        stream = io.StringIO()
        term._stream = stream
        with term.scroll_region():
            pass
        return stream.getvalue()

    output = pty_test(child, rows=24, cols=80)
    assert output == '\x1b[1;24r\x1b[1;24r'


def test_get_fgcolor_bgcolor_invalid_bits():
    """Test get_fg/bgcolor raises ValueError for invalid bits parameter."""
    term = TestTerminal(stream=StringIO())
    with pytest.raises(ValueError, match=r"bits must be 8 or 16, got 24"):
        term.get_fgcolor(bits=24)
    with pytest.raises(ValueError, match=r"bits must be 8 or 16, got 32"):
        term.get_bgcolor(bits=32)


def test_multiple_terminal_kinds_bool_caps():
    """String capability presence survives terminal kind switching."""
    term_a = TestTerminal(kind='xterm-256color', force_styling=True)
    assert term_a.dim != ''

    term_b = TestTerminal(kind='vt220', force_styling=True)
    assert term_b.dim == ''

    assert term_a.dim != ''
    assert term_b.dim == ''


def test_multiple_terminal_kinds_alt_screen():
    """Alternate screen capability survives terminal kind switching."""
    term_a = TestTerminal(kind='xterm-256color', force_styling=True)
    smcup_a = term_a.enter_fullscreen
    assert smcup_a != ''

    term_b = TestTerminal(kind='vt220', force_styling=True)
    smcup_b = term_b.enter_fullscreen
    assert smcup_b == ''

    assert term_a.enter_fullscreen != ''
    assert term_b.enter_fullscreen == ''


def test_multiple_terminal_kinds_key_codes():
    """Key codes survive terminal kind switching."""
    term_a = TestTerminal(kind='xterm-256color', force_styling=True)
    home_a = term_a.khome
    assert home_a == '\x1bOH'

    term_b = TestTerminal(kind='screen', force_styling=True)
    home_b = term_b.khome
    assert home_b == '\x1b[1~'

    assert term_a.khome == '\x1bOH'
    assert term_b.khome == '\x1b[1~'


def test_force_styling_true_no_env_vars(monkeypatch):
    """force_styling=True triggers does_styling=True via last elif branch (line 381)."""
    monkeypatch.delenv('FORCE_COLOR', raising=False)
    monkeypatch.delenv('CLICOLOR_FORCE', raising=False)
    monkeypatch.delenv('NO_COLOR', raising=False)
    term = TestTerminal(stream=StringIO(), force_styling=True)
    assert term.does_styling is True


def test_force_styling_none_is_a_tty():
    """force_styling=None with is_a_tty=True logs 'force_styling is None' (line 381)."""
    stream = StringIO()
    stream.fileno = lambda: 1
    with mock.patch('os.isatty', return_value=True):
        term = TestTerminal(stream=stream, force_styling=None)
        assert term.does_styling is False
        assert any('force_styling is None' in err for err in term.errors)


def test_force_styling_false_not_a_tty(monkeypatch):
    """force_styling=False, no env vars, not a tty -> does_styling=False (line 382 elif False)."""
    monkeypatch.delenv('FORCE_COLOR', raising=False)
    monkeypatch.delenv('CLICOLOR_FORCE', raising=False)
    monkeypatch.delenv('NO_COLOR', raising=False)
    term = TestTerminal(stream=StringIO(), force_styling=False)
    assert term.does_styling is False


def test_getattr_underscore_prefix():
    """__getattr__ raises AttributeError for _-prefixed attribute names."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    with pytest.raises(AttributeError):
        _ = term._invalid_cap


@pytest.mark.parametrize("is_a_tty,xtgettcap_supported,expected", [
    (False, False, None),
    (True, False, None),
    (True, True, "supported"),
])
def test_get_xtgettcap_branches(is_a_tty, xtgettcap_supported, expected):
    """get_xtgettcap returns None when not a tty or XTGETTCAP unsupported."""
    xt_data = TermcapResponse(supported=xtgettcap_supported)
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = is_a_tty
    result = term.get_xtgettcap(timeout=0.01)
    if expected == "supported":
        assert result is not None
        assert result.supported is True
    else:
        assert result is None


def test_does_osc52_clipboard_unsupported():
    """does_osc52_clipboard returns False when neither DA1 nor XTGETTCAP supports it."""
    xt_data = TermcapResponse(supported=True, capabilities={'TN': 'xterm-256color'})
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = True
    term.ungetch('\x1b[?64;1;4c')
    result = term.does_osc52_clipboard(timeout=0.01)
    assert result is False


def test_does_osc52_clipboard_da1_supports():
    """does_osc52_clipboard returns True when DA1 has extension 52."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    term.ungetch('\x1b[?64;1;2;4;52c')
    result = term.does_osc52_clipboard(timeout=0.01)
    assert result is True


def test_does_osc52_clipboard_xtgettcap_supports():
    """does_osc52_clipboard returns True when XTGETTCAP has Ms capability."""
    xt_data = TermcapResponse(supported=True, capabilities={'TN': 'xterm-256color', 'Ms': '1'})
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = True
    term.ungetch('\x1b[?64;1;4c')
    result = term.does_osc52_clipboard(timeout=0.01)
    assert result is True


def test_does_osc52_clipboard_cached():
    """does_osc52_clipboard uses cached result on second call."""
    xt_data = TermcapResponse(supported=True, capabilities={'TN': 'xterm-256color', 'Ms': '1'})
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = True
    term.ungetch('\x1b[?64;1c')
    result1 = term.does_osc52_clipboard(timeout=0.01)
    assert result1 is True
    result2 = term.does_osc52_clipboard(timeout=0.01)
    assert result2 is True


def test_does_osc52_clipboard_force():
    """does_osc52_clipboard with force=True bypasses cache."""
    xt_data = TermcapResponse(supported=True, capabilities={'TN': 'xterm-256color', 'Ms': '1'})
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = True
    term.ungetch('\x1b[?64;1c')
    result1 = term.does_osc52_clipboard(timeout=0.01)
    assert result1 is True
    term._osc52_clipboard_supported = None
    xt_empty = TermcapResponse(supported=True, capabilities={'TN': 'xterm-256color'})
    term._xtgettcap_cache = xt_empty
    term.ungetch('\x1b[?64;1c')
    result2 = term.does_osc52_clipboard(timeout=0.01, force=True)
    assert result2 is False


@pytest.mark.parametrize("response,expected", [
    (None, None),
    ('', ''),
    ('aGVsbG8=', 'hello'),
])
def test_clipboard_paste_branches(response, expected):
    """clipboard_paste handles all response variants."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    if response is None:
        result = term.clipboard_paste(timeout=0.01)
        assert result is None
    else:
        term.ungetch(f'\x1b]52;c;{response}\x07')
        result = term.clipboard_paste(timeout=0.01)
        assert result == expected


def test_get_color_scheme_detects_dark():
    """get_color_scheme returns 'dark' for Ps=1."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    term.ungetch('\x1b[?997;1n')
    result = term.get_color_scheme(timeout=0.01)
    assert result == 'dark'


def test_get_color_scheme_detects_light():
    """get_color_scheme returns 'light' for Ps=2."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    term.ungetch('\x1b[?997;2n')
    result = term.get_color_scheme(timeout=0.01)
    assert result == 'light'


def test_get_color_scheme_cached_failure_sticky():
    """get_color_scheme returns None when previous query failed (sticky failure)."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    term._color_scheme_supported = False
    result = term.get_color_scheme(timeout=0.01)
    assert result is None


def test_get_color_scheme_force_bypasses_sticky_failure():
    """get_color_scheme with force=True bypasses sticky failure."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    term._color_scheme_supported = False
    term.ungetch('\x1b[?997;1n')
    result = term.get_color_scheme(timeout=0.01, force=True)
    assert result == 'dark'


def test_get_location_always_decrements():
    """get_location always converts CPR 1-based coordinates to 0-based."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    term.ungetch('\x1b[2;6R')
    row, col = term.get_location(timeout=0.01)
    assert row == 1
    assert col == 5


def test_get_location_returns_tuple():
    """get_location returns a tuple so callers can subscript it."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    term.ungetch('\x1b[2;6R')
    result = term.get_location(timeout=0.01)
    assert isinstance(result, tuple)
    assert result[0] == 1
    assert result[1] == 5


def test_split_seqs_maxsplit_with_xterm():
    """split_seqs maxsplit truncates remaining text."""
    term = TestTerminal(kind='xterm-256color', stream=StringIO(), force_styling=True)
    result = list(term.split_seqs(term.bold('xy'), 1))
    assert result == [term.bold, 'xy' + term.normal]


def test_does_xtgettcap():
    """does_xtgettcap returns True when XTGETTCAP is supported."""
    xt_data = TermcapResponse(supported=True)
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = True
    assert term.does_xtgettcap() is True


def test_does_xtgettcap_unsupported():
    """does_xtgettcap returns False when XTGETTCAP is not supported."""
    xt_data = TermcapResponse(supported=False)
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = True
    assert term.does_xtgettcap() is False


def test_clipboard_paste_invalid_base64():
    """clipboard_paste returns None for invalid base64 data."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    term.ungetch('\x1b]52;c;!!!not-valid-base64!!!\x07')
    result = term.clipboard_paste(timeout=0.01)
    assert result is None


def test_get_color_scheme_timeout():
    """get_color_scheme returns None on timeout and sets sticky failure."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    result = term.get_color_scheme(timeout=0.01)
    assert result is None
    assert term._color_scheme_supported is False


def test_does_kitty_query():
    """does_kitty_query returns True when XTGETTCAP has kitty-query-name."""
    xt_data = TermcapResponse(supported=True, capabilities={'kitty-query-name': '1'})
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = True
    assert term.does_kitty_query() is True


def test_does_kitty_query_unsupported():
    """does_kitty_query returns False when capability is missing."""
    xt_data = TermcapResponse(supported=True, capabilities={})
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = True
    assert term.does_kitty_query() is False


def test_stream_fileno_valueerror(monkeypatch):
    """__init__streams handles ValueError from stream.fileno()."""
    stream = StringIO()
    stream.fileno = lambda: (_ for _ in ()).throw(ValueError('detached'))
    monkeypatch.delenv('FORCE_COLOR', raising=False)
    monkeypatch.delenv('NO_COLOR', raising=False)
    term = TestTerminal(stream=stream)
    assert any('Unable to determine output stream' in err for err in term.errors)


def test_sys_stdout_fileno_valueerror():
    """__init__streams handles ValueError from sys.__stdout__.fileno()."""
    stream = StringIO()
    with mock.patch('sys.__stdout__.fileno', side_effect=ValueError('detached')):
        term = TestTerminal(stream=stream)
        assert any('sys.__stdout__.fileno() failed' in err for err in term.errors)


def test_clipboard_copy_writes_to_stream():
    """clipboard_copy writes the OSC 52 sequence to self.stream."""
    stream = StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term.clipboard_copy('hello world')
    output = stream.getvalue()
    assert '\x1b]52;c;' in output
    assert base64.b64encode(b'hello world').decode('ascii') in output


def test_does_styled_underlines():
    """does_styled_underlines returns True when XTGETTCAP has Smulx."""
    xt_data = TermcapResponse(supported=True, capabilities={'Smulx': '1'})
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = True
    assert term.does_styled_underlines() is True


def test_does_styled_underlines_unsupported():
    """does_styled_underlines returns False when Smulx is missing."""
    xt_data = TermcapResponse(supported=True, capabilities={})
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = True
    assert term.does_styled_underlines() is False


def test_does_colored_underlines():
    """does_colored_underlines returns True when XTGETTCAP has Setulc."""
    xt_data = TermcapResponse(supported=True, capabilities={'Setulc': '1'})
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = True
    assert term.does_colored_underlines() is True


def test_does_colored_underlines_unsupported():
    """does_colored_underlines returns False when Setulc is missing."""
    xt_data = TermcapResponse(supported=True, capabilities={})
    term = TestTerminal(stream=StringIO(), force_styling=True, _xtgettcap_data=xt_data)
    term._is_a_tty = True
    assert term.does_colored_underlines() is False


def test_clipboard_copy_no_styling():
    """clipboard_copy early-returns when does_styling is False."""
    stream = StringIO()
    term = TestTerminal(stream=stream, force_styling=False)
    term.clipboard_copy('hello')
    assert stream.getvalue() == ''


def test_device_attributes_parse_failure():
    """get_device_attributes returns None for malformed DA1 response."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True

    term.ungetch('\x1b[?')
    result = term.get_device_attributes(timeout=0.01)
    assert result is None


def test_software_version_env_fallback_standalone():
    """get_software_version falls back to TERM_PROGRAM env vars (no XTVERSION)."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    with mock.patch.dict(os.environ, {'TERM_PROGRAM': 'TestTerm', 'TERM_PROGRAM_VERSION': '1.0'}):
        result = term.get_software_version(timeout=0.01)
        assert result is not None
        assert result.name == 'TestTerm'
        assert result.version == '1.0'


def test_software_version_no_response():
    """get_software_version returns None with no XTVERSION and no env vars."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    with mock.patch.dict(os.environ, {}, clear=True):
        result = term.get_software_version(timeout=0.01)
        assert result is None


def test_software_version_cache_hit():
    """get_software_version returns cached result without new query."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    with mock.patch.dict(os.environ, {'TERM_PROGRAM': 'CachedTerm', 'TERM_PROGRAM_VERSION': '2.0'}):
        result1 = term.get_software_version(timeout=0.01)
        assert result1 is not None

        result2 = term.get_software_version(timeout=0.01)
        assert result2 is result1


def test_software_version_xtversion_match():
    """get_software_version parses XTVERSION response via ungetch."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True

    term.ungetch('\x1bP>|WezTerm(20240203)\x1b\\')
    result = term.get_software_version(timeout=0.01)
    assert result is not None
    assert result.name == 'WezTerm'
    assert result.version == '20240203'


def test_kbhit_without_tty(monkeypatch):
    """kbhit returns False when HAS_TTY is False (no termios platform)."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    with mock.patch('blessed.terminal.HAS_TTY', False):
        result = term.kbhit(timeout=0)
        assert result is False


@pytest.mark.parametrize('cpr1,cpr2,expected', [
    ('\x1b[1;10R', '\x1b[1;11R', 1),
    ('\x1b[1;10R', '\x1b[1;12R', 2),
    ('\x1b[1;10R', '\x1b[1;10R', 1),
    ('\x1b[1;10R', '\x1b[1;13R', 1),
])
def test_detect_ambiguous_width_unit(cpr1, cpr2, expected):
    """detect_ambiguous_width returns measured width of U+00A7 via CPR."""
    term = TestTerminal(stream=StringIO(), force_styling=True)
    term._is_a_tty = True
    term.ungetch(cpr1)
    term.ungetch(cpr2)
    result = term.detect_ambiguous_width(timeout=0.1, fallback=1)
    assert result == expected


def test_detect_ambiguous_width_first_timeout():
    """detect_ambiguous_width returns fallback when first get_location times out."""
    stream = StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True

    result = term.detect_ambiguous_width(timeout=0.01, fallback=99)
    assert result == 99


def test_detect_ambiguous_width_second_timeout():
    """detect_ambiguous_width returns fallback when second get_location times out."""
    stream = StringIO()
    term = TestTerminal(stream=stream, force_styling=True)
    term._is_a_tty = True

    term.ungetch('\x1b[1;10R')
    result = term.detect_ambiguous_width(timeout=0.01, fallback=77)
    assert result == 77


@pytest.mark.skipif(not IS_WINDOWS, reason='requires jinxed.win32 (msvcrt)')
def test_windows_init_streams_encoding():
    """__init__streams uses get_console_input_encoding when IS_WINDOWS is True."""
    import blessed.terminal as bt
    with mock.patch.object(bt, 'IS_WINDOWS', True), \
            mock.patch.object(bt, 'get_console_input_encoding', return_value='cp1252'), \
            mock.patch('os.isatty', return_value=True):
        term = TestTerminal(force_styling=True)
        assert term._encoding == 'cp1252'


def test_windows_vtwin10_truecolor():
    """__init__color_capabilities returns 1<<24 for vtwin10 on modern Windows."""
    import blessed.terminal as bt
    original_is_windows = bt.IS_WINDOWS
    try:
        bt.IS_WINDOWS = True
        with mock.patch('platform.version', return_value='10.0.19041'), \
                mock.patch('platform.system', return_value='Windows'):
            term = TestTerminal(stream=StringIO(), kind='vtwin10', force_styling=True)
            assert term.number_of_colors == 1 << 24
    finally:
        bt.IS_WINDOWS = original_is_windows


def test_windows_ms_terminal_truecolor():
    """__init__color_capabilities returns 1<<24 for ms-terminal on modern Windows."""
    import blessed.terminal as bt
    original_is_windows = bt.IS_WINDOWS
    try:
        bt.IS_WINDOWS = True
        with mock.patch('platform.version', return_value='10.0.19041'), \
                mock.patch('platform.system', return_value='Windows'):
            term = TestTerminal(stream=StringIO(), kind='ms-terminal', force_styling=True)
            assert term.number_of_colors == 1 << 24
    finally:
        bt.IS_WINDOWS = original_is_windows
