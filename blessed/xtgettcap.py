"""
XTGETTCAP query and response parser.

Used in blessed.Terminal.__init__, before jinxed is initialized, to gather capabilities for terminal
override of jinxed's virtual terminfo database.  This module has *no* dependencies on jinxed,
curses, or our keyboard.py or terminal.py's Terminal, so that it may be used so early in class
initialization.
"""

from __future__ import annotations

# std imports
import os
import re
import time
import select
import signal
import array
import contextlib
from typing import Iterable, Iterator, Optional

try:
    import fcntl
    import termios
    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False

# local
from ._capabilities import XTGETTCAP_CAPABILITIES, TermcapResponse
from .keyboard import TERMINAL_QUERY_TIMEOUT_SECONDS

# CPR response regex (bytes for raw I/O via os.read).
_RE_CPR_BYTES = re.compile(rb'\x1b\[([0-9]+);([0-9]+)R')


@contextlib.contextmanager
def _cbreak_fd(fd: int) -> Iterator[bool]:
    """
    Context manager that puts *fd* into cbreak (non-canonical, no echo) mode,
    guarding against SIGTTOU for background processes, and restores the
    original termios settings on exit.

    :yields: ``True`` if cbreak mode was successfully set, ``False`` otherwise.
    """
    if not HAS_TERMIOS:
        yield False
        return
    old_sigttou = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    was_raw = False
    try:
        try:
            saved_attrs = termios.tcgetattr(fd)
            raw_attrs = termios.tcgetattr(fd)
            raw_attrs[3] &= ~(termios.ICANON | termios.ECHO)
            raw_attrs[6][termios.VMIN] = 1
            raw_attrs[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, raw_attrs)
            was_raw = True
        except termios.error:
            pass
        yield was_raw
    finally:
        if was_raw:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved_attrs)
        signal.signal(signal.SIGTTOU, old_sigttou)


def _read_response(fd: int, timeout: float) -> str:
    """
    Read bytes from fd until CPR arrives or timeout; decode once at end.

    The terminal must already be in cbreak (non-canonical) mode; this is the caller's responsibility.
    """
    stime = time.time()
    data = b''
    while True:
        remaining = timeout - (time.time() - stime)
        if remaining <= 0:
            break
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            break
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        data += chunk
        if _RE_CPR_BYTES.search(data):
            break
    return data.decode('latin-1', errors='replace')


def query_xtgettcap(stream_fd: int,
                    timeout: Optional[float] = TERMINAL_QUERY_TIMEOUT_SECONDS,
                    input_fd: Optional[int] = None,
                    caps: Optional[Iterable[str]] = None) -> TermcapResponse:
    """
    Spray XTGETTCAP queries and gather responses.

    Writes requested capabilities to *stream_fd* in rapid succession (spray), then reads
    responses from *input_fd* (gather).  Uses a trailing CPR query as a fence to detect when
    all responses have arrived.

    :arg int stream_fd: File descriptor for terminal output (write queries).
    :arg float timeout: Per-read timeout in seconds.
    :arg int input_fd: File descriptor for terminal input (read responses).
        When omitted or ``None``, falls back to *stream_fd*.
    :arg caps: Capability names to query.  When ``None`` (default), all
        standard XTGETTCAP capabilities are queried.
    :returns: Parsed response with discovered capabilities.
    """
    if not HAS_TERMIOS:
        return TermcapResponse(supported=False)

    if input_fd is None:
        input_fd = stream_fd

    # A PTY with no window size (rows=0, cols=0) will not answer
    # XTGETTCAP or CPR queries; return early to avoid timeout delay.
    try:
        buf = array.array('H', [0, 0, 0, 0])
        fcntl.ioctl(input_fd, termios.TIOCGWINSZ, buf)
        if buf[0] == 0 and buf[1] == 0:
            return TermcapResponse(supported=False)
    except OSError:
        pass

    with _cbreak_fd(input_fd) as in_cbreak:
        if not in_cbreak:
            return TermcapResponse(supported=False)
        if timeout is None:
            timeout = TERMINAL_QUERY_TIMEOUT_SECONDS

        if caps is not None:
            cap_list = list(caps)
            if not cap_list:
                return TermcapResponse(supported=False)
        else:
            cap_list = [c[0] for c in XTGETTCAP_CAPABILITIES]

        # Spray all capabilities at once, then CPR fence.
        for capname in cap_list:
            os.write(stream_fd,
                     f'\x1bP+q{TermcapResponse.hex_encode(capname)}\x1b\\'.encode())
        os.write(stream_fd, b'\x1b[6n')  # CPR fence
        if not (raw := _read_response(input_fd, timeout)):
            return TermcapResponse(supported=False)

        # Process any valid XTGETTCAP response exists.
        if TermcapResponse._RE_XTGETTCAP_RESPONSE.search(raw) is None:
            return TermcapResponse(supported=False)

        capabilities = TermcapResponse.parse_capabilities(raw)

        # Record None sentinel for any requested cap that wasn't answered.
        for capname in cap_list:
            if capname not in capabilities:
                capabilities[capname] = None  # type: ignore[assignment]

        return TermcapResponse(supported=True, capabilities=capabilities)
