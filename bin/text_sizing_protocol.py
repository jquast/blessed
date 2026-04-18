#!/usr/bin/env python
"""Demonstrate the Kitty Text Sizing Protocol (OSC 66) with blessed."""
import sys

from wcwidth import wcswidth
from blessed import Terminal


def make_seq(text, scale=1, width=0, numerator=0, denominator=0,
             vertical_align=0, horizontal_align=0):
    parts = []
    if scale != 1:
        parts.append(f's={scale}')
    if width != 0:
        parts.append(f'w={width}')
    if numerator != 0:
        parts.append(f'n={numerator}')
    if denominator != 0:
        parts.append(f'd={denominator}')
    if vertical_align != 0:
        parts.append(f'v={vertical_align}')
    if horizontal_align != 0:
        parts.append(f'h={horizontal_align}')
    return f'\x1b]66;{":".join(parts)};{text}\x07'


def alignment_box(text, rows, cols, v_align, h_align):
    text_w = len(text)
    if h_align == 0:
        content = text + ' ' * (cols - text_w)
    elif h_align == 1:
        content = ' ' * (cols - text_w) + text
    else:
        left = (cols - text_w) // 2
        content = ' ' * left + text + ' ' * (cols - text_w - left)
    empty = ' ' * cols
    if v_align == 0:
        text_row = 0
    elif v_align == 1:
        text_row = rows - 1
    else:
        text_row = rows // 2
    lines = ['\u250c' + '\u2500' * cols + '\u2510']
    for r in range(rows):
        lines.append('\u2502' + (content if r == text_row else empty) + '\u2502')
    lines.append('\u2514' + '\u2500' * cols + '\u2518')
    return lines


def detect(term):
    print('term.does_text_sizing() -> ', end='', flush=True)
    result = term.does_text_sizing(timeout=2)
    print(f'\r{term.clear_eol}', end='')
    yn = {True: term.bold_green('YES'), False: term.bold_red('NO')}
    print(f'Width sizing: {yn[result.width]}   Scale sizing: {yn[result.scale]}')
    return result


def show_scale_factors(term):
    colors = [term.bright_blue, term.bright_red, term.bright_green]
    for i, (s, text) in enumerate([(1, 'Ol\u00e1'), (2, 'Gr\u00fc\u00dfe'), (3, 'Bj\u00f6rk')]):
        heading = term.heading(text, scale=s)
        # color wraps outside the OSC 66 sequence (SGR can't go inside payload)
        print(colors[i](heading))
        print()


def show_char_types():
    types = [
        ('N', 'A', 1),
        ('VS15', '\u231a\ufe0e', 1),
        ('CJK', '\u6f22', 2),
        ('VS16', '\u00a9\ufe0f', 2),
        ('ZWJ', '\U0001f468\u200d\U0001f469', 2),
        ('flag', '\U0001f1ef\U0001f1f5', 2),
    ]
    tl, tr, bl, br, hz, vt = '\u250c\u2510\u2514\u2518\u2500\u2502'
    gap = '    '
    for _, _, w in types:
        print(f'{tl}{hz * w}{tr}{gap}', end='')
    print()
    for _, char, w in types:
        print(f'{vt}{make_seq(char, width=w)}{vt}{gap}', end='')
    print()
    for _, _, w in types:
        print(f'{bl}{hz * w}{br}{gap}', end='')
    print()
    for label, _, w in types:
        col_w = w + 2 + len(gap)
        print(f'{label:<{col_w}}', end='')
    print()


def show_fractional(term):
    fracs = sorted([(n, d) for d in range(2, 16) for n in range(1, d)
                    if n / d >= 0.25], key=lambda nd: nd[0] / nd[1])
    budget = 43
    step = max(1, (len(fracs) + budget - 2) // (budget - 1))
    sampled = fracs[::step]
    sampled.append((0, 0))
    for n, d in sampled:
        print(make_seq('X', width=1, numerator=n, denominator=d,
                       vertical_align=1), end='')
    print()
    pcts = {i: (int(n / d * 100) if d else 100) for i, (n, d) in enumerate(sampled)}
    label_at = {}
    for target in (25, 50, 75, 100):
        best = min(pcts, key=lambda i: abs(pcts[i] - target))
        label_at[best] = f'{pcts[best]}%'
    lbl = [' '] * (len(sampled) + 5)
    for i, text in sorted(label_at.items()):
        for c, ch in enumerate(text):
            if i + c < len(lbl) and lbl[i + c] == ' ':
                lbl[i + c] = ch
    print(''.join(lbl).rstrip())


def show_alignment(term):
    rows, cols, text = 3, 6, 'Hi'
    text_w = len(text)
    gap = '  '
    box_w = cols + 2
    gap_w = len(gap)
    common = dict(scale=rows, width=text_w, numerator=1, denominator=2)

    for params, labels, fixed in [
        ([(0, 0), (2, 0), (1, 0)],
         ['v=top', 'v=center', 'v=bottom'], 'h=left'),
        ([(0, 0), (0, 2), (0, 1)],
         ['h=left', 'h=center', 'h=right'], 'v=top'),
    ]:
        boxes = [alignment_box(text, rows, cols, v, h) for v, h in params]
        for line_parts in zip(*boxes):
            print(gap.join(line_parts))
        print(gap.join(f'{l:^{box_w}s}' for l in labels) + f'  ({fixed})')

        sys.stdout.flush()
        end_y, _ = term.get_location()
        interior_y = end_y - rows - 3 + 1
        if end_y > 0 and interior_y >= 0:
            for i, (v, h) in enumerate(params):
                raw = term.text_sized(text, **dict(common,
                                                   vertical_align=v,
                                                   horizontal_align=h))
                seq = term.bright_red(raw)
                interior_x = i * (box_w + gap_w) + 1
                print(term.move_yx(interior_y, interior_x) + seq, end='')
            print(term.move_yx(end_y, 0), end='', flush=True)
        print()


def show_ljust_rjust_center(term, supported):
    box_cols = 35
    box_rows = 2 if supported else 1
    tl, tr, bl, br, hz, vt = '\u250c\u2510\u2514\u2518\u2500\u2502'
    dot = '\u00b7'

    colors = [term.bright_blue, term.bright_red, term.bright_green]
    for i, (name, method) in enumerate([('ljust', term.ljust), ('rjust', term.rjust),
                                        ('center', term.center)]):
        scaled = colors[i](term.scaled(f'BIG {name.upper()}', 2))
        mixed = 'little and ' + scaled
        content = method(mixed, box_cols, dot)
        print(f'{tl}{hz * box_cols}{tr}')
        for _ in range(box_rows):
            print(f'{vt}{" " * box_cols}{vt}')
        print(f'{bl}{hz * box_cols}{br}')
        sys.stdout.flush()
        end_y, _ = term.get_location()
        if end_y > 0:
            interior_y = end_y - box_rows - 1
            print(term.move_yx(interior_y, 1) + content, end='')
            print(term.move_yx(end_y, 0), end='', flush=True)


def main():
    term = Terminal()
    result = detect(term)
    show_scale_factors(term)
    show_char_types()
    print()
    show_fractional(term)
    print()
    show_alignment(term)
    show_ljust_rjust_center(term, bool(result))


if __name__ == '__main__':
    main()
