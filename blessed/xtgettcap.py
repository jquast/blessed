"""
XTGETTCAP query and response parser.

Used in blessed.Terminal.__init__, before jinxed is initialized, to gather capabilities
for terminal override of jinxed's virtual terminfo database.  This module has *no* dependencies on
jinxed, curses, or our keyboard.py or terminal.py's Terminal, so that it may be used so early in
class initialization.
"""

from __future__ import annotations

# std imports
import os
import re
import time
import select
from typing import Dict

# local
from ._capabilities import XTGETTCAP_CAPABILITIES, TermcapResponse

# CPR response as raw bytes (used as fence during reads)
_RE_CPR_BYTES = re.compile(rb'\x1b\[([0-9]+);([0-9]+)R')


def query_xtgettcap(stream_fd: int, timeout: float = 1.0) -> TermcapResponse:
    """
    Spray XTGETTCAP queries and gather responses.

    Writes all capabilities to *stream_fd* in rapid succession (spray), then reads responses
    (gather).  Uses a trailing CPR query as a fence to detect when all responses have arrived.

    :arg int stream_fd: File descriptor for terminal output (and input).
    :arg float timeout: Per-read timeout in seconds.
    :returns: Parsed response with discovered capabilities.
    """
    capabilities: Dict[str, str] = {}

    # Phase 1: Probe with a single capability to check support.
    probe_cap = XTGETTCAP_CAPABILITIES[0][0]
    os.write(stream_fd,
             f'\x1bP+q{TermcapResponse.hex_encode(probe_cap)}\x1b\\'.encode())
    os.write(stream_fd, b'\x1b[6n')  # CPR fence
    raw = _read_response(stream_fd, timeout)

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

    # Phase 2: Spray remaining capabilities.
    for capname, _desc in XTGETTCAP_CAPABILITIES[1:]:
        os.write(stream_fd,
                 f'\x1bP+q{TermcapResponse.hex_encode(capname)}\x1b\\'.encode())
    os.write(stream_fd, b'\x1b[6n')  # CPR fence
    raw = _read_response(stream_fd, timeout)

    if raw:
        capabilities.update(TermcapResponse.parse_capabilities(raw))

    # Erase any visible DCS garbage on unsupported terminals
    os.write(stream_fd, b'\r\x1b[K')

    return TermcapResponse(supported=True, capabilities=capabilities)


def _read_response(fd: int, timeout: float) -> str:
    """Read bytes from fd until CPR arrives or timeout; decode once at end."""
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
