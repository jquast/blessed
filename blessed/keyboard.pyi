"""Type hints for 'keyboard awareness'"""

# std imports
from typing import (TYPE_CHECKING,
                    Set,
                    Dict,
                    Type,
                    Match,
                    Tuple,
                    Union,
                    Mapping,
                    TypeVar,
                    Iterable,
                    Optional,
                    OrderedDict,
                    NamedTuple,
                    Callable,
                    Any)
import re

if TYPE_CHECKING:
    # local
    from .terminal import Terminal

_T = TypeVar("_T")

# pylint: disable=unused-argument,missing-function-docstring,missing-class-docstring

class Keystroke(str):
    def __new__(
        cls: Type[_T],
        ucs: str = ...,
        code: Optional[int] = ...,
        name: Optional[str] = ...,
        mode: Optional[int] = ...,
        match: Optional[Any] = ...,
    ) -> _T: ...
    @property
    def is_sequence(self) -> bool: ...
    @property
    def name(self) -> Optional[str]: ...
    @property
    def code(self) -> Optional[int]: ...
    @property
    def mode(self) -> Optional[int]: ...
    @property
    def event_mode(self) -> Optional[int]: ...
    @property
    def modifiers(self) -> int: ...
    @property
    def modifiers_bits(self) -> int: ...
    @property
    def value(self) -> str: ...
    def mode_values(self) -> Union[BracketedPasteEvent, MouseSGREvent, MouseLegacyEvent, FocusEvent, SyncEvent]: ...
    def __getattr__(self, attr: str) -> Callable[..., bool]: ...

# Namedtuple classes - these should be defined as proper namedtuples
class BracketedPasteEvent(NamedTuple):
    text: str
    
class MouseSGREvent(NamedTuple):
    button: int
    x: int
    y: int
    is_release: bool
    shift: bool
    meta: bool
    ctrl: bool
    is_drag: bool
    is_wheel: bool

class MouseLegacyEvent(NamedTuple):
    button: int
    x: int
    y: int
    is_release: bool
    shift: bool
    meta: bool
    ctrl: bool
    is_motion: bool
    is_drag: bool
    is_wheel: bool

class FocusEvent(NamedTuple):
    gained: bool

class SyncEvent(NamedTuple):
    begin: bool

class KittyKeyEvent(NamedTuple):
    unicode_key: int
    shifted_key: Optional[int]
    base_key: Optional[int]
    modifiers: int
    event_type: int
    int_codepoints: Tuple[int, ...]

class ModifyOtherKeysEvent(NamedTuple):
    key: int
    modifiers: int

class LegacyCSIKeyEvent(NamedTuple):
    kind: str
    key_id: Union[str, int]
    modifiers: int

class DeviceAttribute:
    raw: str
    service_class: int
    extensions: Set[int]
    
    def __init__(self, raw: str, service_class: int, extensions: Iterable[int]) -> None: ...
    @property
    def supports_sixel(self) -> bool: ...
    @classmethod
    def from_match(cls, match: Match[str]) -> DeviceAttribute: ...
    @classmethod
    def from_string(cls, response_str: str) -> Optional[DeviceAttribute]: ...
    def __repr__(self) -> str: ...
    def __eq__(self, other: Any) -> bool: ...

class KittyKeyboardProtocol:
    value: int
    
    def __init__(self, value: int) -> None: ...
    @property
    def disambiguate(self) -> bool: ...
    @disambiguate.setter
    def disambiguate(self, enabled: bool) -> None: ...
    @property
    def report_events(self) -> bool: ...
    @report_events.setter
    def report_events(self, enabled: bool) -> None: ...
    @property
    def report_alternates(self) -> bool: ...
    @report_alternates.setter
    def report_alternates(self, enabled: bool) -> None: ...
    @property
    def report_all_keys(self) -> bool: ...
    @report_all_keys.setter
    def report_all_keys(self, enabled: bool) -> None: ...
    @property
    def report_text(self) -> bool: ...
    @report_text.setter
    def report_text(self, enabled: bool) -> None: ...
    def make_arguments(self) -> Dict[str, bool]: ...
    def __repr__(self) -> str: ...
    def __eq__(self, other: Any) -> bool: ...

def get_keyboard_codes() -> Dict[str, int]: ...
def get_curses_keycodes() -> Dict[str, int]: ...
def get_keyboard_sequences(term: 'Terminal') -> OrderedDict[str, int]: ...
def get_leading_prefixes(sequences: Iterable[str]) -> Set[str]: ...
def resolve_sequence(
    text: str, 
    mapper: Mapping[str, int], 
    codes: Mapping[int, str],
    prefixes: Set[str],
    final: bool = False,
    mode_1016_active: Optional[bool] = None
) -> Keystroke: ...

def _time_left(stime: float, timeout: Optional[float]) -> Optional[float]: ...
def _read_until(
        term: 'Terminal', pattern: str, timeout: Optional[float]
    ) -> Tuple[Optional[Match[str]], str]: ...

def _match_dec_event(text: str, mode_1016_active: Optional[bool] = None) -> Optional[Keystroke]: ...
def _match_kitty_key(text: str) -> Optional[Keystroke]: ...
def _match_modify_other_keys(text: str) -> Optional[Keystroke]: ...
def _match_legacy_csi_modifiers(text: str) -> Optional[Keystroke]: ...

# Constants
DEFAULT_ESCDELAY: float

# Key constants that are added beyond curses
KEY_TAB: int
KEY_KP_MULTIPLY: int
KEY_KP_ADD: int
KEY_KP_SEPARATOR: int
KEY_KP_SUBTRACT: int
KEY_KP_DECIMAL: int
KEY_KP_DIVIDE: int
KEY_KP_EQUAL: int
KEY_KP_0: int
KEY_KP_1: int
KEY_KP_2: int
KEY_KP_3: int
KEY_KP_4: int
KEY_KP_5: int
KEY_KP_6: int
KEY_KP_7: int
KEY_KP_8: int
KEY_KP_9: int
KEY_MENU: int

# Pattern constants
LEGACY_CSI_MODIFIERS_PATTERN: re.Pattern[str]
LEGACY_CSI_TILDE_PATTERN: re.Pattern[str]
LEGACY_SS3_FKEYS_PATTERN: re.Pattern[str]
KITTY_KB_PROTOCOL_PATTERN: re.Pattern[str]
MODIFY_PATTERN: re.Pattern[str]

# DEC event patterns
DEC_EVENT_PATTERN: type
DEC_EVENT_PATTERNS: list

# Sequence mappings
DEFAULT_SEQUENCE_MIXIN: Tuple[Tuple[str, int], ...]
CURSES_KEYCODE_OVERRIDE_MIXIN: Tuple[Tuple[str, int], ...]

# Character mapping dictionaries
CTRL_CHAR_MAP: Dict[str, int]
CTRL_CODE_MAP: Dict[int, str]
