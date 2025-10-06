"""Sub-module providing 'keyboard awareness'."""
# pylint: disable=too-many-lines
# std imports
import os
import re
import time
import typing
import platform
import functools
from typing import Set, Dict, Match, Tuple, TypeVar, Optional
from collections import OrderedDict, namedtuple

# local
from blessed.dec_modes import DecPrivateMode

_T = TypeVar('_T', bound='Keystroke')

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


class MouseEvent(namedtuple('_MouseEvent',
                            'button x y is_release shift meta ctrl is_motion is_wheel')):
    """
    Mouse event with button, coordinates, and modifier information.

    A unified mouse event structure that supports both legacy and SGR mouse protocols. Provides a
    custom __repr__ that only displays active (non-default) attributes for clarity.
    """

    def __repr__(self) -> str:
        """Return succinct representation showing only active attributes."""
        # Always show button, x, y
        parts = [f'button={self.button}', f'x={self.x}', f'y={self.y}']

        # Only show boolean flags when True
        for bool_name in ('is_release', 'shift', 'meta', 'ctrl', 'is_motion', 'is_wheel'):
            if getattr(self, bool_name):
                parts.append(f'{bool_name}=True')
        return f"MouseEvent({', '.join(parts)})"


# Backwards compatibility aliases
MouseSGREvent = MouseEvent
MouseLegacyEvent = MouseEvent

FocusEvent = namedtuple('FocusEvent', 'gained')
SyncEvent = namedtuple('SyncEvent', 'begin')


# Kitty keyboard protocol and xterm ModifyOtherKeys namedtuples
KittyKeyEvent = namedtuple('KittyKeyEvent',
                           'unicode_key shifted_key base_key modifiers event_type int_codepoints')
ModifyOtherKeysEvent = namedtuple('ModifyOtherKeysEvent', 'key modifiers')

# Legacy CSI modifier key support
LegacyCSIKeyEvent = namedtuple('LegacyCSIKeyEvent', 'kind key_id modifiers event_type')
LEGACY_CSI_MODIFIERS_PATTERN = re.compile(
    r'\x1b\[1;(?P<mod>\d+)(?::(?P<event>\d+))?(?P<final>[ABCDEFHPQRS])~?')
LEGACY_CSI_TILDE_PATTERN = re.compile(r'\x1b\[(?P<key_num>\d+);(?P<mod>\d+)(?::(?P<event>\d+))?~')
LEGACY_SS3_FKEYS_PATTERN = re.compile(r'\x1bO(?P<mod>\d)(?P<final>[PQRS])')
DECEventPattern = functools.namedtuple("DEC_EVENT_PATTERN", ["mode", "pattern"])

# DEC event patterns - compiled regexes with metadata
DEC_EVENT_PATTERNS = [
    # Bracketed paste - must be first due to greedy nature; this is more closely
    # married to ESC_DELAY than it first appears -- the full payload and final
    # marker must be received under ESC_DELAY seconds.
    DECEventPattern(mode=DecPrivateMode.BRACKETED_PASTE, pattern=(
        re.compile(r'\x1b\[200~(?P<text>.*?)\x1b\[201~', re.DOTALL))),
    # Mouse SGR (1006) - recommended format: CSI < b;x;y m/M
    # Also supports legacy format without a '<' for backward compatibility,
    DECEventPattern(mode=DecPrivateMode.MOUSE_EXTENDED_SGR, pattern=(
        re.compile(r'\x1b\[<?(?P<b>\d+);(?P<x>\d+);(?P<y>\d+)(?P<type>[mM])'))),
    # Mouse SGR-Pixels (1016) - identical wire format to 1006!  This helps to
    # have a matching Keystroke.mode, determined by active enabled modes,
    # preferring pixels if enabled, the specification would require the *order*
    # that they were enabled and disabled in case of conflict, too much code to
    # be practical.
    DECEventPattern(mode=DecPrivateMode.MOUSE_EXTENDED_SGR, pattern=(
        re.compile(r'\x1b\[<?(?P<b>\d+);(?P<x>\d+);(?P<y>\d+)(?P<type>[mM])'))),
    # Legacy mouse (X10/1000/1002/1003) - CSI M followed by 3 bytes
    DECEventPattern(mode=DecPrivateMode.MOUSE_REPORT_CLICK,
                    pattern=re.compile(r'\x1b\[M(?P<cb>.)(?P<cx>.)(?P<cy>.)')),
    # Focus tracking, is just 'I'n or 'O'ut
    DECEventPattern(mode=DecPrivateMode.FOCUS_IN_OUT_EVENTS,
                    pattern=re.compile(r'\x1b\[(?P<io>[IO])'))
]

# Match Kitty keyboard protocol: ESC [ ... u
# Pattern covers all variations of the protocol
KITTY_KB_PROTOCOL_PATTERN = re.compile(
    r'\x1b\[(?P<unicode_key>\d+)'
    r'(?::(?P<shifted_key>\d*))?'
    r'(?::(?P<base_key>\d*))?'
    r'(?:;(?P<modifiers>\d*))?'
    r'(?::(?P<event_type>\d+))?'
    r'(?:;(?P<text_codepoints>[\d:]+))?'
    r'u')

# Match ModifyOtherKeys pattern: ESC [ 27 ; modifiers ; key [~]
MODIFY_PATTERN = re.compile(r'\x1b\[27;(?P<modifiers>\d+);(?P<key>\d+)(?P<tilde>~?)')
CTRL_CHAR_SYMBOLS_MAP = {'@': 0, '[': 27, '\\': 28, ']': 29, '^': 30, '_': 31, '?': 127}
CTRL_CODE_SYMBOLS_MAP = {v: k for k, v in CTRL_CHAR_SYMBOLS_MAP.items()}


class KittyModifierBits:
    """Kitty keyboard protocol modifier bit flags."""
    # pylint: disable=too-few-public-methods

    shift = 0b1
    alt = 0b10
    ctrl = 0b100
    super = 0b1000
    hyper = 0b10000
    meta = 0b100000
    caps_lock = 0b1000000
    num_lock = 0b10000000

    #: Names of (kitty-derived) bitwise flags attached to this class
    names = ('shift', 'alt', 'ctrl', 'super', 'hyper', 'meta',
             'caps_lock', 'num_lock')

    #: Modifiers only, in the generally preferred order in phrasing, eg. "CTRL + ALT + DELETE"
    #: is, apparently, KEY_CTRL_ALT_SHIFT_SUPER_HYPER_META('a')
    names_modifiers_only = ('ctrl', 'alt', 'shift', 'super', 'hyper', 'meta')


