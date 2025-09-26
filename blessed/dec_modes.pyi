"""
Type stubs for DEC Private Modes and their Response values.
"""

from typing import Union, Any

class DecModeResponse:
    NOT_QUERIED: int
    NO_RESPONSE: int
    NOT_RECOGNIZED: int
    SET: int
    RESET: int
    PERMANENTLY_SET: int
    PERMANENTLY_RESET: int
    
    def __init__(self, mode: Union[DecPrivateMode, int], value: int) -> None: ...
    
    @property
    def mode(self) -> DecPrivateMode: ...
    
    @property
    def description(self) -> str: ...
    
    @property
    def value(self) -> int: ...
    
    def is_supported(self) -> bool: ...
    def is_recognized(self) -> bool: ...
    def is_enabled(self) -> bool: ...
    def is_disabled(self) -> bool: ...
    def is_permanent(self) -> bool: ...
    def is_changeable(self) -> bool: ...
    def is_temporarily_enabled(self) -> bool: ...
    def is_temporarily_disabled(self) -> bool: ...
    def is_failed(self) -> bool: ...
    def __str__(self) -> str: ...
    def __repr__(self) -> str: ...

class DecPrivateMode:
    # VT/DEC standard modes
    DECCKM: int
    DECANM: int
    DECCOLM: int
    DECSCLM: int
    DECSCNM: int
    DECOM: int
    DECAWM: int
    DECARM: int
    DECINLM: int
    DECEDM: int
    DECLTM: int
    DECKANAM: int
    DECSCFDM: int
    DECTEM: int
    DECEKEM: int
    DECPFF: int
    DECPEX: int
    OV1: int
    BA1: int
    BA2: int
    PK1: int
    AH1: int
    DECTCEM: int
    DECPSP: int
    DECPSM: int
    SHOW_SCROLLBAR_RXVT: int
    DECRLM: int
    DECHEBM: int
    DECHEM: int
    DECTEK: int
    DECCRNLM: int
    DECUPM: int
    DECNRCM: int
    DECGEPM: int
    DECGPCM: int
    DECGPCS: int
    DECGPBM: int
    DECGRPM: int
    DECTHAIM: int
    DECTHAICM: int
    DECBWRM: int
    DECOPM: int
    DEC131TM: int
    DECBPM: int
    DECNAKB: int
    DECIPEM: int
    DECKKDM: int
    DECHCCM: int
    DECVCCM: int
    DECPCCM: int
    DECBCMM: int
    DECNKM: int
    DECBKM: int
    DECKBUM: int
    DECVSSM: int
    DECFPM: int
    DECXRLM: int
    DECSDM: int
    DECKPM: int
    WY_52_LINE: int
    WYENAT_OFF: int
    REPLACEMENT_CHAR_COLOR: int
    DECTHAISCM: int
    DECNCSM: int
    DECRLCM: int
    DECCRTSM: int
    DECARSM: int
    DECMCM: int
    DECAAM: int
    DECCANSM: int
    DECNULM: int
    DECHDPXM: int
    DECESKM: int
    DECOSCNM: int
    DECNUMLK: int
    DECCAPSLK: int
    DECKLHIM: int
    DECFWM: int
    DECRPL: int
    DECHWUM: int
    DECATCUM: int
    DECATCBM: int
    DECBBSM: int
    DECECM: int

    # Mouse reporting modes and xterm/rxvt extensions
    MOUSE_REPORT_CLICK: int
    MOUSE_HILITE_TRACKING: int
    MOUSE_REPORT_DRAG: int
    MOUSE_ALL_MOTION: int
    FOCUS_IN_OUT_EVENTS: int
    MOUSE_EXTENDED_UTF8: int
    MOUSE_EXTENDED_SGR: int
    ALT_SCROLL_XTERM: int
    SCROLL_ON_TTY_OUTPUT_RXVT: int
    SCROLL_ON_KEYPRESS_RXVT: int
    FAST_SCROLL: int
    MOUSE_URXVT: int
    MOUSE_SGR_PIXELS: int
    BOLD_ITALIC_HIGH_INTENSITY: int

    # Keyboard and meta key handling modes
    META_SETS_EIGHTH_BIT: int
    MODIFIERS_ALT_NUMLOCK: int
    META_SENDS_ESC: int
    KP_DELETE_SENDS_DEL: int
    ALT_SENDS_ESC: int

    # Selection, clipboard, and window manager hint modes
    KEEP_SELECTION_NO_HILITE: int
    USE_CLIPBOARD_SELECTION: int
    URGENCY_ON_CTRL_G: int
    RAISE_ON_CTRL_G: int
    REUSE_CLIPBOARD_DATA: int
    EXTENDED_REVERSE_WRAPAROUND: int
    ALT_SCREEN_BUFFER_SWITCH: int

    # Alternate screen buffer and cursor save/restore combinations
    ALT_SCREEN_BUFFER_XTERM: int
    SAVE_CURSOR_DECSC: int
    ALT_SCREEN_AND_SAVE_CLEAR: int

    # Terminal info and function key emulation modes
    TERMINFO_FUNC_KEY_MODE: int
    SUN_FUNC_KEY_MODE: int
    HP_FUNC_KEY_MODE: int
    SCO_FUNC_KEY_MODE: int

    # Legacy keyboard emulation modes
    LEGACY_KBD_X11R6: int
    VT220_KBD_EMULATION: int

    SIXEL_PRIVATE_PALETTE: int

    # VTE BiDi extensions
    BIDI_ARROW_KEY_SWAPPING: int

    # iTerm2 extensions
    ITERM2_REPORT_KEY_UP: int

    # XTerm readline and mouse enhancements
    READLINE_MOUSE_BUTTON_1: int
    READLINE_MOUSE_BUTTON_2: int
    READLINE_MOUSE_BUTTON_3: int
    BRACKETED_PASTE: int
    READLINE_CHARACTER_QUOTING: int
    READLINE_NEWLINE_PASTING: int

    # Modern terminal extensions
    SYNCHRONIZED_OUTPUT: int
    REWRAP_ON_RESIZE_DEPRECATED: int
    TEXT_REFLOW: int
    PASSIVE_MOUSE_TRACKING: int
    REPORT_GRID_CELL_SELECTION: int
    COLOR_PALETTE_UPDATES: int
    IN_BAND_WINDOW_RESIZE: int

    # VTE bidirectional text extensions
    MIRROR_BOX_DRAWING: int
    BIDI_AUTODETECTION: int

    # mintty extensions
    AMBIGUOUS_WIDTH_REPORTING: int
    SCROLL_MARKERS: int
    REWRAP_ON_RESIZE_MINTTY: int
    APPLICATION_ESCAPE_KEY: int
    ESC_KEY_SENDS_BACKSLASH: int
    GRAPHICS_POSITION: int
    ALT_MODIFIED_MOUSEWHEEL: int
    SHOW_HIDE_SCROLLBAR: int
    FONT_CHANGE_REPORTING: int
    GRAPHICS_POSITION_2: int
    SHORTCUT_KEY_MODE: int
    MOUSEWHEEL_REPORTING: int
    APPLICATION_MOUSEWHEEL: int
    BIDI_CURRENT_LINE: int

    # Terminal-specific extensions
    TTCTH: int
    SIXEL_SCROLLING_LEAVES_CURSOR: int
    CHARACTER_MAPPING_SERVICE: int
    AMBIGUOUS_WIDTH_DOUBLE_WIDTH: int
    WIN32_INPUT_MODE: int
    KITTY_HANDLE_CTRL_C_Z: int
    MINTTY_BIDI: int
    INPUT_METHOD_EDITOR: int

    LONG_DESCRIPTIONS: dict[int, str]
    _VALUE_TO_NAME: dict[int, str]

    value: int
    name: str

    def __init__(self, value: int) -> None: ...
    def __repr__(self) -> str: ...
    def __int__(self) -> int: ...
    def __index__(self) -> int: ...
    def __eq__(self, other: Any) -> bool: ...
    def __hash__(self) -> int: ...
    
    @property
    def long_description(self) -> str: ...
