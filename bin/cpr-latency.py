#!/usr/bin/env python
"""CPR (Cursor Position Report) round-trip latency benchmark."""
# this dool was designed to discover slow response times from VTE-based terminals.
#
# theory is that some terminals respond to CPR at different times, depending on the time it was
# received, or how many bytes are also received in output, is sometimes in some separate lockstep/
# buffer/event signal, or poll at 10ms or so, depending on its arrival -- so this test exercises
# many different timings and "burst" cycle measurements.
#
# this hypothesis was proven correct -- gnome terminal processed automatic responses at most 60Hz,
# and because of ping-pong response/delay, often less than 30Hz (~16-32ms) delay for each and every
# automatic response.
import collections
import random
import sys
import time
import timeit

from blessed import Terminal

# Unicode block elements (eighths) for smooth progress bars
_BLOCKS = ' ▏▎▍▌▋▊▉█'
_BURST_COUNT = 80


def _stats(samples):
    """Return (min, avg, max, mdev) for a non-empty sequence."""
    if not samples:
        return 0.0, 0.0, 0.0, 0.0
    n = len(samples)
    avg = sum(samples) / n
    return min(samples), avg, max(samples), sum(abs(s - avg) for s in samples) / n


def _fmt_time(seconds):
    """Format seconds to compact human-readable string."""
    if seconds < 1e-6:
        return f'{seconds * 1e9:.1f}ns'
    if seconds < 1e-3:
        return f'{seconds * 1e6:.1f}us'
    if seconds < 1:
        return f'{seconds * 1e3:.1f}ms'
    return f'{seconds:.2f}s'


def _bar(min_val, avg, max_val, width=38):
    """Draw a unicode-block indicator showing avg position in [min, max] range."""
    if max_val <= min_val:
        mid = width // 2
        return '\u2591' * mid + '\u258c' + '\u2591' * (width - mid - 1)

    pos = (avg - min_val) / (max_val - min_val) * width
    full = int(pos)
    frac = pos - full
    eighths = int(frac * 8)

    result = '\u2588' * full
    if eighths > 0:
        result += _BLOCKS[eighths]
    result += '\u2591' * max(0, width - len(result))
    return result[:width]