class Keystroke(str):
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
    :class:`DecPrivateMode` enum value, and :meth:`mode_values` returns
    a structured namedtuple with parsed event data.
    """

    def __new__(   # pylint: disable=too-many-positional-arguments
            cls: typing.Type[_T], ucs: str = '', code: typing.Optional[int] = None,
            name: typing.Optional[str] = None, mode: typing.Optional[int] = None,
            match: typing.Any = None) -> _T:
        """Class constructor."""
        new = str.__new__(cls, ucs)
        new._name = name
        new._code = code
        new._mode = mode  # DEC private mode integer
        new._match = match  # regex match object
        new._modifiers = cls._infer_modifiers(ucs, mode, match)
        return new

    @staticmethod
    def _infer_modifiers(ucs: str, mode: Optional[int], match: typing.Any) -> int:
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
                return 1 + KittyModifierBits.alt  # 1 + alt flag = 3

            # Other control characters represent Ctrl+Alt combinations
            # (ESC prefix for Alt + control char from Ctrl+letter mapping)
            if 0 <= char_code <= 31 or char_code == 127:
                # 1 + alt flag + ctrl flag = 7
                return 1 + KittyModifierBits.alt + KittyModifierBits.ctrl

            # Printable characters - Alt-only unless uppercase letter (which adds Shift)
            if 32 <= char_code <= 126:
                ch = ucs[1]
                shift = KittyModifierBits.shift if ch.isalpha() and ch.isupper() else 0
                return 1 + KittyModifierBits.alt + shift  # add shift for Alt+uppercase

        # Legacy Ctrl: single control character
        if len(ucs) == 1:
            char_code = ord(ucs)
            if 0 <= char_code <= 31 or char_code == 127:
                return 1 + KittyModifierBits.ctrl  # 1 + ctrl flag = 5

        # No modifiers detected
        return 1

    @property
    def is_sequence(self) -> bool:
        """Whether the value represents a multibyte sequence (bool)."""
        return self._code is not None or self._mode is not None or len(self) > 1

    def __repr__(self) -> str:
        """Docstring overwritten."""
        return (str.__repr__(self) if self._name is None else
                self._name)
    __repr__.__doc__ = str.__doc__

    def _get_modified_keycode_name(self) -> Optional[str]:
        """
        Get name for modern/legacy CSI sequence with modifiers.

        Returns name like 'KEY_CTRL_ALT_F1' or 'KEY_SHIFT_UP_RELEASED'. Also handles release/repeat
        events for keys without modifiers.
        """
        if not (self._mode is not None and self._mode < 0 and self._code is not None):
            return None

        # turn keycode value into 'base name', eg.
        # self._code of 265 -> 'KEY_F1' -> 'F1' base_name
        keycodes = get_keyboard_codes()
        base_name = keycodes.get(self._code)
        if not base_name or not base_name.startswith('KEY_'):
            return None

        # get "base name" name by, 'KEY_F1' -> 'F1'
        base_name = base_name[4:]

        # Build possible modifier prefix series (excludes num/capslock)
        # "Ctrl + Alt + Shift + Super / Meta"
        mod_parts = []
        for mod_name in KittyModifierBits.names_modifiers_only:
            if getattr(self, f'_{mod_name}'):        # 'if self._shift'
                mod_parts.append(mod_name.upper())   # -> 'SHIFT'

        # For press events with no modifiers, return None (no special name needed)
        if not mod_parts and not (self.released or self.repeated):
            return None

        # Build base result with modifiers (if any)
        if mod_parts:
            base_result = f"KEY_{'_'.join(mod_parts)}_{base_name}"
        else:
            base_result = f"KEY_{base_name}"

        # Append event type suffix if not a press event
        if self.repeated:
            return f"{base_result}_REPEATED"
        if self.released:
            return f"{base_result}_RELEASED"
        return base_result

    def _get_kitty_protocol_name(self) -> Optional[str]:
        # pylint: disable=too-many-return-statements
        """
        Get name for Kitty keyboard protocol letter/digit/symbol.

        Returns name like 'KEY_CTRL_ALT_A' or 'KEY_ALT_SHIFT_5'.
        """
        if self._mode != DecPrivateMode.SpecialInternalKitty:
            return None

        # Only synthesize for keypress events (event_type == 1), not release/repeat
        if self._match.event_type != 1:
            return None

        # Determine the base key - prefer base_key if available
        base_codepoint = (self._match.base_key if self._match.base_key is not None
                          else self._match.unicode_key)

        # Special case: '[' always returns 'CSI' regardless of modifiers
        if base_codepoint == 91:  # '['
            return 'CSI'

        # Only proceed if it's an ASCII letter or digit
        if not base_codepoint:
            return None
        if not ((65 <= base_codepoint <= 90) or   # A-Z
                (97 <= base_codepoint <= 122) or  # a-z
                (48 <= base_codepoint <= 57)):    # 0-9
            return None

        # For letters: convert to uppercase for consistent naming
        # For digits: use as-is
        if 65 <= base_codepoint <= 90 or 97 <= base_codepoint <= 122:  # letter
            char = chr(base_codepoint).upper()  # Convert to uppercase
        else:  # digit
            char = chr(base_codepoint)  # Keep as-is

        # Build modifier prefix list in order: CTRL, ALT, SHIFT, SUPER, HYPER, META
        mod_parts = []
        for mod_name in KittyModifierBits.names_modifiers_only:
            if getattr(self, f'_{mod_name}'):
                mod_parts.append(mod_name.upper())

        # Only synthesize name if at least one modifier is present
        if mod_parts:
            return f"KEY_{'_'.join(mod_parts)}_{char}"
        return None

    def _get_control_char_name(self) -> Optional[str]:
        """
        Get name for single-character control sequences.

        Returns name like 'KEY_CTRL_A' or 'KEY_CTRL_@'.
        """
        if len(self) != 1:
            return None

        char_code = ord(self)
        if 1 <= char_code <= 26:
            # Ctrl+A through Ctrl+Z
            return f'KEY_CTRL_{chr(char_code + ord("A") - 1)}'
        if char_code in CTRL_CODE_SYMBOLS_MAP:
            return f'KEY_CTRL_{CTRL_CODE_SYMBOLS_MAP[char_code]}'
        return None

    def _get_control_symbol(self, char_code: int) -> Optional[str]:
        """
        Get control symbol for a character code.

        Returns symbol like 'A' for Ctrl+A, '@' for Ctrl+@, etc.
        """
        if 1 <= char_code <= 26:
            # Ctrl+A through Ctrl+Z
            return chr(char_code + ord("A") - 1)
        if char_code in CTRL_CODE_SYMBOLS_MAP:
            # Ctrl+symbol
            return CTRL_CODE_SYMBOLS_MAP[char_code]
        return None

    def _get_alt_only_control_name(self, char_code: int) -> Optional[str]:
        """
        Get name for Alt-only special control characters.

        Returns names like 'KEY_ALT_ESCAPE', 'KEY_ALT_BACKSPACE', etc.
        """
        control_names = {
            0x1b: 'KEY_ALT_ESCAPE',     # ESC
            0x7f: 'KEY_ALT_BACKSPACE',  # DEL
            0x0d: 'KEY_ALT_ENTER',      # CR
            0x09: 'KEY_ALT_TAB',        # TAB
            0x5b: 'CSI'                 # CSI '['
        }
        return control_names.get(char_code)

    def _get_meta_escape_name(self) -> Optional[str]:
        # pylint: disable=too-many-return-statements
        """
        Get name for metaSendsEscape sequences (ESC + char).

        Returns name like 'KEY_ALT_A', 'KEY_ALT_SHIFT_Z', 'KEY_CTRL_ALT_C', or 'KEY_ALT_ESCAPE'.
        """
        # pylint: disable=too-complex
        if len(self) != 2 or self[0] != '\x1b':
            return None

        char_code = ord(self[1])

        # Check for ESC + control char
        if 0 <= char_code <= 31 or char_code == 127:
            symbol = self._get_control_symbol(char_code)

            if symbol:
                # Check if this is Alt-only or Ctrl+Alt based on modifiers
                if self.modifiers == 3:  # Alt-only (1 + 2)
                    # Special C0 controls that are Alt-only
                    alt_name = self._get_alt_only_control_name(char_code)
                    if alt_name:
                        return alt_name
                elif self.modifiers == 7:  # Ctrl+Alt (1 + 2 + 4)
                    return f'KEY_CTRL_ALT_{symbol}'

        # Check for and return KEY_ALT_ for "metaSendsEscape"
        if self[1].isprintable():
            ch = self[1]
            if ch.isalpha():
                if ch.isupper():
                    return f'KEY_ALT_SHIFT_{ch}'
                return f'KEY_ALT_{ch.upper()}'
            if ch == '[':
                return 'CSI'
            return f'KEY_ALT_{ch}'
        if self[1] == '\x7f' and self.modifiers == 3:
            return 'KEY_ALT_BACKSPACE'
        return None

    @property
    def name(self) -> Optional[str]:
        r"""
        Special application key name.

        This is the best equality attribute to use for special keys, as raw
        string value of 'F1' key can be received in many different values, the
        'name' property will return a reliable constant, 'KEY_F1'. This also
        supports "modifiers", such as 'KEY_CTRL_F1', 'KEY_CTRL_ALT_F1',
        'KEY_CTRL_ALT_SHIFT_F1'.

        This also supports alphanumerics and symbols when combined with a
        modifier, such as KEY_ALT_z and KEY_ALT_SHIFT_Z

        When non-None, all phrases begin with ``'KEY'`` with one
        exception,``'CSI'`` is returned for ``\x1b[`` to indicate the beginning
        of an unsupported input sequence, the phrase ``'KEY_ALT_['`` is never
        returned.

        If this value is None, then it can probably be assumed that the
        ``value`` is an unsurprising textual character without any modifiers.
        """
        if self._name is not None:
            return self._name

        # Try each helper method in sequence
        result = self._get_modified_keycode_name()
        if result is not None:
            return result

        result = self._get_kitty_protocol_name()
        if result is not None:
            return result

        result = self._get_control_char_name()
        if result is not None:
            return result

        result = self._get_meta_escape_name()
        if result is not None:
            return result

        return self._name

    @property
    def code(self) -> Optional[int]:
        """Legacy curses-alike keycode value (int)."""
        return self._code

    @property
    def modifiers(self) -> int:
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
    def modifiers_bits(self) -> int:
        """
        Raw modifier bit flags without the +1 offset.

        :rtype: int
        :returns: Raw bitwise OR of modifier flags (0 means no modifiers)
        """
        return max(0, self._modifiers - 1)

    def _get_plain_char_value(self) -> Optional[str]:
        """
        Get value for plain printable characters.

        Returns the character as-is if it's a single printable character.
        """
        if len(self) == 1 and not self[0] == '\x1b' and self[0].isprintable():
            return str(self)
        return None

    def _get_alt_sequence_value(self) -> Optional[str]:
        """
        Get value for Alt+printable sequences (ESC + char).

        Returns the printable character from Alt sequences.
        """
        if (len(self) == 2 and self[0] == '\x1b' and
                self._alt and not self._ctrl and self[1].isprintable()):
            return self[1]  # Return as-is (preserves case and supports Unicode)
        return None

    def _get_ctrl_alt_sequence_value(self) -> Optional[str]:
        """
        Get value for Ctrl+Alt sequences (ESC + control char).

        Returns the base character from Ctrl+Alt combinations.
        """
        if not (len(self) == 2 and self[0] == '\x1b' and
                self._ctrl and self._alt):
            return None

        char_code = ord(self[1])

        # Ctrl+A through Ctrl+Z (codes 1-26)
        if 1 <= char_code <= 26:
            return chr(char_code + ord('a') - 1)  # lowercase

        # Ctrl+symbol mappings
        if char_code in CTRL_CODE_SYMBOLS_MAP:
            return CTRL_CODE_SYMBOLS_MAP[char_code]

        return None

    def _get_ctrl_sequence_value(self) -> Optional[str]:
        """
        Get value for Ctrl+char sequences.

        Maps control characters back to their base characters.
        """
        if not (len(self) == 1 and self._ctrl and not self._alt):
            return None

        char_code = ord(self)

        # Ctrl+A through Ctrl+Z (codes 1-26)
        if 1 <= char_code <= 26:
            return chr(char_code + ord('a') - 1)  # lowercase

        # Ctrl+symbol mappings
        if char_code in CTRL_CODE_SYMBOLS_MAP:
            return CTRL_CODE_SYMBOLS_MAP[char_code]

        return None

    def _get_protocol_value(self) -> Optional[str]:
        """
        Get value for Kitty or ModifyOtherKeys protocol sequences.

        Extracts the character from modern keyboard protocols.
        """
        # Kitty protocol
        if self._mode == DecPrivateMode.SpecialInternalKitty:
            # prefer text_codepoints if available
            if self._match.int_codepoints:
                return ''.join(chr(cp) for cp in self._match.int_codepoints)

            # Check if this is a PUA modifier key (which don't produce text)
            if KEY_LEFT_SHIFT <= self._match.unicode_key <= KEY_RIGHT_META:
                return ''  # Modifier keys don't produce text
            return chr(self._match.unicode_key)

        # ModifyOtherKeys protocol - extract character from key
        if self._mode == DecPrivateMode.SpecialInternalModifyOtherKeys:
            return chr(self._match.key)

        return None

    def _get_ascii_value(self) -> Optional[str]:
        """Get value for keys matched by curses-imitated keycodes."""
        return {
            curses.KEY_ENTER: '\n',
            KEY_TAB: '\t',
            curses.KEY_BACKSPACE: '\x08',
            curses.KEY_EXIT: '\x1b',
        }.get(self._code)

    @property
    def value(self) -> str:
        # pylint: disable=too-many-return-statements
        r"""
        The textual character represented by this keystroke.

        :rtype: str
        :returns: For text keys, returns the base character (ignoring modifiers).
                  For application keys and sequences, returns empty string ''.
                  For release events, always returns empty string.

        Some Examples,

        - Plain text: 'a', 'A', '1', ';', ' ', 'Ω', emoji with ZWJ sequences
        - Alt+printable: Alt+a _get_ctrl_alt_sequence_value 'a', Alt+A → 'A'
        - Ctrl+letter: Ctrl+A → 'a', Ctrl+Z → 'z'
        - Ctrl+symbol: Ctrl+@ → '@', Ctrl+? → '?', Ctrl+[ → '['
        - Control chars: '\t', '\n', '\x08', '\x1b' (for Enter/Tab/Backspace/Escape keycodes)
        - Application keys: KEY_UP, KEY_F1, etc. → ''
        - DEC events: bracketed paste, mouse, etc. → ''
        - Release events: always → ''
        """
        # Release events never have text
        if self.released:
            return ''

        return (self._get_plain_char_value()
                or self._get_alt_sequence_value()
                or self._get_ctrl_alt_sequence_value()
                or self._get_ctrl_sequence_value()
                or self._get_protocol_value()
                or self._get_ascii_value()
                or '')

    # Private modifier flag properties (internal use)
    @property
    def _shift(self) -> bool:
        """Whether the shift modifier is active."""
        return bool(self.modifiers_bits & KittyModifierBits.shift)

    @property
    def _alt(self) -> bool:
        """Whether the alt modifier is active."""
        return bool(self.modifiers_bits & KittyModifierBits.alt)

    @property
    def _ctrl(self) -> bool:
        """Whether the ctrl modifier is active."""
        return bool(self.modifiers_bits & KittyModifierBits.ctrl)

    @property
    def _super(self) -> bool:
        """Whether the super (Windows/Cmd) modifier is active."""
        return bool(self.modifiers_bits & KittyModifierBits.super)

    @property
    def _hyper(self) -> bool:
        """Whether the hyper modifier is active."""
        return bool(self.modifiers_bits & KittyModifierBits.hyper)

    @property
    def _meta(self) -> bool:
        """Whether the meta modifier is active."""
        return bool(self.modifiers_bits & KittyModifierBits.meta)

    @property
    def _caps_lock(self) -> bool:
        """Whether caps lock was known to be active during this sequence."""
        return bool(self.modifiers_bits & KittyModifierBits.caps_lock)

    @property
    def _num_lock(self) -> bool:
        """Whether num lock was known to be active during this sequence."""
        return bool(self.modifiers_bits & KittyModifierBits.num_lock)

    @property
    def pressed(self) -> bool:
        """
        Whether this is a key press event.

        :rtype: bool
        :returns: True if this is a key press event (event_type=1 or not specified), False for
            repeat or release events
        """
        if self._mode in (DecPrivateMode.SpecialInternalKitty,
                          DecPrivateMode.SpecialInternalLegacyCSIModifier):
            return self._match.event_type == 1
        # Default: always a 'pressed' event
        return True

    @property
    def repeated(self) -> bool:
        """
        Whether this is a key repeat event.

        :rtype: bool
        :returns: True if this is a key repeat event (event_type=2), False otherwise
        """
        if self._mode in (DecPrivateMode.SpecialInternalKitty,
                          DecPrivateMode.SpecialInternalLegacyCSIModifier):
            return self._match.event_type == 2
        # Default: not a repeat event
        return False

    @property
    def released(self) -> bool:
        """
        Whether this is a key release event.

        :rtype: bool
        :returns: True if this is a key release event (event_type=3), False otherwise
        """
        if self._mode in (DecPrivateMode.SpecialInternalKitty,
                          DecPrivateMode.SpecialInternalLegacyCSIModifier):
            return self._match.event_type == 3

        # Default: not a release event
        return False

    @property
    def event_mode(self) -> Optional[DecPrivateMode]:
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
    def mode(self) -> Optional[DecPrivateMode]:
        """
        DEC Private Mode associated with this keystroke, if any.

        :rtype: DecPrivateMode or None
        :returns: The :class:`~blessed.dec_modes.DecPrivateMode` enum value
            associated with this keystroke, or ``None`` if this is not a DEC mode event.
        """
        if self._mode is not None:
            return DecPrivateMode(self._mode)
        return None

    def mode_values(self) -> typing.Union[BracketedPasteEvent,
                                          MouseSGREvent, MouseLegacyEvent, FocusEvent]:
        """
        Return structured data for DEC private mode events.

        This method should only be called when :attr:`Keystroke.mode` is
        non-None and greater than 0.

        Returns a namedtuple with parsed event data for supported
        :class:`~.DecPrivateMode` modes:

        - ``BRACKETED_PASTE``: :class:`BracketedPasteEvent` with ``text`` field
        - ``MOUSE_EXTENDED_SGR``, ``MOUSE_ALL_MOTION``,  ``MOUSE_REPORT_DRAG``,
          and ``MOUSE_REPORT_CLICK`` events: :class:`MouseEvent` with button,
          coordinates, and modifier flags
        - ``FOCUS_EVENT_REPORTING``: :class:`FocusEvent` with ``gained`` boolean field

        :rtype: namedtuple
        :returns: Structured event data for this DEC mode event
        :raises TypeError: If mode is None or if mode is an unsupported DEC mode
        """
        if self._mode is None or self._match is None:
            raise TypeError("Should only call mode_values() when event_mode is non-None")

        # Call appropriate private parser method based on mode
        fn_callback = {
            DecPrivateMode.MOUSE_REPORT_CLICK: self._parse_mouse_legacy,
            DecPrivateMode.MOUSE_HILITE_TRACKING: self._parse_mouse_legacy,
            DecPrivateMode.MOUSE_REPORT_DRAG: self._parse_mouse_legacy,
            DecPrivateMode.MOUSE_ALL_MOTION: self._parse_mouse_legacy,
            DecPrivateMode.FOCUS_IN_OUT_EVENTS: self._parse_focus,
            DecPrivateMode.MOUSE_EXTENDED_SGR: self._parse_mouse_sgr,
            DecPrivateMode.MOUSE_SGR_PIXELS: self._parse_mouse_sgr,
            DecPrivateMode.BRACKETED_PASTE: self._parse_bracketed_paste,
        }.get(self._mode)
        if fn_callback is not None:
            return fn_callback()
        if self._mode > 0:
            # If you're reading this, you must have added a pattern to
            # DEC_EVENT_PATTERNS, now you should make a namedtuple and
            # write a brief parser and add it to the above list !
            raise TypeError(f"Unknown DEC mode {self._mode}")
        # This should never be reached, but mypy needs a return path
        raise TypeError("Should only call mode_values() when event_mode is non-None")

    def _parse_mouse_legacy(self) -> MouseLegacyEvent:
        """Parse legacy mouse event (X10/1000/1002/1003) from stored regex match."""
        cb = ord(self._match.group('cb')) - 32
        cx = ord(self._match.group('cx')) - 32
        cy = ord(self._match.group('cy')) - 32

        # Extract button and modifiers from cb
        button = cb & 3
        is_release = button == 3
        if is_release:
            button = 0  # Release doesn't specify which button

        # Extract modifier flags
        shift = bool(cb & 4)
        meta = bool(cb & 8)
        ctrl = bool(cb & 16)

        # Extract motion/drag flags
        is_motion = bool(cb & 32)

        # Wheel events
        is_wheel = cb >= 64
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
            is_wheel=is_wheel
        )

    def _parse_focus(self) -> FocusEvent:
        """Parse focus event from stored regex match."""
        gained = bool(self._match.group('io') == 'I')
        return FocusEvent(gained=gained)

    def _parse_mouse_sgr(self) -> MouseSGREvent:
        """
        Parse SGR mouse event from stored regex match.

        Handles both SGR (mode 1006) and SGR-Pixels (mode 1016) since they
        use identical wire formats: CSI < b;x;y m/M. The difference is semantic:
        - Mode 1006: coordinates represent character cell positions
        - Mode 1016: coordinates represent pixel positions
        Applications must interpret x,y coordinates based on which mode was enabled.
        """
        b = int(self._match.group('b'))
        x = int(self._match.group('x'))
        y = int(self._match.group('y'))
        event_type = self._match.group('type')

        is_release = event_type == 'm'

        # Extract modifiers from button code
        shift = bool(b & 4)
        meta = bool(b & 8)
        ctrl = bool(b & 16)

        # Extract motion/drag flags
        is_motion = bool(b & 32)
        is_wheel = b in (64, 65)  # wheel up/down

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
            is_motion=is_motion,
            is_wheel=is_wheel
        )

    def _parse_bracketed_paste(self) -> BracketedPasteEvent:
        """Parse bracketed paste event from stored regex match."""
        return BracketedPasteEvent(text=self._match.group('text'))

    def _check_name_match(self, expected_name: str, expected_name_without_event: str) -> bool:
        """
        Check if keystroke name matches expected name patterns.

        Used by event predicates to determine if the name matches.
        """
        if self.name == expected_name:
            # Exact match with event type suffix
            return True
        if self.name == expected_name_without_event:
            # Match without event type suffix (for press events mainly)
            return True
        if self.name and self.name.startswith(expected_name_without_event + '_'):
            # Name starts with expected prefix
            return True
        return False

    def _build_event_predicate(self,
                               event_type: str,
                               expected_name: str,
                               expected_name_without_event: str) -> typing.Callable[[Optional[str],
                                                                                     bool],
                                                                                    bool]:
        """
        Build a predicate function for event-type checking.

        Returns a callable that checks if keystroke matches the expected event type.
        """
        def event_predicate(char: Optional[str] = None, ignore_case: bool = True) -> bool:
            """Check if keystroke matches the expected event type."""
            # Parameters are accepted but not used for event predicates
            if not self._check_name_match(expected_name, expected_name_without_event):
                return False

            # Check event type
            return {'pressed': self.pressed,
                    'released': self.released,
                    'repeated': self.repeated}.get(event_type, False)
        return event_predicate

    def _build_modifier_predicate(
            self, tokens: typing.List[str]) -> typing.Callable[[Optional[str], bool], bool]:
        """
        Build a predicate function for modifier checking.

        Returns a callable that checks if keystroke has the specified modifiers.
        """
        def modifier_predicate(char: Optional[str] = None, ignore_case: bool = True) -> bool:
            # Build expected modifier bits from tokens
            expected_bits = 0
            for token in tokens:
                expected_bits |= getattr(KittyModifierBits, token)

            # Strip lock bits to ignore caps_lock and num_lock
            effective_bits = self.modifiers_bits & ~(
                KittyModifierBits.caps_lock | KittyModifierBits.num_lock)

            # When matching with a character and it's alphabetic, be lenient about Shift
            # because shift is implicit in the case of the letter
            if char and len(char) == 1 and char.isalpha():
                # Strip shift from both sides for letter matching
                effective_bits_no_shift = effective_bits & ~KittyModifierBits.shift
                expected_bits_no_shift = expected_bits & ~KittyModifierBits.shift
                if effective_bits_no_shift != expected_bits_no_shift:
                    return False
            else:
                # Exact matching (no char, or non-alpha char)
                if effective_bits != expected_bits:
                    return False

            # If no character specified
            if char is None:
                # Text keys (with printable character values) require char argument
                keystroke_char = self.value
                if keystroke_char and len(keystroke_char) == 1 and keystroke_char.isprintable():
                    return False
                # Non-text keys can match on modifiers alone
                return True

            # Check character match using same logic as value property
            keystroke_char = self.value

            # If value is empty or not a single printable character, can't match
            if not keystroke_char or len(
                    keystroke_char) > 1 or not keystroke_char.isprintable():
                return False

            # Compare characters
            if ignore_case:
                return keystroke_char.lower() == char.lower()
            return keystroke_char == char

        return modifier_predicate

    def _build_keycode_predicate(
            self, modifier_tokens: typing.List[str],
            key_name: str) -> typing.Callable[[Optional[str], bool], bool]:
        """
        Build a predicate function for application key checking.

        Returns a callable that checks if keystroke matches the expected keycode and modifiers.
        """
        def keycode_predicate(char: Optional[str] = None, ignore_case: bool = True) -> bool:
            # ignore_case parameter is accepted but not used for application keys
            # Application keys don't match when a character is provided
            if char is not None:
                return False

            # Get expected keycode from key name
            keycodes = get_keyboard_codes()
            expected_key_constant = f'KEY_{key_name.upper()}'

            # Find the keycode value
            expected_code = None
            for code, name in keycodes.items():
                if name == expected_key_constant:
                    expected_code = code
                    break

            if expected_code is None or self._code != expected_code:
                return False

            # Build expected modifier bits (same as _build_modifier_predicate)
            expected_bits = 0
            for token in modifier_tokens:
                expected_bits |= getattr(KittyModifierBits, token)

            # Check modifiers - exact match only
            effective_bits = self.modifiers_bits & ~(
                KittyModifierBits.caps_lock | KittyModifierBits.num_lock)
            return effective_bits == expected_bits

        return keycode_predicate

    def __getattr__(self, attr: str) -> typing.Callable[[Optional[str], bool], bool]:
        """
        Dynamic compound modifier and application key predicates via __getattr__.

        Recognizes attributes starting with "is_" and parses underscore-separated
        tokens to create dynamic predicate functions.

        :arg str attr: Attribute name being accessed
        :rtype: callable or raises AttributeError
        :returns: Callable predicate function with signature
            ``Callable[[Optional[str], bool], bool]``.

            All predicates accept the same parameters:

            - ``char`` (Optional[str]): Character to match against keystroke value
            - ``ignore_case`` (bool): Whether to ignore case when matching characters

            For event predicates and application key predicates, these
            parameters are accepted but not used.
        """
        if not attr.startswith('is_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")

        # Extract tokens after 'is_'
        tokens_str = attr[3:]  # Remove 'is_' prefix
        if not tokens_str:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{attr}'")

        # Check if this matches the keystroke name directly (for key names with event types)
        # e.g., is_key_shift_f2_released() should match name='KEY_SHIFT_F2_RELEASED'
        expected_name = tokens_str.upper()
        if self.name == expected_name:
            return lambda: True

        # Try extracting event type suffix, only one of them should be used
        event_type = None
        for match_name in ('pressed', 'released', 'repeated'):
            if tokens_str.endswith(f'_{match_name}'):
                # Remove '_pressed', etc. (length + 1 for the underscore)
                event_type = match_name
                tokens_str = tokens_str[:-len(match_name) - 1]
                break

        # If event type was found, return event predicate
        if event_type:
            expected_name_without_event = tokens_str.upper()
            return self._build_event_predicate(event_type, expected_name,
                                               expected_name_without_event)

        # Parse tokens to separate modifiers from potential key name
        tokens = tokens_str.split('_')

        # Separate modifiers from potential key name
        modifiers = []
        key_name_tokens = []

        for i, token in enumerate(tokens):
            if token in KittyModifierBits.names_modifiers_only:
                modifiers.append(token)
            else:
                # Remaining tokens could be a key name
                key_name_tokens = tokens[i:]
                break

        # If we have key name tokens, check if they form a valid application key
        if key_name_tokens:
            key_name = '_'.join(key_name_tokens)
            keycodes = get_keyboard_codes()
            expected_key_constant = f'KEY_{key_name.upper()}'

            # Check if this is a valid application key
            if expected_key_constant in keycodes.values():
                return self._build_keycode_predicate(modifiers, key_name)

        # No valid key name found - validate as modifier-only predicate
        invalid_tokens = [token for token in tokens
                          if token not in KittyModifierBits.names_modifiers_only]
        if invalid_tokens:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{attr}' "
                f"(invalid modifier tokens: {invalid_tokens})")

        # Return modifier predicate
        return self._build_modifier_predicate(tokens)

# Device Attributes (DA1) response representation


class DeviceAttribute(object):
    """
    Represents a terminal's Device Attributes (DA1) response.

    Device Attributes queries allow discovering terminal capabilities and type.
    The primary DA1 query sends CSI c and expects a response like:

    ```
    CSI ? Psc ; Ps1 ; Ps2 ; ... ; Psn c
    ```

    Where Psc is the service class (architectural class) and Ps1...Psn are
    supported extensions/capabilities.
    """

    def __init__(self, raw: str, service_class: int,
                 extensions: typing.Optional[typing.List[int]]) -> None:
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
    def supports_sixel(self) -> bool:
        """
        Whether the terminal supports sixel graphics.

        :rtype: bool
        :returns: True if extension 4 (sixel) is present in device attributes
        """
        return 4 in self.extensions

    @classmethod
    def from_match(cls, match: Match[str]) -> 'DeviceAttribute':
        """
        Create DeviceAttribute from regex match object.

        :arg re.Match match: Regex match object with groups for service_class and extensions
        :rtype: DeviceAttribute
        :returns: DeviceAttribute instance parsed from match
        """
        service_class = int(match.group(1))
        extensions_str = match.group(2)
        extensions: typing.List[int] = []

        if extensions_str:
            # Remove leading semicolon and split by semicolon
            ext_parts = extensions_str.lstrip(';').split(';')
            for part in ext_parts:
                if part.strip() and part.isdigit():
                    extensions.append(int(part.strip()))

        return cls(match.group(0), service_class, extensions)

    @classmethod
    def from_string(cls, response_str: str) -> Optional['DeviceAttribute']:
        r"""
        Create DeviceAttribute by parsing response string.

        :arg str response_str: DA1 response string like ``\x1b[?64;1;2;4;7c``
        :rtype: DeviceAttribute or None
        :returns: DeviceAttribute instance if parsing succeeds, None otherwise
        """
        # Match pattern: ESC [ ? service_class ; extension1 ; extension2 ; ... c
        pattern = re.compile(r'\x1b\[\?([0-9]+)((?:;[0-9]+)*)c')
        match = pattern.match(response_str)

        if match:
            return cls.from_match(match)
        return None

    def __repr__(self) -> str:
        """String representation of DeviceAttribute."""
        return ('DeviceAttribute(service_class={}, extensions={}, supports_sixel={})'
                .format(self.service_class, sorted(self.extensions), self.supports_sixel))

    def __eq__(self, other: typing.Any) -> bool:
        """Check equality based on service class and extensions."""
        if isinstance(other, DeviceAttribute):
            return (self.service_class == other.service_class and
                    self.extensions == other.extensions)
        return False


def get_curses_keycodes() -> Dict[str, int]:
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


@functools.lru_cache(maxsize=1)
def get_keyboard_codes() -> Dict[int, str]:
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

    # merge in homemade KEY_TAB, KEY_KP_*, KEY_MENU added to our module space
    keycodes.update((k, v) for k, v in globals().items() if k.startswith('KEY_'))

    # invert dictionary (key, values) => (values, key), preferring the
    # last-most inserted value ('KEY_DELETE' over 'KEY_DC').
    return dict(zip(keycodes.values(), keycodes.keys()))


def _alternative_left_right(term: typing.Any) -> Dict[str, int]:
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


def get_keyboard_sequences(term: typing.Any) -> 'OrderedDict[str, int]':
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
    # A small gem from curses.has_key that makes this all possible,
    # _capability_names: a lookup table of terminal capability names for
    # keyboard sequences (fe. kcub1, key_left), keyed by the values of
    # constants found beginning with KEY_ in the main curses module
    # (such as KEY_LEFT).
    #
    # latin1 encoding is used so that bytes in 8-bit range of 127-255
    # have equivalent chr() and unichr() values, so that the sequence
    # of a kermit or avatar terminal, for example, remains unchanged
    # in its byte sequence values even when represented by unicode.
    #
    sequence_map = {
        seq.decode('latin1'): val for seq, val in (
            (curses.tigetstr(cap), val) for (val, cap) in capability_names.items()
        ) if seq
    } if term.does_styling else {}

    sequence_map.update(_alternative_left_right(term))
    sequence_map.update(DEFAULT_SEQUENCE_MIXIN)

    # This is for fast lookup matching of sequences, preferring
    # full-length sequence such as ('\x1b[D', KEY_LEFT)
    # over simple sequences such as ('\x1b', KEY_EXIT).
    return OrderedDict((
        (seq, sequence_map[seq]) for seq in sorted(
            sequence_map.keys(), key=len, reverse=True)))


def get_leading_prefixes(sequences: typing.Iterable[str]) -> Set[str]:
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


def resolve_sequence(  # pylint: disable=too-many-positional-arguments
        text: str,
        mapper: 'OrderedDict[str, int]',
        codes: Dict[int, str],
        prefixes: Set[str],
        final: bool = False,
        mode_1016_active: Optional[bool] = None) -> Keystroke:
    r"""
    Return a single :class:`Keystroke` instance for given sequence ``text``.

    :arg str text: string of characters received from terminal input stream.
    :arg OrderedDict mapper: unicode multibyte sequences, such as ``u'\x1b[D'``
        paired by their integer value (260)
    :arg dict codes: a :type:`dict` of integer values (such as 260) paired
        by their mnemonic name, such as ``'KEY_LEFT'``.
    :arg set prefixes: Set of all valid sequence prefixes for quick matching
    :arg bool final: Whether this is the final resolution attempt (no more input expected)
    :arg bool mode_1016_active: Whether SGR-Pixels mouse mode (1016) is active
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
    for match_fn in (functools.partial(_match_dec_event, mode_1016_active=mode_1016_active),
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

    # Resolve for alt+backspace and metaSendsEscape, KEY_ALT_[..],
    # when the sequence so far is not a 'known prefix', or, when
    # final is True, we return the ambiguously matched KEY_ALT_[...]
    maybe_alt = (ks is not None and ks.code == curses.KEY_EXIT and len(text) > 1)
    final_or_not_keystroke = (
        final or (len(text) > 1 and text[1] == '\x7f') or text[:2] not in prefixes)
    if (maybe_alt and final_or_not_keystroke):
        ks = Keystroke(ucs=text[:2])
    # final match is just simple resolution of the first codepoint of text,
    if ks is None:
        ks = Keystroke(ucs=text and text[0] or '')
    return ks


def _time_left(stime: float, timeout: Optional[float]) -> Optional[float]:
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


def _read_until(term: 'Terminal',
                pattern: str,
                timeout: Optional[float]) -> Tuple[Optional[Match[str]], str]:
    """
    Convenience read-until-pattern function, supporting :meth:`~._query_response`.

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
    match, buf = None, ''

    # first, buffer all pending data. pexpect library provides a
    # 'searchwindowsize' attribute that limits this memory region.  We're not
    # concerned about OOM conditions: only (human) keyboard and mouse input
    # and terminal response sequences are expected, the application developer
    # should keep up.

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


def _match_dec_event(text: str, mode_1016_active: Optional[bool] = None) -> Optional[Keystroke]:
    """
    Attempt to match text against DEC event patterns.

    :arg str text: Input text to match against DEC patterns
    :arg Terminal term: Terminal instance for checking enabled modes (optional)
    :rtype: Keystroke or None
    :returns: :class:`Keystroke` with DEC event data if matched, ``None`` otherwise
    """
    for mode, pattern in DEC_EVENT_PATTERNS:
        match = pattern.match(text)
        if match:
            if mode == DecPrivateMode.MOUSE_EXTENDED_SGR and mode_1016_active:
                # recast mode 1006 as mode 1016 if that mode is known to be active
                mode = DecPrivateMode.MOUSE_SGR_PIXELS
            return Keystroke(ucs=match.group(0), mode=mode, match=match)
    return None


def _match_kitty_key(text: str) -> Optional[Keystroke]:
    """
    Attempt to match text against Kitty keyboard protocol patterns.

    :arg str text: Input text to match against Kitty patterns
    :rtype: Keystroke or None
    :returns: :class:`Keystroke` with Kitty key data if matched, ``None`` otherwise

    Supports Kitty keyboard protocol sequences of the form:

    ```
    CSI unicode-key-code u                                            # Basic form
    CSI unicode-key-code ; modifiers u                                # With modifiers
    CSI unicode-key-code : shifted-key : base-key ; modifiers u       # With alternate keys
    CSI unicode-key-code ; modifiers : event-type u                   # With event type
    CSI unicode-key-code ; modifiers : event-type ; text-codepoints u # Full form
    ```
    """
    match = KITTY_KB_PROTOCOL_PATTERN.match(text)

    def int_when_non_empty(_m: Match[str], _key: str) -> Optional[int]:
        return int(_m.group(_key)) if _m.group(_key) else None

    def int_when_non_empty_otherwise_1(
            _m: Match[str], _key: str) -> int:
        return int(_m.group(_key)) if _m.group(_key) else 1

    if match:
        _int_codepoints: Tuple[int, ...] = tuple()
        if match.group('text_codepoints'):
            _codepoints_text = match.group('text_codepoints').split(':')
            _int_codepoints = tuple(int(cp) for cp in _codepoints_text if cp)

        # Create KittyKeyEvent namedtuple
        kitty_event = KittyKeyEvent(
            unicode_key=int(match.group('unicode_key')),
            shifted_key=int_when_non_empty(match, 'shifted_key'),
            base_key=int_when_non_empty(match, 'base_key'),
            modifiers=int_when_non_empty_otherwise_1(match, 'modifiers'),
            event_type=int_when_non_empty_otherwise_1(match, 'event_type'),
            int_codepoints=_int_codepoints
        )

        # Create Keystroke with special mode to indicate Kitty protocol
        return Keystroke(ucs=match.group(0),
                         mode=DecPrivateMode.SpecialInternalKitty,
                         match=kitty_event)

    return None


def _match_modify_other_keys(text: str) -> Optional[Keystroke]:
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
        return Keystroke(ucs=match.group(0),
                         mode=DecPrivateMode.SpecialInternalModifyOtherKeys,
                         match=modify_event)

    return None


def _match_legacy_csi_modifiers(text: str) -> Optional[Keystroke]:
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
    legacy_event = None
    match = LEGACY_CSI_MODIFIERS_PATTERN.match(text)
    match_tilde = LEGACY_CSI_TILDE_PATTERN.match(text)
    if match:
        kind = 'letter'
        modifiers = int(match.group('mod'))
        key_id = match.group('final')
        matched_text = match.group(0)

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
        }.get(key_id)
        # Extract event_type, default to 1 if not present
        event_type = int(match.group('event')) if match.group('event') else 1

        if keycode_match is not None:
            legacy_event = LegacyCSIKeyEvent(
                kind=kind,
                key_id=key_id,
                modifiers=modifiers,
                event_type=event_type)
            return Keystroke(ucs=matched_text,
                             code=keycode_match,
                             mode=DecPrivateMode.SpecialInternalLegacyCSIModifier,
                             match=legacy_event)

    # Try tilde form: ESC [ number ; modifiers ~
    elif match_tilde:
        kind = 'tilde'
        modifiers = int(match_tilde.group('mod'))
        key_id = int(match_tilde.group('key_num'))
        matched_text = match_tilde.group(0)
        # Extract event_type, default to 1 if not present
        event_type = int(match_tilde.group('event')) if match_tilde.group('event') else 1

        # Map tilde key numbers to curses key codes, you can find a table of these here,
        # https://tomscii.sig7.se/zutty/doc/KEYS.html and somewhat more completely, here:
        # https://invisible-island.net/xterm/xterm-function-keys.html
        keycode_match = {
            2: curses.KEY_IC,       # Insert
            3: curses.KEY_DC,       # Delete
            5: curses.KEY_PPAGE,    # Page Up
            6: curses.KEY_NPAGE,    # Page Down
            7: curses.KEY_HOME,     # Home
            8: curses.KEY_END,      # End
            11: curses.KEY_F1,      # F1
            12: curses.KEY_F2,      # ..
            13: curses.KEY_F3,
            14: curses.KEY_F4,
            15: curses.KEY_F5,
            17: curses.KEY_F6,
            18: curses.KEY_F7,
            19: curses.KEY_F8,
            20: curses.KEY_F9,
            21: curses.KEY_F10,
            23: curses.KEY_F11,
            24: curses.KEY_F12,
            25: curses.KEY_F13,
            26: curses.KEY_F14,
            28: curses.KEY_F15,
            29: KEY_MENU,
            31: curses.KEY_F17,
            32: curses.KEY_F18,
            33: curses.KEY_F19,
            34: curses.KEY_F20,
        }.get(key_id)

        if keycode_match is not None:
            legacy_event = LegacyCSIKeyEvent(
                kind=kind,
                key_id=key_id,
                modifiers=modifiers,
                event_type=event_type)
            return Keystroke(ucs=matched_text,
                             code=keycode_match,
                             mode=DecPrivateMode.SpecialInternalLegacyCSIModifier,
                             match=legacy_event)

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
            # SS3 form doesn't support event_type, default to 1 (press)
            legacy_event = LegacyCSIKeyEvent(
                kind='ss3-fkey',
                key_id=final_char,
                modifiers=modifiers,
                event_type=1)
            return Keystroke(ucs=matched_text, code=keycode_match, mode=-3, match=legacy_event)

    return None


# We invent a few to fixup for missing keys in curses, these aren't especially
# required or useful except to survive as API compatibility for the earliest
# versions of this software. They must be these values in this order, used as
# constants for equality checks to Keystroke.code.
KEY_TAB = 512
KEY_KP_MULTIPLY = 513
KEY_KP_ADD = 514
KEY_KP_SEPARATOR = 515
KEY_KP_SUBTRACT = 516
KEY_KP_DECIMAL = 517
KEY_KP_DIVIDE = 518
KEY_KP_EQUAL = 519
KEY_KP_0 = 520
KEY_KP_1 = 521
KEY_KP_2 = 522
KEY_KP_3 = 523
KEY_KP_4 = 524
KEY_KP_5 = 525
KEY_KP_6 = 526
KEY_KP_7 = 527
KEY_KP_8 = 528
KEY_KP_9 = 529
KEY_MENU = 530

# Kitty keyboard protocol PUA (Private Use Area) key codes for modifier keys
# These are from the functional key definitions in the Kitty keyboard protocol spec
# PUA starts at 57344 (0xE000)
KEY_LEFT_SHIFT = 57441          # 0xE061
KEY_LEFT_CONTROL = 57442        # 0xE062
KEY_LEFT_ALT = 57443            # 0xE063
KEY_LEFT_SUPER = 57444          # 0xE064
KEY_LEFT_HYPER = 57445          # 0xE065
KEY_LEFT_META = 57446           # 0xE066
KEY_RIGHT_SHIFT = 57447         # 0xE067
KEY_RIGHT_CONTROL = 57448       # 0xE068
KEY_RIGHT_ALT = 57449           # 0xE069
KEY_RIGHT_SUPER = 57450         # 0xE06A
KEY_RIGHT_HYPER = 57451         # 0xE06B
KEY_RIGHT_META = 57452          # 0xE06C

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
    (chr(10), curses.KEY_ENTER),
    (chr(13), curses.KEY_ENTER),
    (chr(8), curses.KEY_BACKSPACE),
    (chr(9), KEY_TAB),
    (chr(27), curses.KEY_EXIT),
    (chr(127), curses.KEY_BACKSPACE),

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
    (u"\x1bOM", curses.KEY_ENTER),
    (u"\x1bOj", KEY_KP_MULTIPLY),
    (u"\x1bOk", KEY_KP_ADD),
    (u"\x1bOl", KEY_KP_SEPARATOR),
    (u"\x1bOm", KEY_KP_SUBTRACT),
    (u"\x1bOn", KEY_KP_DECIMAL),
    (u"\x1bOo", KEY_KP_DIVIDE),
    (u"\x1bOX", KEY_KP_EQUAL),
    (u"\x1bOp", KEY_KP_0),
    (u"\x1bOq", KEY_KP_1),
    (u"\x1bOr", KEY_KP_2),
    (u"\x1bOs", KEY_KP_3),
    (u"\x1bOt", KEY_KP_4),
    (u"\x1bOu", KEY_KP_5),
    (u"\x1bOv", KEY_KP_6),
    (u"\x1bOw", KEY_KP_7),
    (u"\x1bOx", KEY_KP_8),
    (u"\x1bOy", KEY_KP_9),

    # We wouldn't even bother to detect them unless 'term.smkx' was known to be
    # emitted with a context manager... if it weren't for these "legacy" DEC VT
    # special keys, that are now transmitted as F1-F4 for many terminals, unless
    # negotiated to do something else! There is a lot of legacy to these F keys
    # in particular, a bit of sordid story.
    (u"\x1bOP", curses.KEY_F1),
    (u"\x1bOQ", curses.KEY_F2),
    (u"\x1bOR", curses.KEY_F3),
    (u"\x1bOS", curses.KEY_F4),

    # Kitty disambiguate mode: F1-F4 sent as CSI sequences instead of SS3
    # F1 = CSI P, F2 = CSI Q, F3 = CSI 13~, F4 = CSI S
    # Note: These must come after longer sequences that start with \x1b[ to avoid
    # premature matching, but get_keyboard_sequences() sorts by length anyway.
    (u"\x1b[P", curses.KEY_F1),
    (u"\x1b[Q", curses.KEY_F2),
    (u"\x1b[13~", curses.KEY_F3),
    (u"\x1b[S", curses.KEY_F4),

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


def _reinit_escdelay() -> None:
    # pylint: disable=global-statement
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

    Encapsulates the integer flag value returned by Kitty keyboard protocol queries and provides
    properties for individual flag bits and a method to convert back to enable_kitty_keyboard()
    arguments.
    """

    def __init__(self, value: int) -> None:
        """
        Initialize with raw integer flag value.

        :arg int value: Raw integer flags value from Kitty keyboard protocol query
        """
        self.value = int(value)

    @property
    def disambiguate(self) -> bool:
        """Whether disambiguated escape codes are enabled (bit 1)."""
        return bool(self.value & 0b1)

    @disambiguate.setter
    def disambiguate(self, enabled: bool) -> None:
        """Set whether disambiguated escape codes are enabled (bit 1)."""
        if enabled:
            self.value |= 0b1
        else:
            self.value &= ~0b1

    @property
    def report_events(self) -> bool:
        """Whether key repeat and release events are reported (bit 2)."""
        return bool(self.value & 0b10)

    @report_events.setter
    def report_events(self, enabled: bool) -> None:
        """Set whether key repeat and release events are reported (bit 2)."""
        if enabled:
            self.value |= 0b10
        else:
            self.value &= ~0b10

    @property
    def report_alternates(self) -> bool:
        """Whether shifted and base layout keys are reported for shortcuts (bit 4)."""
        return bool(self.value & 0b100)

    @report_alternates.setter
    def report_alternates(self, enabled: bool) -> None:
        """Set whether shifted and base layout keys are reported for shortcuts (bit 4)."""
        if enabled:
            self.value |= 0b100
        else:
            self.value &= ~0b100

    @property
    def report_all_keys(self) -> bool:
        """Whether all keys are reported as escape codes (bit 8)."""
        return bool(self.value & 0b1000)

    @report_all_keys.setter
    def report_all_keys(self, enabled: bool) -> None:
        """Set whether all keys are reported as escape codes (bit 8)."""
        if enabled:
            self.value |= 0b1000
        else:
            self.value &= ~0b1000

    @property
    def report_text(self) -> bool:
        """Whether associated text is reported with key events (bit 16)."""
        return bool(self.value & 0b10000)

    @report_text.setter
    def report_text(self, enabled: bool) -> None:
        """Set whether associated text is reported with key events (bit 16)."""
        if enabled:
            self.value |= 0b10000
        else:
            self.value &= ~0b10000

    def make_arguments(self) -> Dict[str, bool]:
        """
        Return dictionary of arguments suitable for enable_kitty_keyboard().

        :rtype: dict
        :returns: Dictionary with boolean flags suitable for passing as keyword arguments to
            enable_kitty_keyboard()
        """
        return {
            'disambiguate': self.disambiguate,
            'report_events': self.report_events,
            'report_alternates': self.report_alternates,
            'report_all_keys': self.report_all_keys,
            'report_text': self.report_text
        }

    def __repr__(self) -> str:
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

    def __eq__(self, other: typing.Any) -> bool:
        """Check equality based on flag values."""
        if isinstance(other, KittyKeyboardProtocol):
            return self.value == other.value
        if isinstance(other, int):
            return self.value == other
        return False


__all__ = ('Keystroke', 'get_keyboard_codes', 'get_keyboard_sequences',
           '_match_dec_event', '_match_kitty_key', '_match_modify_other_keys',
           '_match_legacy_csi_modifiers', 'BracketedPasteEvent', 'MouseEvent',
           'MouseSGREvent', 'MouseLegacyEvent', 'FocusEvent', 'SyncEvent', 'KittyKeyEvent',
           'ModifyOtherKeysEvent', 'LegacyCSIKeyEvent', 'KittyKeyboardProtocol',
           'DeviceAttribute')
