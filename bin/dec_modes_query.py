#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

# Query mouse support
mode = term.DecPrivateMode(term.DecPrivateMode.MOUSE_REPORT_CLICK)
response = term.get_dec_mode(mode)

print(f"Checking {mode.name} (mode {mode.value}) {mode.long_description}: ", end="")

if response.supported:
    status = "enabled" if response.enabled else "disabled"
    state = "permanently" if response.permanent else "temporarily"
    print(f"Supported and {status} {state}")
elif response.failed:
    print("Terminal does not support DEC mode queries")
else:
    print("Mode not supported by this terminal")
