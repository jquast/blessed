"""Terminal capability builder patterns."""
# std imports
import re
import typing
from typing import Set, Dict, Optional
from collections import OrderedDict

# 3rd party
import jinxed.terminfo

__all__ = (
    'CAPABILITY_DATABASE',
    'CAPABILITIES_RAW_MIXIN',
    'CAPABILITIES_ADDITIVES',
    'CAPABILITIES_HORIZONTAL_DISTANCE',
    'CAPABILITIES_CAUSE_MOVEMENT',
    'XTGETTCAP_CAPABILITIES',
    'Decrqss',
    'TermcapResponse',
    'ITerm2Capabilities',
)

CAPABILITY_DATABASE: \
    typing.OrderedDict[str, typing.Tuple[str, typing.Dict[str, typing.Any]]] = OrderedDict((
        ('bell', ('bel', {})),
        ('carriage_return', ('cr', {})),
        ('change_scroll_region', ('csr', {'nparams': 2})),
        ('clear_all_tabs', ('tbc', {})),
        ('clear_screen', ('clear', {})),
        ('clr_bol', ('el1', {})),
        ('clr_eol', ('el', {})),
        ('clr_eos', ('clear_eos', {})),
        ('column_address', ('hpa', {'nparams': 1})),
        ('cursor_address', ('cup', {'nparams': 2, 'match_grouped': True})),
        ('cursor_down', ('cud1', {})),
        ('cursor_home', ('home', {})),
        ('cursor_invisible', ('civis', {})),
        ('cursor_left', ('cub1', {})),
        ('cursor_normal', ('cnorm', {})),
        ('cursor_report', ('u6', {'nparams': 2, 'match_grouped': True})),
        ('cursor_right', ('cuf1', {})),
        ('cursor_up', ('cuu1', {})),
        ('cursor_visible', ('cvvis', {})),
        ('delete_character', ('dch1', {})),
        ('delete_line', ('dl1', {})),
        ('enter_blink_mode', ('blink', {})),
        ('enter_bold_mode', ('bold', {})),
        ('enter_dim_mode', ('dim', {})),
        ('enter_fullscreen', ('smcup', {})),
        ('enter_standout_mode', ('standout', {})),
        ('enter_superscript_mode', ('superscript', {})),
        ('enter_susimpleript_mode', ('ssubm', {})),
        ('enter_underline_mode', ('underline', {})),
        ('erase_chars', ('ech', {'nparams': 1})),
        ('exit_alt_charset_mode', ('rmacs', {})),
        ('disable_line_wrap', ('rmam', {})),
        ('enable_line_wrap', ('smam', {})),
        ('exit_attribute_mode', ('sgr0', {})),
        ('exit_ca_mode', ('rmcup', {})),
        ('exit_fullscreen', ('rmcup', {})),
        ('exit_insert_mode', ('rmir', {})),
        ('exit_standout_mode', ('rmso', {})),
        ('exit_underline_mode', ('rmul', {})),
        ('flash_hook', ('hook', {})),
        ('flash_screen', ('flash', {})),
        ('insert_line', ('il1', {})),
        ('keypad_local', ('rmkx', {})),
        ('keypad_xmit', ('smkx', {})),
        ('meta_off', ('rmm', {})),
        ('meta_on', ('smm', {})),
        ('orig_pair', ('op', {})),
        ('parm_down_cursor', ('cud', {'nparams': 1})),
        ('parm_left_cursor', ('cub', {'nparams': 1, 'match_grouped': True})),
        ('parm_dch', ('dch', {'nparams': 1})),
        ('parm_delete_line', ('dl', {'nparams': 1})),
        ('parm_ich', ('ich', {'nparams': 1})),
        ('parm_index', ('indn', {'nparams': 1})),
        ('parm_insert_line', ('il', {'nparams': 1})),
        ('parm_right_cursor', ('cuf', {'nparams': 1, 'match_grouped': True})),
        ('parm_rindex', ('rin', {'nparams': 1})),
        ('parm_up_cursor', ('cuu', {'nparams': 1})),
        ('print_screen', ('mc0', {})),
        ('prtr_off', ('mc4', {})),
        ('prtr_on', ('mc5', {})),
        ('reset_1string', ('r1', {})),
        ('reset_2string', ('r2', {})),
        ('reset_3string', ('r3', {})),
        ('restore_cursor', ('rc', {})),
        ('row_address', ('vpa', {'nparams': 1})),
        ('save_cursor', ('sc', {})),
        ('scroll_forward', ('ind', {})),
        ('scroll_reverse', ('rev', {})),
        ('set0_des_seq', ('s0ds', {})),
        ('set1_des_seq', ('s1ds', {})),
        ('set2_des_seq', ('s2ds', {})),
        ('set3_des_seq', ('s3ds', {})),
        # this 'color' is deceiving, but often matching, and a better match
        # than set_a_attributes1 or set_a_foreground.
        ('color', ('_foreground_color', {'nparams': 1, 'match_any': True, 'numeric': 1})),
        ('set_a_foreground', ('color', {'nparams': 1, 'match_any': True, 'numeric': 1})),
        ('set_a_background', ('on_color', {'nparams': 1, 'match_any': True, 'numeric': 1})),
        ('set_tab', ('hts', {})),
        ('tab', ('ht', {})),
        ('italic', ('sitm', {})),
        ('no_italic', ('sitm', {})),
    ))

