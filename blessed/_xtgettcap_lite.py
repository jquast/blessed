"""
Lightweight XTGETTCAP query and response parser.

Used during Terminal.__init__ before curses/jinxed is initialized, so capabilities gathered from the
terminal override the virtual terminfo database.  This module has zero dependencies on jinxed,
curses, or blessed's keyboard infrastructure.
"""

# std imports
import os
import re
import time
import select
from typing import Dict, Tuple, Optional

# XTGETTCAP DCS response: DCS <success>+r<hex-name>=<hex-value> ST
_RE_XTGETTCAP_RESPONSE = re.compile(
    r'\x1bP([01])\+r([0-9a-fA-F]+)(?:=([0-9a-fA-F]*))?\x1b\\')

# CPR response as raw bytes (used as fence during reads)
_RE_CPR_BYTES = re.compile(rb'\x1b\[([0-9]+);([0-9]+)R')

# All capabilities we query via XTGETTCAP: (name, description).
# NOTE: Keep synchronized with XTGETTCAP_CAPABILITIES in _capabilities.py.
XTGETTCAP_CAPABILITIES: Tuple[Tuple[str, str], ...] = (
    ('TN', 'Terminal name'),
    ('Co', 'Number of colors'),
    ('colors', 'Max colors on screen'),
    ('bce', 'Background color erase'),
    ('ccc', 'Can redefine colors'),
    ('km', 'Has meta key'),
    ('msgr', 'Move in standout mode'),
    ('npc', 'No pad character'),
    ('xenl', 'Newline glitch'),
    ('am', 'Auto right margin'),
    ('bw', 'Auto left margin'),
    ('da', 'Memory above'),
    ('db', 'Memory below'),
    ('eslok', 'Status line escape OK'),
    ('hs', 'Has status line'),
    ('mir', 'Move in insert mode'),
    ('ul', 'Transparent underline'),
    ('xt', 'Destructive tabs'),
    ('cols', 'Columns'),
    ('lines', 'Lines'),
    ('it', 'Init tabs'),
    ('pairs', 'Max color pairs'),
    ('bold', 'Enter bold mode'),
    ('dim', 'Enter dim mode'),
    ('blink', 'Enter blink mode'),
    ('rev', 'Enter reverse mode'),
    ('smso', 'Enter standout mode'),
    ('rmso', 'Exit standout mode'),
    ('smul', 'Enter underline mode'),
    ('rmul', 'Exit underline mode'),
    ('sitm', 'Enter italics mode'),
    ('ritm', 'Exit italics mode'),
    ('sgr0', 'Exit attribute mode'),
    ('setaf', 'Set foreground color'),
    ('setab', 'Set background color'),
    ('op', 'Reset colors'),
    ('sc', 'Save cursor'),
    ('rc', 'Restore cursor'),
    ('civis', 'Hide cursor'),
    ('cnorm', 'Normal cursor'),
    ('cvvis', 'Very visible cursor'),
    ('cup', 'Cursor address'),
    ('home', 'Cursor home'),
    ('hpa', 'Column address'),
    ('vpa', 'Row address'),
    ('cub1', 'Cursor left'),
    ('cuf1', 'Cursor right'),
    ('cuu1', 'Cursor up'),
    ('cud1', 'Cursor down'),
    ('cub', 'Parm cursor left'),
    ('cuf', 'Parm cursor right'),
    ('cuu', 'Parm cursor up'),
    ('cud', 'Parm cursor down'),
    ('el', 'Clear to end of line'),
    ('el1', 'Clear to beginning of line'),
    ('ed', 'Clear to end of screen'),
    ('clear', 'Clear screen'),
    ('ech', 'Erase characters'),
    ('dch1', 'Delete character'),
    ('dl1', 'Delete line'),
    ('il1', 'Insert line'),
    ('dch', 'Parm delete chars'),
    ('dl', 'Parm delete lines'),
    ('ich', 'Parm insert chars'),
    ('il', 'Parm insert lines'),
    ('indn', 'Parm index'),
    ('ind', 'Index'),
    ('rin', 'Parm reverse index'),
    ('smcup', 'Enter alt screen'),
    ('rmcup', 'Exit alt screen'),
    ('csr', 'Change scroll region'),
    ('smam', 'Enable auto margins'),
    ('rmam', 'Disable auto margins'),
    ('flash', 'Flash screen'),
    ('bel', 'Bell'),
    ('cr', 'Carriage return'),
    ('smkx', 'Keypad transmit'),
    ('rmkx', 'Keypad local'),
    ('smacs', 'Enter alt charset'),
    ('rmacs', 'Exit alt charset'),
    ('u6', 'CPR response format'),
    ('u7', 'CPR request'),
    ('u8', 'DA request'),
    ('u9', 'DA response'),
    ('Ms', 'OSC 52 clipboard'),
    ('Smulx', 'Styled underlines'),
    ('Setulc', 'Underline color'),
)


