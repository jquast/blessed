#!/usr/bin/env python3
"""Cellestial: Interactive Cellular Automata Viewer."""
import argparse
import colorsys
import math
import multiprocessing
import os
import random
import signal
import sys
import time

from blessed import Terminal
from blessed.colorspace import X11_COLORNAMES_TO_RGB, hex_to_rgb

FULL_BLOCK, LEFT_HALF, RIGHT_HALF = '\u2588', '\u258C', '\u2590'
INTERESTING_RULES = [18, 22, 26, 30, 45, 60, 75, 82, 86, 89, 90, 101, 102, 105, 109, 110,
                     120, 122, 124, 126, 129, 135, 137, 146, 147, 149, 150, 151, 153, 154,
                     161, 165, 169, 182, 183, 193, 195, 210, 225]

SEXTANT = [' '] * 64
SEXTANT[63] = FULL_BLOCK
for _b in range(1, 63):
    _u = sum((1 << i) for i in range(6) if _b & (1 << (5 - i)))
    SEXTANT[_b] = LEFT_HALF if _u == 21 else RIGHT_HALF if _u == 42 else chr(
        0x1FB00 + _u - 1 - sum(1 for x in (21, 42) if x < _u))


def _parse_color(name):
    """Parse color name or hex code to RGB tuple."""
    name = name.lower().strip()
    if name.startswith('#'):
        return hex_to_rgb(name)
    if name in X11_COLORNAMES_TO_RGB:
        rgb = X11_COLORNAMES_TO_RGB[name]
        return (rgb.red, rgb.green, rgb.blue)
    raise ValueError(f"Unknown color: {name}")


def _rgb_to_hsv(r, g, b):
    """Convert RGB (0-255) to HSV (h: 0-1, s: 0-1, v: 0-1)."""
    return colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)


def _hsv_to_rgb(h, s, v):
    """Convert HSV (0-1 each) to RGB (0-255 each)."""
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return tuple(int(c * 255) for c in (r, g, b))


def _interpolate_hsv(c1, c2, t, long_path=False):
    """Interpolate between two RGB colors in HSV space."""
    h1, s1, v1 = _rgb_to_hsv(*c1)
    h2, s2, v2 = _rgb_to_hsv(*c2)
    delta_h = h2 - h1
    if not long_path and abs(delta_h) > 0.5:
        delta_h += -1 if delta_h > 0 else 1
    elif long_path and abs(delta_h) <= 0.5:
        delta_h += -1 if delta_h > 0 else 1
    h = (h1 + t * delta_h) % 1.0
    s = s1 + t * (s2 - s1)
    v = v1 + t * (v2 - v1)
    return _hsv_to_rgb(h, s, v)


