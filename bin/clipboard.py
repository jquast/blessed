#!/usr/bin/env python
"""Demonstrate OSC 52 clipboard copy and paste."""

from blessed import Terminal

term = Terminal()

print('Checking OSC 52 clipboard support ...', end='', flush=True)

if not term.does_osc52_clipboard():
    print()
    print(term.bright_red('OSC 52 clipboard not detected.'))
    print('Your terminal may still support clipboard writes --')
    print('many terminals accept OSC 52 set without advertising it.')
    raise SystemExit(1)

print(term.bright_green(' supported!'))
print()

# Copy text to clipboard
message = 'Hello from blessed!'
term.clipboard_copy(message)
print(f'Copied to clipboard: {term.bold(repr(message))}')
print()

# Read clipboard back (may trigger a permission prompt)
print('Reading clipboard (your terminal may ask for permission) ...',
      end='', flush=True)
result = term.clipboard_paste()

if result is None:
    print()
    print(term.bright_yellow('No response -- clipboard read may be '
                             'disabled or was denied.'))
else:
    print(term.bright_green(' OK'))
    print(f'Clipboard contains: {term.bold(repr(result))}')
