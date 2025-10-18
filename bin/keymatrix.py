#!/usr/bin/env python
"""
Keyboard event display tool.

Usage:
- Press any keys to see their properties
- Ctrl+C: Exit
"""
# std imports
import sys
import functools
from collections import deque

# local
from blessed import Terminal


def render_header(term: Terminal) -> int:
    """
    Render the header section.

    Returns number of rows used.
    """
    header = ["Press ^C to quit."]

    # Display, Separators, headers, return row count
    echo = functools.partial(print, end=term.clear_eol + '\r\n', flush=False)
    echo(term.home, end='')
    echo('-' * term.width)
    row_count = 1
    for line in header:
        echo(line)
        row_count += 1
    echo('-' * term.width, flush=True)
    row_count += 1
    return row_count


def render_keymatrix(term: Terminal, n_header_rows: int, raw_sequences: deque,
                     formatted_events: deque) -> None:
    """Render the key matrix display with raw sequences bar and formatted table."""
    # Calculate bar width (1/3 of terminal width)
    bar_width = term.width // 3
    bar_y = n_header_rows + 3

    # remove raw sequences tracked until they fit
    def _fmt(i, sequence):
        if sequence.is_sequence:
            rs = repr(str(sequence))
        else:
            rs = repr(sequence)
        if rs.startswith("'") and rs.endswith("'"):
            rs = rs.strip("'")
        elif rs.startswith('"') and rs.endswith('"'):
            rs = rs.strip('"')

        if i % 2 == 0:
            return term.reverse(rs)
        return rs

    while True:
        bar_content = ''.join(_fmt(len(raw_sequences) - i, sequence)
                              for i, sequence in
                              enumerate(raw_sequences))
        if term.length(bar_content) < bar_width:
            break
        raw_sequences.popleft()

    echo = functools.partial(print, end=term.clear_eol + '\r\n', flush=False)
    bar_line = ' ' * ((term.width // 3) - 3) + f'[ {bar_content} ]'
    echo(term.move_yx(bar_y - 3, 0))
    echo()
    echo(bar_line)
    echo()

    # Calculate available space for formatted events table
    max_event_rows = term.height - bar_y - 5

    # Render formatted events table
    events_to_display = list(formatted_events)[-max_event_rows:]

    echo()
    echo(f"{'value':<6} {'repr':<20} {'Name':<25} extra:")
    echo()
    for event_line in events_to_display:
        echo(event_line)
    echo('', end=term.clear_eos, flush=True)


def format_key_event(term, keystroke) -> str:
    """Format a key event for columnar display."""
    # Build columns: sequence | value | name | modifiers/mode_values
    value_repr = repr(keystroke.value)[:6]
    seq_repr = repr(str(keystroke))[:20]
    name_repr = repr(keystroke.name)[:25]

    modifiers = []
    for modifier_name in (
            # possible with most terminals
            'shift', 'alt', 'ctrl',
            # kitty, only
            'super', 'hyper', 'meta'):
        if getattr(keystroke, f'_{modifier_name}'):
            modifiers.append(modifier_name.upper())
    extra = f'{"+".join(modifiers)}'

    trim_mode = max(10, term.width - 25 - 20 - 6 - 3)
    return f"{value_repr:<6} {seq_repr:<20} {name_repr:<25} {extra[:trim_mode]}"


def main():
    """Main application orchestrator."""
    term = Terminal()

    # Key event storage
    raw_sequences = deque(maxlen=100)  # Store raw sequences
    formatted_events = deque(maxlen=50)  # Store formatted event lines

    # Ensure clean input state
    inp = term.flushinp(0.1)
    if inp:
        formatted_events.append(f"Flushed input: {inp!r}")

    # Main interaction loop
    input_mode = term.cbreak if '--cbreak' in sys.argv else term.raw
    oldsize = (term.height, term.width)
    with input_mode(), term.fullscreen():
        n_header_rows = 0

        # Initial full render
        n_header_rows = render_header(term)
        render_keymatrix(term, n_header_rows, raw_sequences, formatted_events)

        do_exit = False
        while not do_exit:
            # Handle user input
            inp = term.inkey()

            if inp.name == 'KEY_CTRL_C':
                do_exit = True

            if inp:
                raw_sequences.append(inp)
                formatted_events.append(format_key_event(term, inp))

            # If screen was resized or CTRL^L pressed, re-render header
            if (oldsize != (term.height, term.width) or inp.name == 'KEY_CTRL_L'):
                n_header_rows = render_header(term)
                oldsize = (term.height, term.width)

            # Always render key matrix (efficient, only updates changed area)
            render_keymatrix(term, n_header_rows, raw_sequences, formatted_events)


if __name__ == '__main__':
    main()
