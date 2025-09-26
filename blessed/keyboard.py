"""Sub-module providing 'keyboard awareness'."""

# std imports
import os
import re
import time
import platform
import functools
from collections import OrderedDict, namedtuple

# local
from blessed._compat import TextType, unicode_chr
from blessed.dec_modes import DecPrivateMode

# isort: off
# curses
if platform.system() == 'Windows':
    # pylint: disable=import-error
    import jinxed as curses
    from jinxed.has_key import _capability_names as capability_names
else:
    import curses
    from curses.has_key import _capability_names as capability_names

# DEC event namedtuples
BracketedPasteEvent = namedtuple('BracketedPasteEvent', 'text')
MouseSGREvent = namedtuple(
    'MouseSGREvent',
    'button x y is_release shift meta ctrl is_drag is_wheel')
MouseLegacyEvent = namedtuple('MouseLegacyEvent',
                              'button x y is_release shift meta ctrl is_motion is_drag is_wheel')
FocusEvent = namedtuple('FocusEvent', 'gained')
SyncEvent = namedtuple('SyncEvent', 'begin')


# Kitty keyboard protocol and xterm ModifyOtherKeys namedtuples
KittyKeyEvent = namedtuple('KittyKeyEvent', 
                          'unicode_key shifted_key base_key modifiers event_type text_codepoints')
ModifyOtherKeysEvent = namedtuple('ModifyOtherKeysEvent', 'key modifiers')

# Legacy CSI modifier key support
LegacyCSIKeyEvent = namedtuple('LegacyCSIKeyEvent', 'kind key_id modifiers')
LEGACY_CSI_MODIFIERS_PATTERN = re.compile(r'\x1b\[1;(?P<mod>\d+)(?P<final>[ABCDEFHPQRS])~?')
LEGACY_CSI_TILDE_PATTERN = re.compile(r'\x1b\[(?P<key_num>\d+);(?P<mod>\d+)~')
LEGACY_SS3_FKEYS_PATTERN = re.compile(r'\x1bO(?P<mod>\d)(?P<final>[PQRS])')
DEC_EVENT_PATTERN = functools.namedtuple("DEC_EVENT_PATTERN", ["mode", "pattern"])

# DEC event patterns - compiled regexes with metadata
DEC_EVENT_PATTERNS = [
    # Bracketed paste - must be first due to greedy nature; this is more closely
    # married to ESC_DELAY than it first appears -- the full payload and final
    # marker must be received under ESC_DELAY seconds.
    DEC_EVENT_PATTERN(mode=2004, pattern=(
        re.compile(r'\x1b\[200~(?P<text>.*?)\x1b\[201~', re.DOTALL))),
    # Mouse SGR (1006) - recommended format
    DEC_EVENT_PATTERN(mode=1006, pattern=(
        re.compile(r'\x1b\[(?P<b>\d+);(?P<x>\d+);(?P<y>\d+)(?P<type>[mM])'))),
    # Legacy mouse (X10/1000/1002/1003) - CSI M followed by 3 bytes
    DEC_EVENT_PATTERN(mode=1000, pattern=re.compile(r'\x1b\[M(?P<cb>.)(?P<cx>.)(?P<cy>.)')),
    # Focus tracking
    DEC_EVENT_PATTERN(mode=1004, pattern=re.compile(r'\x1b\[(?P<io>[IO])'))
]

# Match Kitty keyboard protocol: ESC [ ... u
# Pattern covers all variations of the protocol
KITTY_KB_PROTOCOL_PATTERN = re.compile(
    r'\x1b\[(?P<unicode_key>\d+)'
    r'(?::(?P<shifted_key>\d*))?'
    r'(?::(?P<base_key>\d*))?'
    r'(?:;(?P<modifiers>\d+))?'
    r'(?::(?P<event_type>\d+))?'
    r'(?:;(?P<text_codepoints>[\d:]+))?'
    r'u')
 
# Match ModifyOtherKeys pattern: ESC [ 27 ; modifiers ; key [~]
MODIFY_PATTERN = re.compile(r'\x1b\[27;(?P<modifiers>\d+);(?P<key>\d+)(?P<tilde>~?)') 
CTRL_CHAR_MAP = {'@': 0, '[': 27, '\\': 28, ']': 29, '^': 30, '_': 31, '?': 127}
CTRL_CODE_MAP = {v: k for k, v in CTRL_CHAR_MAP.items()}



