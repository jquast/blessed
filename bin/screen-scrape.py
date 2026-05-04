#!/usr/bin/env python3
#
# Demonstrates silent screen-reading via DECRQCRA (DEC Request Checksum of Rectangular Area).
#
# Only mlterm, WezTerm (fixed in HEAD), and SyncTERM (fixed in HEAD) are known to be afflicted by
# default. This sequence is very useful for automatic testing like with `vttest`, likely used while
# developing an emulator, but most make the correct choice of using a disabled-by-default
# compile-time option. iTerm2 makes a runtime prompt that clearly warns, "this allows screen
# scraping", while ghostty displays only "DECRQCRA" with an allow/deny.
#
# https://vt100.net/docs/vt510-rm/DECRQCRA.html allows to silently read the contents of the visible
# screen as a "checksum", but we can pre-compute expected checksums for printable ASCII, building a
# reverse lookup table that recovers the original characters.
#
from blessed import Terminal
import argparse
import json
import os
import re
import select
import sys

UNKNOWN_CKSUM_RE = re.compile(r"\?0x[0-9A-Fa-f]{4}")


DECRQCRA = "\x1b[{pid};1;{r};{c};{r};{c}*y"
DECCKSR_RE = re.compile(r"\x1bP(\d+)!~([0-9A-Fa-f]{4})\x1b\\")
CPR_RE = re.compile(r"\x1b\[(\d+);(\d+)R")
# XTCHECKSUM mode 3: use XTerm-compatible positive checksums
XTCHECKSUM = "\x1b[3#y"
ALT_SCREEN_ON = "\x1b[?47h"
ALT_SCREEN_OFF = "\x1b[?47l"
PRINTABLE = range(32, 127)


def emit(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def query_checksum(term, row, col, pid=1, timeout=1):
    # uses private API for direct terminal query/response
    match = term._query_response(
        DECRQCRA.format(pid=pid, r=row, c=col), DECCKSR_RE, timeout=timeout
    )
    return int(match.group(2), 16) if match else None


def blast_collect(fd, expected, timeout=1.0):
    results = {}
    buf = b""
    while len(results) < expected:
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            break
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        buf += chunk
        # latin-1 is 1:1 byte-to-char, so regex indices match byte offsets
        for match in DECCKSR_RE.finditer(buf.decode("latin-1", errors="replace")):
            results[int(match.group(1))] = int(match.group(2), 16)
        last_st = buf.rfind(b"\x1b\\")
        if last_st >= 0:
            buf = buf[last_st + 2:]
    return results


def build_lookup(term, cal_row, usable_cols):
    """Build checksum-to-character lookup by calibrating printable ASCII."""
    fd = sys.stdin.fileno()
    table = {}
    offset = 0

    while offset < len(PRINTABLE):
        batch = PRINTABLE[offset:offset + usable_cols]
        s = term.move_yx(cal_row - 1, 0) + "".join(chr(c) for c in batch)
        for i, code in enumerate(batch):
            s += DECRQCRA.format(pid=code, r=cal_row, c=i + 1)
        emit(s)

        results = blast_collect(fd, len(batch))
        emit(term.move_yx(cal_row - 1, 0) + term.clear_eol)

        if len(results) < len(batch):
            return {}

        for code in batch:
            cksum = results.get(code)
            if cksum is None:
                return {}
            table[cksum] = chr(code)

        offset += usable_cols

    return table


def blast_scrape(term, rows, cols, lookup):
    space_cksum = next((k for k, v in lookup.items() if v == " "), None)
    fd = sys.stdin.fileno()

    queries = []
    for row in range(1, rows + 1):
        for col in range(1, cols + 1):
            pid = (row - 1) * cols + (col - 1)
            queries.append(DECRQCRA.format(pid=pid, r=row, c=col))
    emit("".join(queries))

    results = blast_collect(fd, rows * cols)

    lines = []
    for row in range(1, rows + 1):
        chars = []
        for col in range(1, cols + 1):
            pid = (row - 1) * cols + (col - 1)
            cksum = results.get(pid)
            if cksum is None or cksum == 0 or cksum == space_cksum:
                chars.append(" ")
            elif cksum in lookup:
                chars.append(lookup[cksum])
            else:
                chars.append(f"?0x{cksum:04X}")
        lines.append("".join(chars).rstrip())
    return "\n".join(lines).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-json", metavar="PATH",
                        help="write results as JSON to PATH instead of stdout")
    args = parser.parse_args()

    term = Terminal()
    rows, cols = term.height, term.width
    usable_cols = cols - 1

    with term.raw():
        cpr_match = term._query_response('\x1b[6n', CPR_RE, timeout=1)
        start_row = int(cpr_match.group(1)) - 1 if cpr_match else rows

        cal_row = rows
        # set XTerm-compatible checksum mode, then flush any response
        emit(XTCHECKSUM)
        term.flushinp(timeout=0.1)

        # probe DECRQCRA support with a single-cell test
        emit(term.move_yx(cal_row - 1, 0) + "A")
        cksum = query_checksum(term, cal_row, 1, pid=9999, timeout=2.0)
        emit(term.move_yx(cal_row - 1, 0) + term.clear_eol)
        if cksum is None:
            print("DECRQCRA not supported.", end='\r\n', file=sys.stderr)
            return 1

        lookup = build_lookup(term, cal_row, usable_cols)
        if not lookup:
            print("Failed to build lookup table.", end='\r\n', file=sys.stderr)
            return 1

        # verify round-trip
        emit(term.move_yx(cal_row - 1, 0) + "Z")
        verify = query_checksum(term, cal_row, 1, pid=1, timeout=1)
        emit(term.move_yx(cal_row - 1, 0) + term.clear_eol)
        if lookup.get(verify) != "Z":
            print("Lookup verification failed.", end='\r\n', file=sys.stderr)
            return 1

        normal = blast_scrape(term, rows, cols, lookup)

        # the alt screen already has content from whatever was displayed in
        # any last program that was in 'alternate' screen, eg. vim or less,
        # DECRQCRA can read it by switching to alternate screen during scrape
        emit(ALT_SCREEN_ON)
        alt = blast_scrape(term, rows, cols, lookup)
        emit(ALT_SCREEN_OFF)

    normal_clean = UNKNOWN_CKSUM_RE.sub(" ", normal)
    alt_clean = UNKNOWN_CKSUM_RE.sub(" ", alt)

    # If both screens are identical, the terminal doesn't support
    # alternate buffer: store only screen 0.
    if normal_clean == alt_clean:
        alt_clean = None
        alt = None

    if args.save_json:
        result = {
            "screen_0": normal_clean,
            "screen_0_with_unknown_checksums": normal,
            "rows": rows,
            "cols": cols,
        }
        if alt_clean is not None:
            result["screen_1"] = alt_clean
            result["screen_1_with_unknown_checksums"] = alt
        with open(args.save_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    else:
        emit(term.move_yx(start_row, 0) + term.clear_eol)
        print(f"screen 0: {repr(normal_clean)}")
        if alt_clean is not None:
            print(f"screen 1: {repr(alt_clean)}")
        else:
            print("screen 1: (same as screen 0, no alternate buffer)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
