"""Tests for Windows terminal support (blessed.win_terminal)."""
# pylint: disable=possibly-used-before-assignment
# std imports
import io
import collections
from unittest import mock

# 3rd party
import pytest

# local
from .conftest import IS_WINDOWS

pytestmark = pytest.mark.skipif(
    not IS_WINDOWS, reason="Windows-only tests")

if IS_WINDOWS:
    from blessed.win_terminal import (
        _win32_mouse_to_sgr,
        _win32_resize_to_seq,
        POLL_KBHIT_PERIOD,
    )
    from blessed.dec_modes import DecPrivateMode
    from jinxed import win32
    from .accessories import TestTerminal


def _mock_mouse_event(x=0, y=0, button_state=0, event_flags=0,
                      control_key_state=0):
    """Build a mock INPUT_RECORD for a MOUSE_EVENT."""
    event = mock.MagicMock()
    event.EventType = win32.MOUSE_EVENT
    event.Event.MouseEvent.dwMousePosition.X = x
    event.Event.MouseEvent.dwMousePosition.Y = y
    event.Event.MouseEvent.dwButtonState = button_state
    event.Event.MouseEvent.dwEventFlags = event_flags
    event.Event.MouseEvent.dwControlKeyState = control_key_state
    return event


def _mock_key_event(key_down=True):
    """Build a mock INPUT_RECORD for a KEY_EVENT."""
    event = mock.MagicMock()
    event.EventType = win32.KEY_EVENT
    event.Event.KeyEvent.bKeyDown = key_down
    return event


def _mock_resize_event():
    """Build a mock INPUT_RECORD for a WINDOW_BUFFER_SIZE_EVENT."""
    event = mock.MagicMock()
    event.EventType = win32.WINDOW_BUFFER_SIZE_EVENT
    return event


@pytest.mark.parametrize("btn_state,prev,expected", [
    (0x0001, 0, ['\x1b[<0;1;1M']),
    (0x0002, 0, ['\x1b[<2;1;1M']),
    (0x0004, 0, ['\x1b[<1;1;1M']),
    (0, 0x0001, ['\x1b[<0;1;1m']),
    (0, 0x0002, ['\x1b[<2;1;1m']),
    (0, 0x0004, ['\x1b[<1;1;1m']),
])
def test_sgr_button_press_release(btn_state, prev, expected):
    """Test SGR conversion for button press and release events."""
    event = _mock_mouse_event(button_state=btn_state)
    assert _win32_mouse_to_sgr(event, prev) == expected


def test_sgr_coordinates_are_1_indexed():
    """Test that SGR coordinates are converted from 0-indexed to 1-indexed."""
    event = _mock_mouse_event(x=5, y=10, button_state=0x0001)
    assert _win32_mouse_to_sgr(event, 0) == ['\x1b[<0;6;11M']


@pytest.mark.parametrize("btn_state,sgr_btn", [
    (0x0001, 32),
    (0x0002, 34),
])
def test_sgr_motion_with_button_held(btn_state, sgr_btn):
    """Test SGR conversion for drag motion events."""
    event = _mock_mouse_event(x=5, y=5, button_state=btn_state,
                              event_flags=0x0001)
    assert _win32_mouse_to_sgr(event, btn_state) == [f'\x1b[<{sgr_btn};6;6M']


def test_sgr_bare_motion():
    """Test SGR conversion for motion with no button held."""
    event = _mock_mouse_event(x=1, y=2, event_flags=0x0001)
    assert _win32_mouse_to_sgr(event, 0) == ['\x1b[<35;2;3M']


@pytest.mark.parametrize("high_word,sgr_btn", [
    (0x0078, 64),
    (0xFF88, 65),
])
def test_sgr_scroll_wheel(high_word, sgr_btn):
    """Test SGR conversion for scroll wheel events."""
    event = _mock_mouse_event(button_state=high_word << 16,
                              event_flags=0x0004)
    assert _win32_mouse_to_sgr(event, 0) == [f'\x1b[<{sgr_btn};1;1M']


@pytest.mark.parametrize("ctrl_key,sgr_mod", [
    (0x0010, 4),
    (0x0002, 8),
    (0x0001, 8),
    (0x0008, 16),
    (0x0004, 16),
    (0x001A, 28),
])
def test_sgr_modifiers(ctrl_key, sgr_mod):
    """Test SGR modifier bit mapping from Windows control key state."""
    event = _mock_mouse_event(button_state=0x0001,
                              control_key_state=ctrl_key)
    assert _win32_mouse_to_sgr(event, 0) == [f'\x1b[<{sgr_mod};1;1M']


