#!/usr/bin/env python
"""Example of Terminal.inkey(capture_cpr=True)."""
import blessed
import time

term = blessed.Terminal()


def msg(term, txt):
    print(term.move_yx(term.height // 2, 0) + term.center(txt))


with term.cbreak(), term.fullscreen():
    print(term.home + term.clear)
    interval = 0.5
    cpr_last_sent = time.time() - interval
    while True:
        stime = time.time()
        if stime - cpr_last_sent > interval:
            print(term.u7 or '\x1b[6n', flush=True, end='')
            cpr_last_sent = time.time()
        inp = term.inkey(timeout=0.1, capture_cpr=True)
        print(inp)
        if inp.name == 'CPR_RESPONSE':
            elapsed_ms = (time.time() - cpr_last_sent) * 1000
            msg(term, f'CPR {elapsed_ms:3.2f}ms rtt; yx={inp.cpr_yx}')
        elif inp:
            msg(term, f"Keystroke: {inp!r} !")
