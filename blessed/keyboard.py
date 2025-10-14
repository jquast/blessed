"""Sub-module providing 'keyboard awareness'."""

# std imports
import os
import re
import time
import typing
import platform
from typing import TYPE_CHECKING, Set, Dict, Match, TypeVar, Optional
from collections import OrderedDict, namedtuple

if TYPE_CHECKING:  # pragma: no cover
    # local
    from blessed.terminal import Terminal


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


# Modifier support for advanced keyboard protocols
ModifyOtherKeysEvent = namedtuple('ModifyOtherKeysEvent', 'key modifiers')
LegacyCSIKeyEvent = namedtuple('LegacyCSIKeyEvent', 'kind key_id modifiers event_type')

# Regex patterns for modifier sequences
RE_PATTERN_LEGACY_CSI_MODIFIERS = re.compile(
    r'\x1b\[1;(?P<mod>\d+)(?::(?P<event>\d+))?(?P<final>[ABCDEFHPQRS])')
RE_PATTERN_LEGACY_CSI_TILDE = re.compile(
    r'\x1b\[(?P<key_num>\d+);(?P<mod>\d+)(?::(?P<event>\d+))?~')
RE_PATTERN_LEGACY_SS3_FKEYS = re.compile(r'\x1bO(?P<mod>\d)(?P<final>[PQRS])')
RE_PATTERN_MODIFY_OTHER = re.compile(
    r'\x1b\[27;(?P<modifiers>\d+);(?P<key>\d+)(?P<tilde>~?)')

# Control character mappings
# Note: Ctrl+Space (code 0) is handled specially as 'SPACE', not included here
SYMBOLS_MAP_CTRL_CHAR = {'[': 27, '\\': 28, ']': 29, '^': 30, '_': 31, '?': 127}
SYMBOLS_MAP_CTRL_VALUE = {v: k for k, v in SYMBOLS_MAP_CTRL_CHAR.items()}


