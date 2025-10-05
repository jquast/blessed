#!/usr/bin/env python
"""
Advanced keyboard and special modes interaction example.

Usage:
- F1-F11: Toggle DEC private modes (bracketed paste, mouse, etc.)
- Shift+F1-F5: Toggle Kitty keyboard protocol flags
- Ctrl+C: Exit

All modes that elicit responses are activated for demonstration.
"""
# std imports
import sys
from typing import Dict, List, Tuple, Optional, Any
import functools
from collections import deque

# local
from blessed import Terminal, DecPrivateMode


class DecModeManager:
    """Manages DEC Private Mode probing, tracking, and toggling."""

    def __init__(self, term: Terminal, test_modes: Tuple[DecPrivateMode, ...]):
        self.term = term
        self.test_modes = test_modes
        self.available_modes: Dict[DecPrivateMode, bool] = {}
        self.active_contexts: Dict[DecPrivateMode, Any] = {}

    def probe(self, timeout: float = 1.0) -> List[str]:
        """Probe terminal for DEC mode support and return log messages."""
        messages = ["Checking DEC Private Mode status:"]

        for mode in self.test_modes:
            mode = DecPrivateMode(mode)
            response = self.term.get_dec_mode(mode, timeout=timeout)

            if not response.is_supported():
                messages.append(f'{mode}: no support')
                continue

            status = "enabled" if response.is_enabled() else "disabled"
            if response.is_permanent():
                messages.append(f'{mode}: permanent, enabled={response.is_enabled()}')
                continue

            messages.append(f'{mode}: {status}')
            self.available_modes[mode] = response.is_enabled()

        if not self.available_modes:
            messages.append("All DEC Private Modes fail support")

        return messages

    def entries(self) -> List[Tuple[DecPrivateMode, bool]]:
        """Return list of (mode, enabled) pairs for display."""
        return [(mode, enabled) for mode, enabled in self.available_modes.items()]

    def toggle_by_index(self, f_key_idx: int) -> str:
        """Toggle DEC mode by F-key index and return log message."""
        if f_key_idx >= len(self.test_modes):
            return ""

        mode = self.test_modes[f_key_idx]
        if mode not in self.available_modes:
            return ""

        old_enabled = self.available_modes[mode]
        new_enabled = not old_enabled
        self.available_modes[mode] = new_enabled

        try:
            if new_enabled and mode not in self.active_contexts:
                cm = self.term.dec_modes_enabled(mode)
                cm.__enter__()
                self.active_contexts[mode] = cm
                return f'Enabled {mode}'
            elif not new_enabled and mode in self.active_contexts:
                cm = self.active_contexts.pop(mode)
                cm.__exit__(None, None, None)
                return f'Disabled {mode}'
        except Exception as e:
            self.available_modes[mode] = old_enabled
            return f'Failed to toggle {mode}: {e}'

        return ""

    def toggle_keynames(self) -> List[str]:
        """Return list of key names that toggle DEC modes."""
        return [f'KEY_F{i}' for i in range(1, 12)]

    def get_index_by_key(self, key_name: str) -> int:
        """Convert key name to toggle index."""
        f_num = int(key_name.split('_')[-1][1:])
        return f_num - 1

    def cleanup(self) -> None:
        """Clean up all active context managers."""
        for cm in self.active_contexts.values():
            try:
                cm.__exit__(None, None, None)
            except BaseException:
                pass


class KittyKeyboardManager:
    """Manages Kitty keyboard protocol probing and toggling."""

    def __init__(self, term: Terminal):
        self.term = term
        self.kitty_flags: Optional[Any] = None
        self.active_context: Optional[Any] = None
        self.flag_masks = [1, 2, 4, 8, 16]

    def probe(self, timeout: float = 1.0) -> Tuple[bool, Optional[str], Optional[str]]:
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


