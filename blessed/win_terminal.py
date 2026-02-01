"""Module containing Windows version of :class:`Terminal`."""


# std imports
import contextlib
import ctypes
from ctypes import wintypes
import msvcrt  # pylint: disable=import-error
import time
from typing import Optional, Generator

# 3rd party
from jinxed import win32  # pylint: disable=import-error

# Windows API for efficient waiting (like select() on Unix)
_kernel32 = ctypes.windll.kernel32
_WaitForSingleObject = _kernel32.WaitForSingleObject
_WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_WaitForSingleObject.restype = wintypes.DWORD
_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102
_WAIT_FAILED = 0xFFFFFFFF
_INFINITE = 0xFFFFFFFF

# local
from .terminal import WINSZ
from .terminal import Terminal as _Terminal


class Terminal(_Terminal):
    """Windows subclass of :class:`Terminal`."""

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
        """
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
        be read using :meth:`getch` without blocking.  This is implemented
        using WaitForSingleObject for efficient waiting (like select() on Unix).

        :arg float timeout: When ``timeout`` is 0, this call is
            non-blocking, otherwise blocking indefinitely until keypress
            is detected when None (default). When ``timeout`` is a
            positive number, returns after ``timeout`` seconds have
            elapsed (float).
        :rtype: bool
        :returns: True if a keypress is awaiting to be read on the keyboard
            attached to this terminal.
        """
        # Quick check first - if data is already available, return immediately
        if msvcrt.kbhit():
            return True

        # Get the console input handle for WaitForSingleObject
        if self._keyboard_fd is not None:
            handle = wintypes.HANDLE(msvcrt.get_osfhandle(self._keyboard_fd))
            # Convert timeout to milliseconds for Windows API
            if timeout is None:
                wait_ms = _INFINITE
            elif timeout <= 0:
                return False  # Non-blocking, already checked above
            else:
                wait_ms = int(timeout * 1000)

            # Efficient wait using Windows API (like select() on Unix)
            result = _WaitForSingleObject(handle, wait_ms)
            if result == _WAIT_FAILED:
                # Fallback to polling on error
                return self._kbhit_poll(timeout)
            if result == _WAIT_OBJECT_0:
                return msvcrt.kbhit()  # Double-check after wait
            if result == _WAIT_TIMEOUT:
                return False
            return False  # Unexpected return value
        else:
            # Fallback to polling if no keyboard fd
            return self._kbhit_poll(timeout)

    def _kbhit_poll(self, timeout: Optional[float]) -> bool:
        """Fallback polling implementation for kbhit."""
        end = time.time() + (timeout or 0)
        while True:
            if msvcrt.kbhit():
                return True
            if timeout is not None and end < time.time():
                break
            time.sleep(0.01)
        return False

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
