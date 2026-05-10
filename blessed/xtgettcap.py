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
import termios
from typing import Dict, Iterable, Optional

# local
from ._capabilities import XTGETTCAP_CAPABILITIES, TermcapResponse
from .keyboard import TERMINAL_QUERY_TIMEOUT_SECONDS

# CPR response regex (bytes for raw I/O via os.read).
_RE_CPR_BYTES = re.compile(rb'\x1b\[([0-9]+);([0-9]+)R')


def _read_response(fd: int, timeout: float) -> str:
    """
    Read bytes from fd until CPR arrives or timeout; decode once at end.

    The terminal must already be in raw (non-canonical) mode; this is the caller's responsibility.
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


def query_xtgettcap(stream_fd: int, timeout: Optional[float] = None,
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
    if input_fd is None:
        input_fd = stream_fd

    # Set terminal to raw (non-canonical, no echo) so os.read returns
    # bytes immediately and does not echo them back to the screen.
    # XTGETTCAP/CPR responses do not contain newlines, so canonical
    # mode would buffer them indefinitely; ECHO would leak them.
    try:
        saved_attrs = termios.tcgetattr(input_fd)
        raw_attrs = termios.tcgetattr(input_fd)
        raw_attrs[3] &= ~(termios.ICANON | termios.ECHO)
        raw_attrs[6][termios.VMIN] = 1
        raw_attrs[6][termios.VTIME] = 0
        termios.tcsetattr(input_fd, termios.TCSANOW, raw_attrs)
        was_raw = True
    except termios.error:
        was_raw = False

    try:
        return _query_xtgettcap_impl(stream_fd, input_fd, timeout, caps)
    finally:
        if was_raw:
            termios.tcsetattr(input_fd, termios.TCSANOW, saved_attrs)


def _query_xtgettcap_impl(stream_fd: int, input_fd: int,
                          timeout: Optional[float],
                          caps: Optional[Iterable[str]] = None) -> TermcapResponse:
    """Core XTGETTCAP query logic (terminal already in raw mode)."""
    if timeout is None:
        timeout = TERMINAL_QUERY_TIMEOUT_SECONDS
    capabilities: Dict[str, str] = {}

    if caps is not None:
        cap_list = list(caps)
        if not cap_list:
            return TermcapResponse(supported=False)
    else:
        cap_list = [c[0] for c in XTGETTCAP_CAPABILITIES]

    # Phase 1: Probe with the first capability to check support.
    probe_cap = cap_list[0]
    os.write(stream_fd,
             f'\x1bP+q{TermcapResponse.hex_encode(probe_cap)}\x1b\\'.encode())
    os.write(stream_fd, b'\x1b[6n')  # CPR fence
    raw = _read_response(input_fd, timeout)

    if not raw:
        return TermcapResponse(supported=False)

    # Check if probe got a valid XTGETTCAP response
    probe_match = TermcapResponse._RE_XTGETTCAP_RESPONSE.search(raw)
    if probe_match is None or probe_match.group(1) != '1':
        # Not supported; clean up any garbage on the terminal
        os.write(stream_fd, b'\r\x1b[K')
        return TermcapResponse(supported=False)

    name, value = TermcapResponse.from_match(probe_match)
    capabilities[name] = value

    # Phase 2: Spray remaining capabilities (skip probe cap).
    remaining = cap_list[1:]
    if remaining:
        for capname in remaining:
            os.write(stream_fd,
                     f'\x1bP+q{TermcapResponse.hex_encode(capname)}\x1b\\'.encode())
        os.write(stream_fd, b'\x1b[6n')  # CPR fence
        raw = _read_response(input_fd, timeout)

        if raw:
            capabilities.update(TermcapResponse.parse_capabilities(raw))

    # Record None sentinel for any requested cap that wasn't answered.
    for capname in cap_list:
        if capname not in capabilities:
            capabilities[capname] = None  # type: ignore[assignment]

    # Erase any visible DCS garbage on unsupported terminals
    os.write(stream_fd, b'\r\x1b[K')

    return TermcapResponse(supported=True, capabilities=capabilities)