def get_test_modes() -> Tuple[DecPrivateMode, ...]:
    """Return the tuple of DEC private modes to test."""
    return (
        DecPrivateMode.DECCKM,
        DecPrivateMode.DECSCNM,
        DecPrivateMode.DECKANAM,
        DecPrivateMode.MOUSE_REPORT_CLICK,
        DecPrivateMode.MOUSE_ALL_MOTION,
        DecPrivateMode.FOCUS_IN_OUT_EVENTS,
        DecPrivateMode.MOUSE_EXTENDED_SGR,
        DecPrivateMode.MOUSE_SGR_PIXELS,
        DecPrivateMode.META_SENDS_ESC,
        DecPrivateMode.ALT_SENDS_ESC,
        DecPrivateMode.BRACKETED_PASTE
    )


def render_header(term: Terminal, dec_manager: DecModeManager, kitty_manager:
                  KittyKeyboardManager) -> int:
    """
    Render the header section.

    Returns number of rows used.
    """
    header = ["Press ^C to quit."]
    if kitty_manager.kitty_flags is not None:
        header.append(f"{kitty_manager.repr_flags()} [Shift+F1..F5] to toggle")

    # Display DEC modes table
    if dec_manager.entries():
        maxlen = max(len(repr(m)) for m, _ in dec_manager.entries())
        for mode, enabled in dec_manager.entries():
            idx = dec_manager.test_modes.index(mode)
            status = "  IS  " if enabled else "IS NOT"
            f_key = f"F{idx + 1}"
            mode_description = (
                f"{repr(mode):<{maxlen}} "
                f"{term.reverse(status)} Enabled, "
                f"[{term.reverse(f_key)}] toggles")
            header.append(mode_description)

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

    if keystroke.mode and int(keystroke.mode) > 0:
        extra = f'{keystroke.mode}:{keystroke.mode_values()!r}'
    else:
        extra = f'modifiers?={keystroke.modifiers!r}'

    trim_mode = max(10, term.width - 25 - 20 - 6 - 3)
    return f"{value_repr:<6} {seq_repr:<20} {name_repr:<25} {extra[:trim_mode]}"


def main():
    """Main application orchestrator."""
    term = Terminal()
    test_modes = get_test_modes()

    # Initialize managers

    # Key event storage
    raw_sequences = deque(maxlen=100)  # Store raw sequences
    formatted_events = deque(maxlen=50)  # Store formatted event lines

    # Probe terminal capabilities
    dec_manager = DecModeManager(term, test_modes)
    formatted_events.extend(dec_manager.probe(timeout=1.0))

    kitty_manager = KittyKeyboardManager(term)
    formatted_events.extend(kitty_manager.probe(timeout=1.0))

    # Ensure clean input state
    inp = term.flushinp(0.1)
    assert not inp, "Expected no input after automatic sequence negotiation"

    # Main interaction loop
    input_mode = term.cbreak if '--cbreak' in sys.argv else term.raw
    oldsize = (term.height, term.width)
    with input_mode(), term.fullscreen():
        message = None
        n_header_rows = 0

        # Initial full render
        n_header_rows = render_header(term, dec_manager, kitty_manager)
        render_keymatrix(term, n_header_rows, raw_sequences, formatted_events)

        do_exit = False
        while not do_exit:
            # Handle user input
            inp = term.inkey(0.1)
            for mgr in (dec_manager, kitty_manager):
                if inp.name in mgr.toggle_keynames():
                    index = mgr.get_index_by_key(inp.name)
                    message = mgr.toggle_by_index(index)
                    break

            if inp.name == 'KEY_CTRL_C':
                do_exit = True

            if inp:
                raw_sequences.append(inp)
                formatted_events.append(format_key_event(term, inp))

            # If mode was toggled, screen was resized, or CTRL^L pressed,
            # re-render header
            if (message
                    or oldsize != (term.height, term.width)
                    or inp.name == 'KEY_CTRL_L'):
                if message:
                    message = None
                    formatted_events.append(f">> {message}")
                n_header_rows = render_header(term, dec_manager, kitty_manager)
                oldsize = (term.height, term.width)

            # Always render key matrix (efficient, only updates changed area)
            render_keymatrix(term, n_header_rows, raw_sequences, formatted_events)

        dec_manager.cleanup()
        kitty_manager.cleanup()


if __name__ == '__main__':
    main()
