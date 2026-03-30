"""Module containing Windows version of :class:`Terminal`."""
# pylint: disable=import-error

# std imports
import os
import time
import msvcrt
import asyncio
import contextlib
import collections
from typing import IO, List, Union, Optional, Generator

# 3rd party
from jinxed import win32

# local
from .terminal import WINSZ
from .terminal import Terminal as _Terminal
from .dec_modes import DecPrivateMode as _DecPrivateMode
from .dec_modes import DecModeResponse

# Maximum time to block in WaitForSingleObject before returning
# to Python for signal processing (e.g. KeyboardInterrupt).
POLL_KBHIT_PERIOD = 0.25

# Windows button state bits -> SGR button numbers.
_WIN32_BUTTON_MAP = (
    (0x0001, 0),  # FROM_LEFT_1ST_BUTTON_PRESSED -> left
    (0x0004, 1),  # FROM_LEFT_2ND_BUTTON_PRESSED -> middle
    (0x0002, 2),  # RIGHTMOST_BUTTON_PRESSED -> right
)


def _win32_mouse_to_sgr(  # pylint: disable=too-many-locals
        mouse_event: "win32.INPUT_RECORD",
        prev_button_state: int) -> List[str]:
    """
    Convert a native Windows MOUSE_EVENT to SGR escape sequences.

    :param mouse_event: The INPUT_RECORD with EventType == MOUSE_EVENT.
    :param prev_button_state: Button state from the previous mouse event, used to detect
        press/release transitions.
    :returns: List of SGR escape sequence strings, possibly empty.
    """
    mouse = mouse_event.Event.MouseEvent
    x = mouse.dwMousePosition.X + 1  # SGR is 1-indexed
    y = mouse.dwMousePosition.Y + 1
    btn_state = mouse.dwButtonState & 0x0007
    flags = mouse.dwEventFlags
    ctrl = mouse.dwControlKeyState

    # SGR modifier bits.
    mods = 0
    if ctrl & 0x0010:  # SHIFT_PRESSED
        mods |= 4
    if ctrl & 0x0003:  # RIGHT_ALT_PRESSED | LEFT_ALT_PRESSED
        mods |= 8
    if ctrl & 0x000C:  # RIGHT_CTRL_PRESSED | LEFT_CTRL_PRESSED
        mods |= 16

    sequences: List[str] = []

    if flags & 0x0004:  # MOUSE_WHEELED
        # High word of dwButtonState: negative (>= 0x8000) is scroll down.
        direction = (mouse.dwButtonState >> 16) & 0xFFFF
        btn = 65 if direction >= 0x8000 else 64
        sequences.append(f'\x1b[<{btn | mods};{x};{y}M')
    else:
        pressed = btn_state & ~prev_button_state
        released = prev_button_state & ~btn_state
        is_motion = bool(flags & 0x0001)

        for win_bit, sgr_btn in _WIN32_BUTTON_MAP:
            if pressed & win_bit:
                sequences.append(f'\x1b[<{sgr_btn | mods};{x};{y}M')
            elif released & win_bit:
                sequences.append(f'\x1b[<{sgr_btn | mods};{x};{y}m')

        if is_motion and not sequences:
            for win_bit, sgr_btn in _WIN32_BUTTON_MAP:
                if btn_state & win_bit:
                    sequences.append(
                        f'\x1b[<{sgr_btn | 32 | mods};{x};{y}M')
                    break
            else:
                # No button held -- bare motion (SGR button 35 = 3 + 32).
                sequences.append(f'\x1b[<{35 | mods};{x};{y}M')

    return sequences


def _win32_resize_to_seq(fd: int) -> str:
    """
    Build an in-band resize sequence from the current terminal size.

    The ``WINDOW_BUFFER_SIZE_EVENT`` itself carries the *screen buffer*
    dimensions, which may include scroll-back history and differ from
    the visible window.  We query the actual terminal size instead.

    :param fd: Python file descriptor for the console output.
    :returns: DEC mode 2048 resize sequence.
    """
    size = win32.get_terminal_size(fd)
    return f'\x1b[48;{size.lines};{size.columns};0;0t'