_ESC = re.escape('\x1b')
_CSI = rf'{_ESC}\['
_ANY_NOTESC = rf'[^{_ESC}]*'

CAPABILITIES_RAW_MIXIN: typing.Dict[str, str] = {
    'bell': re.escape('\a'),
    'carriage_return': re.escape('\r'),
    'cursor_left': re.escape('\b'),
    'cursor_report': rf'{_CSI}(\d+)\;(\d+)R',
    'cursor_right': rf'{_CSI}C',
    'exit_attribute_mode': rf'{_CSI}m',
    'parm_left_cursor': rf'{_CSI}(\d+)D',
    'parm_right_cursor': rf'{_CSI}(\d+)C',
    'restore_cursor': rf'{_CSI}u',
    'save_cursor': rf'{_CSI}s',
    'scroll_forward': re.escape('\n'),
    'set0_des_seq': re.escape('\x1b(B'),
    'tab': re.escape('\t'),
}


CAPABILITIES_ADDITIVES: typing.Dict[
    str, typing.Union[typing.Tuple[str, str, int], typing.Tuple[str, str]]] = {
    'link': (rf'{_ESC}\]8;{_ANY_NOTESC};{_ANY_NOTESC}(?:{_ESC}\\|\x07)', 'link', 1),
    'color256': (rf'{_CSI}38;5;\d+m', 'color', 1),
    'on_color256': (rf'{_CSI}48;5;\d+m', 'on_color', 1),
    'color_rgb': (rf'{_CSI}38;2;\d+;\d+;\d+m', 'color_rgb', 3),
    'on_color_rgb': (rf'{_CSI}48;2;\d+;\d+;\d+m', 'on_color_rgb', 3),
    'shift_in': (re.escape('\x0f'), ''),
    'shift_out': (re.escape('\x0e'), ''),
    # sgr(...) outputs strangely, use the basic ANSI/EMCA-48 codes here.
    'set_a_attributes1': (rf'{_CSI}\d+m', 'sgr', 1),
    'set_a_attributes2': (rf'{_CSI}\d+\;\d+m', 'sgr', 2),
    'set_a_attributes3': (rf'{_CSI}\d+\;\d+\;\d+m', 'sgr', 3),
    'set_a_attributes4': (rf'{_CSI}\d+\;\d+\;\d+\;\d+m', 'sgr', 4),
    # this helps where xterm's sgr0 includes set0_des_seq, we'd
    # rather like to also match this immediate substring.
    'sgr0': (rf'{_CSI}m', 'sgr0'),
    'backspace': (re.escape('\b'), ''),
    'ascii_tab': (CAPABILITIES_RAW_MIXIN['tab'], ''),
    'clr_eol': (rf'{_CSI}K', ''),
    'clr_eol0': (rf'{_CSI}0K', ''),
    'clr_bol': (rf'{_CSI}1K', ''),
    'clr_eosK': (rf'{_CSI}2K', ''),
    'cursor_shape': (rf'{_CSI}[0-6] q', ''),
    'cursor_color_reset': (rf'{_ESC}\]112(?:{_ESC}\\|\x07)', ''),
}

CAPABILITIES_HORIZONTAL_DISTANCE: typing.Dict[str, int] = {
    'ascii_tab': 8,
    'backspace': -1,
    'cursor_left': -1,
    'cursor_right': 1,
    'parm_left_cursor': -1,
    'parm_right_cursor': 1,
    'tab': 8,
}

CAPABILITIES_CAUSE_MOVEMENT: typing.Tuple[str, ...] = tuple(CAPABILITIES_HORIZONTAL_DISTANCE) + (
    'carriage_return',
    'clear_screen',
    'column_address',
    'cursor_address',
    'cursor_down',
    'cursor_home',
    'cursor_up',
    'enter_fullscreen',
    'exit_fullscreen',
    'parm_down_cursor',
    'parm_up_cursor',
    'restore_cursor',
    'row_address',
    'scroll_forward',
)