class Keystroke(TextType):
    """
    A unicode-derived class for describing a single keystroke.

    A class instance describes a single keystroke received on input,
    which may contain multiple characters as a multibyte sequence,
    which is indicated by properties :attr:`is_sequence` returning
    ``True``.

    When the string is a known sequence, :attr:`code` matches terminal
    class attributes for comparison, such as ``term.KEY_LEFT``.

    The string-name of the sequence, such as ``u'KEY_LEFT'`` is accessed
    by property :attr:`name`, and is used by the :meth:`__repr__` method
    to display a human-readable form of the Keystroke this class
    instance represents. It may otherwise by joined, split, or evaluated
    just as as any other unicode string.

    For DEC private mode events (such as bracketed paste, mouse tracking,
    focus events), the :attr:`event_mode` property returns the associated
    :class:`DecPrivateMode` enum value, and :meth:`get_event_values` returns
    a structured namedtuple with parsed event data.
    """

    def __new__(cls, ucs='', code=None, name=None, mode=None, match=None):
        """Class constructor."""
        new = TextType.__new__(cls, ucs)
        new._name = name
        new._code = code
        new._mode = mode  # DEC private mode integer
        new._match = match  # regex match object
        new._modifiers = cls._infer_modifiers(ucs, mode, match)
        return new

    @staticmethod
    def _infer_modifiers(ucs, mode, match):
        """
        Infer modifiers from keystroke data.
        
        Returns modifiers in Kitty format: 1 + bitwise OR of modifier flags
        """
        # Kitty protocol
        if mode is not None and mode < 0 and match is not None:
            return match.modifiers
       
        # Legacy sequences starting with ESC
        if len(ucs) == 2 and ucs[0] == '\x1b':
            char_code = ord(ucs[1])
            
            # Special C0 controls that should be Alt-only per legacy spec
            # These represent common Alt+key combinations that are unambiguous
            if char_code in (0x0d, 0x1b, 0x7f, 0x09):  # Enter, Escape, DEL, Tab
                return 1 + 0b10  # 1 + alt flag = 3
            
            # Other control characters represent Ctrl+Alt combinations 
            # (ESC prefix for Alt + control char from Ctrl+letter mapping)
            if 0 <= char_code <= 31 or char_code == 127:
                return 1 + 0b10 + 0b100  # 1 + alt flag + ctrl flag = 7
            
            # Printable characters are Alt-only
            if 32 <= char_code <= 126:
                return 1 + 0b10  # 1 + alt flag = 3
        
        # Legacy Ctrl: single control character
        if len(ucs) == 1:
            char_code = ord(ucs)
            if 0 <= char_code <= 31 or char_code == 127:
                return 1 + 0b100  # 1 + ctrl flag = 5
        
        # No modifiers detected
        return 1

    @property
    def is_sequence(self):
        """Whether the value represents a multibyte sequence (bool)."""
        return self._code is not None or self._mode is not None or len(self) > 1

    def __repr__(self):
        """Docstring overwritten."""
        return (TextType.__repr__(self) if self._name is None else
                self._name)
    __repr__.__doc__ = TextType.__doc__

    @property
    def name(self):
        """
        String-name of key sequence, such as ``u'KEY_LEFT'`` (str).

        This is to be called to identify sequences, control characters, and any
        specially detected combination character, all others return None.
        """
        if self._name is not None:
            return self._name
        
        # Dynamic name generation for modified functional keys
        if (self._mode in (-1, -2, -3) and  # Modern protocols or legacy CSI modifiers
            self._code is not None and      # Has a base keycode
            self.modifiers > 1):            # Has modifiers
            
            # Get base key name from keycode
            keycodes = get_keyboard_codes()
            base_name = keycodes.get(self._code)
            if base_name and base_name.startswith('KEY_'):
                base_name = base_name[4:]  # Remove KEY_ prefix
                
                # Build modifier prefix using private properties
                mod_parts = []
                if self._shift:
                    mod_parts.append('SHIFT')
                if self._ctrl:
                    mod_parts.append('CTRL') 
                if self._alt:
                    mod_parts.append('ALT')
                if self._super:
                    mod_parts.append('SUPER')
                if self._hyper:
                    mod_parts.append('HYPER')
                if self._meta:
                    mod_parts.append('META')
                
                if mod_parts:
                    return f"KEY_{'_'.join(mod_parts)}_{base_name}"
        
        # Synthesize names for control and alt sequences
        if len(self) == 1:
            # Check for and return CTRL_ for control character
            char_code = ord(self)
            if 1 <= char_code <= 26:
                # Ctrl+A through Ctrl+Z
                return f'CTRL_{chr(char_code + ord("A") - 1)}'
            elif char_code in CTRL_CODE_MAP:
                return f'CTRL_{CTRL_CODE_MAP[char_code]}'
        elif len(self) == 2 and self[0] == '\x1b':
            # Check for ESC + control char - could be Alt-only or Ctrl+Alt based on modifiers
            char_code = ord(self[1])
            if 0 <= char_code <= 31 or char_code == 127:
                if 1 <= char_code <= 26:
                    # Ctrl+A through Ctrl+Z
                    symbol = chr(char_code + ord("A") - 1)
                elif char_code in CTRL_CODE_MAP:
                    symbol = CTRL_CODE_MAP[char_code]
                else:
                    symbol = None
                
                if symbol:
                    # Check if this is Alt-only or Ctrl+Alt based on modifiers
                    if self.modifiers == 3:  # Alt-only (1 + 2)
                        # Special C0 controls that are Alt-only
                        if char_code == 0x1b:  # ESC
                            return 'ALT_ESCAPE'
                        elif char_code == 0x7f:  # DEL
                            return 'ALT_BACKSPACE'  
                        elif char_code == 0x0d:  # CR
                            return 'ALT_ENTER'
                        elif char_code == 0x09:  # TAB
                            return 'ALT_TAB'
                        # Could extend with other Alt-only C0 names if needed
                    elif self.modifiers == 7:  # Ctrl+Alt (1 + 2 + 4)
                        return f'CTRL_ALT_{symbol}'
            
            # Check for and return ALT_ for "metaSendsEscape"
            if self[1].isprintable():
                ch = self[1]
                if ch.isalpha():
                    if ch.isupper():
                        return f'ALT_SHIFT_{ch}'
                    else:
                        return f'ALT_{ch.upper()}'
                else:
                    return f'ALT_{ch}'
            elif self[1] == '\x7f' and self.modifiers == 3:
                return f'ALT_BACKSPACE'

        return self._name

    @property
    def code(self):
        """Integer keycode value of multibyte sequence (int)."""
        return self._code

    @property
    def modifiers(self):
        """
        Modifier flags in Kitty keyboard protocol format.
        
        :rtype: int
        :returns: Kitty-style modifiers value (1 means no modifiers)
        
        The value is 1 + bitwise OR of modifier flags:
        - shift: 0b1 (1)
        - alt: 0b10 (2) 
        - ctrl: 0b100 (4)
        - super: 0b1000 (8)
        - hyper: 0b10000 (16)
        - meta: 0b100000 (32)
        - caps_lock: 0b1000000 (64)
        - num_lock: 0b10000000 (128)
        """
        return self._modifiers

    @property
    def modifiers_bits(self):
        """
        Raw modifier bit flags without the +1 offset.
        
        :rtype: int
        :returns: Raw bitwise OR of modifier flags (0 means no modifiers)
        """
        return max(0, self._modifiers - 1)

    @property
    def value(self):
        """
        The textual character represented by this keystroke.
        
        :rtype: str
        :returns: For text keys, returns the base character (ignoring modifiers).
                  For application keys and sequences, returns empty string ''.
        
        Examples:
        - Plain text: 'a', 'A', '1', ';', ' ', 'Ω', emoji with ZWJ sequences
        - Alt+printable: Alt+a → 'a', Alt+A → 'A' 
        - Ctrl+letter: Ctrl+A → 'a', Ctrl+Z → 'z'
        - Ctrl+symbol: Ctrl+@ → '@', Ctrl+? → '?', Ctrl+[ → '['
        - Control chars: '\t', '\n', '\x08', '\x1b' (for Enter/Tab/Backspace/Escape keycodes)
        - Application keys: KEY_UP, KEY_F1, etc. → ''
        - DEC events: bracketed paste, mouse, etc. → ''
        """
        # Plain printable characters - return as-is, supports Unicode and multi-codepoint text
        if len(self) == 1 and not self[0] == '\x1b' and self[0].isprintable():
            return TextType(self)
        
        # Alt sequences (ESC + printable) without Ctrl - return the printable part
        if (len(self) == 2 and self[0] == '\x1b' and 
            self._alt and not self._ctrl):
            return self[1]  # Return as-is (preserves case and supports Unicode)
        
        # Legacy Ctrl sequences - map back to base character
        if len(self) == 1 and self._ctrl and not self._alt:
            char_code = ord(self)
            
            # Ctrl+A through Ctrl+Z (codes 1-26) 
            if 1 <= char_code <= 26:
                return chr(char_code + ord('a') - 1)  # lowercase
            
            # Ctrl+symbol mappings
            if char_code in CTRL_CODE_MAP:
                return CTRL_CODE_MAP[char_code]
                
            # Don't return raw control chars - only map known ones
            # BS, TAB, LF, CR, ESC, DEL should return empty string for application keys
            # unless they have explicit keycodes handled below
        
        # Kitty protocol - extract text from codepoints or unicode_key
        if self._mode == -1 and hasattr(self._match, 'text_codepoints'):  # Kitty
            # Use text_codepoints if available (supports composed sequences like emoji+ZWJ)
            if self._match.text_codepoints:
                try:
                    return ''.join(chr(cp) for cp in self._match.text_codepoints)
                except (ValueError, OverflowError):
                    pass  # Fall through to unicode_key
            
            # Use unicode_key (supports any Unicode codepoint)
            if hasattr(self._match, 'unicode_key'):
                try:
                    return chr(self._match.unicode_key)
                except (ValueError, OverflowError):
                    pass  # Invalid codepoint
        
        # ModifyOtherKeys protocol - extract character from key
        elif self._mode == -2 and hasattr(self._match, 'key'):  # ModifyOtherKeys
            try:
                return chr(self._match.key)
            except (ValueError, OverflowError):
                pass  # Invalid codepoint
        
        # Application keys with known keycodes - map only essential control chars
        if self._code is not None:
            # Map only these essential control characters
            key_mappings = {
                curses.KEY_ENTER: '\n',      # Enter -> LF
                KEY_TAB: '\t',               # Tab -> Tab character
                curses.KEY_BACKSPACE: '\x08', # Backspace -> BS
                curses.KEY_EXIT: '\x1b',     # Escape -> ESC
            }
            
            mapped_char = key_mappings.get(self._code)
            if mapped_char is not None:
                return mapped_char
        
        # For all other cases (application keys, complex sequences), return empty string
        return ''

    # Private modifier flag properties (internal use)
    @property
    def _shift(self):
        """Whether the shift modifier is active."""
        return bool(self.modifiers_bits & 0b1)

    @property
    def _alt(self):
        """Whether the alt modifier is active."""
        return bool(self.modifiers_bits & 0b10)

    @property
    def _ctrl(self):
        """Whether the ctrl modifier is active."""
        return bool(self.modifiers_bits & 0b100)

    @property
    def _super(self):
        """Whether the super (Windows/Cmd) modifier is active."""
        return bool(self.modifiers_bits & 0b1000)

    @property
    def _hyper(self):
        """Whether the hyper modifier is active."""
        return bool(self.modifiers_bits & 0b10000)

    @property
    def _meta(self):
        """Whether the meta modifier is active."""
        return bool(self.modifiers_bits & 0b100000)

    @property
    def _caps_lock(self):
        """Whether caps lock is active."""
        return bool(self.modifiers_bits & 0b1000000)

    @property
    def _num_lock(self):
        """Whether num lock is active."""
        return bool(self.modifiers_bits & 0b10000000)

    @property 
    def event_mode(self):
        """
        DEC Private Mode associated with this keystroke, if any.

        :rtype: DecPrivateMode or None
        :returns: The :class:`~blessed.dec_modes.DecPrivateMode` enum value
            associated with this keystroke, or ``None`` if this is not a DEC mode event.
        """
        if self._mode is not None and self._mode > 0:
            return DecPrivateMode(self._mode)
        return None

    @property
    def mode(self):
        """
        DEC Private Mode associated with this keystroke, if any.

        :rtype: DecPrivateMode or None
        :returns: The :class:`~blessed.dec_modes.DecPrivateMode` enum value
            associated with this keystroke, or ``None`` if this is not a DEC mode event.
        """
        if self._mode is not None:
            return DecPrivateMode(self._mode)
        return None

    def get_event_values(self):
        """
        Return structured data for DEC private mode events.

        Returns a namedtuple with parsed event data for supported DEC modes:

        - ``BRACKETED_PASTE``: :class:`BracketedPasteEvent` with ``text`` field
        - ``MOUSE_TRACK_SGR``: :class:`MouseSGREvent` with button, coordinates, and modifier flags
        - ``MOUSE_REPORT_*``: :class:`MouseLegacyEvent` with button, coordinates, and modifier flags
        - ``FOCUS_EVENT_REPORTING``: :class:`FocusEvent` with ``gained`` boolean field

        :rtype: namedtuple
        :returns: Structured event data for this DEC mode event
        """
        return self.mode_values()

    def mode_values(self):
        """
        Return structured data for DEC private mode events.

        Returns a namedtuple with parsed event data for supported DEC modes:

        - ``BRACKETED_PASTE``: :class:`BracketedPasteEvent` with ``text`` field
        - ``MOUSE_TRACK_SGR``: :class:`MouseSGREvent` with button, coordinates, and modifier flags
        - ``MOUSE_REPORT_*``: :class:`MouseLegacyEvent` with button, coordinates, and modifier flags
        - ``FOCUS_EVENT_REPORTING``: :class:`FocusEvent` with ``gained`` boolean field

        :rtype: namedtuple
        :returns: Structured event data for this DEC mode event
        """
        if self._mode is None or self._match is None:
            raise TypeError("Should only call get_event_values() when event_mode is non-None")

        # Call appropriate private parser method based on mode
        fn_callback = {
            DecPrivateMode.MOUSE_REPORT_CLICK: self._parse_mouse_legacy,
            DecPrivateMode.MOUSE_HILITE_TRACKING: self._parse_mouse_legacy,
            DecPrivateMode.MOUSE_REPORT_DRAG: self._parse_mouse_legacy,
            DecPrivateMode.MOUSE_ALL_MOTION: self._parse_mouse_legacy,
            DecPrivateMode.FOCUS_IN_OUT_EVENTS: self._parse_focus,
            DecPrivateMode.MOUSE_EXTENDED_SGR: self._parse_mouse_sgr,
            DecPrivateMode.BRACKETED_PASTE: self._parse_bracketed_paste,
        }.get(self._mode)
        if fn_callback is None:
            # If you're reading this, you must have added a pattern to
            # DEC_EVENT_PATTERNS, now you should make a namedtuple and
            # write a brief parser and add it to the above list !
            raise TypeError(f"Unknown DEC mode {self._mode}")
        return fn_callback()

    def _parse_mouse_legacy(self):
        """Parse legacy mouse event (X10/1000/1002/1003) from stored regex match."""
        cb = ord(self._match.group('cb')) - 32
        cx = ord(self._match.group('cx')) - 32
        cy = ord(self._match.group('cy')) - 32

        # Extract button and modifiers from cb
        button = cb & 3
        is_release = (button == 3)
        if is_release:
            button = 0  # Release doesn't specify which button

        # Extract modifier flags
        shift = bool(cb & 4)
        meta = bool(cb & 8)
        ctrl = bool(cb & 16)

        # Extract motion/drag flags
        is_motion = bool(cb & 32)
        is_drag = is_motion and not is_release

        # Wheel events
        is_wheel = (cb >= 64)
        if is_wheel:
            button = cb - 64  # 0=wheel up, 1=wheel down

        return MouseLegacyEvent(
            button=button,
            x=cx,
            y=cy,
            is_release=is_release,
            shift=shift,
            meta=meta,
            ctrl=ctrl,
            is_motion=is_motion,
            is_drag=is_drag,
            is_wheel=is_wheel
        )

    def _parse_focus(self):
        """Parse focus event from stored regex match."""
        io = self._match.group('io')
        return FocusEvent(gained=(io == 'I'))

    def _parse_mouse_sgr(self):
        """Parse SGR mouse event from stored regex match."""
        b = int(self._match.group('b'))
        x = int(self._match.group('x'))
        y = int(self._match.group('y'))
        event_type = self._match.group('type')

        is_release = (event_type == 'm')

        # Extract modifiers from button code
        shift = bool(b & 4)
        meta = bool(b & 8)
        ctrl = bool(b & 16)

        # Extract event type flags
        is_drag = bool(b & 32)
        is_wheel = (b == 64 or b == 65)  # wheel up/down

        # Get base button (0-2 for left/middle/right, or 64-65 for wheel)
        button = b & 3 if not is_wheel else b

        return MouseSGREvent(
            button=button,
            x=x,
            y=y,
            is_release=is_release,
            shift=shift,
            meta=meta,
            ctrl=ctrl,
            is_drag=is_drag,
            is_wheel=is_wheel
        )

    def _parse_bracketed_paste(self):
        """Parse bracketed paste event from stored regex match."""
        return BracketedPasteEvent(text=self._match.group('text'))

    def __getattr__(self, attr):
        """
        Dynamic compound modifier predicates via __getattr__.
        
        Recognizes attributes starting with "is_" and parses underscore-separated
        modifier tokens to create dynamic predicate functions.
        
        :arg str attr: Attribute name being accessed
        :rtype: callable or raises AttributeError
        :returns: Callable predicate function for modifier combinations
        
        Examples:
        - ks.is_alt('a') - Alt-only with character 'a'
        - ks.is_ctrl_shift() - exactly Ctrl+Shift, no other modifiers
        - ks.is_meta_alt_ctrl_shift_hyper('z') - all those modifiers with 'z'
        """
        if attr.startswith('is_'):
            # Extract modifier tokens after 'is_'
            tokens_str = attr[3:]  # Remove 'is_' prefix
            if not tokens_str:
                raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")
            
            tokens = tokens_str.split('_')
            
            # Validate tokens - only allow known modifier names
            valid_tokens = {'shift', 'alt', 'ctrl', 'super', 'hyper', 'meta', 'caps_lock', 'num_lock'}
            invalid_tokens = [token for token in tokens if token not in valid_tokens]
            if invalid_tokens:
                raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}' "
                                   f"(invalid modifier tokens: {invalid_tokens})")
            
            # Return a predicate function that checks for the specified modifiers
            def modifier_predicate(char=None, ignore_case=True, exact=True):
                """
                Check if keystroke matches the specified modifier combination.
                
                :arg str char: Character to match (optional)
                :arg bool ignore_case: Whether to ignore case when comparing char (default True)
                :arg bool exact: Whether modifiers must match exactly vs. be subset (default True)
                :rtype: bool
                :returns: True if keystroke matches the specified criteria
                """
                # Build expected modifier bits from tokens
                expected_bits = 0
                for token in tokens:
                    if token == 'shift':
                        expected_bits |= 0b1
                    elif token == 'alt':
                        expected_bits |= 0b10
                    elif token == 'ctrl':
                        expected_bits |= 0b100
                    elif token == 'super':
                        expected_bits |= 0b1000
                    elif token == 'hyper':
                        expected_bits |= 0b10000
                    elif token == 'meta':
                        expected_bits |= 0b100000
                    elif token == 'caps_lock':
                        expected_bits |= 0b1000000
                    elif token == 'num_lock':
                        expected_bits |= 0b10000000
                
                # Get effective modifier bits (ignoring caps_lock/num_lock) for exact matching
                if exact:
                    effective_bits = self.modifiers_bits & ~(0b1000000 | 0b10000000)  # Strip lock bits
                    if effective_bits != expected_bits:
                        return False
                else:
                    # Subset check - all expected bits must be present
                    if (self.modifiers_bits & expected_bits) != expected_bits:
                        return False
                
                # If no character specified, just check modifiers
                if char is None:
                    return True
                
                # Check character match using same logic as value property
                keystroke_char = self.value
                
                # If value is empty or not a single printable character, can't match
                if not keystroke_char or len(keystroke_char) > 1 or not keystroke_char.isprintable():
                    return False
                
                # Compare characters
                if ignore_case:
                    return keystroke_char.lower() == char.lower()
                else:
                    return keystroke_char == char
            
            return modifier_predicate
        
        # If not an "is_" attribute, raise AttributeError as normal
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")

