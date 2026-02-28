#!/usr/bin/env python
"""
Display terminal capabilities, DEC Private Modes, and advanced protocol support.

Usage::

    python bin/display-modes.py          # sugar methods + advanced protocols
    python bin/display-modes.py --all    # also queries all DEC Private Modes
    python bin/display-modes.py --force  # bypass cached results
"""
# std imports
import sys

# local
from blessed import Terminal


def _yn(term, val):
    """Format a boolean as colored YES/NO."""
    return term.bright_green('YES') if val else term.bright_red('NO')


def display_device_attributes(term):
    """Query and display Device Attributes (DA1) information."""
    print(term.bold("Device Attributes (DA1):"))
    print("-" * 40)

    da = term.get_device_attributes()

    if da is None:
        print("  " + term.bright_red("No response - terminal does NOT support DA1 queries"))
        return

    print(f"  Service Class: {term.bright_cyan(str(da.service_class))}")

    if da.extensions:
        print(f"  Extensions: {term.bright_yellow(', '.join(map(str, sorted(da.extensions))))}")

        extension_desc = {
            1: "132 columns",
            2: "Printer port",
            3: "ReGIS graphics",
            4: "Sixel graphics",
            6: "Selective erase",
            7: "DRCS (soft character set)",
            8: "UDK (user-defined keys)",
            9: "NRCS (national replacement character sets)",
            12: "SCS extension (Serbian/Croatian/Slovakian)",
            15: "Technical character set",
            16: "Locator port",
            17: "Terminal state interrogation",
            18: "Windowing capability",
            19: "Sessions capability",
            21: "Horizontal scrolling",
            22: "ANSI color",
            23: "Greek extension",
            24: "Turkish extension",
            28: "Rectangular editing",
            29: "ANSI text locator",
            42: "ISO Latin-2 character set",
            44: "PCTerm",
            45: "Soft key map",
            46: "ASCII emulation",
            52: "OSC 52 clipboard",
        }

        print("  Extension details:")
        for ext in sorted(da.extensions):
            desc = extension_desc.get(ext, "Unknown extension")
            if ext == 4:
                print(f"    {term.bright_green(str(ext))}: {desc}")
            else:
                print(f"    {str(ext)}: {desc}")
    else:
        print("  Extensions: None reported")

    sixel_status = _yn(term, da.supports_sixel)
    print(f"  Sixel Graphics Support: {sixel_status}")


def display_sugar_methods(term):
    """Query and display blessed's public API boolean detection methods."""
    print(term.bold("Detection Methods (blessed public API):"))
    print("-" * 40)

    # DEC mode convenience booleans
    methods = [
        ('does_bracketed_paste', 'Bracketed paste (mode 2004)'),
        ('does_synchronized_output', 'Synchronized output (mode 2026)'),
        ('does_grapheme_clustering', 'Grapheme clustering (mode 2027)'),
        ('does_focus_events', 'Focus event reporting (mode 1004)'),
        ('does_inband_resize', 'In-band resize (mode 2048)'),
    ]

    for method_name, desc in methods:
        print(f'  Testing {method_name}...' + term.clear_eol, end='\r', flush=True)
        result = getattr(term, method_name)()
        print(f"  {_yn(term, result)}  {desc}" + term.clear_eol)

    print()

    # Advanced protocol detections
    print(term.bold("Advanced Protocol Detection:"))
    print("-" * 40)

    print('  Testing XTGETTCAP...' + term.clear_eol, end='\r', flush=True)
    xtgettcap = term.get_xtgettcap()
    print(f"  {_yn(term, xtgettcap is not None)}  XTGETTCAP (DCS +q)" + term.clear_eol)
    if xtgettcap and xtgettcap.supported:
        if xtgettcap.terminal_name:
            print(f"       Terminal name: {term.bright_cyan(xtgettcap.terminal_name)}")
        if xtgettcap.num_colors is not None:
            print(f"       Colors: {xtgettcap.num_colors}")
        print(f"       Capabilities: {len(xtgettcap)}")

    print('  Testing Kitty graphics...' + term.clear_eol, end='\r', flush=True)
    print(f"  {_yn(term, term.does_kitty_graphics())}  "
          f"Kitty graphics protocol (APC)" + term.clear_eol)

    print('  Testing iTerm2...' + term.clear_eol, end='\r', flush=True)
    iterm2 = term.get_iterm2_capabilities()
    has_iterm2 = iterm2 is not None and iterm2.supported
    print(f"  {_yn(term, has_iterm2)}  iTerm2 capabilities (OSC 1337)" + term.clear_eol)
    if has_iterm2:
        print(f"       Detection: {iterm2.detection}")
        if iterm2.features:
            feats = ', '.join(f'{k}={v}' for k, v in sorted(iterm2.features.items()))
            print(f"       Features: {feats}")

    print('  Testing Kitty notifications...' + term.clear_eol, end='\r', flush=True)
    print(f"  {_yn(term, term.does_kitty_notifications())}  "
          f"Kitty desktop notifications (OSC 99)" + term.clear_eol)


def display_all_dec_modes(term):
    """Query and display all DEC Private Mode information."""
    print(term.bold("All DEC Private Modes:"))
    print("-" * 40)

    all_modes = {
        k: getattr(Terminal.DecPrivateMode, k)
        for k in dir(Terminal.DecPrivateMode)
        if k.isupper() and not k.startswith('_')
    }

    supported_modes = {}
    force_mode = '--force' in sys.argv

    for mode_name, mode_code in sorted(all_modes.items(), key=lambda x: x[1]):
        print(f'  Testing {mode_name}...' + term.clear_eol, end='\r', flush=True)
        response = term.get_dec_mode(mode_code, force=force_mode)
        if response.supported:
            supported_modes[mode_name] = response

    print(term.move_x(0) + term.clear_eol, end='', flush=True)

    if not supported_modes:
        print(term.bright_red("DEC Private Mode not supported"))
        return

    print(f"{len(supported_modes)} supported modes:")
    print()

    for mode_name, response in sorted(supported_modes.items(), key=lambda x: x[1].mode.value):
        if response.enabled:
            status = term.bright_green("Enabled")
        else:
            status = term.bright_red("Disabled")

        permanence = term.bold("permanently") if response.permanent else "temporarily"
        mode_info = f"Mode {response.mode.value}"

        print(f"{mode_info:<15} {status} {permanence}")
        print(f"└─ {response.mode.long_description}")
        print()


def main():
    """Main program entry point."""
    term = Terminal()
    show_all = '--all' in sys.argv

    print(term.home + term.clear)
    print()
    print(term.bold("Terminal Capability Report"))
    print()
    _kind = term.bright_cyan(term.kind or 'unknown')
    print(f"Terminal.kind: {_kind}")
    print(f" .is_a_tty: {_yn(term, term.is_a_tty)}")
    print(f" .does_styling: {_yn(term, term.does_styling)}")
    print(f" .does_sixel: {_yn(term, term.does_sixel())}")
    _24bit = term.bright_green('24-bit')
    _no_colors = term.bright_red(str(term.number_of_colors))
    print(f" .number_of_colors: {_24bit if term.number_of_colors == 1 << 24 else _no_colors}")
    print()

    # Display Device Attributes
    display_device_attributes(term)
    print()

    # Display sugar methods and advanced protocols
    display_sugar_methods(term)
    print()

    # Display all DEC Private Modes (only with --all)
    if show_all:
        display_all_dec_modes(term)
    else:
        print(term.bold_black("Use --all to query all DEC Private Modes"))


if __name__ == '__main__':
    main()
