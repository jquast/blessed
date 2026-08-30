"""Performance benchmarks for blessed Sequence methods."""
# local
from blessed.keyboard import _read_until
from .accessories import TestTerminal


# Test data (raw strings, no Terminal dependency at module level)
TEXT_ASCII = "Hello world " * 100
TEXT_CJK = "コンニチハ セカイ " * 50
TEXT_EMOJI_ZWJ = "\U0001F468\u200D\U0001F469\u200D\U0001F467 " * 30
TEXT_EMOJI_VS16 = "\u2764\uFE0F " * 100


def _make_ansi_text(term):
    """Create ANSI-styled test text."""
    return (term.red("Hello, ") + " " + term.bold("world!") +
            term.color_rgb(255, 244, 233)("!")) * 50


# length() benchmarks

def test_length_ascii(benchmark):
    """Benchmark length() with ASCII text."""
    term = TestTerminal(force_styling=True)
    benchmark(term.length, TEXT_ASCII)


def test_length_ansi(benchmark):
    """Benchmark length() with ANSI-styled text."""
    term = TestTerminal(force_styling=True)
    text = _make_ansi_text(term)
    benchmark(term.length, text)


def test_length_cjk(benchmark):
    """Benchmark length() with CJK characters."""
    term = TestTerminal(force_styling=True)
    benchmark(term.length, TEXT_CJK)


def test_length_emoji_zwj(benchmark):
    """Benchmark length() with ZWJ emoji sequences."""
    term = TestTerminal(force_styling=True)
    benchmark(term.length, TEXT_EMOJI_ZWJ)


def test_length_emoji_vs16(benchmark):
    """Benchmark length() with VS-16 emoji."""
    term = TestTerminal(force_styling=True)
    benchmark(term.length, TEXT_EMOJI_VS16)


# ljust() benchmarks

def test_ljust_ascii(benchmark):
    """Benchmark ljust() with ASCII text."""
    term = TestTerminal(force_styling=True)
    benchmark(term.ljust, TEXT_ASCII, 1500)


def test_ljust_ansi(benchmark):
    """Benchmark ljust() with ANSI-styled text."""
    term = TestTerminal(force_styling=True)
    text = _make_ansi_text(term)
    benchmark(term.ljust, text, 1500)


def test_ljust_cjk(benchmark):
    """Benchmark ljust() with CJK characters."""
    term = TestTerminal(force_styling=True)
    benchmark(term.ljust, TEXT_CJK, 1500)


def test_ljust_emoji_zwj(benchmark):
    """Benchmark ljust() with ZWJ emoji sequences."""
    term = TestTerminal(force_styling=True)
    benchmark(term.ljust, TEXT_EMOJI_ZWJ, 1500)


# rjust() benchmarks

def test_rjust_ascii(benchmark):
    """Benchmark rjust() with ASCII text."""
    term = TestTerminal(force_styling=True)
    benchmark(term.rjust, TEXT_ASCII, 1500)


def test_rjust_ansi(benchmark):
    """Benchmark rjust() with ANSI-styled text."""
    term = TestTerminal(force_styling=True)
    text = _make_ansi_text(term)
    benchmark(term.rjust, text, 1500)


def test_rjust_cjk(benchmark):
    """Benchmark rjust() with CJK characters."""
    term = TestTerminal(force_styling=True)
    benchmark(term.rjust, TEXT_CJK, 1500)


def test_rjust_emoji_zwj(benchmark):
    """Benchmark rjust() with ZWJ emoji sequences."""
    term = TestTerminal(force_styling=True)
    benchmark(term.rjust, TEXT_EMOJI_ZWJ, 1500)


# center() benchmarks

def test_center_ascii(benchmark):
    """Benchmark center() with ASCII text."""
    term = TestTerminal(force_styling=True)
    benchmark(term.center, TEXT_ASCII, 1500)


def test_center_ansi(benchmark):
    """Benchmark center() with ANSI-styled text."""
    term = TestTerminal(force_styling=True)
    text = _make_ansi_text(term)
    benchmark(term.center, text, 1500)


def test_center_cjk(benchmark):
    """Benchmark center() with CJK characters."""
    term = TestTerminal(force_styling=True)
    benchmark(term.center, TEXT_CJK, 1500)