XTGETTCAP_INIT_CAPABILITIES = (
    # Terminal capabilities requested at Initialization time:
    # - TN: determines preferred TERM
    # - colors, RGB: determines Terminal.number_of_colors
    # - blink, sitm, ritm, cvvis: nice to have as overlays, often omitted
    #
    # These were chosen from a May 2026 survey of all popular terminal emulators: what capabilities
    # and their values are reported by XTGETTCAP that are otherwise not discovered by the latest
    # ncurses termcap matching their defined TERM?
    'TN', 'RGB', 'colors', 'blink', 'sitm', 'ritm', 'cvvis', 'Smulx', 'Setulc', 'Ms')


XTGETTCAP_CAPABILITIES = (
    # Terminal identification and 24-bit color fields, note that the order of the first three
    # matters for xterm compatibility, described at https://codeberg.org/dnkl/foot#xtgettcap
    ("TN", "Terminal name"),
    ("RGB", "Bits per color channel (8 = 24-bit truecolor)"),
    ("colors", "Number of colors"),
    # as well as the order of the next section, where xterm supports **only** keyboard capabilities
    # via XTGETTCAP, and we have to be sensitive to request only supported capabilities, as xterm
    # stops replying after the first unsupported (non-keyboard) capability after these,
    # String capabilities -- keypad key sequences
    ("kcuu1", "Up arrow key"),
    ("kcud1", "Down arrow key"),
    ("kcub1", "Left arrow key"),
    ("kcuf1", "Right arrow key"),
    ("khome", "Home key"),
    ("kend", "End key"),
    ("knp", "Next page key"),
    ("kpp", "Previous page key"),
    ("kich1", "Insert character key"),
    ("kdch1", "Delete character key"),
    ("kbs", "Backspace key"),
    ("kcbt", "Back-tab key"),
    # String capabilities -- keypad application mode keys
    ("ka1", "Keypad upper left"),
    ("ka3", "Keypad upper right"),
    ("kb2", "Keypad center"),
    ("kc1", "Keypad lower left"),
    ("kc3", "Keypad lower right"),
    # String capabilities -- function keys
    ("kf1", "Function key F1"),
    ("kf2", "Function key F2"),
    ("kf3", "Function key F3"),
    ("kf4", "Function key F4"),
    ("kf5", "Function key F5"),
    ("kf6", "Function key F6"),
    ("kf7", "Function key F7"),
    ("kf8", "Function key F8"),
    ("kf9", "Function key F9"),
    ("kf10", "Function key F10"),
    ("kf11", "Function key F11"),
    # Function keys kf1-kf12 only: higher-numbered F-keys (kf13-kf63) do not
    # meaningfully differ between terminals; they describe F-key-with-modifier support,
    # and differences across terminal descriptions are limited to kf1-kf5 at most.
    ("kf12", "Function key F12"),
    # String capabilities -- modified navigation key sequences
    ("kDC", "Shifted delete-char key"),
    ("kEND", "Shifted end key"),
    ("kHOM", "Shifted home key"),
    ("kIC", "Shifted insert-char key"),
    ("kLFT", "Shifted left-arrow key"),
    ("kRIT", "Shifted right-arrow key"),
    ("kDN", "Shifted down-arrow key"),
    ("kUP", "Shifted up-arrow key"),
    ("kNXT", "Shifted next-page key"),
    ("kPRV", "Shifted previous-page key"),
    ("kent", "Enter/send key"),
    ("kind", "Scroll-down key"),
    ("kri", "Scroll-up key"),
    ("kmous", "Mouse key"),
    # And here is where xterm-supported XTGETTCAP capbilities end.
    #
    # We otherwise expect foot and kitty behavior -- if we wanted to, we could go without jinxed's
    # virtual capability database entirely, after careful audit I find only the following attributes
    # that may be missing or different from xterm-256color, and can be commonly patched by XTGETTCAP
    ("blink", "Enter blink mode"),
    ("sitm", "Enter italics mode"),
    ("ritm", "Exit italics mode"),
    ("cvvis", "Very visible cursor"),
    # And here is where blessed's integration ends. All remaining capabilities, for blessed's
    # purposes, are informational only. Used by the downstream 'ucs-detect' tool for auditing and
    # fingerprinting purposes, like "kitty-query-clipboard_control".
    #
    # Remaining numeric capabilities
    ("colors", "Max colors on screen"),
    ("cols", "Columns"),
    ("lines", "Lines"),
    ("it", "Init tabs"),
    ("pairs", "Max color pairs"),
    ("U8", "UTF-8 line-drawing"),
    # Boolean capabilities
    ("am", "Auto right margin"),
    ("bce", "Background color erase"),
    ("bw", "Auto left margin"),
    ("ccc", "Can redefine colors"),
    ("da", "Memory above"),
    ("db", "Memory below"),
    ("eslok", "Status line escape OK"),
    ("hs", "Has status line"),
    ("km", "Has meta key"),
    ("mir", "Move in insert mode"),
    ("msgr", "Move in standout mode"),
    ("npc", "No pad character"),
    ("ul", "Transparent underline"),
    ("xenl", "Newline glitch"),
    ("xt", "Destructive tabs"),
    ("mc5i", "Will not echo input"),
    ("AX", "Supports default colors"),
    ("Tc", "Truecolor (24-bit RGB)"),
    ("Su", "Colored underlines"),
    ("XT", "Xterm extensions"),
    ("fullkbd", "Full Kitty keyboard protocol"),
    ("xvpa", "Extended vertical positioning"),
    ("XF", "Extended functionality"),
    # String capabilities -- attributes
    ("bold", "Enter bold mode"),
    ("dim", "Enter dim mode"),
    ("rev", "Enter reverse mode"),
    ("smso", "Enter standout mode"),
    ("rmso", "Exit standout mode"),
    ("smul", "Enter underline mode"),
    ("rmul", "Exit underline mode"),
    ("sgr0", "Reset attributes"),
    # String capabilities -- colors
    ("setaf", "Set foreground color"),
    ("setab", "Set background color"),
    ("op", "Original pair"),
    # String capabilities -- cursor
    ("sc", "Save cursor"),
    ("rc", "Restore cursor"),
    ("civis", "Hide cursor"),
    ("cnorm", "Normal cursor"),
    ("cup", "Cursor address"),
    ("home", "Cursor home"),
    ("hpa", "Horizontal position"),
    ("vpa", "Vertical position"),
    ("cub1", "Cursor left"),
    ("cuf1", "Cursor right"),
    ("cuu1", "Cursor up"),
    ("cud1", "Cursor down"),
    ("cub", "Cursor left n"),
    ("cuf", "Cursor right n"),
    ("cuu", "Cursor up n"),
    ("cud", "Cursor down n"),
    # String capabilities -- editing
    ("el", "Clear to end of line"),
    ("el1", "Clear to start of line"),
    ("ed", "Clear to end of screen"),
    ("clear", "Clear screen"),
    ("ech", "Erase characters"),
    ("dch1", "Delete character"),
    ("dl1", "Delete line"),
    ("il1", "Insert line"),
    ("dch", "Delete n characters"),
    ("dl", "Delete n lines"),
    ("ich", "Insert n characters"),
    ("il", "Insert n lines"),
    ("indn", "Scroll forward n"),
    ("ind", "Scroll forward"),
    ("rin", "Scroll reverse n"),
    # String capabilities -- screen
    ("smcup", "Enter alt screen"),
    ("rmcup", "Exit alt screen"),
    ("csr", "Change scroll region"),
    ("smam", "Enable line wrap"),
    ("rmam", "Disable line wrap"),
    ("flash", "Flash screen"),
    ("bel", "Bell"),
    ("cr", "Carriage return"),
    # String capabilities -- keypad
    ("smkx", "Keypad transmit mode"),
    ("rmkx", "Keypad local mode"),
    # String capabilities -- user-defined (xterm convention)
    ("u6", "CPR response format"),
    ("u7", "CPR request"),
    ("u8", "DA response format"),
    ("u9", "DA request"),
    # Terminal-specific queries (kitty and foot extensions)
    ("query-os-name", "OS name query"),
    ("kitty-query-name", "terminal name"),
    ("kitty-query-version", "version"),
    ("kitty-query-allow_hyperlinks", "hyperlink support"),
    ("kitty-query-font_family", "font family"),
    ("kitty-query-bold_font", "bold font"),
    ("kitty-query-italic_font", "italic font"),
    ("kitty-query-bold_italic_font", "bold-italic font"),
    ("kitty-query-font_size", "font size"),
    ("kitty-query-dpi_x", "DPI X"),
    ("kitty-query-dpi_y", "DPI Y"),
    ("kitty-query-foreground", "foreground color"),
    ("kitty-query-background", "background color"),
    ("kitty-query-background_opacity", "background opacity"),
    ("kitty-query-clipboard_control", "clipboard control"),
    ("kitty-query-os_name", "OS name"),
    # String capabilities -- extended attributes
    ("Smulx", "Styled underline"),
    ("Setulc", "Set underline color"),
    ("Ss", "Set underline style"),
    ("Se", "Reset underline style"),
    ("Smol", "Set overline mode"),
    ("Rmol", "Reset overline mode"),
    ("Smxx", "Enter extended modes"),
    ("Rmxx", "Exit extended modes"),
    ("acsc", "Alternate character set"),
    ("smacs", "Enter alternate charset mode"),
    ("rmacs", "Exit alternate charset mode"),
    # String capabilities -- terminal features
    ("Ms", "Clipboard set"),
    ("Sync", "Synchronized output"),
    ("E3", "Erase scrollback"),
    ("Cr", "Set cursor color"),
    ("Cs", "Reset cursor color"),
    # String capabilities -- editing
    ("ht", "Horizontal tab"),
    ("hts", "Set tab stop"),
    ("tbc", "Clear all tabs"),
    ("ich1", "Insert character"),
    ("rep", "Repeat character"),
    # String capabilities -- cursor
    ("invis", "Invisible cursor"),
    ("initc", "Initialize color"),
    # String capabilities -- screen
    ("oc", "Original colors"),
    ("ri", "Reverse index"),
    ("smir", "Enter insert mode"),
    ("rmir", "Exit insert mode"),
    ("rs1", "Reset string 1"),
    ("rs2", "Reset string 2"),
    ("dsl", "Disable status line"),
    ("fsl", "From status line"),
    ("tsl", "To status line"),
    # String capabilities -- colors
    ("setrgbb", "Set RGB background"),
    ("setrgbf", "Set RGB foreground"),
    ("sgr", "Set attributes"),
    # String capabilities -- terminal features (continued)
    ("Rect", "Rectangle operations"),
    ("TS", "Terminal state query"),
    ("S0", "Output 8-bit controls"),
    ("nel", "Newline"),
    ("rmm", "Reset meta mode"),
    ("setal", "Set ANSI label"),
    # String capabilities -- kitty extensions
    ("BD", "Enter bold mode (kitty)"),
    ("BE", "Exit bold mode (kitty)"),
    ("PS", "Presentation start (kitty)"),
    ("PE", "Presentation end (kitty)"),
    ("XM", "Enter marks mode (kitty)"),
    ("xm", "Exit marks mode (kitty)"),
    ("RV", "Enter reverse mode (kitty)"),
    ("rv", "Exit reverse mode (kitty)"),
    ("XR", "Enter reset mode (kitty)"),
    ("xr", "Exit reset mode (kitty)"),
    ("fe", "Exit font mode (kitty)"),
    ("fd", "Enter font mode (kitty)"),
    ("kxIN", "Keyboard in (kitty)"),
    ("kxOUT", "Keyboard out (kitty)"),
    ("is2", "Init 2 string"),
    # String capabilities -- modifier key sequences (kitty keyboard protocol)
    ("kDC3", "Alt delete-char key"),
    ("kDC4", "Alt-Shift delete-char key"),
    ("kDC5", "Ctrl delete-char key"),
    ("kDC6", "Ctrl-Shift delete-char key"),
    ("kDC7", "Ctrl-Alt delete-char key"),
    ("kDN3", "Alt down-arrow key"),
    ("kDN4", "Alt-Shift down-arrow key"),
    ("kDN5", "Ctrl down-arrow key"),
    ("kDN6", "Ctrl-Shift down-arrow key"),
    ("kDN7", "Ctrl-Alt down-arrow key"),
    ("kEND3", "Alt end key"),
    ("kEND4", "Alt-Shift end key"),
    ("kEND5", "Ctrl end key"),
    ("kEND6", "Ctrl-Shift end key"),
    ("kEND7", "Ctrl-Alt end key"),
    ("kHOM3", "Alt home key"),
    ("kHOM4", "Alt-Shift home key"),
    ("kHOM5", "Ctrl home key"),
    ("kHOM6", "Ctrl-Shift home key"),
    ("kHOM7", "Ctrl-Alt home key"),
    ("kIC3", "Alt insert-char key"),
    ("kIC4", "Alt-Shift insert-char key"),
    ("kIC5", "Ctrl insert-char key"),
    ("kIC6", "Ctrl-Shift insert-char key"),
    ("kIC7", "Ctrl-Alt insert-char key"),
    ("kLFT3", "Alt left-arrow key"),
    ("kLFT4", "Alt-Shift left-arrow key"),
    ("kLFT5", "Ctrl left-arrow key"),
    ("kLFT6", "Ctrl-Shift left-arrow key"),
    ("kLFT7", "Ctrl-Alt left-arrow key"),
    ("kNXT3", "Alt next-page key"),
    ("kNXT4", "Alt-Shift next-page key"),
    ("kNXT5", "Ctrl next-page key"),
    ("kNXT6", "Ctrl-Shift next-page key"),
    ("kNXT7", "Ctrl-Alt next-page key"),
    ("kPRV3", "Alt previous-page key"),
    ("kPRV4", "Alt-Shift previous-page key"),
    ("kPRV5", "Ctrl previous-page key"),
    ("kPRV6", "Ctrl-Shift previous-page key"),
    ("kPRV7", "Ctrl-Alt previous-page key"),
    ("kRIT3", "Alt right-arrow key"),
    ("kRIT4", "Alt-Shift right-arrow key"),
    ("kRIT5", "Ctrl right-arrow key"),
    ("kRIT6", "Ctrl-Shift right-arrow key"),
    ("kRIT7", "Ctrl-Alt right-arrow key"),
    ("kUP3", "Alt up-arrow key"),
    ("kUP4", "Alt-Shift up-arrow key"),
    ("kUP5", "Ctrl up-arrow key"),
    ("kUP6", "Ctrl-Shift up-arrow key"),
    ("kUP7", "Ctrl-Alt up-arrow key"),
)


