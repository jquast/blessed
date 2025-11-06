#!/usr/bin/env python

from blessed import Terminal

term = Terminal()

print('Checking software version (XTVERSION) ...', end='', flush=True)

sv = term.get_software_version()

if sv is None:
    print('No response.')
    print(term.bright_red('This terminal does NOT support XTVERSION.'))
else:
    print()
    maybe_version = f', version {sv.version}' if sv.version else ''
    print(f'Terminal: {sv.name}{maybe_version}')
