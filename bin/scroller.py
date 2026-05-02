#!/usr/bin/env python
"""Demoscene sine-wave scroller with per-character text sizing."""
import math
import time
import blessed
from wcwidth import TextSizing, TextSizingParams, iter_graphemes, wcswidth

FRACTIONS = [(n, d) for d in range(1, 16) for n in range(0, d)]


def _nearest_fraction(numerator, denominator, fractions):
    target = numerator / denominator
    return min(fractions, key=lambda f: abs(target - f[0] / f[1]))


def _scale_params(target):
    if 0.97 <= target <= 1.03:
        return 1, 0, 0, 0
    if target < 1.0:
        n, d = _nearest_fraction(round(target * 100), 100, FRACTIONS)
        if n >= d or n == 0:
            return 1, 0, 0, 0
        return 1, 0, n, d
    s = min(7, max(1, math.ceil(target)))
    if target >= s - 0.03:
        return s, 0, 0, 0
    ratio = target / s
    n, d = _nearest_fraction(round(ratio * 100), 100, FRACTIONS)
    if n >= d:
        return s, 0, 0, 0
    return s, 0, n, d


def _lerp(a, b, t):
    return int(a + (b - a) * t)


def _fire_color(t):
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        u = t / 0.5
        r, g, b = _lerp(255, 255, u), _lerp(40, 160, u), _lerp(0, 0, u)
    else:
        u = (t - 0.5) / 0.5
        r, g, b = _lerp(255, 255, u), _lerp(160, 240, u), _lerp(0, 32, u)
    return f'\x1b[38;2;{r};{g};{b}m'


_BLOCKS = (
    '\u2588\u258c\u2590'
    '\u2580\u2584'
    '\u2591\u2592\u2593'
    '\u2596\u2597\u2598\u259d'
    '\u259a\u259e'
)

_MESSAGE = (
    f'{_BLOCKS}  '
    'Greetings to the modern terminal demoscene!  '
    f'{_BLOCKS}  '
    'Check out kitty\'s text sizing protocol  '
    f'{_BLOCKS}  '
    'unicode: \u6f22\u5b57\u30ab\u30bf\u30ab\u30ca  '
    f'emoji: \U0001f680\U0001f47e\U0001f3b5\U0001f31f  '
    f'{_BLOCKS}  '
)


def _sized_char(ch, target, term, v_align=0, h_align=0):
    if not term.does_text_sizing().scale:
        return ch, wcswidth(ch)
    s, w, n, d = _scale_params(target)
    if s == 1 and n == 0:
        return ch, wcswidth(ch)
    params = TextSizingParams(
        scale=s, width=w, numerator=n, denominator=d,
        vertical_align=v_align, horizontal_align=h_align)
    seq = TextSizing(params, ch, '\x07').make_sequence()
    width = TextSizing(params, ch, '\x07').display_width()
    return seq, width


def main():
    term = blessed.Terminal()
    screen_w = term.width
    screen_h = term.height
    vert_amp = screen_h // 3

    graphemes = list(iter_graphemes(_MESSAGE))
    graph_len = len(graphemes)

    with term.cbreak(), term.hidden_cursor():
        t = 0.0
        scroll_pos = 0.0
        bounce_phase = 0.0
        paused = False

        while True:
            if term.kbhit(timeout=0):
                key = term.inkey(timeout=0)
                if key == 'q' or key == '\x03':
                    break
                if key == ' ':
                    paused = not paused

            if paused:
                time.sleep(0.042)
                continue

            t += 1.0
            scroll_pos += 0.003
            bounce_phase += 0.0006

            graph_offset = int(scroll_pos) % graph_len

            base_freq = 2 * math.pi / screen_w
            spatial_freq = base_freq * (0.2 + 1.8 * (math.sin(t * 0.0004) + 1.0) / 2.0)

            col_scales = []
            for col in range(screen_w):
                norm = (math.sin(col * spatial_freq) + 1.0) / 2.0
                col_scales.append(0.4 + norm * 3.55)

            grapheme_idx = graph_offset
            col = 0
            buf = term.home + term.clear_eos

            while col < screen_w:
                gr = graphemes[grapheme_idx % graph_len]
                grapheme_idx += 1
                if col >= screen_w:
                    break

                target = col_scales[col]
                sine_y = vert_amp * math.sin(col * spatial_freq + bounce_phase)
                y = max(0, min(screen_h - 1, int(screen_h // 2 + sine_y)))

                deriv = math.cos(col * spatial_freq + bounce_phase)
                if deriv > 0.3:
                    v = 1
                elif deriv < -0.3:
                    v = 0
                else:
                    v = 2

                seq, cw = _sized_char(gr, target, term, v, v)
                if col + cw > screen_w:
                    break

                lerp_t = (y - (screen_h // 2 - vert_amp)) / max(1, vert_amp * 2)
                lerp_t += 0.15 * math.sin(t * 0.00035)
                lerp_t = max(0.0, min(1.0, lerp_t))
                fg = _fire_color(lerp_t)

                buf += term.move_yx(y, col) + fg + seq
                col += cw

            with term.dec_modes_enabled(term.DecPrivateMode.SYNCHRONIZED_OUTPUT):
                print(buf, end='', flush=True)


if __name__ == '__main__':
    main()
