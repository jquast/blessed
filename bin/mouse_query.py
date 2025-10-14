#!/usr/bin/env python3
from blessed import Terminal

term = Terminal()

# get_dec_mode accepts DecPrivateMode object or an integer, here an object is
# used for its descriptive .name and .value attributes.
mode = term.DecPrivateMode(term.DecPrivateMode.MOUSE_EXTENDED_SGR)
print(f"Checking {mode.name} (mode {mode.value}) ...", end='', flush=True)

# initiate query
response = term.get_dec_mode(mode, timeout=1)

# analyze result
if response.is_failed():
    print(" this terminal " + term.bright_red("does not"), end='')
    print(" support DEC Private Mode queries (timeout)")
elif not response.is_supported():
    print(" Mouse tracking (MOUSE_EXTENDED_SGR) is " + term.bright_red("not supported"))
else:
    status = "enabled" if response.is_enabled() else "disabled"
    print(term.bright_green(f" supported and {status}"))