def test_center_emoji_zwj(benchmark):
    """Benchmark center() with ZWJ emoji sequences."""
    term = TestTerminal(force_styling=True)
    benchmark(term.center, TEXT_EMOJI_ZWJ, 1500)


# truncate() benchmarks

def test_truncate_ascii(benchmark):
    """Benchmark truncate() with ASCII text."""
    term = TestTerminal(force_styling=True)
    benchmark(term.truncate, TEXT_ASCII, 50)


def test_truncate_ansi(benchmark):
    """Benchmark truncate() with ANSI-styled text."""
    term = TestTerminal(force_styling=True)
    text = _make_ansi_text(term)
    benchmark(term.truncate, text, 50)


def test_truncate_cjk(benchmark):
    """Benchmark truncate() with CJK characters."""
    term = TestTerminal(force_styling=True)
    benchmark(term.truncate, TEXT_CJK, 50)


def test_truncate_emoji_zwj(benchmark):
    """Benchmark truncate() with ZWJ emoji sequences."""
    term = TestTerminal(force_styling=True)
    benchmark(term.truncate, TEXT_EMOJI_ZWJ, 50)


# strip_seqs() benchmarks

def test_strip_seqs_ascii(benchmark):
    """Benchmark strip_seqs() with ASCII text."""
    term = TestTerminal(force_styling=True)
    benchmark(term.strip_seqs, TEXT_ASCII)


def test_strip_seqs_ansi(benchmark):
    """Benchmark strip_seqs() with ANSI-styled text."""
    term = TestTerminal(force_styling=True)
    text = _make_ansi_text(term)
    benchmark(term.strip_seqs, text)


def test_strip_seqs_complex(benchmark):
    """Benchmark strip_seqs() with complex ANSI codes."""
    term = TestTerminal(force_styling=True)
    text = '\x1b[38;2;255;150;100mWARN\x1b[0m: \x1b[1mBold\x1b[0m \x1b[4mUnderline\x1b[0m' * 20
    benchmark(term.strip_seqs, text)


# wrap() benchmarks

def test_wrap_ascii(benchmark):
    """Benchmark wrap() with ASCII text."""
    term = TestTerminal(force_styling=True)
    benchmark(term.wrap, TEXT_ASCII, 40)


def test_wrap_ansi(benchmark):
    """Benchmark wrap() with ANSI-styled text."""
    term = TestTerminal(force_styling=True)
    text = _make_ansi_text(term)
    benchmark(term.wrap, text, 40)


def test_wrap_cjk(benchmark):
    """Benchmark wrap() with CJK characters."""
    term = TestTerminal(force_styling=True)
    benchmark(term.wrap, TEXT_CJK, 40)


def test_wrap_emoji_zwj(benchmark):
    """Benchmark wrap() with ZWJ emoji sequences."""
    term = TestTerminal(force_styling=True)
    benchmark(term.wrap, TEXT_EMOJI_ZWJ, 40)


def test_move_yx_full_screen(benchmark):
    """Benchmark move_yx() once per cell of a full screen."""
    def _full_screen_moves(term):
        return ''.join(term.move_yx(y, x) for y in range(24) for x in range(80))
    term = TestTerminal(force_styling=True)
    benchmark(_full_screen_moves, term)


def test_color_256(benchmark):
    """Benchmark color() across all indexes of a 256-color terminal."""
    def _all_256_colors(term):
        return ''.join(term.color(idx) for idx in range(256))
    term = TestTerminal(force_styling=True)
    benchmark(_all_256_colors, term)


# _read_until() benchmarks


def test_read_until_long_reply(benchmark):
    """Benchmark _read_until() digesting a multi-kilobyte query reply."""
    long_query_reply = (
        ''.join(f'\x1bP1+r{idx:04x}=31\x1b\\' for idx in range(1024)) +
        '\x1b[10;20R')

    def _read_buffered(term, reply):
        term.ungetch(reply)
        return _read_until(term, r'\d+;\d+R', timeout=1.0)

    term = TestTerminal(force_styling=True)
    benchmark(_read_buffered, term, long_query_reply)
