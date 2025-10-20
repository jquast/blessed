#!/usr/bin/env python
"""
Kitty keyboard protocol interaction example.

Usage:
- Shift+F1-F5: Toggle Kitty keyboard protocol flags
- Ctrl+C: Exit
"""
# std imports
import sys
from typing import List, Optional, Any
import functools
from collections import deque

# local
from blessed import Terminal


class KittyKeyboardManager:
    """Manages Kitty keyboard protocol probing and toggling."""

    def __init__(self, term: Terminal):
        self.term = term
        self.kitty_flags: Optional[Any] = None
        self.active_context: Optional[Any] = None
        self.flag_masks = [1, 2, 4, 8, 16]

    def probe(self, timeout: float = 1.0) -> List[str]:
        """Probe kitty keyboard support."""
        self.kitty_flags = self.term.get_kitty_keyboard_state(timeout=timeout)

        if self.kitty_flags is None:
            return ["Kitty Keyboard Protocol not supported!"]

        return [f'Kitty Keyboard Protocol is {self.kitty_flags!r}']

    def toggle_by_index(self, shift_f_idx: int) -> str:
        """Toggle kitty flag by Shift+F index and return log message."""
        if self.kitty_flags is None or shift_f_idx >= len(self.flag_masks):
            return ""

        mask = self.flag_masks[shift_f_idx]
        self.kitty_flags.value ^= mask

        try:
            if self.active_context is not None:
                self.active_context.__exit__(None, None, None)
                self.active_context = None

            args = self.kitty_flags.make_arguments()
            if any(args.values()):
                self.active_context = self.term.enable_kitty_keyboard(**args)
                self.active_context.__enter__()
                return f'Kitty: {self.kitty_flags!r}'
            else:
                return 'Kitty: disabled'
        except Exception as e:
            return f'Kitty error: {e}'

    def header_msg(self) -> str:
        return f"{self.repr_flags()} [Shift+F1..F5] to toggle"

    def repr_flags(self) -> str:
        """Return string representation of current flags."""
        return f"{self.kitty_flags!r}" if self.kitty_flags else ""

    def toggle_keynames(self) -> List[str]:
        """Return list of key names that toggle Kitty keyboard flags."""
        return [f'KEY_SHIFT_F{i}' for i in range(1, 6)]

    def get_index_by_key(self, key_name: str) -> int:
        """Convert key name to toggle index."""
        f_num = int(key_name.split('_')[-1][1:])
        return f_num - 1

    def cleanup(self) -> None:
        """Clean up active context manager."""
        if self.active_context is not None:
            try:
                self.active_context.__exit__(None, None, None)
            except BaseException:
                pass


def render_header(term: Terminal, kitty_manager: KittyKeyboardManager) -> int:
    """
    Render the header section.

    Returns number of rows used.
    """
    header = ["Press ^C to quit."]
    if kitty_manager.kitty_flags is not None:
        header.append(f"{kitty_manager.repr_flags()} [Shift+F1..F5] to toggle")

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

    events = []
    for event_name in ('pressed', 'released', 'repeated'):
        if getattr(keystroke, event_name):
            events.append(event_name)
    assert len(events) == 1, events
    modifiers = []
    for modifier_name in (
            # possible with most terminals
            'shift', 'alt', 'ctrl',
            # kitty, only
            'super', 'hyper', 'meta', 'caps_lock', 'num_lock'):
        if getattr(keystroke, f'_{modifier_name}'):
            modifiers.append(modifier_name.upper())
    extra = f'{events[0]} {"+".join(modifiers)}'

    trim_mode = max(10, term.width - 25 - 20 - 6 - 3)
    return f"{value_repr:<6} {seq_repr:<20} {name_repr:<25} {extra[:trim_mode]}"


def main():
    """Main application orchestrator."""
    term = Terminal()

    # Key event storage
    raw_sequences = deque(maxlen=100)  # Store raw sequences
    formatted_events = deque(maxlen=50)  # Store formatted event lines

    # Probe terminal capabilities
    kitty_manager = KittyKeyboardManager(term)
    formatted_events.extend(kitty_manager.probe(timeout=1.0))

    # Ensure clean input state
    inp = term.flushinp(0.1)
    if inp:
        formatted_events.append(f"WARNING: Flushed input: {inp!r}")

    # Main interaction loop
    input_mode = term.cbreak if '--cbreak' in sys.argv else term.raw
    oldsize = (term.height, term.width)
    with input_mode(), term.fullscreen():
        message = None
        n_header_rows = 0

        # Initial full render
        n_header_rows = render_header(term, kitty_manager)
        render_keymatrix(term, n_header_rows, raw_sequences, formatted_events)

        do_exit = False
        while not do_exit:
            # Handle user input
            inp = term.inkey()

            # Check for toggle keys
            if inp.name in kitty_manager.toggle_keynames():
                index = kitty_manager.get_index_by_key(inp.name)
                message = kitty_manager.toggle_by_index(index)

            if inp.name == 'KEY_CTRL_C':
                do_exit = True

            if inp:
                raw_sequences.append(inp)
                formatted_events.append(format_key_event(term, inp))

            # If mode was toggled, screen was resized, or CTRL^L pressed, re-render header
            if (message
                    or oldsize != (term.height, term.width)
                    or inp.name == 'KEY_CTRL_L'):
                if message:
                    formatted_events.append(f">> {message}")
                    message = None
                n_header_rows = render_header(term, kitty_manager)
                oldsize = (term.height, term.width)

            # re-render the entire "key matrix" after any keypress
            render_keymatrix(term, n_header_rows, raw_sequences, formatted_events)

        kitty_manager.cleanup()


if __name__ == '__main__':
    main()
