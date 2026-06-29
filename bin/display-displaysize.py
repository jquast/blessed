#!/usr/bin/env python
"""Display all queryable terminal window size dimensions."""
# I wrote this while working on kitty/sixel development across terminals, and the theory that the
# "window decoration" size could be determined by the difference of TIOCGWINSZ and XTWINOPS14H. It's
# actually a bit true, it can also discover whether scrollbar is enabled, but not very consistently
# across terminal emulators. That's the point of the script, to show these differences!
#
# pylint: disable=protected-access,too-many-locals
#         access to internal query methods; many dimension variables

import argparse
import contextlib
import signal
import sys
import timeit
import threading

from blessed import Terminal
from blessed.keyboard import TERMINAL_QUERY_TIMEOUT_SECONDS


@contextlib.contextmanager
def elapsed_timer():
    """Timer pattern, from https://stackoverflow.com/a/30024601."""
    start = timeit.default_timer()

    def elapser():
        return timeit.default_timer() - start

    # pylint: disable=unnecessary-lambda
    yield lambda: elapser()


def _fmt_px(value, default='--'):
    """Format pixel dimension, returning *default* if <= 0 or None."""
    if value is not None and value > 0:
        return str(value)
    return default


def gather_sizes(term):
    """Query terminal and return (rows, cols, rows_data, label_w)."""
    rows, cols = term.height, term.width

    with elapsed_timer() as t_ioctl:
        winsize = term._height_and_width()
    t_ioctl = t_ioctl()
    tiocgwinsz_h = winsize.ws_ypixel
    tiocgwinsz_w = winsize.ws_xpixel

    with elapsed_timer() as t_14t:
        xtwinops14_h, xtwinops14_w = term._get_xtwinops_window_size(
            TERMINAL_QUERY_TIMEOUT_SECONDS)
    t_14t = t_14t()

    with elapsed_timer() as t_16t:
        cell_h, cell_w = term.get_cell_height_and_width()
    t_16t = t_16t()
    cell_text_h = cell_h * rows if cell_h > 0 else -1
    cell_text_w = cell_w * cols if cell_w > 0 else -1

    with elapsed_timer() as t_sixel:
        sixel_h, sixel_w = term._get_xtsmgraphics(TERMINAL_QUERY_TIMEOUT_SECONDS)
    t_sixel = t_sixel()

    with elapsed_timer() as t_resolved:
        resolved_h, resolved_w = term.get_sixel_height_and_width()
    t_resolved = t_resolved()

    deco_h = (tiocgwinsz_h - xtwinops14_h
              if tiocgwinsz_h and tiocgwinsz_h > 0 and xtwinops14_h > 0
              else None)
    deco_w = (tiocgwinsz_w - xtwinops14_w
              if tiocgwinsz_w and tiocgwinsz_w > 0 and xtwinops14_w > 0
              else None)

    def _star(h, w):
        return ' *' if (h, w) == (resolved_h, resolved_w) and h > 0 else ''

    rows_data = [
        ('TIOCGWINSZ (ioctl)', tiocgwinsz_h, tiocgwinsz_w, t_ioctl,
         f'{_star(tiocgwinsz_h, tiocgwinsz_w)}'),
        ('XTWINOPS 14t (text area)', xtwinops14_h, xtwinops14_w, t_14t,
         f'{_star(xtwinops14_h, xtwinops14_w)}'),
        ('XTWINOPS 16t (cell size)', cell_h, cell_w, t_16t,
         f'{_star(cell_h, cell_w)}'),
    ]
    if cell_h > 0 and cell_w > 0:
        rows_data.append(
            ('  -> text area (cell x rows/cols)', cell_text_h, cell_text_w, t_16t,
             f'{_star(cell_text_h, cell_text_w)}'))
    rows_data.append(
        ('XTSMGRAPHICS (sixel)', sixel_h, sixel_w, t_sixel,
         f'{_star(sixel_h, sixel_w)}'))
    if deco_h is not None or deco_w is not None:
        rows_data.append(
            ('Est. decoration (ioctl - 14t)', deco_h, deco_w, 0.0, ''))

    rows_data.append(
        ('  resolved by get_sixel_height_and_width()', resolved_h, resolved_w, t_resolved,
         f'{_star(resolved_h, resolved_w)}'))

    label_w = max((len(r[0]) for r in rows_data), default=0)
    label_w += 2  # indent
    return rows, cols, rows_data, label_w


def display_sizes(term, rows, cols, rows_data, label_w):
    """Print size information table."""
    hdr_label = 'Source / query'
    hdr_h = 'Height'
    hdr_w = 'Width'
    hdr_t = 'Time'

    label_w = max(label_w, len(hdr_label))

    def _fmt_time(elapsed):
        if elapsed < 0.001:
            return f'{elapsed * 1_000_000:.0f}us'
        if elapsed < 1.0:
            return f'{elapsed * 1000:.1f}ms'
        return f'{elapsed:.2f}s'

    def _row(label, h, w, elapsed, note=''):
        return (f'  {label.ljust(label_w)} '
                f'{_fmt_px(h).rjust(6)}  '
                f'{_fmt_px(w).rjust(6)}  '
                f'{_fmt_time(elapsed).rjust(8)}  '
                f'{note}')

    print(f'Terminal.kind: {term.bold(term.kind or "unknown")}')
    print(f'Character cells: {rows} rows x {cols} cols')
    print(f'Query timeout: {TERMINAL_QUERY_TIMEOUT_SECONDS}s')
    print()
    print(f'  {term.bold(hdr_label.ljust(label_w))} '
          f'{term.bold(hdr_h.rjust(6))}  '
          f'{term.bold(hdr_w.rjust(6))}  '
          f'{term.bold(hdr_t.rjust(8))}')
    for label, h, w, elapsed, note in rows_data:
        print(_row(label, h, w, elapsed, note))
    print()
    print(term.bold('*') + ' matches get_sixel_height_and_width()')


def interactive_mode(term):
    """Run interactive display, refreshing on resize."""
    _resize = threading.Event()

    def on_resize(*_):
        _resize.set()

    if not term.does_inband_resize():
        signal.signal(signal.SIGWINCH, on_resize)

    with term.fullscreen(), term.cbreak(), term.notify_on_resize(), term.hidden_cursor():
        settle_time = 0.05

        def redraw():
            rows, cols, rows_data, label_w = gather_sizes(term)
            with term.synchronized_output():
                print(term.home + term.clear)
                display_sizes(term, rows, cols, rows_data, label_w)
                print()
                print("press 'q' to quit.")

        redraw()
        while True:
            inp = term.inkey(timeout=0.1)
            if inp == 'q':
                break
            if inp.name == 'RESIZE_EVENT' or _resize.is_set():
                _resize.clear()
                # Debounce: wait for resize storm to settle
                while True:
                    inp2 = term.inkey(timeout=settle_time)
                    if inp2.name == 'RESIZE_EVENT' or _resize.is_set():
                        _resize.clear()
                        continue
                    if inp2 == 'q':
                        return
                    break
                redraw()


def main():
    """Program entry point."""
    parser = argparse.ArgumentParser(
        description='Display terminal window size dimensions.')
    parser.add_argument('-i', '--interactive',
                        action='store_true',
                        help='Interactive mode: fullscreen display refreshed on resize')
    args = parser.parse_args()

    term = Terminal()

    if args.interactive:
        sys.exit(interactive_mode(term))

    rows, cols, rows_data, label_w = gather_sizes(term)
    display_sizes(term, rows, cols, rows_data, label_w)


if __name__ == '__main__':
    main()
