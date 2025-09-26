#!/usr/bin/env python
"""
Advanced keyboard and special modes interaction example.

Usage:
- F1-F10: Toggle DEC private modes (bracketed paste, mouse, etc.)
- Shift+F1-F5: Toggle Kitty keyboard protocol flags
- Ctrl+C: Exit

All modes that elicit responses are activated for demonstration.
"""
# std imports
import sys
from typing import Dict, List, Tuple, Optional, Any

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
        messages = []
        messages.append("Checking DEC Private Mode status:")
        
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
                # Enable mode
                cm = self.term.dec_modes_enabled(mode)
                cm.__enter__()
                self.active_contexts[mode] = cm
                return f'Enabled {mode}'
            elif not new_enabled and mode in self.active_contexts:
                # Disable mode
                cm = self.active_contexts.pop(mode)
                cm.__exit__(None, None, None)
                return f'Disabled {mode}'
        except Exception as e:
            # Rollback on failure
            self.available_modes[mode] = old_enabled
            return f'Failed to toggle {mode}: {e}'
        
        return ""
    
    def cleanup(self) -> None:
        """Clean up all active context managers."""
        for cm in self.active_contexts.values():
            try:
                cm.__exit__(None, None, None)
            except:
                pass


class KittyKeyboardManager:
    """Manages Kitty keyboard protocol probing and toggling."""
    
    def __init__(self, term: Terminal):
        self.term = term
        self.kitty_flags: Optional[Any] = None
        self.active_context: Optional[Any] = None
        self.flag_masks = [1, 2, 4, 8, 16]  # disambiguate, report_events, report_alternates, report_all_keys, report_text
    
    def probe(self, timeout: float = 1.0) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Probe kitty keyboard support.
        Returns (supported, header_line, initial_log_message).
        """
        self.kitty_flags = self.term.get_kitty_keyboard_state(timeout=timeout)
        
        if self.kitty_flags is None:
            return False, "Kitty Keyboard Protocol not supported!", None
        
        header = f"Kitty Keyboard Protocol supported: {self.kitty_flags!r} press [Shift+F1..F5] to toggle!"
        initial_log = f'{self.kitty_flags!r}'
        return True, header, initial_log
    
    def toggle_by_index(self, shift_f_idx: int) -> str:
        """Toggle kitty flag by Shift+F index and return log message."""
        if self.kitty_flags is None or shift_f_idx >= len(self.flag_masks):
            return ""
        
        # Toggle the bit using XOR
        mask = self.flag_masks[shift_f_idx]
        self.kitty_flags.value ^= mask
        
        try:
            # Exit current context if active
            if self.active_context is not None:
                self.active_context.__exit__(None, None, None)
                self.active_context = None
            
            # Apply new configuration if any flags are enabled
            args = self.kitty_flags.make_arguments()
            if any(args.values()):
                self.active_context = self.term.enable_kitty_keyboard(**args)
                self.active_context.__enter__()
                return f'Updated Kitty keyboard: {self.kitty_flags!r}'
            else:
                return 'Disabled Kitty keyboard protocol'
        except Exception as e:
            return f'Error updating Kitty keyboard: {e}'
    
    def repr_flags(self) -> str:
        """Return string representation of current flags."""
        return f"{self.kitty_flags!r}" if self.kitty_flags else ""
    
    def cleanup(self) -> None:
        """Clean up active context manager."""
        if self.active_context is not None:
            try:
                self.active_context.__exit__(None, None, None)
            except:
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
        DecPrivateMode.META_SENDS_ESC,
        DecPrivateMode.ALT_SENDS_ESC,
        DecPrivateMode.BRACKETED_PASTE
    )


def render_screen(term: Terminal, header: List[str], dec_manager: DecModeManager, 
                  kitty_manager: KittyKeyboardManager, buffer: List[str]) -> None:
    """Render the complete screen display, showing latest buffer lines only."""
    print(term.home, end='', flush=False)
    
    # Kitty header line
    if kitty_manager.kitty_flags is not None:
        print(f"{kitty_manager.repr_flags()} press [Shift+F1..F5] to toggle!", end='\r\n', flush=False)

    # Display DEC modes table
    maxlen = max(len(repr(m)) for m, _ in dec_manager.entries()) if dec_manager.entries() else 20
    for mode, enabled in dec_manager.entries():
        idx = dec_manager.test_modes.index(mode)
        status = "  IS  " if enabled else "IS NOT"
        f_key = f"F{idx + 1}"
        print(f"{repr(mode):<{maxlen}} "
              f"{term.reverse(status)} Enabled, "
              f"toggle using {f_key}: {mode.long_description}",
              end=term.normal + term.clear_eol + '\r\n', flush=False)
    
    # Separator and header
    print('-' * term.width, end='\r\n', flush=False)
    print((term.clear_eol + '\r\n').join(header), end=term.clear_eol + '\r\n', flush=False)
    print('-' * term.width, end='\r\n', flush=False)
    
    # Calculate available space for buffer
    reserved_rows = (3 +  # separators and header block
                    len(dec_manager.entries()) +
                    len(header) + 
                    (1 if kitty_manager.kitty_flags is not None else 0))
    max_rows = max(term.height - reserved_rows, 0)
    
    # Wrap all buffer lines and show only the latest that fit
    if max_rows > 0:
        wrapped_lines = []
        for line in buffer:
            wrapped_lines.extend(term.wrap(line, width=term.width))
        
        # Show only the last max_rows lines
        display_lines = wrapped_lines[-max_rows:] if len(wrapped_lines) > max_rows else wrapped_lines
        
        for line in display_lines:
            print(line, end=term.clear_eol + '\r\n', flush=False)
    
    print('', end=term.clear_eos, flush=True)


def log_key_event(key: Any, buffer: List[str]) -> None:
    """Log key event to buffer."""
    if key.mode and int(key.mode) > 0:
        buffer.append(f'{repr(str(key))} .name={key.name} get_event_values()={repr(key.get_event_values())}')
    else:
        buffer.append(f'{repr(str(key))} .name={key.name} .modifiers={key.modifiers}')


def drain_pending_input(term: Terminal) -> None:
    """Flush any pending input and assert none was expected."""
    badseqs = ''
    while term.kbhit(0.1):
        badseqs += term.inkey()
    if badseqs:
        badseqs_msg = ("Expected *no input* on start, did you press a keyboard key? "
                      "or, is it a bad automatic Terminal response?? Please verify!")
        assert False, (badseqs_msg, repr(badseqs))


def main():
    """Main application orchestrator."""
    term = Terminal()
    test_modes = get_test_modes()
    
    # Initialize managers
    dec_manager = DecModeManager(term, test_modes)
    kitty_manager = KittyKeyboardManager(term)
    
    # State
    header = ["Press ^C to quit."]
    buffer = []
    do_exit = False
    
    # Probe terminal capabilities
    mode_messages = dec_manager.probe(timeout=1.0)
    buffer.extend(mode_messages)
    if not dec_manager.available_modes:
        header.append(f"All DEC Private Modes {term.bold_red('fail support')}")
    
    supported, kitty_header, kitty_log = kitty_manager.probe(timeout=1.0)
    if kitty_header:
        header.append(kitty_header)
    if kitty_log:
        buffer.append(kitty_log)
    
    # Ensure clean input state
    drain_pending_input(term)

    # Main interaction loop
    with term.cbreak():
        while True:
            render_screen(term, header, dec_manager, kitty_manager, buffer)

            if do_exit:
                dec_manager.cleanup()
                kitty_manager.cleanup()
                exit(0)

            # Handle user input
            key = term.inkey()
            
            # Handle F1-F10 for DEC mode toggles
            if key.name and key.name.startswith('KEY_F') and not key.name.startswith('KEY_SHIFT_'):
                f_num = int(key.name.split('_')[-1][1:])  # Extract number from KEY_F1, KEY_F2, etc.
                if 1 <= f_num <= 10:
                    f_key_idx = f_num - 1  # Convert F1->0, F2->1, etc.
                    message = dec_manager.toggle_by_index(f_key_idx)
                    if message:
                        buffer.append(message)
            
            # Handle Shift+F1-F5 for Kitty keyboard flag toggles
            elif key.name and key.name.startswith('KEY_SHIFT_F'):
                f_num = int(key.name.split('_')[-1][1:])  # Extract number from KEY_SHIFT_F1, etc.
                if 1 <= f_num <= 5:
                    shift_f_idx = f_num - 1  # Convert Shift+F1->0, Shift+F2->1, etc.
                    message = kitty_manager.toggle_by_index(shift_f_idx)
                    if message:
                        buffer.append(message)
            
            elif key.name == 'CTRL_C':
                do_exit = True
            
            # Log all key events
            log_key_event(key, buffer)


if __name__ == '__main__':
    main()