def test_sgr_no_change_returns_empty():
    """Test that no sequences are emitted when nothing changed."""
    event = _mock_mouse_event(button_state=0x0001, event_flags=0x0002)
    assert not _win32_mouse_to_sgr(event, 0x0001)


def test_sgr_simultaneous_press_and_release():
    """Test press of one button and release of another in same event."""
    event = _mock_mouse_event(button_state=0x0002)
    result = _win32_mouse_to_sgr(event, 0x0001)
    assert len(result) == 2
    assert '\x1b[<2;1;1M' in result
    assert '\x1b[<0;1;1m' in result


@pytest.mark.parametrize("lines,cols,expected", [
    (24, 80, '\x1b[48;24;80;0;0t'),
    (50, 200, '\x1b[48;50;200;0;0t'),
])
def test_resize_to_seq(lines, cols, expected):
    """Test DEC mode 2048 resize sequence generation."""
    with mock.patch('blessed.win_terminal.win32.get_terminal_size') as m:
        m.return_value = mock.MagicMock(lines=lines, columns=cols)
        assert _win32_resize_to_seq(1) == expected


@pytest.mark.parametrize("method", ['does_mouse', 'does_inband_resize'])
def test_does_returns_false_without_styling(method):
    """Test does_mouse/does_inband_resize return False without styling."""
    term = TestTerminal(stream=io.StringIO(), force_styling=False)
    assert getattr(term, method)() is False


@pytest.mark.parametrize("method", ['does_mouse', 'does_inband_resize'])
def test_does_returns_false_without_tty(method):
    """Test does_mouse/does_inband_resize return False without tty."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True,
                            is_a_tty=False)
        assert getattr(term, method)() is False
    child()


@pytest.mark.parametrize("method", ['does_mouse', 'does_inband_resize'])
def test_does_returns_true_with_tty_and_styling(method):
    """Test does_mouse/does_inband_resize return True with tty and styling."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = True
        assert getattr(term, method)() is True
    child()


def test_getch_drains_event_buf():
    """Test getch returns buffered event characters first."""
    def child():
        seq = '\x1b[<0;1;1M'
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._event_buf.extend(seq)
        assert ''.join(term.getch() for _ in range(len(seq))) == seq
    child()


def test_kbhit_returns_true_when_buf_has_data():
    """Test kbhit returns True when event buffer is populated."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._keyboard_fd = 0
        term._event_buf.extend('x')
        assert term.kbhit(timeout=0) is True
    child()


def test_kbhit_returns_false_with_no_keyboard_fd():
    """Test kbhit returns False when keyboard fd is None."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._keyboard_fd = None
        assert term.kbhit(timeout=0) is False
    child()


def test_kbhit_timeout_zero_returns_false_on_empty():
    """Test kbhit returns False on empty buffer with zero timeout."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(win32, 'ConsoleInput') as mock_ci:
            console = mock.MagicMock()
            console.peek.return_value = None
            console.wait.return_value = False
            mock_ci.return_value = console
            assert term.kbhit(timeout=0) is False
    child()


def test_drain_mouse_event_buffered():
    """Test drain converts mouse events to SGR sequences."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._native_mouse = True

        console = mock.MagicMock()
        console.peek.side_effect = [
            _mock_mouse_event(x=5, y=10, button_state=0x0001), None]

        term._drain_native_events(console)
        assert ''.join(term._event_buf) == '\x1b[<0;6;11M'
        console.read.assert_called_once()
    child()


def test_drain_resize_event_buffered():
    """Test drain converts resize events to DEC mode 2048 sequences."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._native_resize = True

        console = mock.MagicMock()
        console.peek.side_effect = [_mock_resize_event(), None]

        with mock.patch('blessed.win_terminal.win32.get_terminal_size') as m:
            m.return_value = mock.MagicMock(lines=24, columns=80)
            term._drain_native_events(console)

        assert ''.join(term._event_buf) == '\x1b[48;24;80;0;0t'
    child()


def test_drain_stops_at_key_down():
    """Test drain stops processing at key-down events."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._native_mouse = True

        console = mock.MagicMock()
        console.peek.return_value = _mock_key_event(key_down=True)

        term._drain_native_events(console)
        assert len(term._event_buf) == 0
        console.read.assert_not_called()
    child()


