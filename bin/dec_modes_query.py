#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

# Query mouse support
mode = term.DecPrivateMode.MOUSE_REPORT_CLICK
response = term.get_dec_mode(mode, timeout=1.0)

print(f"Checking {mode.name} (mode {mode.value})...")

if response.is_supported():
    status = "enabled" if response.is_enabled() else "disabled"
    changeability = "permanently" if response.is_permanent() else "temporarily"
    print(f"  Supported: {status} {changeability}")
elif response.is_failed():
    print("  Terminal doesn't support DEC mode queries")
else:
    print("  Not supported by this terminal")