class XtgettcapResponse:
    """Parsed XTGETTCAP response data."""

    def __init__(self, supported: bool,
                 capabilities: Optional[Dict[str, str]] = None) -> None:
        self.supported = supported
        self.capabilities: Dict[str, str] = capabilities or {}

    @property
    def terminal_name(self) -> Optional[str]:
        """Terminal name from TN capability, or None."""
        return self.capabilities.get('TN')

    def __repr__(self) -> str:
        return (f'XtgettcapResponse(supported={self.supported}, '
                f'capabilities={self.capabilities})')


def query_xtgettcap(stream_fd: int, timeout: float = 1.0) -> XtgettcapResponse:
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
    os.write(stream_fd, f'\x1bP+q{_hex_encode(probe_cap)}\x1b\\'.encode())
    os.write(stream_fd, b'\x1b[6n')  # CPR fence
    raw = _read_response(stream_fd, timeout)

    if not raw:
        return XtgettcapResponse(supported=False)

    # Check if probe got a valid XTGETTCAP response
    probe_match = _RE_XTGETTCAP_RESPONSE.search(raw)
    if probe_match is None or probe_match.group(1) != '1':
        # Not supported; clean up any garbage on the terminal
        os.write(stream_fd, b'\r\x1b[K')
        return XtgettcapResponse(supported=False)

    _parse_match(probe_match, capabilities)

    # Phase 2: Spray remaining capabilities.
    for capname, _desc in XTGETTCAP_CAPABILITIES[1:]:
        os.write(stream_fd,
                 f'\x1bP+q{_hex_encode(capname)}\x1b\\'.encode())
    os.write(stream_fd, b'\x1b[6n')  # CPR fence
    raw = _read_response(stream_fd, timeout)

    if raw:
        _parse_responses(raw, capabilities)

    # Erase any visible DCS garbage on unsupported terminals
    os.write(stream_fd, b'\r\x1b[K')

    return XtgettcapResponse(supported=True, capabilities=capabilities)


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


def _hex_encode(name: str) -> str:
    """Hex-encode a capability name for an XTGETTCAP query."""
    return name.encode('ascii').hex()


def _hex_decode(hex_str: str) -> str:
    """Decode a hex-encoded string from an XTGETTCAP response."""
    try:
        return bytes.fromhex(hex_str).decode('ascii', errors='strict')
    except ValueError:
        return ''


def _parse_match(match: re.Match, capabilities: Dict[str, str]) -> None:
    """Parse a single XTGETTCAP DCS +r regex match."""
    cap_name = _hex_decode(match.group(2))
    val_hex = match.group(3)
    capabilities[cap_name] = (
        _hex_decode(val_hex) if val_hex is not None else '')


def _parse_responses(raw: str, capabilities: Dict[str, str]) -> None:
    """Parse all DCS +r responses from raw text."""
    for match in _RE_XTGETTCAP_RESPONSE.finditer(raw):
        if match.group(1) == '1':
            _parse_match(match, capabilities)