# Device Attributes (DA1) response representation
class DeviceAttribute(object):
    """
    Represents a terminal's Device Attributes (DA1) response.
    
    Device Attributes queries allow discovering terminal capabilities and type.
    The primary DA1 query sends CSI c and expects a response like:
    CSI ? Psc ; Ps1 ; Ps2 ; ... ; Psn c
    
    Where Psc is the service class (architectural class) and Ps1...Psn are
    supported extensions/capabilities.
    """
    
    def __init__(self, raw, service_class, extensions):
        """
        Initialize DeviceAttribute instance.
        
        :arg str raw: Original response string from terminal
        :arg int service_class: Service class number (first parameter)
        :arg set extensions: Set of extension numbers (remaining parameters)
        """
        self.raw = raw
        self.service_class = service_class
        self.extensions = set(extensions) if extensions else set()
    
    @property
    def supports_sixel(self):
        """
        Whether the terminal supports sixel graphics.
        
        :rtype: bool
        :returns: True if extension 4 (sixel) is present in device attributes
        """
        return 4 in self.extensions
    
    @classmethod
    def from_match(cls, match):
        """
        Create DeviceAttribute from regex match object.
        
        :arg re.Match match: Regex match object with groups for service_class and extensions
        :rtype: DeviceAttribute
        :returns: DeviceAttribute instance parsed from match
        """
        service_class = int(match.group(1))
        extensions_str = match.group(2)
        extensions = []
        
        if extensions_str:
            # Remove leading semicolon and split by semicolon
            ext_parts = extensions_str.lstrip(';').split(';')
            for part in ext_parts:
                if part.strip() and part.isdigit():
                    extensions.append(int(part.strip()))
        
        return cls(match.group(0), service_class, extensions)
    
    @classmethod 
    def from_string(cls, response_str):
        """
        Create DeviceAttribute by parsing response string.
        
        :arg str response_str: DA1 response string like '\x1b[?64;1;2;4;7c'
        :rtype: DeviceAttribute or None
        :returns: DeviceAttribute instance if parsing succeeds, None otherwise
        """
        # Match pattern: ESC [ ? service_class ; extension1 ; extension2 ; ... c
        import re
        pattern = re.compile(r'\x1b\[\?([0-9]+)((?:;[0-9]+)*)c')
        match = pattern.match(response_str)
        
        if match:
            return cls.from_match(match)
        return None
    
    def __repr__(self):
        """String representation of DeviceAttribute."""
        return ('DeviceAttribute(service_class={}, extensions={}, supports_sixel={})'
                .format(self.service_class, sorted(self.extensions), self.supports_sixel))
    
    def __eq__(self, other):
        """Check equality based on service class and extensions."""
        if isinstance(other, DeviceAttribute):
            return (self.service_class == other.service_class and 
                    self.extensions == other.extensions)
        return False


