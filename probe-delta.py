#!/usr/bin/env python
import base64
import struct
import sys
import zlib
from blessed import Terminal
from blessed.terminal import _ITERM2_PROBE_IMAGE

LABEL = 30

def opaque_cell():
    def chunk(kind, data):
        body = kind + data
        return (struct.pack('>I', len(data)) + body
                + struct.pack('>I', zlib.crc32(body) & 0xffffffff))
    raw = (b'\x00' + bytes((211, 54, 130, 255)) * 8) * 8
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 8, 6, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw, 9))
           + chunk(b'IEND', b''))
    return ('\x1b]1337;File=inline=1;size={};width=1;height=1;'
            'preserveAspectRatio=0:{}\x07').format(
                len(png), base64.b64encode(png).decode('ascii'))


def draw_cell(term, label, content, erase=False):
    # save and restore around the image: whether it advances a column or a row is
    # the unknown being measured, so the layout must not depend on it.
    term.stream.write(f'  {label:<{LABEL}}[' + term.save + content + term.restore)
    term.stream.write(' ' if erase else term.move_right)
    term.stream.write(']\n')
    term.stream.flush()


def main():
    term = Terminal()
    if not term.is_a_tty:
        sys.exit('not a tty')

    print()
    draw_cell(term, 'plain space (control)', ' ')
    draw_cell(term, 'probe image, left as drawn', _ITERM2_PROBE_IMAGE)
    draw_cell(term, 'probe image, then erased', _ITERM2_PROBE_IMAGE, erase=True)
    draw_cell(term, 'opaque image (drawn?)', opaque_cell())

    term.stream.write(f'  {"cursor movement":<{LABEL}}[' + term.save)
    term.stream.flush()
    row0, col0 = term.get_location()
    term.stream.write(_ITERM2_PROBE_IMAGE)
    term.stream.flush()
    row1, col1 = term.get_location()
    term.stream.write(term.restore + ' ' + term.restore + term.move_right + ']\n')
    term.stream.flush()

    print(f'\n  the first three rows are identical in every terminal: a transparent'
          f'\n  image and an undrawn cell are the same picture.  the opaque row is'
          f'\n  the tell, a magenta block means the terminal really drew it.\n')
    print(f'  {"cursor from":>{LABEL}}: {(row0, col0)}')
    print(f'  {"to":>{LABEL}}: {(row1, col1)}')
    print(f'  {"delta":>{LABEL}}: row {row1 - row0:+d}, col {col1 - col0:+d}')
    print(f'  {"accepted":>{LABEL}}: {(row1, col1) in ((row0, col0 + 1), (row0 + 1, 0))}')
    print(f'  {"verdict":>{LABEL}}: {term.does_iterm2_graphics()}')


if __name__ == '__main__':
    main()
