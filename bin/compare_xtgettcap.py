"""Compare XTGETTCAP capabilities from ucs-detect YAML data against jinxed terminfo."""
# I wanted to know, are there any self-reported capability strings that differ from terminfo.src of
# ncurses, transcribed by jinxed ?
#
# Turns out, there are a few!
# - 1 bug (kitty blinking code is inverted)
# - quite a few minor/comsetic differences:
#   - in cursor visibility (cnorm)
#   - smcup/rmcup,
#   - and setab/setaf,
#
# This one bug has me convinced that negotiating XTGETTCAP is best, for at least unknown terminals
# of the future, if somebody releases one tomorrow 'jeff-term', of a new termcap name, so long as
# they implement XTGETTCAP, they no longer have to "distribute terminfo" files to all hosts in use
#
# Should we call XTGETTCAP on initialization of Terminal() ?

import importlib
import re
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent

UCS_DATA = _ROOT / "ucs-detect" / "data"

# Standard terminfo capabilities tracked by jinxed
# Plus Co/RGB which are ncurses extensions not in jinxed's capability catalog
# Co -> colors, RGB -> bits per color channel
EXTENSION_NUM_CAPS = {"Co", "RGB"}

# Extension string caps that some terminals report
EXTENSION_STR_CAPS = {"Setulc", "Smulx", "Smglr", "Smglt", "Smgb", "Smgrp"}

# Map software_name to jinxed module name
SOFTWARE_TO_MODULE = {
    "kitty": "kitty",
    "XTerm": "xterm",
    "foot": "foot",
    "ghostty": "ghostty",
    "WezTerm": "wezterm",
    "contour": "contour",
    "rxvt-unicode": "rxvt_unicode",
    "tmux": "tmux",
    "screen": "screen",
    "PuTTY": "putty",
    "st": "st",
    "alacritty": "alacritty",
    "Rio": "rio",
    "SyncTERM": "syncterm",
    "iTerm2": "iTerm2_app",
}

FALLBACK_TERMINALS = {
    "GNOME Terminal", "Konsole", "xfce4-terminal", "LXTerminal", "QTerminal",
    "terminator", "cool-retro-term", "mintty", "termit", "terminology",
    "tabby", "Hyper", "Extraterm", "Bobcat", "libvterm", "zutty", "mlterm",
    "weston-terminal", "xterm.js", "Terminal.exe", "cmd.exe", "ConEmu",
    "AbsoluteTelnet/SSH", "securecrt", "teraterm", "Apple_Terminal",
    "linux fbdev",
}

# Capabilities that are "TN" (terminal name) -- informational only
INFO_CAPS = {"TN"}


_BACKSLASH_MAP = {
    "E": 0x1B, "e": 0x1B,
    "n": 0x0A, "t": 0x09, "r": 0x0D,
    "b": 0x08, "f": 0x0C,
    "\\": 0x5C, "^": 0x5E, ":": 0x3A,
}


def _parse_xt_val(val):
    r"""Parse an XTGETTCAP string value, handling \E, ^X, etc. Returns bytes."""
    result = bytearray()
    i = 0
    s = str(val)
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            code = _BACKSLASH_MAP.get(nxt)
            if code is not None:
                result.append(code)
                i += 2
                continue
            if nxt in "01234567":
                j = i + 2
                while j < len(s) and s[j] in "01234567":
                    j += 1
                if j > i + 2:
                    result.append(int(s[i + 2:j], 8))
                    i = j
                    continue
        elif s[i] == "^" and i + 1 < len(s):
            c = s[i + 1]
            if "A" <= c <= "_":
                result.append(ord(c) - ord("A") + 1)
                i += 2
                continue
            if c == "?":
                result.append(0x7F)
                i += 2
                continue
        result.append(ord(s[i]))
        i += 1
    return bytes(result)


def _norm_str(val):
    """Normalize a terminfo string: decode, remove padding and jinxed-stripped codes."""
    if isinstance(val, bytes):
        s = val.decode("latin-1")
    else:
        s = str(val)
    s = re.sub(r"\$\<[^>]*\>", "", s)
    s = re.sub(r"\x1b\([0ABUK]", "", s)
    s = s.replace("\x0e", "").replace("\x0f", "")
    return s