def get_curses_keycodes():
    """
    Return mapping of curses key-names paired by their keycode integer value.

    :rtype: dict
    :returns: Dictionary of (name, code) pairs for curses keyboard constant
        values and their mnemonic name. Such as code ``260``, with the value of
        its key-name identity, ``u'KEY_LEFT'``.
    """
    _keynames = [attr for attr in dir(curses)
                 if attr.startswith('KEY_')]
    return {keyname: getattr(curses, keyname) for keyname in _keynames}


def get_keyboard_codes():
    """
    Return mapping of keycode integer values paired by their curses key-name.

    :rtype: dict
    :returns: Dictionary of (code, name) pairs for curses keyboard constant
        values and their mnemonic name. Such as key ``260``, with the value of
        its identity, ``u'KEY_LEFT'``.

    These keys are derived from the attributes by the same of the curses module,
    with the following exceptions:

    * ``KEY_DELETE`` in place of ``KEY_DC``
    * ``KEY_INSERT`` in place of ``KEY_IC``
    * ``KEY_PGUP`` in place of ``KEY_PPAGE``
    * ``KEY_PGDOWN`` in place of ``KEY_NPAGE``
    * ``KEY_ESCAPE`` in place of ``KEY_EXIT``
    * ``KEY_SUP`` in place of ``KEY_SR``
    * ``KEY_SDOWN`` in place of ``KEY_SF``

    This function is the inverse of :func:`get_curses_keycodes`.  With the
    given override "mixins" listed above, the keycode for the delete key will
    map to our imaginary ``KEY_DELETE`` mnemonic, effectively erasing the
    phrase ``KEY_DC`` from our code vocabulary for anyone that wishes to use
    the return value to determine the key-name by keycode.
    """
    keycodes = OrderedDict(get_curses_keycodes())
    keycodes.update(CURSES_KEYCODE_OVERRIDE_MIXIN)
    # merge _CURSES_KEYCODE_ADDINS added to our module space
    keycodes.update(
        (name, value) for name, value in globals().copy().items() if name.startswith('KEY_')
    )

    # invert dictionary (key, values) => (values, key), preferring the
    # last-most inserted value ('KEY_DELETE' over 'KEY_DC').
    return dict(zip(keycodes.values(), keycodes.keys()))


