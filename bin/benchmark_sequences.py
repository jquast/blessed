#!/usr/bin/env python
"""Benchmark blessed text manipulation functions."""
import timeit
from blessed import Terminal


def main():
    term = Terminal(force_styling=True)

    test_cases = {
        'ascii': "Hello world " * 100,
        'ansi': (term.red("Hello") + " " + term.bold("world") + " ") * 50,
        'cjk': "コンニチハ セカイ " * 50,
        'emoji_zwj': "\U0001F468\u200D\U0001F469\u200D\U0001F467 " * 30,
        'emoji_vs16': "\u2764\uFE0F " * 100,
    }

    for name, text in test_cases.items():
        print(f"\n=== {name} ({len(text)} chars) ===")

        t = timeit.timeit(lambda txt=text: term.length(txt), number=1000)
        print(f"  length:     {t * 1000:.2f}ms/1000")

        t = timeit.timeit(lambda txt=text: term.ljust(txt, 300), number=1000)
        print(f"  ljust:      {t * 1000:.2f}ms/1000")

        t = timeit.timeit(lambda txt=text: term.rjust(txt, 300), number=1000)
        print(f"  rjust:      {t * 1000:.2f}ms/1000")

        t = timeit.timeit(lambda txt=text: term.center(txt, 300), number=1000)
        print(f"  center:     {t * 1000:.2f}ms/1000")

        t = timeit.timeit(lambda txt=text: term.truncate(txt, 50), number=1000)
        print(f"  truncate:   {t * 1000:.2f}ms/1000")

        t = timeit.timeit(lambda txt=text: term.strip_seqs(txt), number=1000)
        print(f"  strip_seqs: {t * 1000:.2f}ms/1000")

        t = timeit.timeit(lambda txt=text: term.wrap(txt, 40), number=100)
        print(f"  wrap:       {t * 1000:.2f}ms/100")


if __name__ == '__main__':
    main()