class KittyModifierBits:
    """Standard modifier bit flags (compatible with Kitty keyboard protocol)."""
    # pylint: disable=too-few-public-methods

    shift = 0b1
    alt = 0b10
    ctrl = 0b100
    super = 0b1000
    hyper = 0b10000
    meta = 0b100000
    caps_lock = 0b1000000
    num_lock = 0b10000000

    #: Names of bitwise flags attached to this class
    names = ('shift', 'alt', 'ctrl', 'super', 'hyper', 'meta',
             'caps_lock', 'num_lock')

    #: Modifiers only, in the generally preferred order in phrasing
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

    The string-name of the sequence, such as ``'KEY_LEFT'`` is accessed
    by property :attr:`name`, and is used by the :meth:`__repr__` method
    to display a human-readable form of the Keystroke this class
    instance represents. It may otherwise by joined, split, or evaluated
    just as as any other unicode string.
    """
    _name = None
    _code = None

    def __new__(cls: typing.Type[_T], ucs: str = '', code: Optional[int] = None,
                name: Optional[str] = None, mode: Optional[int] = None,
                match: typing.Any = None) -> _T:
        # pylint: disable=too-many-positional-arguments
        """Class constructor."""
        new = str.__new__(cls, ucs)
        new._name = name
        new._code = code
        new._mode = mode  # Internal mode indicator for different protocols
        new._match = match  # regex match object for protocol-specific data
        new._modifiers = cls._infer_modifiers(ucs, mode, match)
        return new

    @staticmethod
    def _infer_modifiers(ucs: str, mode: Optional[int], match: typing.Any) -> int:
        """
        Infer modifiers from keystroke data.

        Returns modifiers in standard format: 1 + bitwise OR of modifier flags.
        """
        # ModifyOtherKeys or Legacy CSI modifiers
        if mode is not None and mode < 0 and match is not None:
            return match.modifiers

        # Legacy sequences starting with ESC (metaSendsEscape)
        if len(ucs) == 2 and ucs[0] == '\x1b':
            char_code = ord(ucs[1])

            # Special C0 controls that should be Alt-only per legacy spec
            # These represent common Alt+key combinations that are unambiguous
            # (Enter, Escape, DEL, Tab)
            if char_code in {0x0d, 0x1b, 0x7f, 0x09}:
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
                return 1 + KittyModifierBits.alt + shift

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

        Returns name like 'KEY_CTRL_ALT_F1' or 'KEY_SHIFT_UP'.
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

        # For press events with no modifiers, return None (use existing name)
        if not mod_parts:
            return None

        # Build result with modifiers
        return f"KEY_{'_'.join(mod_parts)}_{base_name}"

    def _get_control_char_name(self) -> Optional[str]:
        """
        Get name for single-character control sequences.

        Returns name like 'KEY_CTRL_A' or 'KEY_CTRL_SPACE'.
        """
        if len(self) != 1:
            return None

        char_code = ord(self)
        # Special case: Ctrl+Space sends \x00
        if char_code == 0:
            return 'KEY_CTRL_SPACE'
        if 1 <= char_code <= 26:
            # Ctrl+A through Ctrl+Z
            return f'KEY_CTRL_{chr(char_code + ord("A") - 1)}'
        if char_code in SYMBOLS_MAP_CTRL_VALUE:
            return f'KEY_CTRL_{SYMBOLS_MAP_CTRL_VALUE[char_code]}'
        return None

    def _get_control_symbol(self, char_code: int) -> Optional[str]:
        """
        Get control symbol for a character code.

        Returns symbol like 'A' for Ctrl+A, 'SPACE' for Ctrl+Space, etc.
        """
        # Special case: Ctrl+Space sends \x00
        if char_code == 0:
            return 'SPACE'
        if 1 <= char_code <= 26:
            # Ctrl+A through Ctrl+Z
            return chr(char_code + ord("A") - 1)
        if char_code in SYMBOLS_MAP_CTRL_VALUE:
            # Ctrl+symbol
            return SYMBOLS_MAP_CTRL_VALUE[char_code]
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
        """
        Get name for metaSendsEscape sequences (ESC + char).

        Returns name like 'KEY_ALT_A', 'KEY_ALT_SHIFT_Z', 'KEY_CTRL_ALT_C', or 'KEY_ALT_ESCAPE'.
        """
        # pylint: disable=too-many-return-statements,too-complex
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
            if ch == ' ':
                return 'KEY_ALT_SPACE'
            return f'KEY_ALT_{ch}'
        if self[1] == '\x7f' and self.modifiers == 3:
            return 'KEY_ALT_BACKSPACE'
        return None

    @property
    def name(self) -> Optional[str]:
        r"""
        Special application key name.

        This is the best equality attribute to use for special keys, as raw string value of the 'F1'
        key can be received in many different values.

        The 'name' property will return a reliable constant, 'KEY_F1'.

        The name supports "modifiers", such as 'KEY_CTRL_F1', 'KEY_CTRL_ALT_F1',
        'KEY_CTRL_ALT_SHIFT_F1'.

        This also supports alphanumerics when combined with a modifier, such as KEY_ALT_z and
        KEY_ALT_SHIFT_Z

        When non-None, all phrases begin with 'KEY' except one exception, 'CSI' is returned for
        '\\x1b[' to indicate the beginning of a presumed unsupported input sequence. The phrase
        'KEY_ALT_[' is never returned and unsupported.

        If this value is None, then it can probably be assumed that the value is an unsurprising
        textual character without any modifiers.
        """
        if self._name is not None:
            return self._name

        # Try each helper method in sequence
        result = self._get_modified_keycode_name()
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
        Modifier flags in standard keyboard protocol format.

        :rtype: int
        :returns: Standard-style modifiers value (1 means no modifiers)

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
        if self._mode is not None and self._mode < 0:
            # Check if _match has event_type (LegacyCSIKeyEvent),
            # defaulting to 1 (pressed) if not present.
            return getattr(self._match, 'event_type', 1) == 1
        # Default: always a 'pressed' event
        return True

    @staticmethod
    def _make_expected_bits(tokens_modifiers: typing.List[str]) -> int:
        """Build expected modifier bits from token list."""
        expected_bits = 0
        for token in tokens_modifiers:
            expected_bits |= getattr(KittyModifierBits, token)
        return expected_bits

    def _make_effective_bits(self) -> int:
        """Returns modifier bits stripped of caps_lock and num_lock."""
        stripped_bits = KittyModifierBits.caps_lock | KittyModifierBits.num_lock
        return self.modifiers_bits & ~(stripped_bits)

    def _build_appkeys_predicate(self, tokens_modifiers: typing.List[str], key_name: str
                                 ) -> typing.Callable[[Optional[str], bool], bool]:
        """
        Build a predicate function for checking modifiers of application keys.

        Returns a callable that checks only 'token_modifiers'
        """
        def keycode_predicate(char: Optional[str] = None, ignore_case: bool = True) -> bool:
            # pylint: disable=unused-argument
            # ignore_case parameter is accepted but not used for application keys

            # Application keys never match when 'char' is non-None/non-Empty
            if char:
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

            # validate only the modifier tokens
            return self._make_expected_bits(tokens_modifiers) == self._make_effective_bits()

        return keycode_predicate

    def _build_alphanum_predicate(self, tokens_modifiers: typing.List[str]
                                  ) -> typing.Callable[[Optional[str], bool], bool]:
        """
        Build a predicate function for modifier checking of alphanumeric input.

        Returns a callable that checks if keystroke matches the predicate 'tokens_modifiers', as
        well as the alphanumeric checks of optional 'char' and 'ignore_case'.
        """
        # pylint: disable=too-many-return-statements
        def modifier_predicate(char: Optional[str] = None, ignore_case: bool = True) -> bool:
            # Build expected modifier bits from tokens,
            # Stripped to ignore caps_lock and num_lock
            expected_bits = self._make_expected_bits(tokens_modifiers)
            effective_bits = self._make_effective_bits()

            # When matching with a character and it's alphabetic, be lenient
            # about Shift because it is implicit in the case of the letter
            if char and len(char) == 1 and char.isalpha():
                # Strip shift from both sides for letter matching
                effective_bits_no_shift = effective_bits & ~KittyModifierBits.shift
                expected_bits_no_shift = expected_bits & ~KittyModifierBits.shift
                if effective_bits_no_shift != expected_bits_no_shift:
                    return False
            elif effective_bits != expected_bits:
                # Exact matching (no char, or non-alpha char)
                return False

            # If no character specified
            if char is None:
                # Text keys (with printable character values) require char argument
                keystroke_char = self.value
                if keystroke_char and len(keystroke_char) == 1 and keystroke_char.isprintable():
                    return False
                return True

            # Check character match using value property
            keystroke_char = self.value

            # If value is empty or not a single printable character, can't match
            if not keystroke_char or len(keystroke_char) > 1 or not keystroke_char.isprintable():
                return False

            # Compare characters
            if ignore_case:
                return keystroke_char.lower() == char.lower()
            return keystroke_char == char

        return modifier_predicate

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
        # Check if this is a property in the class (str subclasses have special lookup behavior)
        for klass in type(self).__mro__:
            if attr in klass.__dict__:
                class_attr = klass.__dict__[attr]
                if isinstance(class_attr, property):
                    # Call the property getter explicitly
                    return class_attr.fget(self)
                # Found a non-property class attribute, let normal lookup continue
                break

        if not attr.startswith('is_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")

        # Extract tokens after 'is_'
        tokens_str = attr[3:]  # Remove 'is_' prefix
        if not tokens_str:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")

        # Parse tokens to separate modifiers from potential key name
        tokens = tokens_str.split('_')

        # Separate modifiers from potential key name
        tokens_modifiers = []
        tokens_key_names = []

        # a mini 'getopt' for breaking modifiers_key_names -> [modifiers], [key_name_tokens]
        for i, token in enumerate(tokens):
            if token in KittyModifierBits.names_modifiers_only:
                tokens_modifiers.append(token)
            else:
                # Remaining tokens could be a key name
                tokens_key_names = tokens[i:]
                break

        # If we have any non-modifier tokens,
        if tokens_key_names:
            # check if they form a valid application key,
            key_name = '_'.join(tokens_key_names)
            keycodes = get_keyboard_codes()
            expected_key_constant = f'KEY_{key_name.upper()}'
            if expected_key_constant in keycodes.values():
                # and return as predicate function
                return self._build_appkeys_predicate(tokens_modifiers, key_name)

        # No valid key name was found by 'tokens_key_names', this could just as
        # easily be asking for an attribute that doesn't exist, or a spelling
        # error of application key or modifier, report as 'invalid' token
        invalid_tokens = [token for token in tokens
                          if token not in KittyModifierBits.names_modifiers_only]
        if invalid_tokens:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{attr}' "
                f"(invalid modifier or application key tokens: {invalid_tokens})")

        # Return modifier predicate for alphanumeric keys
        return self._build_alphanum_predicate(tokens_modifiers)

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

    def _get_alt_control_sequence_value(self) -> Optional[str]:
        """
        Get value for Alt-only control sequences (ESC + control char, Alt-only).

        Returns empty string for special application keys with Alt modifier.
        """
        if not (len(self) == 2 and self[0] == '\x1b' and
                self._alt and not self._ctrl):
            return None

        char_code = ord(self[1])

        # Special application keys with Alt modifier should return empty string
        # These are: Escape (0x1b), Backspace/DEL (0x7f), Enter (0x0d), Tab (0x09)
        # They are application keys, not text keys, so they have no text value
        if char_code in {0x1b, 0x7f, 0x0d, 0x09}:
            return ''

        # Other Alt+control combinations map to their control symbols
        if char_code in SYMBOLS_MAP_CTRL_VALUE:
            return SYMBOLS_MAP_CTRL_VALUE[char_code]

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

        # Special case: Ctrl+Alt+Space sends ESC + \x00
        if char_code == 0:
            return ' '

        # Ctrl+A through Ctrl+Z (codes 1-26)
        if 1 <= char_code <= 26:
            return chr(char_code + ord('a') - 1)  # lowercase

        # Ctrl+symbol mappings
        if char_code in SYMBOLS_MAP_CTRL_VALUE:
            return SYMBOLS_MAP_CTRL_VALUE[char_code]

        return None

    def _get_ctrl_sequence_value(self) -> Optional[str]:
        """
        Get value for Ctrl+char sequences.

        Maps control characters back to their base characters.
        """
        if not (len(self) == 1 and self._ctrl and not self._alt):
            return None

        char_code = ord(self)

        # Special case: Ctrl+Space sends \x00
        if char_code == 0:
            return ' '

        # Ctrl+A through Ctrl+Z (codes 1-26)
        if 1 <= char_code <= 26:
            return chr(char_code + ord('a') - 1)  # lowercase

        # Ctrl+symbol mappings
        if char_code in SYMBOLS_MAP_CTRL_VALUE:
            return SYMBOLS_MAP_CTRL_VALUE[char_code]

        return None

    def _get_protocol_value(self) -> Optional[str]:
        """
        Get value for ModifyOtherKeys protocol sequences.

        Extracts the character from modern keyboard protocols.
        """
        # ModifyOtherKeys protocol - extract character from key
        if self._mode == -2:
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
        r"""
        The textual character represented by this keystroke.

        :rtype: str
        :returns: For text keys, returns the base character (ignoring modifiers).
                  For application keys and sequences, returns empty string ''.

        Some Examples,

        - Plain text: 'a', 'A', '1', ';', ' ', 'Ω', emoji with ZWJ sequences
        - Alt+printable: Alt+a → 'a', Alt+A → 'A'
        - Ctrl+letter: Ctrl+A → 'a', Ctrl+Z → 'z'
        - Ctrl+symbol: Ctrl+@ → '@', Ctrl+? → '?', Ctrl+[ → '['
        - Control chars: '\t', '\n', '\x08', '\x1b' (for Enter/Tab/Backspace/Escape keycodes)
        - Application keys: KEY_UP, KEY_F1, etc. → ''
        """
        return (self._get_plain_char_value()
                or self._get_alt_sequence_value()
                or self._get_alt_control_sequence_value()
                or self._get_ctrl_alt_sequence_value()
                or self._get_ctrl_sequence_value()
                or self._get_protocol_value()
                or self._get_ascii_value()
                or '')


def get_curses_keycodes() -> Dict[str, int]:
    """
    Return mapping of curses key-names paired by their keycode integer value.

    :rtype: dict
    :returns: Dictionary of (name, code) pairs for curses keyboard constant
        values and their mnemonic name. Such as code ``260``, with the value of
        its key-name identity, ``'KEY_LEFT'``.
    """
    _keynames = [attr for attr in dir(curses)
                 if attr.startswith('KEY_')]
    return {keyname: getattr(curses, keyname) for keyname in _keynames}


def get_keyboard_codes() -> Dict[int, str]:
    """
    Return mapping of keycode integer values paired by their curses key-name.

    :rtype: dict
    :returns: Dictionary of (code, name) pairs for curses keyboard constant
        values and their mnemonic name. Such as key ``260``, with the value of
        its identity, ``'KEY_LEFT'``.

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


def _alternative_left_right(term: 'Terminal') -> typing.Dict[str, int]:
    r"""
    Determine and return mapping of left and right arrow keys sequences.

    :arg blessed.Terminal term: :class:`~.Terminal` instance.
    :rtype: dict
    :returns: Dictionary of sequences ``term._cuf1``, and ``term._cub1``,
        valued as ``KEY_RIGHT``, ``KEY_LEFT`` (when appropriate).

    This function supports :func:`get_terminal_sequences` to discover
    the preferred input sequence for the left and right application keys.

    It is necessary to check the value of these sequences to ensure we do not
    use ``' '`` and ``'\b'`` for ``KEY_RIGHT`` and ``KEY_LEFT``,
    preferring their true application key sequence, instead.
    """
    # pylint: disable=protected-access
    keymap: typing.Dict[str, int] = {}
    if term._cuf1 and term._cuf1 != ' ':
        keymap[term._cuf1] = curses.KEY_RIGHT
    if term._cub1 and term._cub1 != '\b':
        keymap[term._cub1] = curses.KEY_LEFT
    return keymap


def get_keyboard_sequences(term: 'Terminal') -> typing.OrderedDict[str, int]:
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
    characters, such as ``'\x1b[D'``, and ``keycode`` is an integer
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
    set(['a', 'ab', 'abd', 'j', 'jk'])
    """
    return {seq[:i] for seq in sequences for i in range(1, len(seq))}


def resolve_sequence(text: str,
                     mapper: typing.Mapping[str, int],
                     codes: typing.Mapping[int, str],
                     prefixes: Optional[Set[str]] = None,
                     final: bool = False) -> Keystroke:
    r"""
    Return a single :class:`Keystroke` instance for given sequence ``text``.

    :arg str text: string of characters received from terminal input stream.
    :arg OrderedDict mapper: unicode multibyte sequences, such as ``'\x1b[D'``
        paired by their integer value (260)
    :arg dict codes: a :type:`dict` of integer values (such as 260) paired
        by their mnemonic name, such as ``'KEY_LEFT'``.
    :arg set prefixes: Set of all valid sequence prefixes for quick matching
    :arg bool final: Whether this is the final resolution attempt (no more input expected)
    :rtype: Keystroke
    :returns: Keystroke instance for the given sequence

    The given ``text`` may extend beyond a matching sequence, such as
    ``u\x1b[Dxxx`` returns a :class:`Keystroke` instance of attribute
    :attr:`Keystroke.sequence` valued only ``u\x1b[D``.  It is up to
    calls to determine that ``xxx`` remains unresolved.

    In an ideal world, we could detect and resolve only for key sequences
    expected in the current terminal mode. For example, only the ennoblement of
    mode 1036 (META_SENDS_ESC) would match for 2-character ESC+char sequences.

    But terminals are unpredictable, I am using a popular linux terminal now
    that does not negotiate about any DEC Private modes but transmits
    metaSendsEscape anyway, so exhaustive match is performed in all cases.
    """
    # First try advanced keyboard protocol matchers
    ks = None
    for match_fn in (_match_modify_other_keys,
                     _match_legacy_csi_letter_form,
                     _match_legacy_csi_tilde_form,
                     _match_legacy_ss3_fkey_form):
        ks = match_fn(text)
        if ks:
            break

    # Then try static sequence lookups from terminal capabilities
    if ks is None:
        for sequence, code in mapper.items():
            if text.startswith(sequence):
                ks = Keystroke(ucs=sequence, code=code, name=codes[code])
                break

    # Resolve for alt+backspace and metaSendsEscape, KEY_ALT_[..],
    # when the sequence so far is not a 'known prefix', or, when
    # final is True, we return the ambiguously matched KEY_ALT_[...]
    if prefixes is not None:
        maybe_alt = (ks is not None and ks.code == curses.KEY_EXIT and len(text) > 1)
        final_or_not_keystroke = (
            final or (len(text) > 1 and text[1] == '\x7f') or text[:2] not in prefixes)
        if (maybe_alt and final_or_not_keystroke):
            ks = Keystroke(ucs=text[:2])

    # final match is just simple resolution of the first codepoint of text
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
                timeout: typing.Optional[float]
                ) -> typing.Tuple[typing.Optional[Match[str]], str]:
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
    match, buf = None, ''

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


def _match_modify_other_keys(text: str) -> Optional['Keystroke']:
    """
    Attempt to match text against xterm ModifyOtherKeys patterns.

    :arg str text: Input text to match against ModifyOtherKeys patterns
    :rtype: Keystroke or None
    :returns: :class:`Keystroke` when matched, otherwise ``None``.

    Supports xterm ModifyOtherKeys sequences of the form:
    ESC [ 27 ; modifiers ; key ~     # Standard form
    ESC [ 27 ; modifiers ; key       # Alternative form without trailing ~
    """
    match = RE_PATTERN_MODIFY_OTHER.match(text)
    if match:
        # Create ModifyOtherKeysEvent namedtuple
        modify_event = ModifyOtherKeysEvent(
            key=int(match.group('key')),
            modifiers=int(match.group('modifiers')))
        # Create Keystroke with mode=-2 to indicate ModifyOtherKeys protocol
        return Keystroke(ucs=match.group(0),
                         mode=-2,
                         match=modify_event)

    return None


def _match_legacy_csi_letter_form(text: str) -> Optional[Keystroke]:
    """
    Match legacy CSI letter form: ESC [ 1 ; modifiers [ABCDEFHPQRS].

    :arg str text: Input text to match
    :rtype: Keystroke or None
    :returns: :class:`Keystroke` if matched, ``None`` otherwise

    Handles arrow keys, Home/End, F1-F4 with modifiers.
    """
    match = RE_PATTERN_LEGACY_CSI_MODIFIERS.match(text)
    if not match:
        return None

    modifiers = int(match.group('mod'))
    key_id = match.group('final')
    matched_text = match.group(0)
    event_type = int(match.group('event')) if match.group('event') else 1

    keycode = CSI_FINAL_CHAR_TO_KEYCODE.get(key_id)
    if keycode is None:
        return None

    legacy_event = LegacyCSIKeyEvent(
        kind='letter',
        key_id=key_id,
        modifiers=modifiers,
        event_type=event_type)

    return Keystroke(ucs=matched_text, code=keycode, mode=-3, match=legacy_event)


def _match_legacy_csi_tilde_form(text: str) -> Optional[Keystroke]:
    """
    Match legacy CSI tilde form: ESC [ number ; modifiers ~.

    :arg str text: Input text to match
    :rtype: Keystroke or None
    :returns: :class:`Keystroke` if matched, ``None`` otherwise

    Handles function keys and navigation keys (Insert, Delete, Page Up/Down, etc.)
    with modifiers. See https://tomscii.sig7.se/zutty/doc/KEYS.html and
    https://invisible-island.net/xterm/xterm-function-keys.html for reference.
    """
    match = RE_PATTERN_LEGACY_CSI_TILDE.match(text)
    if not match:
        return None

    modifiers = int(match.group('mod'))
    key_id = int(match.group('key_num'))
    matched_text = match.group(0)
    event_type = int(match.group('event')) if match.group('event') else 1

    keycode = CSI_TILDE_NUM_TO_KEYCODE.get(key_id)
    if keycode is None:
        return None

    legacy_event = LegacyCSIKeyEvent(
        kind='tilde',
        key_id=key_id,
        modifiers=modifiers,
        event_type=event_type)

    return Keystroke(ucs=matched_text, code=keycode, mode=-3, match=legacy_event)


def _match_legacy_ss3_fkey_form(text: str) -> Optional[Keystroke]:
    """
    Match legacy SS3 F-key form: ESC O modifier [PQRS].

    :arg str text: Input text to match
    :rtype: Keystroke or None
    :returns: :class:`Keystroke` if matched, ``None`` otherwise

    Handles F1-F4 with modifiers in SS3 format (used by Konsole and others).
    """
    match = RE_PATTERN_LEGACY_SS3_FKEYS.match(text)
    if not match:
        return None

    modifiers = int(match.group('mod'))
    final_char = match.group('final')
    matched_text = match.group(0)

    # Modifier 0 is invalid - modifiers start from 1 (no modifiers)
    if modifiers == 0:
        return None

    keycode = SS3_FKEY_TO_KEYCODE.get(final_char)
    if keycode is None:
        return None

    # SS3 form doesn't support event_type, default to 1 (press)
    legacy_event = LegacyCSIKeyEvent(
        kind='ss3-fkey',
        key_id=final_char,
        modifiers=modifiers,
        event_type=1)

    return Keystroke(ucs=matched_text, code=keycode, mode=-3, match=legacy_event)


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

#: Legacy CSI modifier sequence mappings
#: Maps CSI final characters to curses keycodes for sequences
#: like ESC [ 1 ; mod [ABCDEFHPQRS]
CSI_FINAL_CHAR_TO_KEYCODE = {
    'A': curses.KEY_UP,
    'B': curses.KEY_DOWN,
    'C': curses.KEY_RIGHT,
    'D': curses.KEY_LEFT,
    'E': curses.KEY_B2,      # Center/Begin
    'F': curses.KEY_END,
    'H': curses.KEY_HOME,
    'P': curses.KEY_F1,
    'Q': curses.KEY_F2,
    'R': curses.KEY_F3,
    'S': curses.KEY_F4,
}

#: Maps CSI tilde numbers to curses keycodes for sequences
#: like ESC [ num ; mod ~
CSI_TILDE_NUM_TO_KEYCODE = {
    2: curses.KEY_IC,        # Insert
    3: curses.KEY_DC,        # Delete
    5: curses.KEY_PPAGE,     # Page Up
    6: curses.KEY_NPAGE,     # Page Down
    7: curses.KEY_HOME,      # Home
    8: curses.KEY_END,       # End
    11: curses.KEY_F1,       # F1
    12: curses.KEY_F2,       # F2
    13: curses.KEY_F3,       # F3
    14: curses.KEY_F4,       # F4
    15: curses.KEY_F5,       # F5
    17: curses.KEY_F6,       # F6
    18: curses.KEY_F7,       # F7
    19: curses.KEY_F8,       # F8
    20: curses.KEY_F9,       # F9
    21: curses.KEY_F10,      # F10
    23: curses.KEY_F11,      # F11
    24: curses.KEY_F12,      # F12
    25: curses.KEY_F13,      # F13
    26: curses.KEY_F14,      # F14
    28: curses.KEY_F15,      # F15
    29: KEY_MENU,            # Menu
    31: curses.KEY_F17,      # F17
    32: curses.KEY_F18,      # F18
    33: curses.KEY_F19,      # F19
    34: curses.KEY_F20,      # F20
}

#: Maps SS3 final characters to curses keycodes for sequences
#: like ESC O mod [PQRS]
SS3_FKEY_TO_KEYCODE = {
    'P': curses.KEY_F1,      # F1
    'Q': curses.KEY_F2,      # F2
    'R': curses.KEY_F3,      # F3
    'S': curses.KEY_F4,      # F4
}

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
#: These "mixins" are used for *all* terminals, regardless of their type.
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
    (chr(9), KEY_TAB),  # noqa
    (chr(27), curses.KEY_EXIT),
    (chr(127), curses.KEY_BACKSPACE),

    ("\x1b[A", curses.KEY_UP),
    ("\x1b[B", curses.KEY_DOWN),
    ("\x1b[C", curses.KEY_RIGHT),
    ("\x1b[D", curses.KEY_LEFT),
    ("\x1b[E", curses.KEY_B2),  # Center/Begin key
    ("\x1b[1;2A", curses.KEY_SR),
    ("\x1b[1;2B", curses.KEY_SF),
    ("\x1b[1;2C", curses.KEY_SRIGHT),
    ("\x1b[1;2D", curses.KEY_SLEFT),
    ("\x1b[F", curses.KEY_END),
    ("\x1b[H", curses.KEY_HOME),
    # not sure where these are from .. please report
    ("\x1b[K", curses.KEY_END),
    ("\x1b[U", curses.KEY_NPAGE),
    ("\x1b[V", curses.KEY_PPAGE),

    # keys sent after term.smkx (keypad_xmit) is emitted, source:
    # http://www.xfree86.org/current/ctlseqs.html#PC-Style%20Function%20Keys
    # http://fossies.org/linux/rxvt/doc/rxvtRef.html#KeyCodes
    #
    # keypad, numlock on
    ("\x1bOM", curses.KEY_ENTER),
    ("\x1bOj", KEY_KP_MULTIPLY),
    ("\x1bOk", KEY_KP_ADD),
    ("\x1bOl", KEY_KP_SEPARATOR),
    ("\x1bOm", KEY_KP_SUBTRACT),
    ("\x1bOn", KEY_KP_DECIMAL),
    ("\x1bOo", KEY_KP_DIVIDE),
    ("\x1bOX", KEY_KP_EQUAL),
    ("\x1bOp", KEY_KP_0),
    ("\x1bOq", KEY_KP_1),
    ("\x1bOr", KEY_KP_2),
    ("\x1bOs", KEY_KP_3),
    ("\x1bOt", KEY_KP_4),
    ("\x1bOu", KEY_KP_5),
    ("\x1bOv", KEY_KP_6),
    ("\x1bOw", KEY_KP_7),
    ("\x1bOx", KEY_KP_8),
    ("\x1bOy", KEY_KP_9),

    # keypad, numlock off
    ("\x1b[1~", curses.KEY_FIND),         # find
    ("\x1b[2~", curses.KEY_IC),           # insert (0)
    ("\x1b[3~", curses.KEY_DC),           # delete (.), "Execute"
    ("\x1b[4~", curses.KEY_SELECT),       # select
    ("\x1b[5~", curses.KEY_PPAGE),        # pgup   (9)
    ("\x1b[6~", curses.KEY_NPAGE),        # pgdown (3)
    ("\x1b[7~", curses.KEY_HOME),         # home
    ("\x1b[8~", curses.KEY_END),          # end
    ("\x1b[OA", curses.KEY_UP),           # up     (8)
    ("\x1b[OB", curses.KEY_DOWN),         # down   (2)
    ("\x1b[OC", curses.KEY_RIGHT),        # right  (6)
    ("\x1b[OD", curses.KEY_LEFT),         # left   (4)
    ("\x1b[OF", curses.KEY_END),          # end    (1)
    ("\x1b[OH", curses.KEY_HOME),         # home   (7)

    # The vt220 placed F1-F4 above the keypad, in place of actual
    # F1-F4 were local functions (hold screen, print screen,
    # set up, data/talk, break).
    ("\x1bOP", curses.KEY_F1),
    ("\x1bOQ", curses.KEY_F2),
    ("\x1bOR", curses.KEY_F3),
    ("\x1bOS", curses.KEY_F4),

    # Kitty disambiguate mode F-keys (CSI form instead of SS3)
    ("\x1b[P", curses.KEY_F1),
    ("\x1b[Q", curses.KEY_F2),
    ("\x1b[13~", curses.KEY_F3),
    ("\x1b[S", curses.KEY_F4),
)

#: Override mixins for a few curses constants with easier
#: mnemonics: there may only be a 1:1 mapping when only a
#: keycode (int) is given, where these phrases are preferred.
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
    ('KEY_CENTER', curses.KEY_B2),
    ('KEY_BEGIN', curses.KEY_BEG),
    ('KEY_DOWN_LEFT', curses.KEY_C1),
    ('KEY_DOWN_RIGHT', curses.KEY_C3),
)

#: Default delay, in seconds, of Escape key detection in
#: :meth:`Terminal.inkey`.` curses has a default delay of 1000ms (1 second) for
#: escape sequences.  This is too long for modern applications, so we set it to
#: 350ms, or 0.35 seconds. It is still a bit conservative, for remote telnet or
#: ssh servers, for example.
DEFAULT_ESCDELAY = 0.35  # pylint: disable=invalid-name


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


__all__ = ('Keystroke', 'get_keyboard_codes', 'get_keyboard_sequences',)