def _alternative_left_right(term):
    r"""
    Determine and return mapping of left and right arrow keys sequences.

    :arg blessed.Terminal term: :class:`~.Terminal` instance.
    :rtype: dict
    :returns: Dictionary of sequences ``term._cuf1``, and ``term._cub1``,
        valued as ``KEY_RIGHT``, ``KEY_LEFT`` (when appropriate).

    This function supports :func:`get_keyboard_sequences` to discover
    the preferred input sequence for the left and right application keys.

    It is necessary to check the value of these sequences to ensure we do not
    use ``u' '`` and ``u'\b'`` for ``KEY_RIGHT`` and ``KEY_LEFT``,
    preferring their true application key sequence, instead.
    """
    # pylint: disable=protected-access
    keymap = {}
    if term._cuf1 and term._cuf1 != u' ':
        keymap[term._cuf1] = curses.KEY_RIGHT
    if term._cub1 and term._cub1 != u'\b':
        keymap[term._cub1] = curses.KEY_LEFT
    return keymap


def get_keyboard_sequences(term):
    r"""
    Return mapping of keyboard sequences paired by keycodes.

    :arg blessed.Terminal term: :class:`~.Terminal` instance.
    :returns: mapping of keyboard unicode sequences paired by keycodes
        as integer.  This is used as the argument ``mapper`` to
        the supporting function :func:`resolve_sequence`.
    :rtype: OrderedDict

    Initialize and return a keyboard map and sequence lookup table,
    (sequence, keycode) from :class:`~.Terminal` instance ``term``,
    where ``sequence`` is a multibyte input sequence of unicode
    characters, such as ``u'\x1b[D'``, and ``keycode`` is an integer
    value, matching curses constant such as term.KEY_LEFT.

    The return value is an OrderedDict instance, with their keys
    sorted longest-first.
    """
    sequence_map = dict((
        (seq.decode('latin1'), val)
        for (seq, val) in (
            (curses.tigetstr(cap), val)
            for (val, cap) in capability_names.items()
        ) if seq
    ) if term.does_styling else ())

    sequence_map.update(_alternative_left_right(term))
    sequence_map.update(DEFAULT_SEQUENCE_MIXIN)

    # This is for fast lookup matching of sequences, preferring
    # full-length sequence such as ('\x1b[D', KEY_LEFT)
    # over simple sequences such as ('\x1b', KEY_EXIT).
    return OrderedDict((
        (seq, sequence_map[seq]) for seq in sorted(
            sequence_map.keys(), key=len, reverse=True)))


def get_leading_prefixes(sequences):#
    """
    Return a set of proper prefixes for given sequence of strings.

    :arg iterable sequences
    :rtype: set
    :return: Set of all string prefixes

    Given an iterable of strings, all textparts leading up to the final
    string is returned as a unique set.  This function supports the
    :meth:`~.Terminal.inkey` method by determining whether the given
    input is a sequence that **may** lead to a final matching pattern.

    >>> prefixes(['abc', 'abdf', 'e', 'jkl'])
    set([u'a', u'ab', u'abd', u'j', u'jk'])
    """
    return {seq[:i] for seq in sequences for i in range(1, len(seq))}


def resolve_sequence(text, mapper, codes, prefixes, final=False):
    r"""
    Return a single :class:`Keystroke` instance for given sequence ``text``.

    :arg str text: string of characters received from terminal input stream.
    :arg OrderedDict mapper: unicode multibyte sequences, such as ``u'\x1b[D'``
        paired by their integer value (260)
    :arg dict codes: a :type:`dict` of integer values (such as 260) paired
        by their mnemonic name, such as ``'KEY_LEFT'``.
    :rtype: Keystroke
    :returns: Keystroke instance for the given sequence

    The given ``text`` may extend beyond a matching sequence, such as
    ``u\x1b[Dxxx`` returns a :class:`Keystroke` instance of attribute
    :attr:`Keystroke.sequence` valued only ``u\x1b[D``.  It is up to
    calls to determine that ``xxx`` remains unresolved.

    In an ideal world, we could detect and resolve only for key sequences
    expected in the current terminal mode. For example, only the enablement
    of mode 1036 (META_SENDS_ESC) would match
    """
    # static sequence lookups, from terminal capabilities
    ks = None
    for match_fn in (_match_dec_event,
                     _match_kitty_key,
                     _match_modify_other_keys,
                     _match_legacy_csi_modifiers):
        ks = match_fn(text)
        if ks:
            break
    if ks is None:
        for sequence, code in mapper.items():
            if text.startswith(sequence):
                ks = Keystroke(ucs=sequence, code=code, name=codes[code])
                break
    if ks is not None and ks.code == curses.KEY_EXIT and len(text) >= 2:
        if text[1] == '\x7f':
            # alt + backspace
            ks = Keystroke(ucs=text[:2])
        if final or text[:2] not in prefixes:
            # KEY_ALT_[..]
            ks = Keystroke(ucs=text[:2])
    if ks is None:
        ks = Keystroke(ucs=text and text[0] or u'')
    return ks


def _time_left(stime, timeout):
    """
    Return time remaining since ``stime`` before given ``timeout``.

    This function assists determining the value of ``timeout`` for
    class method :meth:`~.Terminal.kbhit` and similar functions.

    :arg float stime: starting time for measurement
    :arg float timeout: timeout period, may be set to None to
       indicate no timeout (where None is always returned).
    :rtype: float or int
    :returns: time remaining as float. If no time is remaining,
       then the integer ``0`` is returned.
    """
    return max(0, timeout - (time.time() - stime)) if timeout else timeout


