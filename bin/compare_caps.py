#!/usr/bin/env python
"""Compare jinxed terminfo capabilities against XTGETTCAP responses."""
import sys
import os
from collections import OrderedDict

import jinxed
from blessed import Terminal
from blessed._capabilities import XTGETTCAP_CAPABILITIES

# Map of interesting string caps: capname -> description
FOCUS_CAPS = OrderedDict()

# Cursor & screen string caps most relevant to the visible bug
CRITICAL_STR = [
    'sc', 'rc', 'cup', 'home', 'hpa', 'vpa',
    'cub1', 'cuf1', 'cuu1', 'cud1',
    'cub', 'cuf', 'cuu', 'cud',
    'el', 'el1', 'ed', 'clear',
    'smcup', 'rmcup', 'csr',
    'civis', 'cnorm', 'cvvis',
    'sgr0', 'bold', 'dim', 'blink', 'rev', 'smso', 'rmso',
    'smul', 'rmul', 'sitm', 'ritm',
    'setaf', 'setab', 'op',
    'smkx', 'rmkx',
    'smam', 'rmam',
    'cr', 'bel',
    'u6', 'u7', 'u8', 'u9',
]

CRITICAL_NUM = [
    'Co', 'colors', 'cols', 'lines', 'it', 'pairs', 'RGB',
]

CRITICAL_BOOL = [
    'am', 'bce', 'bw', 'ccc', 'da', 'db', 'eslok', 'hs',
    'km', 'mir', 'msgr', 'npc', 'ul', 'xenl', 'xt',
]

CRITICAL_EXT = [
    'Ms', 'Smulx', 'Setulc',
]


def decode_cap(value: str) -> str:
    """Decode a string capability value for display, showing control chars."""
    result = []
    for ch in value:
        if ch == '\x1b':
            result.append('\\E')
        elif ch == '\r':
            result.append('\\r')
        elif ch == '\n':
            result.append('\\n')
        elif ch == '\t':
            result.append('\\t')
        elif '\x00' <= ch < ' ':
            result.append(f'^{chr(ord(ch) + 64)}')
        elif ch == '\x7f':
            result.append('^?')
        else:
            result.append(ch)
    return ''.join(result)


def fmt_match(xt_val: str, jinxed_val: str) -> str:
    """Return 'MATCH', 'MISMATCH', or 'XTGETTCAP ONLY'."""
    if xt_val == jinxed_val:
        return 'MATCH'
    if jinxed_val is None:
        return 'XTGETTCAP ONLY'
    return 'MISMATCH'


def parse_numeric(value):  # type: (str | None) -> int | None
    """Parse a numeric capability value, handling r/g/b and binary formats."""
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        # r/g/b format used by some terminals for RGB capability
        return int(value.split('/')[0])
    except (ValueError, IndexError):
        pass
    try:
        return int.from_bytes(value.encode('latin-1'), 'big')
    except (ValueError, OverflowError):
        pass
    return None


