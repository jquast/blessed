#!/usr/bin/env python
"""Demonstrate the Kitty Text Sizing Protocol (OSC 66) with blessed."""

# std imports
import math

# 3rd party
from wcwidth import TextSizing, TextSizingParams

# local
from blessed import Terminal

FRACTIONS = [(n, d) for d in range(1, 16) for n in range(0, d)]


def _nearest_fraction(numerator, denominator, fractions):
    """Return nearest fraction from *fractions* to numerator/denominator."""
    target = numerator / denominator
    return min(fractions, key=lambda f: abs(target - f[0] / f[1]))


def _params_for_target(target):
    """
    Return (scale, numerator, denominator) for a target visual size.

    *scale* is ``ceil(target)`` since *n/d* can only reduce font size.
    """
    if target <= 1.0:
        return 1, 0, 0
    s = min(7, max(1, math.ceil(target)))
    if target >= s - 0.03:
        return s, 0, 0
    ratio = target / s
    n, d = _nearest_fraction(round(ratio * 100), 100, FRACTIONS)
    if n >= d:
        return s, 0, 0
    return s, n, d


def show_scale_range(term, lo, hi, steps):
    """Display a row of 'X' characters ranging from *lo* to *hi* in *steps*."""
    targets_params = []
    max_s = 1
    for i in range(steps + 1):
        target = lo + (hi - lo) * i / steps
        s, n, d = _params_for_target(target)
        if s > max_s:
            max_s = s
        targets_params.append((target, s, n, d))

    chars = []
    col_starts = []
    col = 0
    for i, (target, s, n, d) in enumerate(targets_params):
        if i == 0 and n == 0 and d == 0 and s < max_s:
            s = max_s
            ratio = target / s
            n, d = _nearest_fraction(round(ratio * 100), 100, FRACTIONS)
            if n >= d:
                n = d - 1
            if n == 0:
                n = 1
        params = TextSizingParams(scale=s, numerator=n, denominator=d)
        chars.append(TextSizing(params, 'X', '\x07').make_sequence())
        col_starts.append(col)
        col += s

    total_cols = col

    pcts = {i: int(target * 100) for i, (target, _, _, _) in enumerate(targets_params)}
    num_labels = 5
    label_at = {}

    for j in range(num_labels):
        pct_target = lo * 100 + (hi - lo) * 100 * j / (num_labels - 1)
        best = min(pcts, key=lambda i: abs(pcts[i] - pct_target))
        label_text = f'{pcts[best]}%'
        start_col = col_starts[best]
        if j > 0:
            overlaps = False
            for prev_i, prev_text in label_at.items():
                prev_start = col_starts[prev_i]
                if prev_start + len(prev_text) > start_col:
                    overlaps = True
                    break
            if overlaps:
                continue
        label_at[best] = label_text

    lbl_top = [' '] * (total_cols + 5)
    for i, text in sorted(label_at.items()):
        start = col_starts[i]
        for c, ch in enumerate(text):
            pos = start + c
            if pos < len(lbl_top) and lbl_top[pos] == ' ':
                lbl_top[pos] = ch
    lbl_bot = [' '] * (total_cols + 5)
    for i, text in sorted(label_at.items()):
        s_val = targets_params[i][1]
        text_s = f's={s_val}'
        start = col_starts[i]
        for c, ch in enumerate(text_s):
            pos = start + c
            if pos < len(lbl_bot) and lbl_bot[pos] == ' ':
                lbl_bot[pos] = ch

    print(''.join(chars), end='\n' * max_s)
    print(''.join(lbl_top).rstrip())
    print(''.join(lbl_bot).rstrip())
    print()


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
    scale_headings = [(1, 'Ol\u00e1'), (2, 'Gr\u00fc\u00dfe'), (3, 'Bj\u00f6rk')]
    for idx, (s, text) in enumerate(scale_headings):
        heading = colors[idx](term.text_sized(text, scale=s))
        newlines = ('\n' * s) if term.does_text_sizing().scale else '\n'
        print(heading + newlines + '=' * term.length(heading) + '\n')


def show_char_types(term):
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
    widths = [w for _, _, w in types]
    box_parts = [f'{tl}{hz * w}{tr}' for w in widths]
    print(gap.join(box_parts))
    mid_parts = [f'{vt}{term.text_sized(ucs, width=w)}{vt}' for _, ucs, w in types]
    print(gap.join(mid_parts))
    bot_parts = [f'{bl}{hz * w}{br}' for w in widths]
    print(gap.join(bot_parts))
    label_parts = [f'{label:<{w + 2}}' for label, _, w in types]
    print(gap.join(label_parts))
    print()


def show_fractional(term):
    fracs = sorted([(n, d) for d in range(2, 16) for n in range(1, d)
                    if n / d >= 0.25], key=lambda nd: nd[0] / nd[1])
    budget = 42
    step = max(1, (len(fracs) + budget - 2) // (budget - 1))
    sampled = fracs[::step]
    sampled.append((0, 0))
    for n, d in sampled:
        print(term.text_sized('X', width=1, numerator=n, denominator=d, vertical_align=0), end='')
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
    print()


def show_alignment(term):
    rows, cols, text = 3, 6, 'Hi'
    text_w = len(text)
    gap = '   '
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
        for row_idx, line_parts in enumerate(zip(*boxes)):
            line = gap.join(line_parts)
            if row_idx == 3:
                line += '    ' + fixed
            print(line)
        print(gap.join(f'{label:^{box_w}s}' for label in labels))

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

    colors = [term.bright_blue, term.bright_red, term.bright_green]
    for i, (name, method) in enumerate([('ljust', term.ljust), ('rjust', term.rjust),
                                        ('center', term.center)]):
        scaled = colors[i](term.text_sized(f'BIG {name.upper()}', 2))
        mixed = 'little and ' + scaled
        content = method(mixed, width=box_cols, fillchar='\u00b7')
        print(f'{tl}{hz * box_cols}{tr}')
        for _ in range(box_rows):
            print(f'{vt}{" " * box_cols}{vt}')
        print(f'{bl}{hz * box_cols}{br}')

        end_y, _ = term.get_location()
        interior_y = max(0, end_y - box_rows - 1)
        print(term.move_yx(interior_y, 1) + content, end='')
        print(term.move_yx(end_y, 0), end='', flush=True)


def main():
    term = Terminal()
    result = detect(term)
    show_scale_factors(term)
    show_char_types(term)
    show_fractional(term)
    show_scale_range(term, 1.0, 2.0, 20)
    show_scale_range(term, 2.0, 3.0, 13)
    show_alignment(term)
    show_ljust_rjust_center(term, bool(result))


if __name__ == '__main__':
    main()