def _read_until(term, pattern, timeout):
    """
    Convenience read-until-pattern function, supporting :meth:`~.get_location`.

    :arg blessed.Terminal term: :class:`~.Terminal` instance.
    :arg float timeout: timeout period, may be set to None to indicate no
        timeout (where 0 is always returned).
    :arg str pattern: target regular expression pattern to seek.
    :rtype: tuple
    :returns: tuple in form of ``(match, str)``, *match*
        may be :class:`re.MatchObject` if pattern is discovered
        in input stream before timeout has elapsed, otherwise
        None. ``str`` is any remaining text received exclusive
        of the matching pattern).

    The reason a tuple containing non-matching data is returned, is that the
    consumer should push such data back into the input buffer by
    :meth:`~.Terminal.ungetch` if any was received.

    For example, when a user is performing rapid input keystrokes while its
    terminal emulator surreptitiously responds to this in-band sequence, we
    must ensure any such keyboard data is well-received by the next call to
    term.inkey() without delay.
    """
    stime = time.time()
    match, buf = None, u''

    # first, buffer all pending data. pexpect library provides a
    # 'searchwindowsize' attribute that limits this memory region.  We're not
    # concerned about OOM conditions: only (human) keyboard input and terminal
    # response sequences are expected.

    while True:  # pragma: no branch
        # block as long as necessary to ensure at least one character is
        # received on input or remaining timeout has elapsed.
        ucs = term.inkey(timeout=_time_left(stime, timeout))
        
        # while the keyboard buffer is "hot" (has input), we continue to
        # aggregate all awaiting data.  We do this to ensure slow I/O
        # calls do not unnecessarily give up within the first 'while' loop
        # for short timeout periods.
        while ucs:
            buf += ucs
            ucs = term.inkey(timeout=0)

        match = re.search(pattern=pattern, string=buf)
        if match is not None:
            # match
            break

        if timeout is not None and not _time_left(stime, timeout):
            # timeout
            break

    return match, buf



def _match_dec_event(text):
    """
    Attempt to match text against DEC event patterns.

    :arg str text: Input text to match against DEC patterns
    :rtype: Keystroke or None
    :returns: :class:`Keystroke` with DEC event data if matched, ``None`` otherwise
    """
    for mode, pattern in DEC_EVENT_PATTERNS:
        match = pattern.match(text)
        if match:
            return Keystroke(ucs=match.group(0), mode=mode, match=match)
    return None


def _match_kitty_key(text):
    """
    Attempt to match text against Kitty keyboard protocol patterns.
    
    :arg str text: Input text to match against Kitty patterns
    :rtype: Keystroke or None
    :returns: :class:`Keystroke` with Kitty key data if matched, ``None`` otherwise
    
    Supports Kitty keyboard protocol sequences of the form:
    CSI unicode-key-code u                                            # Basic form
    CSI unicode-key-code ; modifiers u                                # With modifiers  
    CSI unicode-key-code : shifted-key : base-key ; modifiers u       # With alternate keys
    CSI unicode-key-code ; modifiers : event-type u                   # With event type
    CSI unicode-key-code ; modifiers : event-type ; text-codepoints u # Full form
    """
    match = KITTY_KB_PROTOCOL_PATTERN.match(text)
    when_non_empty = lambda _m, _key: int(_m.group(_key)) if _m.group(_key) else None
    when_non_empty_then_1 = lambda _m, _key: int(_m.group(_key)) if _m.group(_key) else 1
    if match:
        # TODO: We haven't parsed _text_codepoints yet, i think its something out of this world ..
        _codepoints_text = match.group('text_codepoints').split(':') if match.group('text_codepoints') else []
        _text_codepoints = [int(cp) for cp in _codepoints_text if cp]
        
        # Create KittyKeyEvent namedtuple
        kitty_event = KittyKeyEvent(
            unicode_key=int(match.group('unicode_key')),
            shifted_key=when_non_empty(match, 'shifted_key'),
            base_key=when_non_empty(match, 'base_key'),
            modifiers=when_non_empty_then_1(match, 'modifiers'),
            event_type=when_non_empty_then_1(match, 'event_type'),
            text_codepoints=_text_codepoints
        )
        
        # Create Keystroke with special mode to indicate Kitty protocol
        return Keystroke(ucs=match.group(0), mode=-1, match=kitty_event)
    
    return None


def _match_modify_other_keys(text):
    """
    Attempt to match text against xterm ModifyOtherKeys patterns.
    
    :arg str text: Input text to match against ModifyOtherKeys patterns
    :rtype: Keystroke or None  
    :returns: :class:`Keystroke` with ModifyOtherKeys data if matched, ``None`` otherwise
    
    Supports xterm ModifyOtherKeys sequences of the form:
    ESC [ 27 ; modifiers ; key ~     # Standard form
    ESC [ 27 ; modifiers ; key       # Alternative form without trailing ~
    """
    match = MODIFY_PATTERN.match(text)
    if match:
        # Create ModifyOtherKeysEvent namedtuple
        modify_event = ModifyOtherKeysEvent(
            key=int(match.group('key')),
            modifiers=int(match.group('modifiers')))
        # Create Keystroke with special mode to indicate ModifyOtherKeys protocol
        return Keystroke(ucs=match.group(0), mode=-2, match=modify_event)
    
    return None


def _match_legacy_csi_modifiers(text):
    """
    Attempt to match text against legacy CSI modifier patterns.
    
    :arg str text: Input text to match against legacy CSI modifier patterns
    :rtype: Keystroke or None
    :returns: :class:`Keystroke` with legacy CSI modifier data if matched, ``None`` otherwise
    
    Supports legacy CSI modifier sequences of the form:
    ESC [ 1 ; modifiers [ABCDEFHPQS]  # Arrow keys, Home/End, F1-F4 (letter form)
    ESC [ number ; modifiers ~        # Function keys and others (tilde form)
    
    These sequences may be sent by many terminals even when advanced keyboard
    protocols are not enabled, as it is the only way to transmit about modifier
    + application keys in a common legacy-compatible form.
    """
    # Try letter form: ESC [ 1 ; modifiers [ABCDEFHPQS] with optional '~'
    match = LEGACY_CSI_MODIFIERS_PATTERN.match(text)
    if match:
        matched_text = match.group(0)
        modifiers = int(match.group('mod'))
        final_char = match.group('final')
        
        keycode_match = {
            'A': curses.KEY_UP,
            'B': curses.KEY_DOWN,
            'C': curses.KEY_RIGHT,
            'D': curses.KEY_LEFT,
            'F': curses.KEY_END,
            'H': curses.KEY_HOME,
            'P': curses.KEY_F1,
            'Q': curses.KEY_F2,
            'R': curses.KEY_F3,   # this 'f3' is rarely (ever?) transmitted
            'S': curses.KEY_F4,
            }.get(final_char)
        if keycode_match is not None:
            legacy_event = LegacyCSIKeyEvent(
                kind='letter',
                key_id=final_char,
                modifiers=modifiers)
            return Keystroke(ucs=matched_text, code=keycode_match, mode=-3, match=legacy_event)
    
    # Try tilde form: ESC [ number ; modifiers ~
    match = LEGACY_CSI_TILDE_PATTERN.match(text)
    if match:
        matched_text = match.group(0)
        key_num = int(match.group('key_num'))
        modifiers = int(match.group('mod'))
        
        # Map tilde key numbers to curses key codes
        keycode_match = {
            2: curses.KEY_IC,       # Insert
            3: curses.KEY_DC,       # Delete
            5: curses.KEY_PPAGE,    # Page Up
            6: curses.KEY_NPAGE,    # Page Down
            7: curses.KEY_HOME,     # Home
            8: curses.KEY_END,      # End
            13: curses.KEY_F3,      # F3
            15: curses.KEY_F5,      # F5
            17: curses.KEY_F6,      # F6
            18: curses.KEY_F7,      # F7
            19: curses.KEY_F8,      # F8
            20: curses.KEY_F9,      # F9
            21: curses.KEY_F10,     # F10
            23: curses.KEY_F11,     # F11
            24: curses.KEY_F12,     # F12
            29: KEY_MENU,           # Menu key  # pylint: disable=undefined-variable
            }.get(key_num)
            
        if keycode_match is not None:
            legacy_event = LegacyCSIKeyEvent(
                kind='tilde',
                key_id=key_num,
                modifiers=modifiers)
            return Keystroke(ucs=matched_text, code=keycode_match, mode=-3, match=legacy_event)
    
    # Try SS3 F-key form: ESC O modifier [PQRS] (Konsole)
    match = LEGACY_SS3_FKEYS_PATTERN.match(text)
    if match:
        matched_text = match.group(0)
        modifiers = int(match.group('mod'))
        final_char = match.group('final')
        
        # Modifier 0 is invalid - modifiers start from 1 (no modifiers) 
        if modifiers == 0:
            return None
        
        # Map SS3 F-key final characters to curses key codes
        keycode_match = {
            'P': curses.KEY_F1,     # F1
            'Q': curses.KEY_F2,     # F2
            'R': curses.KEY_F3,     # F3
            'S': curses.KEY_F4,     # F4
            }.get(final_char)
            
        if keycode_match is not None:
            legacy_event = LegacyCSIKeyEvent(
                kind='ss3-fkey',
                key_id=final_char,
                modifiers=modifiers)
            return Keystroke(ucs=matched_text, code=keycode_match, mode=-3, match=legacy_event)
    
    return None