class Decrqss:
    """
    DECRQSS setting identifiers for querying terminal state.

    Each attribute is the "final character(s)" sent inside
    ``DCS $ q <setting_id> ST`` to request the current value
    of a particular terminal setting.

    .. seealso::

        `DECRQSS specification
        <https://vt100.net/docs/vt510-rm/DECRQSS.html>`_
    """

    # Display and rendering
    SGR = 'm'                  # Select Graphic Rendition
    DECSCUSR = ' q'            # Set Cursor Style
    DECSTBM = 'r'              # Set Top and Bottom Margins
    DECSLRM = 's'              # Set Left and Right Margins
    DECSCL = '"p'              # Set Conformance Level
    DECSCA = '"q'              # Set Character Protection Attribute
    DECSCPP = '$|'             # Set Columns Per Page
    DECSLPP = 't'              # Set Lines Per Page
    DECSNLS = '*|'             # Set Number of Lines per Screen
    DECSASD = '$}'             # Select Active Status Display
    DECSSDT = '$~'             # Set Status Line Type

    # Selection and extent
    DECSACE = '*x'             # Select Attribute Change Extent

    # Communication and hardware (VT510-specific)
    DECSSL = 'p'               # Select Set-Up Language
    DECSPRTT = '$s'            # Select Printer Type
    DECSRFR = '"t'             # Select Refresh Rate
    DECSDPT = '(p'             # Select Digital Printed Data Type
    DECSPPCS = '*p'            # Select ProPrinter Character Set
    DECSCS = '*r'              # Select Communication Speed
    DECSCP = '*u'              # Select Communication Port
    DECSSCLS = ' p'            # Set Scroll Speed
    DECSKCV = ' r'             # Set Key Click Volume
    DECSWBV = ' t'             # Set Warning Bell Volume
    DECSMBV = ' u'             # Set Margin Bell Volume
    DECSLCK = ' v'             # Set Lock Key Style
    DECSFC = '*s'              # Select Flow Control Type
    DECSDDT = '$q'             # Select Disconnect Delay Time
    DECSTRL = '"u'             # Set Transmit Rate Limit
    DECSPP = '+w'              # Set Port Parameter