def main():
    """Compare jinxed terminfo against XTGETTCAP."""
    print("=== XTGETTCAP Probe ===")
    term = Terminal(force_styling=True)
    result = term.get_xtgettcap(timeout=2)

    if result is None:
        print("XTGETTCAP query returned None")
        sys.exit(1)

    print(f"Supported: {result.supported}")
    print(f"Capabilities reported: {len(result.capabilities)}")

    # Determine jinxed kind from TN or TERM
    tn = result.capabilities.get('TN', '')
    term_kind = tn if tn else os.environ.get('TERM', '')
    info_src = 'XTGETTCAP TN' if tn else 'TERM env'
    print(
        f"Terminal kind (from TN): {term_kind if tn else os.environ.get('TERM', '?')} "
        f"({info_src})")

    # Initialize jinxed
    try:
        jterm = jinxed.Terminal(term_kind)
        jterm_kind = term_kind
    except jinxed.error:
        fallback = 'xterm-256color'
        print(f"jinxed.Terminal({term_kind!r}) failed, using fallback {fallback!r}")
        jterm = jinxed.Terminal(fallback)
        jterm_kind = fallback

    print(f"\njinxed terminal kind: {jterm_kind}")

    # --- String capabilities ---
    print("\n=== String Capabilities ===")
    hdr = f"{'Cap':>5s}  {'XTGETTCAP':<25s}  {'jinxed':<25s}  {'Status':<15s}  Description"
    print(hdr)
    print("-" * len(hdr))

    mismatches = 0
    matches = 0
    for capname in CRITICAL_STR:
        xt_val = result.capabilities.get(capname, None)
        if xt_val is not None:
            xt_val = decode_cap(xt_val)
        jinxed_val_bytes = jterm.tigetstr(capname)
        jinxed_val = decode_cap(jinxed_val_bytes.decode('latin-1')) if jinxed_val_bytes else None
        status = fmt_match(xt_val, jinxed_val)
        xt_disp = repr(xt_val) if xt_val else '(not reported)'
        jn_disp = repr(jinxed_val) if jinxed_val else '(none)'
        if status == 'MISMATCH':
            mismatches += 1
        if status == 'MATCH':
            matches += 1
        desc = dict(XTGETTCAP_CAPABILITIES).get(capname, '')
        if status != 'MATCH' and '--all' not in sys.argv:
            print(f"{capname:>5s}  {xt_disp:<25s}  {jn_disp:<25s}  {status:<15s}  {desc}")

    # --- Numeric capabilities ---
    print("\n=== Numeric Capabilities ===")
    hdr = f"{'Cap':>6s}  {'XTGETTCAP':>8s}  {'jinxed':>8s}  {'Status':<15s}  Description"
    print(hdr)
    print("-" * len(hdr))
    for capname in CRITICAL_NUM:
        xt_val_str = result.capabilities.get(capname, None)
        xt_val = parse_numeric(xt_val_str)
        jinxed_val = jterm.tigetnum(capname)
        jinxed_val = jinxed_val if jinxed_val >= 0 else None
        status = fmt_match(str(xt_val), str(jinxed_val))
        xt_disp = str(xt_val) if xt_val is not None else '(not reported)'
        jn_disp = str(jinxed_val) if jinxed_val is not None else '(none)'
        if status == 'MISMATCH':
            mismatches += 1
        else:
            matches += 1
        desc = dict(XTGETTCAP_CAPABILITIES).get(capname, '')
        if status != 'MATCH' and '--all' not in sys.argv:
            print(f"{capname:>6s}  {xt_disp:>8s}  {jn_disp:>8s}  {status:<15s}  {desc}")

    # --- Boolean capabilities ---
    print("\n=== Boolean Capabilities ===")
    hdr = f"{'Cap':>5s}  {'XTGETTCAP':>9s}  {'jinxed':>9s}  {'Status':<15s}  Description"
    print(hdr)
    print("-" * len(hdr))
    for capname in CRITICAL_BOOL:
        xt_val = capname in result.capabilities  # present means true
        jinxed_val = jterm.tigetflag(capname) == 1
        status = 'MATCH' if xt_val == jinxed_val else 'MISMATCH'
        xt_disp = str(xt_val)
        jn_disp = str(jinxed_val)
        if status == 'MISMATCH':
            mismatches += 1
        if status == 'MATCH':
            matches += 1
        desc = dict(XTGETTCAP_CAPABILITIES).get(capname, '')
        if status != 'MATCH' and '--all' not in sys.argv:
            print(f"{capname:>5s}  {xt_disp:>9s}  {jn_disp:>9s}  {status:<15s}  {desc}")

    # --- Extended capabilities ---
    print("\n=== Extended Capabilities ===")
    for capname in CRITICAL_EXT:
        xt_val = result.capabilities.get(capname, '(not reported)') or '(not supported)'
        desc = dict(XTGETTCAP_CAPABILITIES).get(capname, '')
        print(f"{capname:>6s}  {xt_val:<30s}  {desc}")

    print(f"\n=== Summary: {mismatches} mismatches, {matches} matches ===")


if __name__ == '__main__':
    main()
