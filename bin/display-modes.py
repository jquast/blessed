#!/usr/bin/env python
"""
Display all supported DEC Private Modes and Device Attributes for the current terminal.

This utility queries the terminal for support of various DEC Private Modes and Device Attributes,
displaying the results in a formatted table.

Unsupported modes are not displayed.
"""
# std imports
import sys

# local
from blessed import Terminal


def display_device_attributes(term):
    """Query and display Device Attributes (DA1) information."""
    print(term.bold("Device Attributes (DA1):"))
    print("-" * 40)

    # Query device attributes
    da = term.get_device_attributes()

    if da is None:
        print("  " + term.bright_red("No response - terminal does NOT support DA1 queries"))
        return

    # Display service class
    print(f"  Service Class: {term.bright_cyan(str(da.service_class))}")

    # Display extensions
    if da.extensions:
        print(f"  Extensions: {term.bright_yellow(', '.join(map(str, sorted(da.extensions))))}")

        # Describe notable extensions, we don't do this inside blessed itself
        # because I don't think any of this stuff other than sixel matters
        # anymore.
        extension_desc = {
            1: "132 columns",
            2: "Printer port",
            4: "Sixel graphics",
            6: "Selective erase",
            7: "DRCS (soft character set)",
            8: "UDK (user-defined keys)",
            9: "NRCS (national replacement character sets)",
            12: "SCS extension (Serbian/Croatian/Slovakian)",
            15: "Technical character set",
            18: "Windowing capability",
            21: "Horizontal scrolling",
            23: "Greek extension",
            24: "Turkish extension",
            42: "ISO Latin-2 character set",
            44: "PCTerm",
            45: "Soft key map",
            46: "ASCII emulation"
        }

        print("  Extension details:")
        for ext in sorted(da.extensions):
            desc = extension_desc.get(ext, "Unknown extension")
            if ext == 4:  # Highlight sixel
                print(f"    {term.bright_green(str(ext))}: {desc}")
            else:
                print(f"    {str(ext)}: {desc}")
    else:
        print("  Extensions: None reported")

    # Specifically highlight sixel support
    sixel_status = term.bright_green("YES") if da.supports_sixel else term.bright_red("NO")
    print(f"  Sixel Graphics Support: {sixel_status}")


def display_dec_modes(term):
    """Query and display DEC Private Mode information."""
    print(term.bold("DEC Private Modes:"))
    print("-" * 40)

    # Get all available DEC Private Modes
    all_modes = {
        k: getattr(Terminal.DecPrivateMode, k)
        for k in dir(Terminal.DecPrivateMode)
        if k.isupper() and not k.startswith('_')
    }

    supported_modes = {}
    force_mode = '--force' in sys.argv

    # Query each mode
    for idx, (mode_name, mode_code) in enumerate(sorted(all_modes.items(), key=lambda x: x[1])):
        print(f'  Testing {mode_name}...' + term.clear_eol, end='\r', flush=True)
        response = term.get_dec_mode(mode_code, force=force_mode)
        if response.supported:
            supported_modes[mode_name] = response

    # Clear the testing line
    print(term.move_x(0) + term.clear_eol, end='', flush=True)

    if not supported_modes:
        print(term.bright_red("DEC Private Mode not supported"))
        return

    # Display supported modes in a table
    print(f"{len(supported_modes)} supported modes:")
    print()

    for mode_name, response in sorted(supported_modes.items(), key=lambda x: x[1].mode.value):
        # Status with color coding
        if response.enabled:
            status = term.bright_green("Enabled")
        else:
            status = term.bright_red("Disabled")

        # Permanence indicator
        permanence = term.bold("permanently") if response.permanent else "temporarily"

        # Mode info
        mode_info = f"Mode {response.mode.value}"

        print(f"{mode_info:<15} {status} {permanence}")
        print(f"└─ {response.mode.long_description}")
        print()


def main():
    """Main program entry point."""
    term = Terminal()

    print(term.home + term.clear)
    print()
    print(term.bold("Terminal Capability Report"))
    print()
    _kind = term.bright_cyan(term.kind or 'unknown')
    print(f"Terminal.kind: {_kind}")
    _yes = term.bright_green('YES')
    _no = term.bright_red('NO')
    print(f" .is_a_tty: {_yes if term.is_a_tty else _no}")
    print(f" .does_styling: {_yes if term.does_styling else _no}")
    print(f" .does_sixel: {_yes if term.does_sixel() else _no}")
    _24bit = term.bright_green('24-bit')
    _no_colors = term.bright_red(str(term.number_of_colors))
    print(f" .number_of_colors: {_24bit if term.number_of_colors == 1 << 24 else _no_colors}")
    print()

    # Display Device Attributes
    try:
        display_device_attributes(term)
        print()
    except Exception as e:
        print(f"Error querying device attributes: {e}")
        print()

    # Display DEC Private Modes
    try:
        display_dec_modes(term)
    except Exception as e:
        print(f"Error querying DEC modes: {e}")


if __name__ == '__main__':
    main()
