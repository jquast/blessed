#!/usr/bin/env python
"""Compare jinxed terminfo capabilities against XTGETTCAP responses."""
import sys
import os

import jinxed
from blessed import Terminal
from blessed._capabilities import XTGETTCAP_CAPABILITIES

FOCUS = frozenset({
    # String caps
    'sc', 'rc', 'cup', 'home', 'hpa', 'vpa',
    'cub1', 'cuf1', 'cuu1', 'cud1', 'cub', 'cuf', 'cuu', 'cud',
    'el', 'el1', 'ed', 'clear', 'smcup', 'rmcup', 'csr',
    'civis', 'cnorm', 'cvvis',
    'sgr0', 'bold', 'dim', 'blink', 'rev', 'smso', 'rmso',
    'smul', 'rmul', 'sitm', 'ritm',
    'setaf', 'setab', 'op', 'smkx', 'rmkx', 'smam', 'rmam',
    'cr', 'bel', 'u6', 'u7', 'u8', 'u9',
    # Numeric caps
    'colors', 'cols', 'lines', 'it', 'pairs', 'RGB',
    # Boolean caps
    'am', 'bce', 'bw', 'ccc', 'da', 'db', 'eslok', 'hs',
    'km', 'mir', 'msgr', 'npc', 'ul', 'xenl', 'xt',
    # Extended (XTGETTCAP-only, no jinxed equivalent)
    'Ms', 'Smulx', 'Setulc',
})

# Classify caps using jinxed's built-in type lists.
# RGB is not a standard terminfo cap so jinxed doesn't know about it.
_JINXED_BOOL = frozenset(jinxed.terminfo.BOOL_CAPS)
_JINXED_NUM = frozenset(jinxed.terminfo.NUM_CAPS) | {'RGB'}


def decode_cap(value: str) -> str:
    """Display-formatted capability value with visible control characters."""
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


def parse_numeric(value):
    """Parse a numeric capability, handling r/g/b format."""
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return int(value.split('/')[0])
    except (ValueError, IndexError):
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

    tn = result.capabilities.get('TN', '')
    term_kind = tn if tn else os.environ.get('TERM', '')
    print(
        f"Terminal kind: {term_kind!r}"
        + (" (from TN)" if tn else " (from $TERM)")
    )

    try:
        jterm = jinxed.Terminal(term_kind)
    except jinxed.error:
        fallback = 'xterm-256color'
        print(f"jinxed.Terminal({term_kind!r}) failed, using {fallback!r}")
        jterm = jinxed.Terminal(fallback)
        term_kind = fallback

    print(f"jinxed terminal: {term_kind}")

    caps_desc = dict(XTGETTCAP_CAPABILITIES)
    show_all = '--all' in sys.argv

    str_caps = [c for c in FOCUS if c not in _JINXED_BOOL and c not in _JINXED_NUM]
    num_caps = [c for c in FOCUS if c in _JINXED_NUM]
    bool_caps = [c for c in FOCUS if c in _JINXED_BOOL]

    mismatches = 0
    matches = 0

    def print_section(title, capnames, compare_fn):
        nonlocal mismatches, matches
        print(f"\n=== {title} ===")
        hdr = (
            f"{'Cap':>6s}  {'XTGETTCAP':<30s}  {'jinxed':<30s}  "
            f"{'Status':<15s}  Description"
        )
        print(hdr)
        print("-" * len(hdr))
        for capname in capnames:
            xt_disp, jn_disp, status = compare_fn(capname)
            if status == 'MISMATCH':
                mismatches += 1
            elif status == 'MATCH':
                matches += 1
            desc = caps_desc.get(capname, '')
            if show_all or status != 'MATCH':
                print(
                    f"{capname:>6s}  {xt_disp:<30s}  {jn_disp:<30s}  "
                    f"{status:<15s}  {desc}"
                )

    def compare_str(capname):
        xt_raw = result.capabilities.get(capname)
        xt_val = decode_cap(xt_raw) if xt_raw else None
        jn_bytes = jterm.tigetstr(capname)
        jn_val = decode_cap(jn_bytes.decode('latin-1')) if jn_bytes else None
        if xt_val == jn_val:
            status = 'MATCH'
        elif jn_val is None and xt_val is not None:
            status = 'XTGETTCAP ONLY'
        else:
            status = 'MISMATCH'
        return (
            repr(xt_val) if xt_val else '-',
            repr(jn_val) if jn_val else '-',
            status,
        )

    def compare_num(capname):
        xt_val = parse_numeric(result.capabilities.get(capname))
        jn_val = jterm.tigetnum(capname)
        jn_val = jn_val if jn_val >= 0 else None
        if str(xt_val) == str(jn_val):
            status = 'MATCH'
        elif jn_val is None and xt_val is not None:
            status = 'XTGETTCAP ONLY'
        else:
            status = 'MISMATCH'
        return (
            str(xt_val) if xt_val is not None else '-',
            str(jn_val) if jn_val is not None else '-',
            status,
        )

    def compare_bool(capname):
        xt_val = capname in result.capabilities
        jn_val = jterm.tigetflag(capname) == 1
        status = 'MATCH' if xt_val == jn_val else 'MISMATCH'
        return str(xt_val), str(jn_val), status

    print_section('String Capabilities', str_caps, compare_str)
    print_section('Numeric Capabilities', num_caps, compare_num)
    print_section('Boolean Capabilities', bool_caps, compare_bool)

    print(f"\n=== Summary: {mismatches} mismatches, {matches} matches ===")


if __name__ == '__main__':
    main()
