#!/usr/bin/env python
"""Display all termino styles supported by the terminal."""
from blessed import Terminal

term = Terminal()
print(term.home + term.clear)

styles = [
    # common
    ('bold', term.bold),
    ('dim', term.dim),
    ('italic', term.italic),  # often doesn't work
    ('underline', term.underline),
    ('blink', term.blink),
    ('reverse', term.reverse),
    ('standout', term.standout),
    ('strikethrough', term.strikethrough),
    # not common
    ('overline', term.overline),
    ('shadow', term.shadow),
    ('subscript', term.subscript),
    ('superscript', term.superscript),
]

for name, cap in styles:
    if cap:
        txt = cap('The quick brown fox') + '   ' + repr(str(cap))
    else:
        txt = term.webgray('(unsupported)')
    print(f'{name:>14s}   {txt}')