def compare_terminal(yaml_path, module_name):
    """
    Compare XTGETTCAP data from YAML against jinxed module.

    Returns (diffs, extension_caps, error).
    """
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    xt = data.get("terminal_results", {}).get("xtgettcap", {})
    if not xt.get("supported"):
        return None, None, "XTGETTCAP not supported"

    xt_caps = xt.get("capabilities", {})
    if not xt_caps:
        return None, None, "XTGETTCAP supported but no capabilities returned"

    try:
        mod = importlib.import_module(f"jinxed.terminfo.{module_name}")
    except ImportError:
        return None, None, f"No jinxed module '{module_name}'"

    jinxed_bools = set(mod.BOOL_CAPS)
    jinxed_nums = dict(mod.NUM_CAPS)
    jinxed_strs = dict(mod.STR_CAPS)

    diffs = []
    extensions = []

    for capname, xt_val in sorted(xt_caps.items()):
        xt_str = str(xt_val).strip() if xt_val is not None else ""

        # Skip empty values (may indicate terminal bug)
        if not xt_str:
            continue

        # Skip informational caps
        if capname in INFO_CAPS:
            continue

        if capname in EXTENSION_STR_CAPS:
            extensions.append((capname, "STR_EXT", xt_str))
            continue

        if capname in EXTENSION_NUM_CAPS:
            if capname == "Co":
                try:
                    xt_co = int(xt_str)
                except ValueError:
                    diffs.append((capname, "NUM_PARSE", xt_str,
                                  str(jinxed_nums.get("colors", "?"))))
                    continue
                jinxed_colors = jinxed_nums.get("colors")
                if jinxed_colors is not None and xt_co != jinxed_colors:
                    diffs.append((capname, "Co_vs_colors",
                                  f"Co={xt_co}", f"colors={jinxed_colors}"))
                continue
            if capname == "RGB":
                try:
                    int(xt_str)
                except ValueError:
                    continue
                extensions.append((capname, "NUM_EXT", xt_str))
                continue

        if capname in jinxed_bools:
            continue

        if capname in jinxed_nums:
            try:
                xt_num = int(xt_str)
            except ValueError:
                diffs.append((capname, "NUM_PARSE", xt_str,
                              str(jinxed_nums[capname])))
                continue
            jn_num = jinxed_nums[capname]
            if xt_num != jn_num:
                diffs.append((capname, "NUM",
                              str(xt_num), str(jn_num)))
            continue

        if capname in jinxed_strs:
            xt_bytes = _parse_xt_val(xt_str)
            xt_norm = _norm_str(xt_bytes)
            jn_norm = _norm_str(jinxed_strs[capname])
            if xt_norm != jn_norm:
                diffs.append((capname, "STR", xt_norm, jn_norm))
            continue

        if capname in jinxed_bools:
            continue
        if capname in jinxed_nums:
            try:
                xt_num = int(xt_str)
            except ValueError:
                diffs.append((capname, "NUM_PARSE", xt_str,
                              str(jinxed_nums[capname])))
                continue
            jn_num = jinxed_nums[capname]
            if xt_num != jn_num:
                diffs.append((capname, "NUM",
                              str(xt_num), str(jn_num)))
            continue
        if capname in jinxed_strs:
            xt_bytes = _parse_xt_val(xt_str)
            xt_norm = _norm_str(xt_bytes)
            jn_norm = _norm_str(jinxed_strs[capname])
            if xt_norm != jn_norm:
                diffs.append((capname, "STR_EXTRA", xt_norm, jn_norm))
            continue

        extensions.append((capname, "UNKNOWN", xt_str))

    return diffs, extensions, None


def main():
    yaml_files = sorted(UCS_DATA.glob("*.yaml"))
    results = []

    for yf in yaml_files:
        try:
            with open(yf) as f:
                data = yaml.safe_load(f)
            sw_name = data.get("software_name", "")
        except Exception:
            continue

        module_name = SOFTWARE_TO_MODULE.get(sw_name)
        if module_name is None and sw_name in FALLBACK_TERMINALS:
            module_name = "xterm_256color"
        if module_name is None:
            continue

        diffs, exts, error = compare_terminal(yf, module_name)
        if error:
            results.append((sw_name, yf.stem, module_name, "SKIP", error, None))
        elif diffs or exts:
            results.append((sw_name, yf.stem, module_name, "DIFFS", diffs, exts))
        else:
            results.append((sw_name, yf.stem, module_name, "MATCH", None, None))

    diffs_found = 0
    for sw_name, stem, mod, status, diffs, exts in results:
        if status == "SKIP":
            continue
        if status == "MATCH" and not exts:
            continue
        diffs_found += 1
        parts = []
        str_diffs = []
        for capname, d_type, xt_val, jn_val in (diffs or []):
            if d_type == "NUM":
                parts.append(f"{capname}={xt_val}(jinxed:{jn_val})")
            elif d_type == "Co_vs_colors":
                parts.append(f"Co/colors {xt_val} vs {jn_val}")
            elif d_type in ("STR", "STR_EXTRA"):
                parts.append(f"{capname} differs")
                str_diffs.append((capname, jn_val, xt_val))
            elif d_type == "NUM_PARSE":
                parts.append(f"{capname} unparseable")
        for capname, e_type, xt_val in (exts or []):
            parts.append(f"{capname}(ext)")

        print(f"\n{sw_name} ({mod})")
        if parts:
            print(f"  {', '.join(parts)}")
        for capname, jn_val, xt_val in str_diffs:
            print(f"  {capname}:")
            print(f"    - {jn_val!r}")
            print(f"    + {xt_val!r}")

    if not diffs_found:
        print("All clear, no differences found.")

    n_skipped = sum(1 for _, _, _, s, _, _ in results if s == "SKIP")
    print(f"\n{len(results)} terminals, {diffs_found} with diffs/exts, {n_skipped} no XTGETTCAP")


if __name__ == "__main__":
    main()