class CprBenchmark:
    """CPR latency benchmark with three measurement strategies."""

    def __init__(self, term, maxlen=10000):
        """
        Initialize benchmark with a Terminal instance.

        :arg Terminal term: Terminal instance for I/O and queries.
        """
        self.term = term
        self.samples_raw = collections.deque(maxlen=maxlen)
        self.samples_jittered = collections.deque(maxlen=maxlen)
        self.samples_burst = collections.deque(maxlen=maxlen)
        self.samples_stepladder = collections.deque(maxlen=maxlen)
        self.samples_overhead = collections.deque(maxlen=maxlen)
        self.software_version = term.get_software_version()
        self._stepladder_index = 0
        self._stepladder_direction = 1
        self.paused = False

    def measure_raw(self):
        """Single ``get_location()`` ping-pong, no artificial delay."""
        t0 = timeit.default_timer()
        y, x = self.term.get_location()
        elapsed = timeit.default_timer() - t0
        if (y, x) != (-1, -1):
            self.samples_raw.append(elapsed)
        return elapsed

    def measure_jittered(self):
        """``get_location()`` preceded by random sleep in [0, avg_all] range."""
        all_samples = (list(self.samples_raw) + list(self.samples_jittered)
                       + list(self.samples_burst))
        if all_samples:
            jitter_max = sum(all_samples) / len(all_samples)
        else:
            jitter_max = 0.0
        time.sleep(random.uniform(0, jitter_max))

        t0 = timeit.default_timer()
        y, x = self.term.get_location()
        elapsed = timeit.default_timer() - t0
        if (y, x) != (-1, -1):
            self.samples_jittered.append(elapsed)
        return elapsed

    def measure_burst(self):
        """N rapid ``get_location()`` calls, recording per-call wall-clock time."""
        t_start = timeit.default_timer()
        for _ in range(_BURST_COUNT):
            self.term.get_location()
        elapsed = timeit.default_timer() - t_start
        self.samples_burst.append(elapsed / _BURST_COUNT)
        return elapsed

    def measure_stepladder(self):
        """
        ``get_location()`` preceded by a linearly stepped delay.

        The delay cycles from 0 to *max_rtt* in 1 ms increments and back, producing a bar that grows
        and shrinks across the latency window.
        """
        all_samples = (list(self.samples_raw) + list(self.samples_jittered)
                       + list(self.samples_burst))
        max_rtt = max(all_samples) if all_samples else 0.010
        max_step = max(1, int(max_rtt * 1000))

        step_delay = (self._stepladder_index % max_step) / 1000.0
        time.sleep(step_delay)

        t0 = timeit.default_timer()
        y, x = self.term.get_location()
        elapsed = timeit.default_timer() - t0
        if (y, x) != (-1, -1):
            self.samples_stepladder.append(elapsed)

        self._stepladder_index += self._stepladder_direction
        if self._stepladder_index >= max_step - 1:
            self._stepladder_direction = -1
        elif self._stepladder_index <= 0:
            self._stepladder_direction = 1

        return elapsed

    def _render_panel(self, samples, heading=None, jitter_label=None):
        """
        Render one measurement panel.

        Returns list of lines.
        """
        s_min, s_avg, s_max, s_mdev = _stats(samples)

        if heading is None:
            heading = (
                f'Cursor Position Report: + {jitter_label} jitter'
                if jitter_label
                else 'Cursor Position Report: Ping-Pong'
            )

        return [
            f'{heading}'
            f'{" " * 6}samples: {len(samples):>5}',
            f'  min {_fmt_time(s_min):>7} '
            f'\u2502{_bar(s_min, s_avg, s_max)}\u2502 '
            f'max {_fmt_time(s_max):>7}',
            f'{" " * 13}avg {_fmt_time(s_avg):>7}  '
            f'mdev {_fmt_time(s_mdev):>7}',
        ]

    def render(self):
        """Display benchmark results on the terminal, overwriting lines in place."""
        sv = self.software_version
        if sv is not None:
            maybe_version = f', version {sv.version}' if sv.version else ''
            sv_heading = f'{sv.name}{maybe_version}'
        else:
            sv_heading = '(unknown terminal)'

        lines = []

        lines.append(sv_heading)
        lines.append('-' * min(len(sv_heading), self.term.width))
        lines.append('')

        lines.extend(self._render_panel(self.samples_raw))
        lines.append('')

        lines.append(
            f'Cursor Position Report: burst ({_BURST_COUNT} calls)'
            f'{" " * 6}samples: {len(self.samples_burst):>5}')
        s_min, s_avg, s_max, s_mdev = _stats(self.samples_burst)
        lines.append(
            f'  min {_fmt_time(s_min):>7} '
            f'\u2502{_bar(s_min, s_avg, s_max)}\u2502 '
            f'max {_fmt_time(s_max):>7}')
        lines.append(
            f'{" " * 13}avg {_fmt_time(s_avg):>7}  '
            f'mdev {_fmt_time(s_mdev):>7}  '
            f'(per-call)')
        lines.append('')

        all_s = (list(self.samples_raw) + list(self.samples_jittered)
                 + list(self.samples_burst))
        max_rtt = max(all_s) if all_s else 0.010
        max_step = max(1, int(max_rtt * 1000))
        step_delay = (self._stepladder_index % max_step) / 1000.0

        last_sample = self.samples_stepladder[-1] if self.samples_stepladder else None
        last_str = _fmt_time(last_sample) if last_sample is not None else '-'

        lines.append(
            f'Cursor Position Report: stepped'
            f'{" " * 6}samples: {len(self.samples_stepladder):>5}'
            f'  last: {last_str:>7}')
        lines.append(
            f'  step {_fmt_time(step_delay):>7} '
            f'\u2502{_bar(step_delay, step_delay, max_rtt)}\u2502 '
            f'range {_fmt_time(max_rtt):>7}')
        s_min, s_avg, s_max, s_mdev = _stats(self.samples_stepladder)
        lines.append(
            f'{" " * 13}avg {_fmt_time(s_avg):>7}  '
            f'mdev {_fmt_time(s_mdev):>7}')
        lines.append('')

        if all_s:
            jlabel = _fmt_time(sum(all_s) / len(all_s))
        else:
            jlabel = '0s'
        lines.extend(self._render_panel(self.samples_jittered, jitter_label=jlabel))
        lines.append('')

        lines.extend(self._render_panel(self.samples_overhead,
                                        heading='overhead (non-measurement)'))
        lines.append('')

        hint = 'PAUSED  ' if self.paused else ''
        hint += 'q:quit  space:pause'
        lines.append(hint)

        for row, line in enumerate(lines):
            print(self.term.move_yx(row, 0) + self.term.ljust(line))


def main():
    """Program entry point."""
    term = Terminal()
    if not term.is_a_tty:
        sys.exit('This program requires a terminal.')

    bench = CprBenchmark(term)

    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        while True:
            if not bench.paused:
                t_iter = timeit.default_timer()
                t_raw = bench.measure_raw()
                t_burst = bench.measure_burst()
                t_step = bench.measure_stepladder()
                t_jit = bench.measure_jittered()
                bench.render()
                t_meas = t_raw + t_burst + t_step + t_jit
                bench.samples_overhead.append(
                    timeit.default_timer() - t_iter - t_meas)

            inp = term.inkey(timeout=(0.1 if bench.paused else 0))
            if inp == 'q':
                break
            if inp == ' ':
                bench.paused = not bench.paused
                bench.render()


if __name__ == '__main__':
    main()