def _generate_rule_data(args):
    rule, width, max_rows, initial_row = args
    if initial_row is None:
        row = bytearray(width)
        row[width // 2] = 1
    else:
        row = bytearray(initial_row)
    rows = [bytes(row)]
    for _ in range(1, max_rows):
        new_row = bytearray(width)
        for x in range(width):
            left = row[x - 1] if x > 0 else 0
            right = row[x + 1] if x < width - 1 else 0
            new_row[x] = (rule >> ((left << 2) | (row[x] << 1) | right)) & 1
        row = new_row
        rows.append(bytes(row))
    # Pre-render sextant lines as bytes (each covers 3 rows, 2 columns per char)
    sextants = []
    for base_r in range(0, max_rows - 2, 3):
        r0, r1, r2 = rows[base_r], rows[base_r + 1], rows[base_r + 2]
        line = bytearray(width // 2)
        for cx in range(width // 2):
            c0 = cx * 2
            bits = 0
            if r0[c0]:
                bits |= 32
            if r0[c0 + 1]:
                bits |= 16
            if r1[c0]:
                bits |= 8
            if r1[c0 + 1]:
                bits |= 4
            if r2[c0]:
                bits |= 2
            if r2[c0 + 1]:
                bits |= 1
            line[cx] = bits
        sextants.append(bytes(line))
    return rule, sextants


class CAEngine:
    def __init__(self, max_rows=1000):
        self._cache, self._pending, self._pool, self._results = {}, set(), None, []
        self._initial_row = None
        self.max_rows = max_rows
        self.width = 2 * max_rows - 1

    def get_sextant_line(self, rule, base_r):
        """Return raw bytes for sextant line (each byte is 0-63 index)."""
        if rule not in self._cache:
            return None
        idx = base_r // 3
        sextants = self._cache[rule]
        if idx >= len(sextants):
            return None
        return sextants[idx]

    def tick(self):
        self._results = [ar for ar in self._results if not self._collect(ar)]

    def _collect(self, ar):
        if not ar.ready():
            return False
        try:
            rule, sextants = ar.get(timeout=0)
            self._cache[rule] = sextants
            self._pending.discard(rule)
        except Exception:
            pass
        return True

    def ensure_rule(self, rule):
        if rule in self._cache or rule in self._pending:
            return
        if not self._pool:
            self._pool = multiprocessing.Pool(max(1, (os.cpu_count() or 1) - 2))
        self._pending.add(rule)
        self._results.append(
            self._pool.apply_async(
                _generate_rule_data, [(rule, self.width, self.max_rows, self._initial_row)]))

    def start(self, popular_rules, random_mode):
        # Terminate existing pool to cancel pending work
        if self._pool:
            self._pool.terminate()
            self._pool.join()
        self._pool = multiprocessing.Pool(max(1, (os.cpu_count() or 1) - 2))
        # Clear cache and pending
        self._cache.clear()
        self._pending.clear()
        self._results.clear()
        # Set initial row based on mode
        if random_mode:
            self._initial_row = bytes(random.randint(0, 1) for _ in range(self.width))
        else:
            self._initial_row = None
        # Queue all rules
        all_rules = list(range(256))
        remaining = [r for r in all_rules if r not in popular_rules]
        for rule in popular_rules:
            self._queue_rule(rule)
        for rule in remaining:
            self._queue_rule(rule)

    def _queue_rule(self, rule):
        if rule in self._cache or rule in self._pending:
            return
        self._pending.add(rule)
        self._results.append(
            self._pool.apply_async(
                _generate_rule_data, [(rule, self.width, self.max_rows, self._initial_row)]))

    def stop(self):
        if self._pool:
            self._pool.terminate()
            self._pool.join()
            self._pool = None
        self._results = []
        self._pending = set()


class Pager:
    # Direction vectors: (dx, dy)
    STEP_MOVES = {
        'h': (-1, 0), 'j': (0, 1), 'k': (0, -1), 'l': (1, 0),
        'y': (-1, -1), 'u': (1, -1), 'b': (-1, 1), 'n': (1, 1),
        'KEY_LEFT': (-1, 0), 'KEY_RIGHT': (1, 0), 'KEY_UP': (0, -1), 'KEY_DOWN': (0, 1),
    }
    PAGE_MOVES = {
        'H': (-1, 0), 'J': (0, 1), 'K': (0, -1), 'L': (1, 0),
        'Y': (-1, -1), 'U': (1, -1), 'B': (-1, 1), 'N': (1, 1),
        'KEY_SLEFT': (-1, 0), 'KEY_SRIGHT': (1, 0), 'KEY_SUP': (0, -1), 'KEY_SDOWN': (0, 1),
        'KEY_SHIFT_LEFT': (-1, 0), 'KEY_SHIFT_RIGHT': (1, 0),
        'KEY_SHIFT_UP': (0, -1), 'KEY_SHIFT_DOWN': (0, 1),
        'KEY_PGUP': (0, -1), 'KEY_PGDOWN': (0, 1),
    }

    def __init__(self, term, engine, autoscroll=False, rule_change_secs=60, rules=None,
                 fullscreen=False, fg_color1='lightsteelblue2', fg_color2='coral',
                 bg_color='midnightblue', palette_path='short', default_state=False,
                 speed_range=(1, 100), oscillation_rate=30):
        self.term, self.engine, self.rule = term, engine, 30
        self.viewport_y = self.viewport_x = 0
        self._dirty, self._refresh_all, self._loading = True, True, False
        self._autoscroll, self._rule_change_secs = autoscroll, rule_change_secs
        self._fullscreen = fullscreen
        self._random_mode = not default_state
        self._speed_min, self._speed_max = speed_range
        self._oscillation_rate = oscillation_rate
        self._last_drawn = (None, None, None, None, None)  # (y, x, rule, random_mode, loading)
        self._rules = rules or INTERESTING_RULES
        # Build 64-color palette via HSV interpolation
        c1, c2 = _parse_color(fg_color1), _parse_color(fg_color2)
        bg_rgb = _parse_color(bg_color)
        long_path = palette_path == 'long'
        bg_seq = term.on_color_rgb(*bg_rgb)
        self._palette = [
            term.color_rgb(*_interpolate_hsv(c1, c2, i / 63, long_path)) + bg_seq
            for i in range(64)
        ]
        self._normal = term.normal
        # For rule diagram, use a simple color with the background
        self._ui_color = term.color_rgb(*c2) + bg_seq
        self._auto_angle = random.uniform(0, 2 * math.pi) if autoscroll else 0
        self._auto_xy, self._turn_timer = [0.0, 0.0], 0.0
        self._last_rule_change = self._last_frame = self._start_time = time.monotonic()
        if autoscroll and self._rules:
            self.rule = self._rules[0]
            self.viewport_y = random.randint(0, max(0, engine.max_rows - self._page()[0]))
        self._constrain()

    def _page(self):
        h = self.term.height if self._fullscreen else self.term.height - 8
        return max(1, h) * 3, max(1, self.term.width) * 2

    def _constrain(self):
        ph, pw = self._page()
        max_rows, width = self.engine.max_rows, self.engine.width
        self.viewport_y = max(0, min(max_rows - ph, self.viewport_y))
        self.viewport_x = max(0, min(width - pw, self.viewport_x))

    def _set_rule(self, rule):
        self.rule = rule % 256
        self._dirty = self._refresh_all = True

    def _colored_sextants(self, line_bytes):
        """Generator yielding sextant chars with color escapes only on change."""
        last = None
        for b in line_bytes:
            seq = self._palette[b]
            if seq != last:
                yield seq
                last = seq
            yield SEXTANT[b]
        yield self._normal

    def _render_row(self, rule, base_r, viewport_x, width):
        """Render a row of sextants with HSV-interpolated colors."""
        line_bytes = self.engine.get_sextant_line(rule, base_r)
        if line_bytes is None:
            return None
        sliced = line_bytes[viewport_x // 2:viewport_x // 2 + width]
        return ''.join(self._colored_sextants(sliced))

    def _draw_rule(self):
        t, rl = self.term, self.rule
        pad = ' ' * max(0, (t.width - 63) // 2)
        c, n = self._ui_color, self._normal

        def input_row(i):
            l, m, r = (FULL_BLOCK if i & b else ' ' for b in (4, 2, 1))
            return f'{c}│{l}│{m}│{r}│{n}'

        def output_row(i):
            o = FULL_BLOCK if (rl >> i) & 1 else ' '
            return f'  {c}│{o}│{n}  '

        lines = [
            pad + ' '.join([f'{c}┌─┬─┬─┐{n}'] * 8),
            pad + ' '.join(input_row(i) for i in range(7, -1, -1)),
            pad + ' '.join([f'{c}└─┴─┴─┘{n}'] * 8),
            pad + ' '.join([f'  {c}┌─┐{n}  '] * 8),
            pad + ' '.join(output_row(i) for i in range(7, -1, -1)),
            pad + ' '.join(f'  {c}└{i}┘{n}  ' for i in range(8, 0, -1)),
        ]
        return ''.join(t.move_yx(i, 0) + line for i, line in enumerate(lines))

    def _draw_grid(self):
        t, gw = self.term, self.term.width
        gh = t.height if self._fullscreen else t.height - 8
        start_y = 0 if self._fullscreen else 7
        out = []
        if not self._fullscreen:
            header = ' 1-8 bits :: [] prev/next :: {} fine :: ^R random ^D default '
            pad = t.width - len(header)
            out.append(t.move_yx(6, 0) + '─' * (pad // 2) + header + '─' * (pad - pad // 2))
        self._loading, rows_data = False, []
        for sy in range(gh):
            row = self._render_row(self.rule, self.viewport_y + sy * 3, self.viewport_x, gw)
            if row is None:
                self._loading = True
                rows_data.append(None)
            else:
                rows_data.append(row)
        for sy, row_data in enumerate(rows_data):
            content = '.' * gw if row_data is None else row_data
            out.append(t.move_yx(start_y + sy, 0) + content)
        if self._loading:
            msg = ' please wait '
            cx, cy = (gw - len(msg)) // 2, start_y + gh // 2
            out.append(t.move_yx(cy, cx) + msg)
        return ''.join(out)

    def _draw_status(self):
        t, ph, pw = self.term, *self._page()
        y = 7 + t.height - 8
        end_y, end_x = min(self.viewport_y + ph - 1, self.engine.max_rows -
                           1), min(self.viewport_x + pw - 1, self.engine.width - 1)
        arrow = '→↘↓↙←↖↑↗'[
            int((self._auto_angle % (2 * math.pi) + math.pi / 8) / (math.pi / 4)) % 8]
        auto = f' [{arrow}AUTO]' if self._autoscroll else ''
        rand = ' [RAND]' if self._random_mode else ''
        left = f' Rule {
            self.rule} row:{
            self.viewport_y}-{end_y} col:{
            self.viewport_x}-{end_x}{auto}{rand} '
        right = ' ^C quit ^S auto ^F full '
        fill = t.width - len(left) - len(right)
        print(t.move_yx(y, 0) + left + '─' * max(0, fill) + right, end='', flush=True)

    def _draw(self, refresh_all=False):
        current = (self.viewport_y, self.viewport_x, self.rule, self._random_mode, self._loading)
        grid_changed = refresh_all or current != self._last_drawn
        draw_status = not self._fullscreen
        if not (refresh_all or grid_changed or draw_status):
            return
        with self.term.synchronized_output():
            if refresh_all:
                print(self.term.home + self.term.clear, end='')
                if draw_status:
                    print(self._draw_rule(), end='')
            if grid_changed:
                print(self._draw_grid(), end='')
                # Save state after draw (loading may have changed)
                self._last_drawn = (self.viewport_y, self.viewport_x, self.rule,
                                    self._random_mode, self._loading)
            if draw_status:
                self._draw_status()

    def _move_auto(self, dt):
        self._turn_timer -= dt
        if self._turn_timer <= 0:
            self._auto_angle += random.uniform(-0.5, 0.5)
            self._turn_timer = random.uniform(0.5, 2.0)
        # Oscillate speed in sine wave
        t = time.monotonic() - self._start_time
        phase = (t / self._oscillation_rate) * 2 * math.pi
        speed = self._speed_min + (self._speed_max - self._speed_min) * \
            (0.5 + 0.5 * math.sin(phase))
        self._auto_xy[0] += math.cos(self._auto_angle) * speed * dt
        self._auto_xy[1] += math.sin(self._auto_angle) * speed * dt
        dx, dy = int(round(self._auto_xy[0])), int(round(self._auto_xy[1]))
        if dx or dy:
            self._auto_xy[0] -= dx
            self._auto_xy[1] -= dy
        return dx, dy

    def _autoscroll_tick(self, dt):
        now = time.monotonic()
        cache = self.engine._cache
        if self._rule_change_secs > 0 and now - self._last_rule_change >= self._rule_change_secs:
            available = [r for r in self._rules if r in cache and r != self.rule]
            if available:
                new_rule = random.choice(available)
                if new_rule != self.rule:
                    self._last_rule_change, self.rule = now, new_rule
                    self._refresh_all = True
                    return True
        dx, dy = self._move_auto(dt)
        if dx or dy:
            old_x, old_y = self.viewport_x, self.viewport_y
            self.viewport_x += dx
            self.viewport_y += dy
            self._constrain()
            if dx and self.viewport_x == old_x:
                self._auto_angle = math.pi - self._auto_angle
            if dy and self.viewport_y == old_y:
                self._auto_angle = -self._auto_angle
            return True
        return False

    def _process_input(self, inp):
        s = str(inp)
        if s == '\x03':
            self.engine.stop()
            return True
        if s == '\x13':
            self._autoscroll = not self._autoscroll
            if self._autoscroll:
                self._auto_angle, self._auto_xy = random.uniform(0, 2 * math.pi), [0.0, 0.0]
                self._last_rule_change = time.monotonic()
            self._dirty = True
            return False
        if s == '\x12':  # ^R - random initial state
            self._random_mode = True
            self.engine.start([self.rule] + [r for r in self._rules if r != self.rule], True)
            self._dirty = self._refresh_all = True
            return False
        if s == '\x04':  # ^D - default initial state
            self._random_mode = False
            self.engine.start([self.rule] + [r for r in self._rules if r != self.rule], False)
            self._dirty = self._refresh_all = True
            return False
        if s == '\x06':  # Ctrl+F - toggle fullscreen
            self._fullscreen = not self._fullscreen
            self._dirty = self._refresh_all = True
            return False
        if s == '\x0c':  # Ctrl+L - force redraw
            self._dirty = self._refresh_all = True
            return False
        key = inp.name if inp.is_sequence else str(inp)
        if self._autoscroll and (key in self.STEP_MOVES or key in self.PAGE_MOVES or inp == ' '):
            self._autoscroll, self._dirty = False, True
            return False
        if inp in '12345678':
            self._set_rule(self.rule ^ (1 << (int(inp) - 1)))
        elif inp in '][':
            delta = 1 if inp == ']' else -1
            if self.rule in self._rules:
                idx = (self._rules.index(self.rule) + delta) % len(self._rules)
            else:
                idx = 0 if delta > 0 else -1
            self._set_rule(self._rules[idx])
        elif inp in '{}':
            self._set_rule(self.rule + (1 if inp == '}' else -1))
        elif key in self.STEP_MOVES:
            dx, dy = self.STEP_MOVES[key]
            self.viewport_x += dx
            self.viewport_y += dy
            self._constrain()
            self._dirty = True
        elif key in self.PAGE_MOVES:
            bx, by = self.PAGE_MOVES[key]
            step = max(20, self._page()[1] // 2)
            self.viewport_x += bx * step
            self.viewport_y += by * step
            self._constrain()
            self._dirty = True
        elif inp.name == 'KEY_HOME':
            self.viewport_y, self._dirty = 0, True
            self._constrain()
        elif inp.name == 'KEY_END':
            self.viewport_y, self._dirty = self.engine.max_rows - self._page()[0], True
            self._constrain()
        elif inp.name in ('KEY_SHOME', 'KEY_SHIFT_HOME'):
            self.viewport_x, self._dirty = 0, True
        elif inp.name in ('KEY_SEND', 'KEY_SHIFT_END'):
            self.viewport_x, self._dirty = self.engine.width - self._page()[1], True
        return False

    def run(self):
        self.engine.start([self.rule] +
                          [r for r in self._rules if r != self.rule], self._random_mode)
        if sys.platform != 'win32':
            signal.signal(signal.SIGWINCH, lambda *_: (setattr(self, '_dirty', True),
                          setattr(self, '_refresh_all', True)))
        with self.term.raw(), self.term.fullscreen(), self.term.hidden_cursor(), \
                self.term.notify_on_resize():
            while True:
                self.engine.tick()
                cache = self.engine._cache
                if self._loading and self.rule in cache:
                    self._loading = False  # Data arrived, force grid change detection
                    self._dirty = True
                dt = time.monotonic() - self._last_frame
                self._last_frame = time.monotonic()
                if self._autoscroll and self._autoscroll_tick(dt):
                    self._dirty = True
                if self._dirty:
                    self._constrain()
                    self._draw(self._refresh_all)
                    self._dirty = self._refresh_all = False
                    if self._loading:
                        self.engine.ensure_rule(self.rule)
                inp = self.term.inkey(timeout=0.033)
                if inp:
                    self.term.flushinp()
                    if inp.name == 'RESIZE_EVENT':
                        self._dirty = self._refresh_all = True
                    elif self._process_input(inp):
                        break


def main():
    random.seed()
    p = argparse.ArgumentParser(description="Interactive Cellular Automata Viewer",
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('--autoscroll', action='store_true', help='auto-pan mode')
    p.add_argument('--fullscreen', action='store_true', help='fullscreen mode (no UI)')
    p.add_argument('--foreground-color1', default='mediumpurple2',
                   help='foreground color for empty cells (X11 name or #hex)')
    p.add_argument('--foreground-color2', default='goldenrod1',
                   help='foreground color for filled cells (X11 name or #hex)')
    p.add_argument('--background-color', default='black',
                   help='background color (X11 name or #hex)')
    p.add_argument('--palette-path', choices=['short', 'long'], default='short',
                   help='hue interpolation path (short=direct, long=around)')
    p.add_argument('--width', type=int, default=1000, help='simulation width (max rows)')
    p.add_argument('--rule-change-seconds', type=float, default=20,
                   help='auto-change rule interval (0 to disable)')
    p.add_argument('--rules', type=lambda v: [int(x) % 256 for x in v.split(',')] if v else None,
                   help='comma-separated list of rules to cycle through')
    p.add_argument('--default-state', action='store_true',
                   help='use single-cell center initial state instead of random')
    p.add_argument('--speed-range', default='12-80',
                   help='min-max speed range for autoscroll oscillation')
    p.add_argument('--oscillation-rate', type=float, default=20,
                   help='seconds for one full speed oscillation cycle')
    a = p.parse_args()
    speed_range = tuple(int(x) for x in a.speed_range.split('-'))
    engine = CAEngine(max_rows=a.width)
    Pager(term=Terminal(), engine=engine,
          autoscroll=a.autoscroll,
          rule_change_secs=a.rule_change_seconds,
          rules=a.rules or INTERESTING_RULES,
          fullscreen=a.fullscreen,
          fg_color1=a.foreground_color1,
          fg_color2=a.foreground_color2,
          bg_color=a.background_color,
          palette_path=a.palette_path,
          default_state=a.default_state,
          speed_range=speed_range,
          oscillation_rate=a.oscillation_rate).run()
    engine.stop()


if __name__ == '__main__':
    main()