def test_drain_consumes_non_key_down_events():
    """Test drain silently consumes key-up, focus, and menu events."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._native_mouse = True

        console = mock.MagicMock()
        console.peek.side_effect = [
            _mock_key_event(key_down=False),
            mock.MagicMock(EventType=0x0010),
            None]

        term._drain_native_events(console)
        assert len(term._event_buf) == 0
        assert console.read.call_count == 2
    child()


def test_drain_multiple_mouse_events():
    """Test drain processes all pending mouse events eagerly."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._native_mouse = True

        console = mock.MagicMock()
        console.peek.side_effect = [
            _mock_mouse_event(x=1, y=0, button_state=0x0001),
            _mock_mouse_event(x=2, y=0, button_state=0x0001,
                              event_flags=0x0001),
            None]

        term._drain_native_events(console)
        buf = ''.join(term._event_buf)
        assert '\x1b[<0;2;1M' in buf
        assert '\x1b[<32;3;1M' in buf
        assert console.read.call_count == 2
    child()


@pytest.mark.parametrize("flag", ['_native_mouse', '_native_resize'])
def test_drain_ignores_events_when_flag_disabled(flag):
    """Test drain consumes but does not convert events when flag is off."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        setattr(term, flag, False)

        console = mock.MagicMock()
        evt = (_mock_mouse_event(button_state=0x0001)
               if flag == '_native_mouse' else _mock_resize_event())
        console.peek.side_effect = [evt, None]

        term._drain_native_events(console)
        assert len(term._event_buf) == 0
        console.read.assert_called_once()
    child()


def test_drain_tracks_button_state():
    """Test drain updates prev_button_state across consecutive events."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._native_mouse = True

        console = mock.MagicMock()
        console.peek.side_effect = [
            _mock_mouse_event(button_state=0x0001),
            _mock_mouse_event(button_state=0),
            None]

        term._drain_native_events(console)
        buf = ''.join(term._event_buf)
        assert '\x1b[<0;1;1M' in buf
        assert '\x1b[<0;1;1m' in buf
        assert term._prev_button_state == 0
    child()


_NATIVE_CTX_PARAMS = pytest.mark.parametrize(
    "ctx_method,probe_method,flag,dec_mode,enable_bit", [
        ('mouse_enabled', 'does_mouse', '_native_mouse',
         DecPrivateMode.MOUSE_EXTENDED_SGR if IS_WINDOWS else 0,
         win32.ENABLE_MOUSE_INPUT if IS_WINDOWS else 0),
        ('notify_on_resize', 'does_inband_resize', '_native_resize',
         DecPrivateMode.IN_BAND_WINDOW_RESIZE if IS_WINDOWS else 0,
         win32.ENABLE_WINDOW_INPUT if IS_WINDOWS else 0),
    ])


@_NATIVE_CTX_PARAMS
def test_native_fallback_sets_and_clears(
        ctx_method, probe_method, flag, dec_mode, enable_bit):
    """Test native fallback enables console mode and cleans up on exit."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._keyboard_fd = 0

        with mock.patch.object(type(term), probe_method,
                               return_value=False, create=True), \
                mock.patch('blessed.win_terminal.msvcrt.get_osfhandle',
                           return_value=42), \
                mock.patch.object(
                win32, 'get_console_mode',
                return_value=0x0201), \
                mock.patch.object(win32, 'set_console_mode') as mock_set:
            cache_key = int(dec_mode)
            with getattr(term, ctx_method)():
                assert getattr(term, flag) is True
                assert cache_key in term._dec_mode_cache
                mock_set.assert_called_with(42, 0x0201 | enable_bit)

            assert getattr(term, flag) is False
            assert len(term._event_buf) == 0
            assert cache_key not in term._dec_mode_cache
            assert mock_set.call_args_list[-1] == mock.call(42, 0x0201)
    child()


@_NATIVE_CTX_PARAMS
def test_native_fallback_no_keyboard_fd(
        ctx_method, probe_method, flag, dec_mode, enable_bit):
    """Test native fallback yields without action when keyboard fd is None."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._keyboard_fd = None

        with mock.patch.object(type(term), probe_method,
                               return_value=False, create=True):
            with getattr(term, ctx_method)():
                assert getattr(term, flag) is False
    child()


def test_init_attributes():
    """Test Terminal.__init__ initializes native event attributes."""
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        assert isinstance(term._event_buf, collections.deque)
        assert len(term._event_buf) == 0
        assert term._native_mouse is False
        assert term._native_resize is False
        assert term._prev_button_state == 0
    child()


def test_poll_kbhit_period():
    """Test POLL_KBHIT_PERIOD is a reasonable positive value."""
    assert isinstance(POLL_KBHIT_PERIOD, float)
    assert 0 < POLL_KBHIT_PERIOD < 2.0
