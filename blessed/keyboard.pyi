"""Type hints for 'keyboard awareness'"""

# std imports
from typing import (TYPE_CHECKING,
                    Set,
                    Dict,
                    Type,
                    Match,
                    Tuple,
                    Mapping,
                    TypeVar,
                    Iterable,
                    Optional,
                    OrderedDict)

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
        match: Optional[Match[str]] = ...,
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
    def get_event_values(self) -> Tuple[int, ...]: ...

def get_keyboard_codes() -> Dict[int, str]: ...
def get_keyboard_sequences(term: 'Terminal') -> OrderedDict[str, int]: ...
def get_leading_prefixes(sequences: Iterable[str]) -> Set[str]: ...
def resolve_sequence(
    text: str, mapper: Mapping[str, int], codes: Mapping[int, str]
) -> Keystroke: ...
def _time_left(stime: float, timeout: Optional[float]) -> Optional[float]: ...
def _read_until(
        term: 'Terminal', pattern: str, timeout: Optional[float]
    ) -> Tuple[Optional[Match[str]], str]: ...

class BracketedPasteEvent:
    def __init__(self, text: str) -> None: ...
    @property
    def text(self) -> str: ...

class FocusEvent:
    def __init__(self, gained: bool) -> None: ...
    @property
    def gained(self) -> bool: ...

class MouseLegacyEvent:
    def __init__(
        self,
        button: int,
        x: int,
        y: int,
        is_release: bool,
        shift: bool,
        meta: bool,
        ctrl: bool,
        is_motion: bool,
        is_drag: bool,
        is_wheel: bool,
    ) -> None: ...

class MouseSGREvent:
    def __init__(
        self,
        button: int,
        x: int,
        y: int,
        is_release: bool,
        shift: bool,
        meta: bool,
        ctrl: bool,
        is_drag: bool,
        is_wheel: bool,
    ) -> None: ...

class SyncEvent:
    def __init__(self, begin: bool) -> None: ...
    @property
    def begin(self) -> bool: ...

def _match_dec_event(text: str) -> Optional[Keystroke]: ...

DEFAULT_ESCDELAY: float