class TermcapResponse:
    """
    Terminal capabilities queried via XTGETTCAP (DCS +q).

    XTGETTCAP queries the terminal emulator's built-in terminfo
    capabilities, bypassing the local terminfo database.  Capabilities
    are accessible by name via dict-like interface.

    .. seealso::

        `XTGETTCAP specification
        <https://invisible-island.net/xterm/ctlseqs/ctlseqs.html>`_
    """

    _TERMINFO_ESCAPE: typing.ClassVar[typing.Dict[str, str]] = {
        'E': '\x1b', 'e': '\x1b',
        'n': '\n', 't': '\t', 'r': '\r',
        'b': '\b', 'f': '\f',
        '\\': '\\', '^': '^', ':': ':',
    }

    # XTGETTCAP DCS response: DCS <valid>+r<hex-name>[=<hex-value>] ST
    #   valid=1: terminal supports this capability, value follows
    # valid=0: terminal does not support this capability (negative acknowledgement)
    # The capability name is hex-encoded; VTE-based terminals (GNOME Terminal, et al.) send
    # malformed ``\\x1bP0+r\\x1b\\\\`` (empty name) for unsupported capabilities, so we accept
    # zero-or-more hex digits rather than requiring at least one.
    _RE_XTGETTCAP_RESPONSE: typing.ClassVar[typing.Pattern[str]] = re.compile(
        r'\x1bP([01])\+r([0-9a-fA-F]*)(?:=([0-9a-fA-F]*))?\x1b\\')

    def __init__(self, supported: bool = False,
                 capabilities: Optional[Dict[str, str]] = None) -> None:
        """Initialize TermcapResponse with support status and capabilities."""
        self.supported = supported
        self.capabilities: Dict[str, str] = capabilities or {}

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Return capability value by name, or *default*."""
        return self.capabilities.get(name, default)

    def __contains__(self, name: object) -> bool:
        """Return True if capability *name* was reported."""
        return name in self.capabilities

    def __getitem__(self, name: str) -> str:
        """Return capability value, raising :exc:`KeyError` if absent."""
        return self.capabilities[name]

    def __len__(self) -> int:
        """Return number of capabilities."""
        return len(self.capabilities)

    @property
    def terminal_name(self) -> Optional[str]:
        """
        Terminal name from ``TN`` capability, or ``None``.

        .. deprecated:: This alias is not useful or used by blessed.
        """
        return self.capabilities.get('TN')

    @property
    def num_colors(self) -> Optional[int]:
        """
        Number of colors from ``colors`` capability, or ``None``.

        .. deprecated:: This value is not useful or used by blessed.
        """
        val = self.capabilities.get('colors')
        if val is not None:
            try:
                return int(val)
            except ValueError:
                pass
        return None

    def __repr__(self) -> str:
        """Return string representation."""
        return (f'TermcapResponse(supported={self.supported}, '
                f'capabilities={self.capabilities})')

    @staticmethod
    def hex_encode(name: str) -> str:
        """Hex-encode a capability name for an XTGETTCAP query."""
        return name.encode('ascii').hex()

    @staticmethod
    def hex_decode(hex_str: str) -> str:
        """Decode a hex-encoded string from an XTGETTCAP response."""
        try:
            return bytes.fromhex(hex_str).decode('ascii', errors='strict')
        except ValueError:
            return ''

    @staticmethod
    def unescape_terminfo(
        value: str,
    ) -> str:
        r"""
        Unescape terminfo source-level escape sequences.

        Terminfo source format uses ``\E``, ``\n``, ``\t``, ``\r``, ``\b``, ``\f``, ``\\``, ``\^``,
        ``\:``, ``\NNN`` octal, and ``^X`` control-character notation.  XTGETTCAP responses from
        some terminals (e.g. ghostty, kitty, foot, rio) report values in this source format rather
        than as raw binary.  Convert these to their actual byte values.
        """
        result = []
        idx = 0
        while idx < len(value):
            cur = value[idx]
            if cur == '\\' and idx + 1 < len(value):
                nxt = value[idx + 1]
                esc = TermcapResponse._TERMINFO_ESCAPE.get(nxt)
                if esc is not None:
                    result.append(esc)
                    idx += 2
                    continue
                if nxt in '01234567':
                    end = idx + 1
                    while end < len(value) and value[end] in '01234567':
                        end += 1
                    result.append(chr(int(value[idx + 1:end], 8)))
                    idx = end
                    continue
            elif cur == '^' and idx + 1 < len(value):
                nxt = value[idx + 1]
                if 'A' <= nxt <= '_':
                    result.append(chr(ord(nxt) - ord('A') + 1))
                    idx += 2
                    continue
                if nxt == '?':
                    result.append('\x7f')
                    idx += 2
                    continue
            result.append(cur)
            idx += 1
        return ''.join(result)

    @classmethod
    def from_match(cls, match: 're.Match[str]') -> 'tuple[str, str]':
        """Parse a single XTGETTCAP DCS +r regex match into (name, value)."""
        cap_name = cls.hex_decode(match.group(2))
        value = (
            cls.unescape_terminfo(cls.hex_decode(val_hex))
            if (val_hex := match.group(3)) is not None
            else ''
        )
        return cap_name, value

    @classmethod
    def parse_capabilities(cls, raw: str) -> 'Dict[str, str]':
        """Parse all successful DCS +r responses from raw text."""
        capabilities: Dict[str, str] = {}
        for match in cls._RE_XTGETTCAP_RESPONSE.finditer(raw):
            if match.group(1) == '1':
                name, value = cls.from_match(match)
                capabilities[name] = value
        return capabilities

    def make_jinxed_capabilities(self) -> 'Dict[str, Dict[str, str] | Dict[str, int] | Set[str]]':
        """
        Classify discovered capabilities for injection into a jinxed Terminal.

        :returns: dict with keys ``str_caps``, ``num_caps``, ``bool_caps``, matching
            the keyword arguments accepted by jinxed Terminal method, ``apply_capabilities()``
        """
        str_caps: Dict[str, str] = {}
        num_caps: Dict[str, int] = {}
        bool_caps: Set[str] = set()

        for capname, value in self.capabilities.items():
            if capname == 'RGB':
                # 'RGB' is not a terminfo(5) capability, as noted by foot, "RGB - number of bits per
                # color channel (different semantics from the RGB capability in file-based terminfo
                # definitions!)." https://codeberg.org/dnkl/foot#xtgettcap
                continue
            if not value:
                if capname in jinxed.terminfo.BOOL_CAPS:
                    bool_caps.add(capname)
            elif capname in jinxed.terminfo.NUM_CAPS:
                if value.isdigit():
                    num_caps[capname] = int(value)
            else:
                str_caps[capname] = value

        return {'str_caps': str_caps, 'num_caps': num_caps, 'bool_caps': bool_caps}


class ITerm2Capabilities:
    """
    ITerm2 capability features from OSC 1337;Capabilities response.

    Features are accessible as a dict via :attr:`features`.

    .. seealso::

        `iTerm2 escape codes
        <https://iterm2.com/documentation-escape-codes.html>`_
    """

    FEATURE_MAP = {
        'T': ('truecolor', 'int', 2),
        'Cw': ('clipboard_writable', 'bool', 0),
        'Lr': ('decslrm', 'bool', 0),
        'M': ('mouse', 'bool', 0),
        'Sc': ('decscusr', 'int', 3),
        'U': ('unicode_basic', 'bool', 0),
        'Aw': ('ambiguous_wide', 'bool', 0),
        'Uw': ('unicode_widths', 'int', 6),
        'Ts': ('titles', 'int', 2),
        'B': ('bracketed_paste', 'bool', 0),
        'F': ('focus_reporting', 'bool', 0),
        'Gs': ('strikethrough', 'bool', 0),
        'Go': ('overline', 'bool', 0),
        'Sy': ('sync', 'bool', 0),
        'H': ('hyperlinks', 'bool', 0),
        'No': ('notifications', 'bool', 0),
        'Sx': ('sixel', 'bool', 0),
    }

    def __init__(self, supported: bool = False,
                 features: Optional[Dict[str, typing.Any]] = None) -> None:
        """Initialize ITerm2Capabilities with support status and features."""
        self.supported = supported
        self.features: Dict[str, typing.Any] = features or {}

    @staticmethod
    def parse_feature_string(feature_str: str) -> Dict[str, typing.Any]:
        """Parse an iTerm2 Capabilities feature string into a dict."""
        features: Dict[str, typing.Any] = {}
        pos = 0
        while pos < len(feature_str):
            matched = False
            for code_len in (2, 1):
                code = feature_str[pos:pos + code_len]
                if code in ITerm2Capabilities.FEATURE_MAP:
                    name, ftype, bits = ITerm2Capabilities.FEATURE_MAP[code]
                    pos += code_len
                    if ftype == 'int' and bits > 0:
                        # parse integer value
                        digits = ''
                        while pos < len(feature_str) and feature_str[pos].isdigit():
                            digits += feature_str[pos]
                            pos += 1
                        features[name] = int(digits) if digits else 0
                    else:
                        # non-ints are bools, when present
                        features[name] = True
                    matched = True
                    break
            if not matched:
                pos += 1
        return features

    def __repr__(self) -> str:
        """Return string representation."""
        return (f'ITerm2Capabilities(supported={self.supported}, '
                f'features={self.features})')


class TextSizingResult:
    """
    Result of Kitty text sizing protocol detection (OSC 66).

    :param bool width: True if width sizing is supported.
    :param bool scale: True if scale sizing is supported.
    """

    def __init__(self, width: bool = False, scale: bool = False) -> None:
        self.width = width
        self.scale = scale

    def __bool__(self) -> bool:
        return self.width or self.scale

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TextSizingResult):
            return self.width == other.width and self.scale == other.scale
        return NotImplemented

    def __repr__(self) -> str:
        return f"TextSizingResult(width={self.width}, scale={self.scale})"