#: Though we may determine *keynames* and codes for keyboard input that
#: generate multibyte sequences, it is also especially useful to aliases
#: a few basic ASCII characters such as ``KEY_TAB`` instead of ``u'\t'`` for
#: uniformity. KEY_MENU is missing in curses and so is also added, here.
#:
#: many key-names for application keys enabled only by context manager
#: :meth:`~.Terminal.keypad` are surprisingly absent (KP_), and so they
#: are artificially recreated.
_CURSES_KEYCODE_ADDINS = (
    'TAB',
    'KP_MULTIPLY',
    'KP_ADD',
    'KP_SEPARATOR',
    'KP_SUBTRACT',
    'KP_DECIMAL',
    'KP_DIVIDE',
    'KP_EQUAL',
    'KP_0',
    'KP_1',
    'KP_2',
    'KP_3',
    'KP_4',
    'KP_5',
    'KP_6',
    'KP_7',
    'KP_8',
    'KP_9',
    'MENU')

_LASTVAL = max(get_curses_keycodes().values())
for keycode_name in _CURSES_KEYCODE_ADDINS:
    _LASTVAL += 1
    globals()['KEY_' + keycode_name] = _LASTVAL

#: In a perfect world, terminal emulators would always send exactly what
#: the terminfo(5) capability database plans for them, accordingly by the
#: value of the ``TERM`` name they declare.
#:
#: But this isn't a perfect world. Many vt220-derived terminals, such as
#: those declaring 'xterm', will continue to send vt220 codes instead of
#: their native-declared codes, for backwards-compatibility.
#:
#: This goes for many: rxvt, putty, iTerm.
#:
#: These "mixins" are used to match *most* general purpose terminals,
#: regardless of their declared ``TERM`` type.
#:
#: Furthermore, curses does not provide sequences sent by the keypad,
#: at least, it does not provide a way to distinguish between keypad 0
#: and numeric 0.
DEFAULT_SEQUENCE_MIXIN = (
    # these common control characters (and 127, ctrl+'?') mapped to
    # an application key definition.
    (unicode_chr(10), curses.KEY_ENTER),
    (unicode_chr(13), curses.KEY_ENTER),
    (unicode_chr(8), curses.KEY_BACKSPACE),
    (unicode_chr(9), KEY_TAB),  # noqa  # pylint: disable=undefined-variable
    (unicode_chr(27), curses.KEY_EXIT),
    (unicode_chr(127), curses.KEY_BACKSPACE),

    (u"\x1b[A", curses.KEY_UP),
    (u"\x1b[B", curses.KEY_DOWN),
    (u"\x1b[C", curses.KEY_RIGHT),
    (u"\x1b[D", curses.KEY_LEFT),
    (u"\x1b[F", curses.KEY_END),
    (u"\x1b[H", curses.KEY_HOME),
    (u"\x1b[K", curses.KEY_END),
    (u"\x1b[U", curses.KEY_NPAGE),
    (u"\x1b[V", curses.KEY_PPAGE),

    # keys sent after term.smkx (keypad_xmit) is emitted, source:
    # http://www.xfree86.org/current/ctlseqs.html#PC-Style%20Function%20Keys
    # http://fossies.org/linux/rxvt/doc/rxvtRef.html#KeyCodes
    #
    # keypad, numlock on -- these sequences cause quite a stir, unlike almost
    # every other kind of application or "special input" keys, they do not begin
    # with CSI !!
    (u"\x1bOM", curses.KEY_ENTER),  # noqa return
    (u"\x1bOj", KEY_KP_MULTIPLY),   # noqa *  # pylint: disable=undefined-variable
    (u"\x1bOk", KEY_KP_ADD),        # noqa +  # pylint: disable=undefined-variable
    (u"\x1bOl", KEY_KP_SEPARATOR),  # noqa ,  # pylint: disable=undefined-variable
    (u"\x1bOm", KEY_KP_SUBTRACT),   # noqa -  # pylint: disable=undefined-variable
    (u"\x1bOn", KEY_KP_DECIMAL),    # noqa .  # pylint: disable=undefined-variable
    (u"\x1bOo", KEY_KP_DIVIDE),     # noqa /  # pylint: disable=undefined-variable
    (u"\x1bOX", KEY_KP_EQUAL),      # noqa =  # pylint: disable=undefined-variable
    (u"\x1bOp", KEY_KP_0),          # noqa 0  # pylint: disable=undefined-variable
    (u"\x1bOq", KEY_KP_1),          # noqa 1  # pylint: disable=undefined-variable
    (u"\x1bOr", KEY_KP_2),          # noqa 2  # pylint: disable=undefined-variable
    (u"\x1bOs", KEY_KP_3),          # noqa 3  # pylint: disable=undefined-variable
    (u"\x1bOt", KEY_KP_4),          # noqa 4  # pylint: disable=undefined-variable
    (u"\x1bOu", KEY_KP_5),          # noqa 5  # pylint: disable=undefined-variable
    (u"\x1bOv", KEY_KP_6),          # noqa 6  # pylint: disable=undefined-variable
    (u"\x1bOw", KEY_KP_7),          # noqa 7  # pylint: disable=undefined-variable
    (u"\x1bOx", KEY_KP_8),          # noqa 8  # pylint: disable=undefined-variable
    (u"\x1bOy", KEY_KP_9),          # noqa 9  # pylint: disable=undefined-variable

    # We wouldn't even bother to detect them unless 'term.smkx' was known to be
    # emitted with a context manager... if it weren't for these "legacy" DEC VT
    # special keys, that are now transmitted as F1-F4 for many terminals, unless
    # negotiated to do something else! There is a lot of legacy to these F keys
    # in particular, a bit of sordid story.
    (u"\x1bOP", curses.KEY_F1),
    (u"\x1bOQ", curses.KEY_F2),
    (u"\x1bOR", curses.KEY_F3),
    (u"\x1bOS", curses.KEY_F4),

    # keypad, numlock off
    (u"\x1b[1~", curses.KEY_FIND),         # find
    (u"\x1b[2~", curses.KEY_IC),           # insert (0)
    (u"\x1b[3~", curses.KEY_DC),           # delete (.), "Execute"
    (u"\x1b[4~", curses.KEY_SELECT),       # select
    (u"\x1b[5~", curses.KEY_PPAGE),        # pgup   (9)
    (u"\x1b[6~", curses.KEY_NPAGE),        # pgdown (3)
    (u"\x1b[7~", curses.KEY_HOME),         # home
    (u"\x1b[8~", curses.KEY_END),          # end
    (u"\x1b[OA", curses.KEY_UP),           # up     (8)
    (u"\x1b[OB", curses.KEY_DOWN),         # down   (2)
    (u"\x1b[OC", curses.KEY_RIGHT),        # right  (6)
    (u"\x1b[OD", curses.KEY_LEFT),         # left   (4)
    (u"\x1b[OF", curses.KEY_END),          # end    (1)
    (u"\x1b[OH", curses.KEY_HOME),         # home   (7)

)