class Terminal(_Terminal):
    """Windows subclass of :class:`Terminal`."""

    def __init__(self,
                 kind: Optional[str] = None,
                 stream: Optional[IO[str]] = None,
                 force_styling: Union[bool, None] = False) -> None:
        """Initialize Windows terminal instance."""
        super().__init__(kind=kind, stream=stream, force_styling=force_styling)
        self._event_buf: collections.deque[str] = collections.deque()
        self._prev_button_state: int = 0
        self._native_mouse: bool = False
        self._native_resize: bool = False

    def getch(self, decode_latin1: bool = False) -> str:
        r"""
        Read, decode, and return the next byte from the keyboard stream.

        :arg bool decode_latin1: If True, decode byte as latin-1 (for legacy mouse
            sequences with 8-bit coordinates).
        :rtype: unicode
        :returns: a single unicode character, or ``''`` if a multi-byte
            sequence has not yet been fully received.

        For versions of Windows 10.0.10586 and later, the console is expected
        to be in ENABLE_VIRTUAL_TERMINAL_INPUT mode and the default method is
        called.

        For older versions of Windows, msvcrt.getwch() is used. If the received
        character is ``\x00`` or ``\xe0``, the next character is
        automatically retrieved.

        When native console events (mouse, resize) have been synthesized
        into escape sequences, buffered characters are returned first.
        """
        if self._event_buf:
            return self._event_buf.popleft()

        if win32.VTMODE_SUPPORTED:
            return super().getch(decode_latin1=decode_latin1)

        rtn = msvcrt.getwch()
        if rtn in {'\x00', '\xe0'}:
            rtn += msvcrt.getwch()
        return rtn

    def kbhit(self, timeout: Optional[float] = None) -> bool:
        """
        Return whether a keypress has been detected on the keyboard.

        This method is used by :meth:`inkey` to determine if a byte may
        be read using :meth:`getch` without blocking.

        Uses :class:`jinxed.win32.ConsoleInput` for efficient, non-polling
        input detection.  Non-key-down events (key-up releases, resize)
        are consumed so they do not cause spurious returns.

        When native event handling is enabled, ``MOUSE_EVENT`` and
        ``WINDOW_BUFFER_SIZE_EVENT`` records are converted to escape
        sequences and buffered for :meth:`getch`.

        :arg float timeout: When ``timeout`` is 0, this call is
            non-blocking, otherwise blocking indefinitely until keypress
            is detected when None (default). When ``timeout`` is a
            positive number, returns after ``timeout`` seconds have
            elapsed (float).
        :rtype: bool
        :returns: True if a keypress is awaiting to be read on the keyboard
            attached to this terminal within the given ``timeout``.
        """
        if self._keyboard_fd is None:
            return False

        if self._event_buf:
            return True

        console = win32.ConsoleInput(self._keyboard_fd)
        deadline = None if timeout is None else time.monotonic() + timeout

        while True:
            if self._native_mouse or self._native_resize:
                self._drain_native_events(console)
                if self._event_buf:
                    return True

            event = console.peek()

            if event is not None:
                if (event.EventType == win32.KEY_EVENT
                        and event.Event.KeyEvent.bKeyDown):
                    return True
                # Consume non-key-down events.
                console.read()
                continue

            # Buffer empty -- wait for something to arrive.
            remaining = (
                deadline - time.monotonic() if deadline
                else POLL_KBHIT_PERIOD)
            if remaining <= 0:
                return False

            if not console.wait(min(remaining, POLL_KBHIT_PERIOD)):
                continue

    async def _async_read_byte(
        self,
        loop: "asyncio.AbstractEventLoop",
        timeout: Optional[float],
    ) -> Optional[bytes]:
        """
        Read one byte from the keyboard using non-blocking console polling.

        ``ProactorEventLoop`` (the Windows default) does not support
        ``add_reader``, so we poll the console input buffer directly.

        When native event handling is enabled, ``MOUSE_EVENT`` and
        ``WINDOW_BUFFER_SIZE_EVENT`` records are converted to escape
        sequences and returned as bytes, interleaved with normal
        keyboard input.

        :arg loop: The running asyncio event loop.
        :arg timeout: Seconds to wait, or ``None`` to wait indefinitely.
        :returns: A single byte, or ``None`` on timeout.
        """
        deadline = loop.time() + timeout if timeout is not None else None
        console = (win32.ConsoleInput(self._keyboard_fd)
                   if self._native_mouse or self._native_resize else None)

        while True:
            if self._event_buf:
                return self._event_buf.popleft().encode('latin-1')

            if console is not None:
                self._drain_native_events(console)
                if self._event_buf:
                    return self._event_buf.popleft().encode('latin-1')

            if msvcrt.kbhit():
                return os.read(self._keyboard_fd, 1)

            if deadline is not None and loop.time() >= deadline:
                return None

            await asyncio.sleep(0.005)

    def _drain_native_events(
        self, console: "win32.ConsoleInput"
    ) -> None:
        """
        Process pending native console events into the event buffer.

        Drains the console input buffer in one pass, converting all
        pending ``MOUSE_EVENT`` and ``WINDOW_BUFFER_SIZE_EVENT``
        records to escape sequences.  Consuming events eagerly
        prevents the console from coalescing mouse positions during
        fast drags.

        Stops at the first key-down event or when the buffer is
        empty.  Non-key-down events that are not handled (key-up,
        focus, menu) are consumed silently.
        """
        while True:
            event = console.peek()
            if event is None:
                return
            if (self._native_mouse
                    and event.EventType == win32.MOUSE_EVENT):
                sgr_seqs = _win32_mouse_to_sgr(
                    event, self._prev_button_state)
                self._prev_button_state = (
                    event.Event.MouseEvent.dwButtonState & 0x0007)
                console.read()
                for seq in sgr_seqs:
                    self._event_buf.extend(seq)
                continue
            if (self._native_resize
                    and event.EventType == win32.WINDOW_BUFFER_SIZE_EVENT):
                console.read()
                seq = _win32_resize_to_seq(self._init_descriptor)
                self._event_buf.extend(seq)
                continue
            if (event.EventType == win32.KEY_EVENT
                    and event.Event.KeyEvent.bKeyDown):
                return
            console.read()

    @staticmethod
    def _winsize(fd: int) -> WINSZ:
        """
        Return named tuple describing size of the terminal by ``fd``.

        :arg int fd: file descriptor queries for its window size.
        :rtype: WINSZ
        :returns: named tuple describing size of the terminal

        WINSZ is a :class:`collections.namedtuple` instance, whose structure
        directly maps to the return value of the :const:`termios.TIOCGWINSZ`
        ioctl return value. The return parameters are:

            - ``ws_row``: width of terminal by its number of character cells.
            - ``ws_col``: height of terminal by its number of character cells.
            - ``ws_xpixel``: width of terminal by pixels (not accurate).
            - ``ws_ypixel``: height of terminal by pixels (not accurate).
        """
        window = win32.get_terminal_size(fd)
        return WINSZ(ws_row=window.lines, ws_col=window.columns,
                     ws_xpixel=0, ws_ypixel=0)

    @contextlib.contextmanager
    def mouse_enabled(self, *, clicks: bool = True, report_pixels: bool = False,
                      report_drag: bool = False, report_motion: bool = False,
                      timeout: float = 1.0) -> Generator[None, None, None]:
        """
        Context manager for enabling mouse tracking.

        Probes the terminal for DEC private mode support (SGR mouse,
        mode 1006).  If supported, delegates to the base class so that
        escape-sequence-based mouse tracking is used natively.

        Otherwise, falls back to enabling ``ENABLE_MOUSE_INPUT`` on
        the console handle and converting native ``MOUSE_EVENT``
        records into SGR escape sequences so that :meth:`inkey`
        returns standard :class:`~.Keystroke` objects with
        ``MOUSE_*`` names.

        Accepts the same keyword arguments as
        :meth:`~blessed.terminal.Terminal.mouse_enabled`.
        """
        if super().does_mouse(clicks=clicks, report_pixels=report_pixels,
                              report_drag=report_drag,
                              report_motion=report_motion, timeout=timeout):
            with super().mouse_enabled(clicks=clicks,
                                       report_pixels=report_pixels,
                                       report_drag=report_drag,
                                       report_motion=report_motion,
                                       timeout=timeout):
                yield
            return

        if self._keyboard_fd is None:
            yield
            return

        filehandle = msvcrt.get_osfhandle(self._keyboard_fd)
        save_mode = win32.get_console_mode(filehandle)
        win32.set_console_mode(
            filehandle, save_mode | win32.ENABLE_MOUSE_INPUT)
        self._native_mouse = True
        self._prev_button_state = 0
        self._dec_mode_cache[
            _DecPrivateMode.MOUSE_EXTENDED_SGR] = DecModeResponse.SET
        try:
            yield
        finally:
            self._native_mouse = False
            self._event_buf.clear()
            del self._dec_mode_cache[
                _DecPrivateMode.MOUSE_EXTENDED_SGR]
            win32.set_console_mode(filehandle, save_mode)

    def does_mouse(self, *, clicks: bool = True, report_pixels: bool = False,
                   report_drag: bool = False, report_motion: bool = False,
                   timeout: float = 1.0) -> bool:
        """
        Check if the terminal supports mouse tracking.

        Returns ``True`` on Windows when connected to a real console
        with styling enabled.  The terminal may support DEC private
        modes for mouse (probed at enable time), but the native
        console API is always available as a fallback.
        """
        if not self.is_a_tty or not self._does_styling:
            return False
        return True

    @contextlib.contextmanager
    def notify_on_resize(self, timeout: float = 1.0) -> Generator[None, None, None]:
        """
        Context manager for enabling in-band window resize notifications.

        Probes the terminal for DEC private mode 2048 support.  If
        supported, delegates to the base class.  Otherwise, falls back
        to enabling ``ENABLE_WINDOW_INPUT`` on the console handle and
        converting native ``WINDOW_BUFFER_SIZE_EVENT`` records into
        DEC mode 2048 escape sequences so that :meth:`inkey` returns
        a :class:`~.Keystroke` with ``name == 'RESIZE_EVENT'``.

        DEC mode 2048 is not yet supported by Windows Terminal
        (`microsoft/terminal#19618
        <https://github.com/microsoft/terminal/issues/19618>`_),
        so the native fallback is currently always used.

        Accepts the same keyword arguments as
        :meth:`~blessed.terminal.Terminal.notify_on_resize`.
        """
        if super().does_inband_resize(timeout=timeout):
            with super().notify_on_resize(timeout=timeout):
                yield
            return

        if self._keyboard_fd is None:
            yield
            return

        filehandle = msvcrt.get_osfhandle(self._keyboard_fd)
        save_mode = win32.get_console_mode(filehandle)
        win32.set_console_mode(
            filehandle, save_mode | win32.ENABLE_WINDOW_INPUT)
        self._native_resize = True
        self._dec_mode_cache[
            _DecPrivateMode.IN_BAND_WINDOW_RESIZE] = DecModeResponse.SET
        try:
            yield
        finally:
            self._native_resize = False
            self._event_buf.clear()
            del self._dec_mode_cache[
                _DecPrivateMode.IN_BAND_WINDOW_RESIZE]
            self._preferred_size_cache = None  # pylint: disable=attribute-defined-outside-init
            win32.set_console_mode(filehandle, save_mode)

    def does_inband_resize(self, timeout: float = 1.0) -> bool:
        """
        Check if the terminal supports in-band window resize notifications.

        Returns ``True`` on Windows when connected to a real console
        with styling enabled.  The terminal may support DEC mode 2048
        (probed at enable time), but the native console
        ``WINDOW_BUFFER_SIZE_EVENT`` is always available as a fallback.
        """
        if not self.is_a_tty or not self._does_styling:
            return False
        return True

    @contextlib.contextmanager
    def cbreak(self) -> Generator[None, None, None]:
        """
        Allow each keystroke to be read immediately after it is pressed.

        This is a context manager for ``jinxed.w32.setcbreak()``.

        .. note:: You must explicitly print any user input you would like
            displayed.  If you provide any kind of editing, you must handle
            backspace and other line-editing control functions in this mode
            as well!

        **Normally**, characters received from the keyboard cannot be read
        by Python until the *Return* key is pressed. Also known as *cooked* or
        *canonical input* mode, it allows the tty driver to provide
        line-editing before shuttling the input to your program and is the
        (implicit) default terminal mode set by most unix shells before
        executing programs.
        """
        if self._keyboard_fd is not None:

            filehandle = msvcrt.get_osfhandle(self._keyboard_fd)

            # Save current terminal mode:
            save_mode = win32.get_console_mode(filehandle)
            save_line_buffered = self._line_buffered
            win32.setcbreak(filehandle)

            try:
                self._line_buffered = False
                yield
            finally:
                win32.set_console_mode(filehandle, save_mode)
                self._line_buffered = save_line_buffered

        else:
            yield

    @contextlib.contextmanager
    def raw(self) -> Generator[None, None, None]:
        """
        A context manager for ``jinxed.w32.setcbreak()``.

        Although both :meth:`break` and :meth:`raw` modes allow each keystroke
        to be read immediately after it is pressed, Raw mode disables
        processing of input and output.

        In cbreak mode, special input characters such as ``^C`` are
        interpreted by the terminal driver and excluded from the stdin stream.
        In raw mode these values are receive by the :meth:`inkey` method.
        """
        if self._keyboard_fd is not None:

            filehandle = msvcrt.get_osfhandle(self._keyboard_fd)

            # Save current terminal mode:
            save_mode = win32.get_console_mode(filehandle)
            save_line_buffered = self._line_buffered
            win32.setraw(filehandle)

            try:
                self._line_buffered = False
                yield
            finally:
                win32.set_console_mode(filehandle, save_mode)
                self._line_buffered = save_line_buffered

        else:
            yield