#: Override mixins for a few curses constants with easier
#: mnemonics: there may only be a 1:1 mapping when only a
#: keycode (int) is given, where these phrases are *preferred*.
CURSES_KEYCODE_OVERRIDE_MIXIN = (
    ('KEY_DELETE', curses.KEY_DC),
    ('KEY_INSERT', curses.KEY_IC),
    ('KEY_PGUP', curses.KEY_PPAGE),
    ('KEY_PGDOWN', curses.KEY_NPAGE),
    ('KEY_ESCAPE', curses.KEY_EXIT),
    ('KEY_SUP', curses.KEY_SR),
    ('KEY_SDOWN', curses.KEY_SF),
    ('KEY_UP_LEFT', curses.KEY_A1),
    ('KEY_UP_RIGHT', curses.KEY_A3),
    ('KEY_DOWN_LEFT', curses.KEY_C1),
    ('KEY_DOWN_RIGHT', curses.KEY_C3),
    ('KEY_CENTER', curses.KEY_B2),
    ('KEY_BEGIN', curses.KEY_BEG),
)

#: Default delay, in seconds, of Escape key detection in
#: :meth:`Terminal.inkey`.` curses has a default delay of 1000ms (1 second) for
#: escape sequences.  This is too long for modern applications, so we set it to
#: 350ms, or 0.35 seconds. It is still a bit conservative, for remote telnet or
#: ssh servers, for example.
DEFAULT_ESCDELAY = 0.35


def _reinit_escdelay():
    # pylint: disable=W0603
    # Using the global statement: this is necessary to
    # allow test coverage without complex module reload
    global DEFAULT_ESCDELAY
    if os.environ.get('ESCDELAY'):
        try:
            DEFAULT_ESCDELAY = int(os.environ['ESCDELAY']) / 1000.0
        except ValueError:
            # invalid values of 'ESCDELAY' are ignored
            pass


_reinit_escdelay()

class KittyKeyboardProtocol:
    """
    Represents Kitty keyboard protocol flags.
    
    Encapsulates the integer flag value returned by Kitty keyboard protocol 
    queries and provides properties for individual flag bits and a method 
    to convert back to enable_kitty_keyboard() arguments.
    """
    
    def __init__(self, value):
        """
        Initialize with raw integer flag value.
        
        :arg int value: Raw integer flags value from Kitty keyboard protocol query
        """
        self.value = int(value)
    
    @property
    def disambiguate(self):
        """Whether disambiguated escape codes are enabled (bit 1)."""
        return bool(self.value & 0b1)
    
    @disambiguate.setter
    def disambiguate(self, enabled):
        """Set whether disambiguated escape codes are enabled (bit 1)."""
        if enabled:
            self.value |= 0b1
        else:
            self.value &= ~0b1
    
    @property 
    def report_events(self):
        """Whether key repeat and release events are reported (bit 2)."""
        return bool(self.value & 0b10)
    
    @report_events.setter
    def report_events(self, enabled):
        """Set whether key repeat and release events are reported (bit 2)."""
        if enabled:
            self.value |= 0b10
        else:
            self.value &= ~0b10
    
    @property
    def report_alternates(self):
        """Whether shifted and base layout keys are reported for shortcuts (bit 4)."""
        return bool(self.value & 0b100)
    
    @report_alternates.setter
    def report_alternates(self, enabled):
        """Set whether shifted and base layout keys are reported for shortcuts (bit 4)."""
        if enabled:
            self.value |= 0b100
        else:
            self.value &= ~0b100
    
    @property
    def report_all_keys(self):
        """Whether all keys are reported as escape codes (bit 8)."""
        return bool(self.value & 0b1000)
    
    @report_all_keys.setter
    def report_all_keys(self, enabled):
        """Set whether all keys are reported as escape codes (bit 8)."""
        if enabled:
            self.value |= 0b1000
        else:
            self.value &= ~0b1000
    
    @property
    def report_text(self):
        """Whether associated text is reported with key events (bit 16)."""
        return bool(self.value & 0b10000)
    
    @report_text.setter
    def report_text(self, enabled):
        """Set whether associated text is reported with key events (bit 16)."""
        if enabled:
            self.value |= 0b10000
        else:
            self.value &= ~0b10000
    
    def make_arguments(self):
        """
        Return dictionary of arguments suitable for enable_kitty_keyboard().
        
        :rtype: dict
        :returns: Dictionary with boolean flags suitable for passing as 
            keyword arguments to enable_kitty_keyboard()
        """
        return {
            'disambiguate': self.disambiguate,
            'report_events': self.report_events, 
            'report_alternates': self.report_alternates,
            'report_all_keys': self.report_all_keys,
            'report_text': self.report_text
        }
    
    def __repr__(self):
        """Return string representation of the protocol flags."""
        flags = []
        if self.disambiguate:
            flags.append('disambiguate')
        if self.report_events:
            flags.append('report_events')
        if self.report_alternates:
            flags.append('report_alternates')
        if self.report_all_keys:
            flags.append('report_all_keys')
        if self.report_text:
            flags.append('report_text')
        
        return f"KittyKeyboardProtocol(value={self.value}, flags=[{', '.join(flags)}])"
    
    def __eq__(self, other):
        """Check equality based on flag values."""
        if isinstance(other, KittyKeyboardProtocol):
            return self.value == other.value
        elif isinstance(other, int):
            return self.value == other
        return False


__all__ = ('Keystroke', 'get_keyboard_codes', 'get_keyboard_sequences',
           '_match_dec_event', '_match_kitty_key', '_match_modify_other_keys',
           '_match_legacy_csi_modifiers', 'BracketedPasteEvent', 'MouseSGREvent', 
           'MouseLegacyEvent', 'FocusEvent', 'SyncEvent', 'KittyKeyEvent', 
           'ModifyOtherKeysEvent', 'LegacyCSIKeyEvent', 'KittyKeyboardProtocol',
           'DeviceAttribute')