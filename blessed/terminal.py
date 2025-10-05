# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""Module containing :class:`Terminal`, the primary API entry point."""
# std imports
import os
import re
import sys
import time
import codecs
import locale
import select
import struct
import platform
import warnings
import contextlib
import collections
from typing import IO, Dict, List, Match, Tuple, Union, Optional, Generator

# SupportsIndex was added in Python 3.8
if sys.version_info >= (3, 8):
    # std imports
    from typing import SupportsIndex
else:
    SupportsIndex = int  # type: ignore


# local
from .color import COLOR_DISTANCE_ALGORITHMS, xterm256gray_from_rgb, xterm256color_from_rgb
from .keyboard import (DEFAULT_ESCDELAY,
                       Keystroke,
                       DeviceAttribute,
                       KittyKeyboardProtocol,
                       _time_left,
                       _read_until,
                       resolve_sequence,
                       get_keyboard_codes,
                       get_leading_prefixes,
                       get_keyboard_sequences)
from .dec_modes import DecPrivateMode, DecModeResponse
from .sequences import Termcap, Sequence, SequenceTextWrapper
from .colorspace import RGB_256TABLE
from .formatters import (COLORS,
                         COMPOUNDABLES,
                         FormattingString,
                         NullCallableString,
                         ParameterizingString,
                         FormattingOtherString,
                         split_compound,
                         resolve_attribute,
                         resolve_capability)
from ._capabilities import (CAPABILITY_DATABASE,
                            CAPABILITIES_ADDITIVES,
                            CAPABILITIES_RAW_MIXIN,
                            CAPABILITIES_HORIZONTAL_DISTANCE)

# isort: off


HAS_TTY = True
if platform.system() == 'Windows':
    IS_WINDOWS = True
    import jinxed as curses  # pylint: disable=import-error
    from jinxed.win32 import get_console_input_encoding  # pylint: disable=import-error
else:
    IS_WINDOWS = False
    import curses

    try:
        import fcntl
        import termios
        import tty
    except ImportError:
        _TTY_METHODS = ('setraw', 'cbreak', 'kbhit', 'height', 'width')
        _MSG_NOSUPPORT = (
            "One or more of the modules: 'termios', 'fcntl', and 'tty' "
            f"are not found on your platform '{platform.system()}'. "
            "The following methods of Terminal are dummy/no-op "
            f"unless a deriving class overrides them: {', '.join(_TTY_METHODS)}."
        )
        warnings.warn(_MSG_NOSUPPORT)
        HAS_TTY = False

_CUR_TERM = None  # See comments at end of file
_RE_GET_FGCOLOR_RESPONSE = re.compile(
    '\x1b]10;rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)\x07')
_RE_GET_BGCOLOR_RESPONSE = re.compile(
    '\x1b]11;rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)\x07')

class WINSZ(collections.namedtuple('WINSZ', (
        'ws_row', 'ws_col', 'ws_xpixel', 'ws_ypixel'))):
    """
    Structure represents return value of :const:`termios.TIOCGWINSZ`.

    .. py:attribute:: ws_row

        rows, in characters

    .. py:attribute:: ws_col

        columns, in characters

    .. py:attribute:: ws_xpixel

        horizontal size, pixels

    .. py:attribute:: ws_ypixel

        vertical size, pixels
    """
    #: format of termios structure
    _FMT = 'hhhh'
    #: buffer of termios structure appropriate for ioctl argument
    _BUF = '\x00' * struct.calcsize(_FMT)


class Terminal():
    """
    An abstraction for color, style, positioning, and input in the terminal.

    This keeps the endless calls to ``tigetstr()`` and ``tparm()`` out of your code, acts
    intelligently when somebody pipes your output to a non-terminal, and abstracts over the
    complexity of unbuffered keyboard input. It uses the terminfo database to remain portable across
    terminal types.
    """
    # pylint: disable=too-many-instance-attributes,too-many-public-methods
    #         Too many public methods (28/20)
    #         Too many instance attributes (12/7)

    #: Sugary names for commonly-used capabilities
    _sugar = {
        'save': 'sc',
        'restore': 'rc',
        'clear_eol': 'el',
        'clear_bol': 'el1',
        'clear_eos': 'ed',
        'enter_fullscreen': 'smcup',
        'exit_fullscreen': 'rmcup',
        'move': 'cup',
        'move_yx': 'cup',
        'move_x': 'hpa',
        'move_y': 'vpa',
        'hide_cursor': 'civis',
        'normal_cursor': 'cnorm',
        'reset_colors': 'op',
        'normal': 'sgr0',
        'reverse': 'rev',
        'italic': 'sitm',
        'no_italic': 'ritm',
        'shadow': 'sshm',
        'no_shadow': 'rshm',
        'standout': 'smso',
        'no_standout': 'rmso',
        'subscript': 'ssubm',
        'no_subscript': 'rsubm',
        'superscript': 'ssupm',
        'no_superscript': 'rsupm',
        'underline': 'smul',
        'no_underline': 'rmul',
        'cursor_report': 'u6',
        'cursor_request': 'u7',
        'terminal_answerback': 'u8',
        'terminal_enquire': 'u9',
    }

    def __init__(self, kind: Optional[str] = None, stream: Optional[IO[str]] = None,
                 force_styling: Union[bool, None] = False) -> None:
        """
        Initialize the terminal.

        :arg str kind: A terminal string as taken by :func:`curses.setupterm`.
            Defaults to the value of the ``TERM`` environment variable.

            .. note:: Terminals within a single process must share a common
                ``kind``. See :obj:`_CUR_TERM`.

        :arg file stream: A file-like object representing the Terminal output.
            Defaults to the original value of :obj:`sys.__stdout__`, like
            :func:`curses.initscr` does.

            If ``stream`` is not a tty, empty Unicode strings are returned for
            all capability values, so things like piping your program output to
            a pipe or file does not emit terminal sequences.

        :arg bool force_styling: Whether to force the emission of capabilities
            even if :obj:`sys.__stdout__` does not seem to be connected to a
            terminal. If you want to force styling to not happen, use
            ``force_styling=None``.

            This comes in handy if users are trying to pipe your output through
            something like ``less -r`` or build systems which support decoding
            of terminal sequences.

            When the OS Environment variable FORCE_COLOR_ or CLICOLOR_FORCE_ is
            *non-empty*, styling is used no matter the value specified by
            ``force_styling``.

            Conversely, When OS Environment variable NO_COLOR_ is *non-empty*,
            styling is **not** used no matter the value specified by
            ``force_styling`` and has precedence over FORCE_COLOR_ and
            CLICOLOR_FORCE_.

            .. _FORCE_COLOR: https://force-color.org/
            .. _CLICOLOR_FORCE: https://bixense.com/clicolors/
            .. _NO_COLOR: https://no-color.org/
        """
        # pylint: disable=global-statement
        global _CUR_TERM
        self.errors = [
            f'parameters: kind={kind!r}, stream={stream!r}, force_styling={force_styling!r}',
        ]
        self._normal = None  # cache normal attr, preventing recursive lookups
        # we assume our input stream to be line-buffered until either the
        # cbreak of raw context manager methods are entered with an attached tty.
        self._line_buffered = True

        self._stream = stream
        self._keyboard_fd = None
        self._init_descriptor = None
        self._is_a_tty = False
        self.__init__streams()

        if IS_WINDOWS and self._init_descriptor is not None:
            self._kind = kind or curses.get_term(self._init_descriptor)
        else:
            self._kind = kind or os.environ.get('TERM', 'dumb') or 'dumb'

        self.__init_set_styling(force_styling)
        if self.does_styling:
            # Initialize curses (call setupterm), so things like tigetstr() work.
            try:
                curses.setupterm(self._kind, self._init_descriptor)
            except curses.error as err:
                msg = f'Failed to setupterm(kind={self._kind!r}): {err}'
                warnings.warn(msg)
                self.errors.append(msg)
                self._kind = None
                self._does_styling = False
            else:
                if _CUR_TERM is None or self._kind == _CUR_TERM:
                    _CUR_TERM = self._kind
                else:
                    # termcap 'kind' is immutable in a python process! Once
                    # initialized by setupterm, it is unsupported by the
                    # 'curses' module to change the terminal type again. If you
                    # are a downstream developer and you need this
                    # functionality, consider sub-processing, instead.
                    warnings.warn(
                        f'A terminal of kind "{kind}" has been requested; due to an'
                        ' internal python curses bug, terminal capabilities'
                        f' for a terminal of kind "{_CUR_TERM}" will continue to be'
                        ' returned for the remainder of this process.'
                    )

        self.__init__color_capabilities()
        self.__init__capabilities()
        self.__init__keycodes()
        self.__init__dec_private_modes()

    def __init__dec_private_modes(self) -> None:
        """Initialize DEC Private Mode caching and state tracking."""
        # Cache for queried DEC private modes to avoid repeated queries
        self._dec_mode_cache: Dict[int, int] = {}
        # Global timeout tracking state
        self._dec_any_query_succeeded = False
        self._dec_first_query_failed = False

        # Kitty keyboard protocol timeout tracking (no caching)
        self._kitty_kb_first_query_failed = False
        self._kitty_kb_first_query_attempted = False

        # Device Attributes (DA1) cache
        # pylint: disable=attribute-defined-outside-init
        self._device_attributes_cache: Optional[DeviceAttribute] = None

    def __init_set_styling(self, force_styling: bool) -> None:
        self._does_styling = False
        if os.getenv('NO_COLOR'):
            self.errors.append(f'NO_COLOR={os.getenv("NO_COLOR")!r}')
        elif os.getenv('FORCE_COLOR'):
            self.errors.append(f'FORCE_COLOR={os.getenv("FORCE_COLOR")!r}')
            self._does_styling = True
        elif os.getenv('CLICOLOR_FORCE'):
            self.errors.append(f'CLICOLOR_FORCE={os.getenv("CLICOLOR_FORCE")!r}')
            self._does_styling = True
        elif force_styling is None and self.is_a_tty:
            self.errors.append('force_styling is None')
        elif force_styling or self.is_a_tty:
            self._does_styling = True

    def __init__streams(self) -> None:
        # pylint: disable=too-complex,too-many-branches
        #         Agree to disagree !
        stream_fd = None

        # Default stream is stdout
        if self._stream is None:
            self._stream = sys.__stdout__

        if not hasattr(self._stream, 'fileno'):
            self.errors.append('stream has no fileno method')
        elif not callable(self._stream.fileno):  # type: ignore
            self.errors.append('stream.fileno is not callable')
        else:
            try:
                stream_fd = self._stream.fileno()  # type: ignore
            except ValueError as err:
                # The stream is not a file, such as the case of StringIO, or, when it has been
                # "detached", such as might be the case of stdout in some test scenarios.
                self.errors.append(f'Unable to determine output stream file descriptor: {err}')
            else:
                self._is_a_tty = os.isatty(stream_fd)
                if not self._is_a_tty:
                    self.errors.append('stream not a TTY')

        # Keyboard valid as stdin only when output stream is stdout or stderr and is a tty.
        if self._stream in (sys.__stdout__, sys.__stderr__):
            try:
                if sys.__stdin__ is not None:
                    self._keyboard_fd = sys.__stdin__.fileno()
            except (AttributeError, ValueError) as err:
                self.errors.append(f'Unable to determine input stream file descriptor: {err}')
            else:
                # _keyboard_fd only non-None if both stdin and stdout is a tty.
                if not self.is_a_tty:
                    self.errors.append('Output stream is not a TTY')
                    self._keyboard_fd = None
                elif not os.isatty(self._keyboard_fd):
                    self.errors.append('Input stream is not a TTY')
                    self._keyboard_fd = None
        else:
            self.errors.append('Output stream is not a default stream')

        # The descriptor to direct terminal initialization sequences to.
        self._init_descriptor = stream_fd
        if stream_fd is None:
            try:
                self._init_descriptor = sys.__stdout__.fileno()  # type: ignore
            except ValueError as err:
                self.errors.append(f'Unable to determine __stdout__ file descriptor: {err}')

    def __init__color_capabilities(self) -> None:
        self._color_distance_algorithm = 'cie2000'
        if not self.does_styling:
            self.number_of_colors = 0
        elif IS_WINDOWS or os.environ.get('COLORTERM') in {'truecolor', '24bit'}:
            self.number_of_colors = 1 << 24
        else:
            self.number_of_colors = max(0, curses.tigetnum('colors') or -1)

    def __clear_color_capabilities(self) -> None:
        for cached_color_cap in set(dir(self)) & COLORS:
            delattr(self, cached_color_cap)

    def __init__capabilities(self) -> None:
        # important that we lay these in their ordered direction, so that our
        # preferred, 'color' over 'set_a_attributes1', for example.
        self.caps = collections.OrderedDict()

        # some static injected patterns, esp. without named attribute access.
        for name, args in CAPABILITIES_ADDITIVES.items():
            self.caps[name] = Termcap(name, *args)

        for name, (attribute, kwds) in CAPABILITY_DATABASE.items():
            if self.does_styling:
                # attempt dynamic lookup
                cap = getattr(self, attribute)
                if cap:
                    self.caps[name] = Termcap.build(
                        name, cap, attribute, **kwds)
                    continue

            # fall-back
            pattern = CAPABILITIES_RAW_MIXIN.get(name)
            if pattern:
                self.caps[name] = Termcap(name, pattern, attribute, kwds.get('nparams', 0))

        # make a compiled named regular expression table
        self.caps_compiled = re.compile(
            '|'.join(cap.pattern for cap in self.caps.values())
        )
        # Used with padd() to separate plain text from caps
        self._caps_named_compiled = re.compile(
            '|'.join(cap.named_pattern for cap in self.caps.values())
        )
        # Used with padd() to strip non-horizontal caps
        self._caps_compiled_without_hdist = re.compile('|'.join(
            cap.pattern for cap in self.caps.values()
            if cap.name not in CAPABILITIES_HORIZONTAL_DISTANCE)
        )
        # for tokenizer, the '.lastgroup' is the primary lookup key for
        # 'self.caps', unless 'MISMATCH'; then it is an unmatched character.
        self._caps_compiled_any = re.compile(
            f'{"|".join(cap.named_pattern for cap in self.caps.values())}|(?P<MISMATCH>.)'
        )
        self._caps_unnamed_any = re.compile(
            f'{"|".join(f"({cap.pattern})" for cap in self.caps.values())}|(.)'
        )

    def __init__keycodes(self) -> None:
        # Initialize keyboard data determined by capability.
        # Build database of int code <=> KEY_NAME.
        self._keycodes = get_keyboard_codes()

        # Store attributes as: self.KEY_NAME = code. These only work for porting
        # legacy curses applications that used key codes, and are not really
        # suggested, and they do not support modifier keys, eg. 'KEY_SHIFT_F1'
        # does not exist and has no code.
        for key_code, key_name in self._keycodes.items():
            setattr(self, key_name, key_code)

        # Build database of sequence <=> KEY_NAME.
        self._keymap = get_keyboard_sequences(self)
        self._keymap_prefixes = get_leading_prefixes(self._keymap)

        # keyboard stream buffer
        self._keyboard_buf: collections.deque[str] = collections.deque()

        if self._keyboard_fd is not None:
            # set input encoding and initialize incremental decoder

            if IS_WINDOWS:
                # pylint: disable-next=possibly-used-before-assignment
                self._encoding = get_console_input_encoding() \
                    or locale.getpreferredencoding() or 'UTF-8'
            else:
                self._encoding = locale.getpreferredencoding() or 'UTF-8'

            try:
                self._keyboard_decoder = codecs.getincrementaldecoder(self._encoding)()
            except LookupError as err:
                # encoding is illegal or unsupported, use 'UTF-8'
                warnings.warn(f'LookupError: {err}, defaulting to UTF-8 for keyboard.')
                self._encoding = 'UTF-8'
                self._keyboard_decoder = codecs.getincrementaldecoder(self._encoding)()

            # Initialize latin-1 decoder for legacy mouse sequences
            # This is used for sequences starting with '\x1b[M' that may contain high bytes (≥0x80)
            # which are not valid UTF-8 but are valid in latin-1 encoding
            self._keyboard_decoder_latin1 = codecs.getincrementaldecoder('latin-1')()

    def __getattr__(self, attr: str) -> Union[
            NullCallableString, ParameterizingString, FormattingString]:
        r"""
        Return a terminal capability as Unicode string.

        For example, ``term.bold`` is a unicode string that may be prepended
        to text to set the video attribute for bold, which should also be
        terminated with the pairing :attr:`normal`. This capability
        returns a callable, so you can use ``term.bold("hi")`` which
        results in the joining of ``(term.bold, "hi", term.normal)``.

        Compound formatters may also be used. For example::

            >>> term.bold_blink_red_on_green("merry x-mas!")

        For a parameterized capability such as ``move`` (or ``cup``), pass the
        parameters as positional arguments::

            >>> term.move(line, column)

        See the manual page `terminfo(5)
        <https://invisible-island.net/ncurses/man/terminfo.5.html>`_ for a
        complete list of capabilities and their arguments.
        """
        if not self._does_styling:
            return NullCallableString()
        # Fetch the missing 'attribute' into some kind of curses-resolved
        # capability, and cache by attaching to this Terminal class instance.
        #
        # Note that this will prevent future calls to __getattr__(), but
        # that's precisely the idea of the cache!
        val = resolve_attribute(self, attr)
        setattr(self, attr, val)
        return val

    @property
    def kind(self) -> str:
        """
        Read-only property: Terminal kind determined on class initialization.

        :rtype: str
        """
        return self._kind

    @property
    def does_styling(self) -> bool:
        """
        Read-only property: Whether this class instance may emit sequences.

        :rtype: bool
        """
        return self._does_styling

    @property
    def is_a_tty(self) -> bool:
        """
        Read-only property: Whether :attr:`~.stream` is a terminal.

        :rtype: bool
        """
        return self._is_a_tty

    @property
    def height(self) -> int:
        """
        Read-only property: Height of the terminal (in number of lines).

        :rtype: int
        """
        return self._height_and_width().ws_row

    @property
    def width(self) -> int:
        """
        Read-only property: Width of the terminal (in number of columns).

        :rtype: int
        """
        return self._height_and_width().ws_col

    @property
    def pixel_height(self) -> int:
        """
        Read-only property: Height of the terminal (in pixels).

        :rtype: int
        """
        return self._height_and_width().ws_ypixel

    @property
    def pixel_width(self) -> int:
        """
        Read-only property: Width of terminal (in pixels).

        :rtype: int
        """
        return self._height_and_width().ws_xpixel

    @staticmethod
    def _winsize(fd):  # type: ignore[no-untyped-def]
        """
        Return named tuple describing size of the terminal by ``fd``.

        If the given platform does not have modules :mod:`termios`,
        :mod:`fcntl`, or :mod:`tty`, window size of 80 columns by 25
        rows is always returned.

        :arg int fd: file descriptor queries for its window size.
        :raises IOError: the file descriptor ``fd`` is not a terminal.
        :rtype: WINSZ
        :returns: named tuple describing size of the terminal

        WINSZ is a :class:`collections.namedtuple` instance, whose structure
        directly maps to the return value of the :const:`termios.TIOCGWINSZ`
        ioctl return value. The return parameters are:

            - ``ws_row``: width of terminal by its number of character cells.
            - ``ws_col``: height of terminal by its number of character cells.
            - ``ws_xpixel``: width of terminal by pixels (not accurate).
            - ``ws_ypixel``: height of terminal by pixels (not accurate).
        """
        if HAS_TTY:
            # pylint: disable=protected-access,possibly-used-before-assignment
            data = fcntl.ioctl(fd, termios.TIOCGWINSZ, WINSZ._BUF)
            return WINSZ(*struct.unpack(WINSZ._FMT, data))
        return WINSZ(ws_row=25, ws_col=80, ws_xpixel=0, ws_ypixel=0)

    def _height_and_width(self) -> WINSZ:
        """
        Return a tuple of (terminal height, terminal width).

        If :attr:`stream` or :obj:`sys.__stdout__` is not a tty or does not
        support :func:`fcntl.ioctl` of :const:`termios.TIOCGWINSZ`, a window
        size of 80 columns by 25 rows is returned for any values not
        represented by environment variables ``LINES`` and ``COLUMNS``, which
        is the default text mode of IBM PC compatibles.

        :rtype: WINSZ
        :returns: Named tuple specifying the terminal size

        WINSZ is a :class:`collections.namedtuple` instance, whose structure
        directly maps to the return value of the :const:`termios.TIOCGWINSZ`
        ioctl return value. The return parameters are:

            - ``ws_row``: height of terminal by its number of cell rows.
            - ``ws_col``: width of terminal by its number of cell columns.
            - ``ws_xpixel``: width of terminal by pixels (not accurate).
            - ``ws_ypixel``: height of terminal by pixels (not accurate).

            .. note:: the peculiar (height, width, width, height) order, which
               matches the return order of TIOCGWINSZ!
        """
        for fd in (self._init_descriptor, sys.__stdout__):
            try:
                if fd is not None:
                    return self._winsize(fd)
            except (IOError, OSError, ValueError, TypeError):  # pylint: disable=overlapping-except
                pass

        return WINSZ(ws_row=int(os.getenv('LINES', '25')),
                     ws_col=int(os.getenv('COLUMNS', '80')),
                     ws_xpixel=None,
                     ws_ypixel=None)

    def _query_response(self, query_str: str, response_re: str,
                        timeout: Optional[float]) -> Optional[Match[str]]:
        """
        Sends a query string to the terminal and waits for a response.

        :arg str query_str: Query string written to output
        :arg str response_re: Regular expression matching query response
        :arg float timeout: Return after time elapsed in seconds
        :return: re.match object for response_re or None if not found
        :rtype: re.Match
        """
        # Avoid changing user's desired raw or cbreak mode if already entered,
        # by entering cbreak mode ourselves.  This is necessary to receive user
        # input without awaiting a human to press the return key.   This mode
        # also disables echo, which we should also hide, as our input is an
        # sequence that is not meaningful for display as an output sequence.

        ctx = None
        try:
            if self._line_buffered:
                ctx = self.cbreak()
                ctx.__enter__()

            # Emit the query sequence,
            self.stream.write(query_str)
            self.stream.flush()

            # Wait for response
            match, data = _read_until(term=self,  # pylint: disable=unpacking-non-sequence
                                      pattern=response_re,
                                      timeout=timeout)

            # Exclude response from subsequent input
            if match:
                data = data[:match.start()] + data[match.end():]

            # re-buffer keyboard data, if any
            self.ungetch(data)

        finally:
            if ctx is not None:
                ctx.__exit__(None, None, None)

        return match

    @contextlib.contextmanager
    def location(self, x: Optional[int] = None,
                 y: Optional[int] = None) -> Generator[None, None, None]:
        """
        Context manager for temporarily moving the cursor.

        :arg int x: horizontal position, from left, *0*, to right edge of screen, *self.width - 1*.
        :arg int y: vertical position, from top, *0*, to bottom of screen, *self.height - 1*.
        :return: a context manager.
        :rtype: Iterator

        Move the cursor to a certain position on entry, do any kind of I/O, and upon exit
        let you print stuff there, then return the cursor to its original position:


        .. code-block:: python

            term = Terminal()
            with term.location(y=0, x=0):
                for row_num in range(term.height-1):
                    print('Row #{row_num}')
            print(term.clear_eol + 'Back to original location.')

        Specify ``x`` to move to a certain column, ``y`` to move to a certain
        row, both, or neither. If you specify neither, only the saving and
        restoration of cursor position will happen. This can be useful if you
        simply want to restore your place after doing some manual cursor
        movement.

        Calls cannot be nested: only one should be entered at a time.

        .. note:: The argument order *(x, y)* differs from the return value order *(y, x)*
            of :meth:`get_location`, or argument order *(y, x)* of :meth:`move`. This is
            for API Compatibility with the blessings library, sorry for the trouble!
        """
        # Save position and move to the requested column, row, or both:
        self.stream.write(self.save)
        if x is not None and y is not None:
            self.stream.write(self.move(y, x))
        elif x is not None:
            self.stream.write(self.move_x(x))
        elif y is not None:
            self.stream.write(self.move_y(y))
        try:
            self.stream.flush()
            yield
        finally:
            # Restore original cursor position:
            self.stream.write(self.restore)
            self.stream.flush()

    def get_location(self, timeout: Optional[float] = None) -> Tuple[int, int]:
        r"""
        Return tuple (row, column) of cursor position.

        :arg float timeout: Return after time elapsed in seconds with value ``(-1, -1)`` indicating
            that the remote end did not respond.
        :rtype: tuple
        :returns: cursor position as tuple in form of ``(y, x)``.  When a timeout is specified,
            always ensure the return value is checked for ``(-1, -1)``.

        The location of the cursor is determined by emitting the ``u7`` terminal capability, or
        VT100 `Query Cursor Position
        <https://www2.ccs.neu.edu/research/gpc/VonaUtils/vona/terminal/vtansi.htm#status>`_
        when such capability is undefined, which elicits a response from a reply string described by
        capability ``u6``, or again VT100's definition of ``\x1b[%i%d;%dR`` when undefined.

        The ``(y, x)`` return value matches the parameter order of the :meth:`move_yx` capability.
        The following sequence should cause the cursor to not move at all::

            >>> term = Terminal()
            >>> term.move_yx(*term.get_location()))

        And the following should assert True with a terminal:

            >>> term = Terminal()
            >>> given_y, given_x = 10, 20
            >>> with term.location(y=given_y, x=given_x):
            ...     result_y, result_x = term.get_location()
            ...
            >>> assert given_x == result_x, (given_x, result_x)
            >>> assert given_y == result_y, (given_y, result_y)
        """
        # Local lines attached by termios and remote login protocols such as
        # ssh and telnet both provide a means to determine the window
        # dimensions of a connected client, but **no means to determine the
        # location of the cursor**.
        #
        # from https://invisible-island.net/ncurses/terminfo.src.html,
        #
        # > The System V Release 4 and XPG4 terminfo format defines ten string
        # > capabilities for use by applications, <u0>...<u9>.   In this file,
        # > we use certain of these capabilities to describe functions which
        # > are not covered by terminfo.  The mapping is as follows:
        # >
        # >  u9   terminal enquire string (equiv. to ANSI/ECMA-48 DA)
        # >  u8   terminal answerback description
        # >  u7   cursor position request (equiv. to VT100/ANSI/ECMA-48 DSR 6)
        # >  u6   cursor position report (equiv. to ANSI/ECMA-48 CPR)

        response_str = getattr(self, self.caps['cursor_report'].attribute) or '\x1b[%i%d;%dR'
        match = self._query_response(
            self.u7 or '\x1b[6n', self.caps['cursor_report'].re_compiled, timeout
        )

        if match:
            # return matching sequence response, the cursor location.
            row, col = (int(val) for val in match.groups())

            # Per https://invisible-island.net/ncurses/terminfo.src.html
            # The cursor position report (<u6>) string must contain two
            # scanf(3)-style %d format elements.  The first of these must
            # correspond to the Y coordinate and the second to the %d.
            # If the string contains the sequence %i, it is taken as an
            # instruction to decrement each value after reading it (this is
            # the inverse sense from the cup string).
            if '%i' in response_str:
                row -= 1
                col -= 1
            return row, col

        # We chose to return an illegal value rather than an exception,
        # favoring that users author function filters, such as max(0, y),
        # rather than crowbarring such logic into an exception handler.
        return -1, -1

    def get_fgcolor(self, timeout: Optional[float] = None) -> Tuple[int, int, int]:
        """
        Return tuple (r, g, b) of foreground color.

        :arg float timeout: Return after time elapsed in seconds with value ``(-1, -1, -1)``
            indicating that the remote end did not respond.
        :rtype: tuple
        :returns: foreground color as tuple in form of ``(r, g, b)``.  When a timeout is specified,
            always ensure the return value is checked for ``(-1, -1, -1)``.

        The foreground color is determined by emitting an `OSC 10 color query
        <https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Operating-System-Commands>`_.
        """
        match = self._query_response('\x1b]10;?\x07', _RE_GET_FGCOLOR_RESPONSE, timeout)

        return tuple(int(val, 16) for val in match.groups()) if match else (-1, -1, -1)

    def get_bgcolor(self, timeout: Optional[float] = None) -> Tuple[int, int, int]:
        """
        Return tuple (r, g, b) of background color.

        :arg float timeout: Return after time elapsed in seconds with value ``(-1, -1, -1)``
            indicating that the remote end did not respond.
        :rtype: tuple
        :returns: background color as tuple in form of ``(r, g, b)``.  When a timeout is specified,
            always ensure the return value is checked for ``(-1, -1, -1)``.

        The background color is determined by emitting an `OSC 11 color query
        <https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Operating-System-Commands>`_.
        """
        match = self._query_response('\x1b]11;?\x07', _RE_GET_BGCOLOR_RESPONSE, timeout)

        return tuple(int(val, 16) for val in match.groups()) if match else (-1, -1, -1)

    def _dec_mode_set_enabled(self, *modes: Union[int, DecPrivateMode]) -> None:
        """
        Enable one or more DEC Private Modes (DECSET).

        :arg int | DecPrivateMode modes: One or more DEC Private Modes to enable

        Emits the DECSET sequence to the attached stream as a side-effect, to
        enable the specified modes, and cache their known state as 'SET'
        (enabled) for subsequent :meth:`get_dec_mode` queries.

        It is suggested to use the context manager, :meth:`dec_modes_enabled`.
        Otherwise, an application should also evaluate the :meth:`get_dec_mode`
        response to conditionally only call this method when
        :meth:`DecModeResponse.is_supported` is True for the given mode, and to
        conditionally call :meth:`_dec_mode_set_disabled` to return terminal to
        its prior state in a try/finally clause.
        """
        # Extract mode numbers
        mode_numbers = []
        for arg_pos, mode in enumerate(modes):
            if isinstance(mode, DecPrivateMode):
                mode_num = mode.value
            elif isinstance(mode, int):
                mode_num = mode
            else:
                raise TypeError("Invalid mode argument number {0}, got {1!r}, "
                                "DecPrivateMode or int expected".format(arg_pos, mode))
            mode_numbers.append(mode_num)

        if not self.does_styling or not mode_numbers:
            return

        sequence = '\x1b[?{0}h'.format(';'.join(str(val) for val in mode_numbers))
        self.stream.write(sequence)
        self.stream.flush()

        # Update cache for set (enabled) modes
        for mode_num in mode_numbers:
            self._dec_mode_cache[mode_num] = DecModeResponse.SET

    def _dec_mode_set_disabled(self, *modes: Union[int, DecPrivateMode]) -> None:
        """
        Disable one or more DEC Private Modes (DECRST).

        :arg int | DecPrivateMode modes: One or more DEC Private Modes to disable

        Emits the DECRST sequence to the attached stream as a side-effect, to
        enable the specified modes, and cache their known state as 'RESET'
        (disabled) for subsequent :meth:`get_dec_mode` queries.

        It is suggested to use the context manager, :meth:`dec_modes_disabled`.
        Otherwise, an application should also evaluate the :meth:`get_dec_mode`
        response to codec_modes_enablednditionally only call this method when
        :meth:`DecModeResponse.is_supported` is True for the given mode, and to
        conditionally call :meth:`_dec_mode_set_enabled` to return terminal to
        its prior state in a try/finally clause.
        """
        # Extract mode numbers
        mode_numbers = []
        for arg_pos, mode in enumerate(modes):
            if isinstance(mode, DecPrivateMode):
                mode_num = mode.value
            elif isinstance(mode, int):
                mode_num = mode
            else:
                raise TypeError("Invalid mode argument number {0}, got {1!r}, "
                                "DecPrivateMode or int expected".format(arg_pos, mode))
            mode_numbers.append(mode_num)

        if not self.does_styling or not modes:
            return

        sequence = '\x1b[?{0}l'.format(';'.join(str(val) for val in mode_numbers))
        self.stream.write(sequence)
        self.stream.flush()

        # Update cache for reset (disabled) modes
        for mode_num in mode_numbers:
            self._dec_mode_cache[mode_num] = DecModeResponse.RESET

    def get_dec_mode(self, mode: Union[int, DecPrivateMode],
                     timeout: Optional[float] = None, force: bool = False) -> DecModeResponse:
        """
        Query the state of a DEC Private Mode (DECRQM).

        Sends a DECRQM query to the terminal and returns a
        :class:`DecModeResponse` instance. Use the helper methods,
        :meth:`DecModeResponse.is_supported`,
        :meth:`DecModeResponse.is_enabled`, etc. to interpret the result.

        When :attr:`does_styling` or :attr:`is_a_tty` is False, no sequences are
        transmitted or response awaited, and the :class:`DecModeResponse` value
        returned is always :attr:`DecModeResponse.NOT_QUERIED`.

        In some cases a ``timeout`` value should be set, as it is possible for a
        terminal that succeeds :attr:`does_styling` and :attr:`is_a_tty` to fail
        to respond to DEC Private Modes, such as in a CI Build Service or other
        "dumb" terminal, even a few popular modern ones such as Konsole.

        If a DEC Private mode query fails to respond within the ``timeout``
        specified, the :class:`DecModeResponse` value returned is
        :attr:`DecModeResponse.NO_RESPONSE`. If this was the first DEC Private
        mode query, all subsequent queries return a :class:`DecModeResponse`
        value of :attr:`DecModeResponse.NOT_QUERIED` unless ``force=True`` is
        set.

        **Repeat queries return the (cached) known state immediately** without
        re-inquiry unless ``force=True``.  Although there are special cases
        where a user may re-configure their terminal settings after the state
        was requested by an application, the application is generally restarted
        to recognize the new settings rather than to repeatidly re-inquire about
        their latest value!

        :arg mode: DEC Private Mode to query
        :type mode: DecPrivateMode | int
        :arg float timeout: Timeout in seconds to await terminal response
        :arg bool force: Force active terminal inquery in all cases
        :rtype: DecModeResponse
        :returns: DecModeResponse instance
        :raises TypeError: If mode is not DecPrivateMode or int

        .. code-block:: python

            term = Terminal()

            # Query synchronized output support
            response = term.get_dec_mode(DecPrivateMode.SYNCHRONIZED_OUTPUT)
            if response.is_supported():
                print("Synchronized output is available")
        """
        # pylint: disable=too-many-return-statements
        if not isinstance(mode, (int, DecPrivateMode)):
            raise TypeError("Invalid mode argument, got {0!r}, "
                            "DecPrivateMode or int expected".format(mode))

        if not self.does_styling or not self.is_a_tty:
            # no query is ever done for terminals where does_styling is False
            return DecModeResponse(mode, DecModeResponse.NOT_QUERIED)

        if self._dec_first_query_failed and not force:
            # When the first query is not responded, we can safely assume all
            # subsequent inqueries will be ignored
            return DecModeResponse(mode, DecModeResponse.NOT_QUERIED)

        # Always return the cached response when available unless force=True
        if int(mode) in self._dec_mode_cache and not force:
            cached_value = self._dec_mode_cache[int(mode)]
            return DecModeResponse(mode, cached_value)

        # Build and send query sequence and expected response pattern
        query = '\x1b[?{0:d}$p'.format(int(mode))
        response_pattern = re.compile('\x1b\\[\\?{0:d};([0-4])\\$y'.format(int(mode)))

        match = self._query_response(query, response_pattern, timeout)

        # pylint issues with _dec_first_query_failed and _dec_any_query_succeeded
        # ignored, pylint: disable=attribute-defined-outside-init

        # invalid or no response (timeout)
        if match is None:
            if not self._dec_any_query_succeeded:
                # This is the first-ever query and it failed! This query returns
                # NO_RESPONSE to indicate the timeout, subsequent queries will
                # return NOT_QUERIED.
                self._dec_first_query_failed = True
                return DecModeResponse(mode, DecModeResponse.NO_RESPONSE)
            # Rather unusual, we've previously had success with get_dec_mode,
            # but no response was found in this instance -- presumably the
            # remote end is disconnected or stalled, indicated by NO_RESPONSE,
            # or otherwise had some corruption in this specific response string.
            return DecModeResponse(mode, DecModeResponse.NO_RESPONSE)

        # parse, cache, and return the response value
        response_value = int(match.group(1))
        self._dec_mode_cache[int(mode)] = response_value
        self._dec_any_query_succeeded = True
        return DecModeResponse(mode, response_value)

    def get_kitty_keyboard_state(self, timeout: Optional[float] = None,
                                 force: bool = False) -> Optional[KittyKeyboardProtocol]:
        """
        Query the current Kitty keyboard protocol flags.

        Sends a Kitty keyboard protocol query to the terminal and returns a
        :class:`KittyKeyboardProtocol` instance with the current flags. This
        method is not normally used directly, rather it is used by the
        :meth:`enable_kitty_keyboard` context manager on entrance to discover
        and restore the previous state on exit.

        When :attr:`does_styling` or :attr:`is_a_tty` is False, no sequences are
        transmitted or response awaited, and ``None`` is returned.

        In many cases a ``timeout`` value of about ``1.0`` should be set, as it
        is possible for a terminal that succeeds :attr:`does_styling` and
        :attr:`is_a_tty` to fail to respond to either of the Kitty keyboard
        protocol or device attribute request query, such as in a CI Build
        Service, "dumb", even modern terminals like Konsole. The timeout value
        should approximate the value of the maximum round-trip time, maybe 1 second.

        If a Kitty keyboard protocol query fails to respond within the ``timeout``
        specified, ``None`` is returned. If this was the first Kitty keyboard
        protocol query, all subsequent queries return ``None`` unless ``force=True`` is
        set.

        **No state caching is performed** - each call re-queries the terminal unless
        the first query previously failed (sticky failure) and ``force=False``.

        This method uses a boundary detection approach on the first query to quickly
        determine terminal capabilities by sending both Kitty keyboard and Device
        Attributes (DA1) queries simultaneously, as suggested by Kitty,
        https://sw.kovidgoyal.net/kitty/keyboard-protocol/#detection-of-support-for-this-protocol
        By sending both queries together and checking which responses are
        received, we can quickly infer support without multiple round trips.
        Note that Kitty *does not answer* to primary device attributes request
        despite making this very recommendation!

        > An application can query the terminal for support of this protocol by
        > sending the escape code querying for the current progressive
        > enhancement status followed by request for the primary device
        > attributes. If an answer for the device attributes is received without
        > getting back an answer for the progressive enhancement the terminal
        > does not support this protocol.

        :arg float timeout: Timeout in seconds to await terminal response
        :arg bool force: Force active terminal inquiry in all cases
        :rtype: KittyKeyboardProtocol or None
        :returns: KittyKeyboardProtocol instance with current flags, or None if unsupported/timeout
        """
        # pylint: disable=too-many-return-statements
        if not self.does_styling or not self.is_a_tty:
            # no query is ever done for terminals where does_styling or is_a_tty is False
            return None

        if self._kitty_kb_first_query_failed and not force:
            # When the first query is not responded, we can safely assume all
            # subsequent inquiries will be ignored
            return None

        # ignore pylint problem with '_kitty_kb_first_query_attempted', because this
        # variable is defined outside of init (__init__dec_private_modes)
        # pylint: disable=attribute-defined-outside-init

        # Use boundary approach on first query attempt (when not previously
        # attempted and not forced)
        if not self._kitty_kb_first_query_attempted and not force:
            # Mark that we've attempted the first query
            self._kitty_kb_first_query_attempted = True

            # Send both Kitty and DA queries together for boundary detection
            # This allows us to quickly determine which protocols are supported:
            # - Kitty terminal: responds to Kitty query but not DA1
            # - xterm-like: responds to both Kitty and DA1
            # - Konsole-like: responds to DA1 but not Kitty
            # - Dumb terminals: respond to neither
            boundary_query = '\x1b[?u\x1b[c'

            # Use a simple pattern that captures the full response
            boundary_pattern = re.compile('(.+)', re.DOTALL)

            match = self._query_response(boundary_query, boundary_pattern, timeout)

            # invalid or no response (timeout)
            if match is None:
                # Set sticky failure flag on first timeout
                self._kitty_kb_first_query_failed = True
                return None

            response_text = match.group(1)

            # Check for Kitty keyboard response first
            kitty_pattern = re.compile(r'\x1b\[\?([0-9]+)u')
            kitty_match = kitty_pattern.search(response_text)

            if kitty_match:
                # Kitty response found - parse and return flags
                # (doesn't matter if DA1 also responded or not)
                flags_value = int(kitty_match.group(1))
                return KittyKeyboardProtocol(flags_value)

            # Check for DA1 response
            da1_pattern = re.compile(r'\x1b\[\?([0-9]+)(?:;[0-9]+)*c')
            da1_match = da1_pattern.search(response_text)

            if da1_match:
                # Only DA1 response found, no Kitty support
                self._kitty_kb_first_query_failed = True
                return None

            # Neither response found - no support
            self._kitty_kb_first_query_failed = True
            return None

        # Subsequent calls or forced calls use the standard single-query approach
        query = '\x1b[?u'
        response_pattern = re.compile('\x1b\\[\\?([0-9]+)u')

        match = self._query_response(query, response_pattern, timeout)

        # invalid or no response (timeout)
        if match is None:
            # Set sticky failure flag on timeout (though this should be rare for subsequent calls)
            self._kitty_kb_first_query_failed = True
            return None

        # parse and return the response value (no caching)
        flags_value = int(match.group(1))
        return KittyKeyboardProtocol(flags_value)

    def get_device_attributes(self, timeout: Optional[float] = None,
                              force: bool = True) -> Optional[DeviceAttribute]:
        """
        Query the terminal's Device Attributes (DA1).

        Sends a Device Attributes query to the terminal and returns a
        :class:`DeviceAttribute` instance with the terminal's capabilities.

        If a Device Attributes query fails to respond within the ``timeout``
        specified, ``None`` is returned.

        **Successful responses are cached indefinitely** unless ``force=True`` is
        specified. Unlike other query methods, there is no sticky failure mechanism -
        each failed query can be retried.

        :arg float timeout: Timeout in seconds to await terminal response
        :arg bool force: Force active terminal inquiry even if cached result exists
        :rtype: DeviceAttribute or None
        :returns: DeviceAttribute instance with terminal capabilities, or None
            if unsupported/timeout

        .. code-block:: python

            term = Terminal()

            # Query device attributes
            da = term.get_device_attributes()
            if da is not None:
                print(f"Service class: {da.service_class}")
                print(f"Supports sixel: {da.supports_sixel}")
                print(f"Extensions: {sorted(da.extensions)}")
        """
        # Return cached result unless force=True
        if self._device_attributes_cache is not None and not force:
            return self._device_attributes_cache

        # Build and send query sequence and expected response pattern
        query = '\x1b[c'

        match = self._query_response(query, _RE_GET_DEVICE_ATTR_RESPONSE, timeout)

        # invalid or no response (timeout)
        if match is None:
            return None

        # parse, cache, and return the response
        # pylint: disable=attribute-defined-outside-init
        self._device_attributes_cache = DeviceAttribute.from_match(match)
        return self._device_attributes_cache

    def does_sixel(self, timeout: Optional[float] = None) -> bool:
        """
        Return whether the terminal supports sixel graphics.

        This method queries the terminal's Device Attributes (DA1) to determine
        if sixel graphics are supported (extension 4). The result is cached
        after the first successful query.

        If the Device Attributes query fails or times out, ``False`` is returned.

        :arg float timeout: Timeout in seconds to await terminal response
        :rtype: bool
        :returns: True if sixel graphics are supported, False otherwise

        .. code-block:: python

            term = Terminal()

            if term.does_sixel():
                print("Terminal supports sixel graphics")
            else:
                print("Terminal does not support sixel graphics")
        """
        # Get device attributes, using cache if available (force=False)
        da = self.get_device_attributes(timeout=timeout, force=False)
        return da.supports_sixel if da is not None else False

    @contextlib.contextmanager
    def dec_modes_enabled(self, *modes: Union[int, DecPrivateMode],
                          timeout: Optional[float] = None) -> Generator[None, None, None]:
        """
        Context manager for temporarily enabling DEC Private Modes.

        On entry, queries each mode's current state using get_dec_mode().
        For modes that are supported but currently disabled, enables them
        and tracks them for restoration. On exit, disables all modes that
        were enabled by this context manager, restoring original state.
        Unsupported modes are silently ignored.

        :arg modes: One or more DEC Private Mode numbers or enum members
        :arg float timeout: Timeout in seconds for get_dec_mode calls
        :raises TypeError: If mode is not DecPrivateMode or int

        .. code-block:: python

            term = Terminal()

            # Enable synchronized output temporarily
            with term.dec_modes_enabled(DecPrivateMode.SYNCHRONIZED_OUTPUT):
                # All output will be atomic
                print("Frame 1")
                print("Frame 2")
        """
        # Track modes enabled ('SET") to be re-enabled ('RESET') after the yield
        enabled_modes = []

        # Query current state of each mode and build enable list
        for arg_pos, mode in enumerate(modes):
            if isinstance(mode, DecPrivateMode):
                mode_num = mode.value
            elif isinstance(mode, int):
                mode_num = mode
            else:
                raise TypeError("Invalid mode argument number {0}, got {1!r}, "
                                "DecPrivateMode or int expected".format(arg_pos, mode))

            response = self.get_dec_mode(mode_num, timeout=timeout)
            if response.is_supported() and not response.is_enabled():
                enabled_modes.append(mode_num)

        self._dec_mode_set_enabled(*enabled_modes)
        try:
            yield
        finally:
            self._dec_mode_set_disabled(*enabled_modes)

    @contextlib.contextmanager
    def dec_modes_disabled(self, *modes: Union[int, DecPrivateMode],
                           timeout: Optional[float] = None) -> Generator[None, None, None]:
        """
        Context manager for temporarily disabling DEC Private Modes.

        Uses the same logic as dec_modes_enabled but inverted: disables
        supported modes that are currently enabled on entry, then restores
        them on exit.

        :arg modes: One or more DEC Private Mode numbers or enum members
        :arg float timeout: Timeout in seconds for get_dec_mode calls
        :raises TypeError: If mode is not DecPrivateMode or int
        """
        # Track modes disabled ('RESET") to be re-enabled ('SET') after the yield
        disabled_modes = []

        # Query current state of each mode and build disable list
        for arg_pos, mode in enumerate(modes):
            if isinstance(mode, DecPrivateMode):
                mode_num = mode.value
            elif isinstance(mode, int):
                mode_num = mode
            else:
                raise TypeError("Invalid mode argument number {0}, got {1!r}, "
                                "DecPrivateMode or int expected".format(arg_pos, mode))

            response = self.get_dec_mode(mode_num, timeout=timeout)
            if response.is_supported() and response.is_enabled():
                disabled_modes.append(mode_num)

        self._dec_mode_set_disabled(*disabled_modes)
        try:
            yield
        finally:
            self._dec_mode_set_enabled(*disabled_modes)

    @contextlib.contextmanager
    def fullscreen(self) -> Generator[None, None, None]:
        """
        Context manager that switches to secondary screen, restoring on exit.

        Under the hood, this switches between the primary screen buffer and
        the secondary one. The primary one is saved on entry and restored on
        exit.  Likewise, the secondary contents are also stable and are
        faithfully restored on the next entry::

            with term.fullscreen():
                main()

        .. note:: There is only one primary and one secondary screen buffer.
           :meth:`fullscreen` calls cannot be nested, only one should be
           entered at a time.
        """
        self.stream.write(self.enter_fullscreen)
        self.stream.flush()
        try:
            yield
        finally:
            self.stream.write(self.exit_fullscreen)
            self.stream.flush()

    @contextlib.contextmanager
    def hidden_cursor(self) -> Generator[None, None, None]:
        """
        Context manager that hides the cursor, setting visibility on exit.

            with term.hidden_cursor():
                main()

        .. note:: :meth:`hidden_cursor` calls cannot be nested: only one
            should be entered at a time.
        """
        self.stream.write(self.hide_cursor)
        self.stream.flush()
        try:
            yield
        finally:
            self.stream.write(self.normal_cursor)
            self.stream.flush()

    def move_xy(self, x: int, y: int) -> str:
        """
        A callable string that moves the cursor to the given ``(x, y)`` screen coordinates.

        :arg int x: horizontal position, from left, *0*, to right edge of screen, *self.width - 1*.
        :arg int y: vertical position, from top, *0*, to bottom of screen, *self.height - 1*.
        :rtype: ParameterizingString
        :returns: Callable string that moves the cursor to the given coordinates
        """
        # this is just a convenience alias to the built-in, but hidden 'move'
        # attribute -- we encourage folks to use only (x, y) positional
        # arguments, or, if they must use (y, x), then use the 'move_yx'
        # alias.
        return self.move(y, x)

    def move_yx(self, y: int, x: int) -> str:
        """
        A callable string that moves the cursor to the given ``(y, x)`` screen coordinates.

        :arg int y: vertical position, from top, *0*, to bottom of screen, *self.height - 1*.
        :arg int x: horizontal position, from left, *0*, to right edge of screen, *self.width - 1*.
        :rtype: ParameterizingString
        :returns: Callable string that moves the cursor to the given coordinates
        """
        return self.move(y, x)

    @property
    def move_left(self) -> FormattingOtherString:
        """Move cursor 1 cells to the left, or callable string for n>1 cells."""
        return FormattingOtherString(self.cub1, ParameterizingString(self.cub))

    @property
    def move_right(self) -> FormattingOtherString:
        """Move cursor 1 or more cells to the right, or callable string for n>1 cells."""
        return FormattingOtherString(self.cuf1, ParameterizingString(self.cuf))

    @property
    def move_up(self) -> FormattingOtherString:
        """Move cursor 1 or more cells upwards, or callable string for n>1 cells."""
        return FormattingOtherString(self.cuu1, ParameterizingString(self.cuu))

    @property
    def move_down(self) -> FormattingOtherString:
        """Move cursor 1 or more cells downwards, or callable string for n>1 cells."""
        return FormattingOtherString(self.cud1, ParameterizingString(self.cud))

    @property
    def color(self) -> Union[NullCallableString, ParameterizingString]:
        """
        A callable string that sets the foreground color.

        :rtype: ParameterizingString

        The capability is unparameterized until called and passed a number, at which point it
        returns another string which represents a specific color change. This second string can
        further be called to color a piece of text and set everything back to normal afterward.

        This should not be used directly, but rather a specific color by name or
        :meth:`~.Terminal.color_rgb` value.
        """
        if self.does_styling:
            return ParameterizingString(self._foreground_color, self.normal, 'color')

        return NullCallableString()

    def color_rgb(self, red: int, green: int, blue: int) -> FormattingString:
        """
        Provides callable formatting string to set foreground color to the specified RGB color.

        :arg int red: RGB value of Red.
        :arg int green: RGB value of Green.
        :arg int blue: RGB value of Blue.
        :rtype: FormattingString
        :returns: Callable string that sets the foreground color

        If the terminal does not support RGB color, the nearest supported
        color will be determined using :py:attr:`color_distance_algorithm`.
        """
        if self.number_of_colors == 1 << 24:
            # "truecolor" 24-bit
            fmt_attr = f'\x1b[38;2;{red};{green};{blue}m'
            return FormattingString(fmt_attr, self.normal)

        # color by approximation to 256 or 16-color terminals
        color_idx = self.rgb_downconvert(red, green, blue)
        return FormattingString(self._foreground_color(color_idx), self.normal)

    @property
    def on_color(self) -> Union[NullCallableString, ParameterizingString]:
        """
        A callable capability that sets the background color.

        :rtype: ParameterizingString
        """
        if self.does_styling:
            return ParameterizingString(self._background_color, self.normal, 'on_color')

        return NullCallableString()

    def on_color_rgb(self, red: int, green: int, blue: int) -> FormattingString:
        """
        Provides callable formatting string to set background color to the specified RGB color.

        :arg int red: RGB value of Red.
        :arg int green: RGB value of Green.
        :arg int blue: RGB value of Blue.
        :rtype: FormattingString
        :returns: Callable string that sets the foreground color

        If the terminal does not support RGB color, the nearest supported
        color will be determined using :py:attr:`color_distance_algorithm`.
        """
        if self.number_of_colors == 1 << 24:
            fmt_attr = f'\x1b[48;2;{red};{green};{blue}m'
            return FormattingString(fmt_attr, self.normal)

        color_idx = self.rgb_downconvert(red, green, blue)
        return FormattingString(self._background_color(color_idx), self.normal)

    def formatter(self, value: str) -> Union[NullCallableString, FormattingString]:
        """
        Provides callable formatting string to set color and other text formatting options.

        :arg str value: Sugary, ordinary, or compound formatted terminal capability,
            such as "red_on_white", "normal", "red", or "bold_on_black".
        :rtype: :class:`FormattingString` or :class:`NullCallableString`
        :returns: Callable string that sets color and other text formatting options

        Calling ``term.formatter('bold_on_red')`` is equivalent to ``term.bold_on_red``, but a
        string that is not a valid text formatter will return a :class:`NullCallableString`.
        This is intended to allow validation of text formatters without the possibility of
        inadvertently returning another terminal capability.
        """
        formatters = split_compound(value)
        if all((fmt in COLORS or fmt in COMPOUNDABLES) for fmt in formatters):
            return getattr(self, value)

        return NullCallableString()

    def rgb_downconvert(self, red: int, green: int, blue: int) -> int:
        """
        Translate an RGB color to a color code of the terminal's color depth.

        This method is only be used to downconvert for terminals of 256 or fewer colors.

        :arg int red: RGB value of Red (0-255).
        :arg int green: RGB value of Green (0-255).
        :arg int blue: RGB value of Blue (0-255).
        :rtype: int
        :returns: Color code of downconverted RGB color
        """
        # pylint: disable=too-many-locals

        if self.number_of_colors == 0:
            # bit of a waste to downconvert to no color at all, the final
            # formatting string will be empty, we play along with color #7
            return 7

        target_rgb = (red, green, blue)
        fn_distance = COLOR_DISTANCE_ALGORITHMS[self.color_distance_algorithm]

        if self.number_of_colors < 256:  # 8 or 16 colors
            # because there just are not very many colors, we can use a color distance
            # algorithm to measure all of 8 or 16 colors, selecting the nearest match.
            best_idx = 7
            best_distance = float('inf')
            for idx in range(min(self.number_of_colors, 16)):
                distance = fn_distance(RGB_256TABLE[idx], target_rgb)
                if distance < best_distance:
                    best_distance = distance
                    best_idx = idx
            return best_idx
        # For 256-color terminals, use *only* cube (16-231) and grayscale
        # (232-255) color matches, avoid ANSI colors 0-15 altogether, to prevent
        # interference from user themes, and its fastest for our purpose,
        # anyway! We chose the nearest distance of either color.
        cube_idx, cube_rgb = xterm256color_from_rgb(red, green, blue)
        gray_idx, gray_rgb = xterm256gray_from_rgb(red, green, blue)
        cube_distance = fn_distance(cube_rgb, target_rgb)
        gray_distance = fn_distance(gray_rgb, target_rgb)
        return cube_idx if cube_distance <= gray_distance else gray_idx

    @property
    def normal(self) -> str:
        """
        A capability that resets all video attributes.

        :rtype: str

        ``normal`` is an alias for ``sgr0`` or ``exit_attribute_mode``. Any
        styling attributes previously applied, such as foreground or
        background colors, reverse video, or bold are reset to defaults.
        """
        if self._normal:
            return self._normal
        self._normal = resolve_capability(self, 'normal')
        return self._normal

    def link(self, url: str, text: str, url_id: str = '') -> str:
        """
        Display ``text`` that when touched or clicked, navigates to ``url``.

        Optional ``url_id`` may be specified, so that non-adjacent cells can reference a single
        target, all cells painted with the same "id" will highlight on hover, rather than any
        individual one, as described in "Hovering and underlining the id parameter" of gist
        https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda.

        :param str url: Hyperlink URL.
        :param str text: Clickable text.
        :param str url_id: Optional 'id'.
        :rtype: str
        :returns: String of ``text`` as a hyperlink to ``url``.
        """
        assert len(url) < 2000, (len(url), url)
        if url_id:
            assert len(str(url_id)) < 250, (len(str(url_id)), url_id)
            params = f'id={url_id}'
        else:
            params = ''
        if not self.does_styling:
            return text
        return f'\x1b]8;{params};{url}\x1b\\{text}\x1b]8;;\x1b\\'

    @property
    def stream(self) -> IO[str]:
        """
        Read-only property: stream the terminal outputs to.

        This is a convenience attribute. It is used internally for implied
        writes performed by context managers :meth:`~.hidden_cursor`,
        :meth:`~.fullscreen`, :meth:`~.location`, and :meth:`~.keypad`.
        """
        return self._stream

    @property
    def number_of_colors(self) -> int:
        """
        Number of colors supported by terminal.

        Common return values are 0, 8, 16, 256, or 1 << 24.

        This may be used to test whether the terminal supports colors, and at what depth, if that's
        a concern.

        If this property is assigned a value of 88, the value 16 will be saved. This is due to the
        the rarity of 88 color support and the inconsistency of behavior between implementations.

        Assigning this property to a value other than 0, 4, 8, 16, 88, 256, or 1 << 24 will raise an
        :py:exc:`AssertionError`.
        """
        return self._number_of_colors

    @number_of_colors.setter
    def number_of_colors(self, value: int) -> None:
        assert value in (0, 4, 8, 16, 88, 256, 1 << 24)
        # Because 88 colors is rare and we can't guarantee consistent behavior,
        # when 88 colors is detected, it is treated as 16 colors
        self._number_of_colors = 16 if value == 88 else value
        self.__clear_color_capabilities()

    @property
    def color_distance_algorithm(self) -> str:
        """
        Color distance algorithm used by :meth:`rgb_downconvert`.

        The slowest, but most accurate, 'cie2000', is default. Other available options are 'rgb',
        'rgb-weighted', 'cie76', and 'cie94'.
        """
        return self._color_distance_algorithm

    @color_distance_algorithm.setter
    def color_distance_algorithm(self, value: str) -> None:
        assert value in COLOR_DISTANCE_ALGORITHMS
        self._color_distance_algorithm = value
        self.__clear_color_capabilities()

    @property
    def _foreground_color(self) -> Union[NullCallableString, ParameterizingString]:
        """
        Convenience capability to support :attr:`~.on_color`.

        Prefers returning sequence for capability ``setaf``, "Set foreground color to #1, using ANSI
        escape". If the given terminal does not support such sequence, fallback to returning
        attribute ``setf``, "Set foreground color #1".
        """
        return self.setaf or self.setf

    @property
    def _background_color(self) -> Union[NullCallableString, ParameterizingString]:
        """
        Convenience capability to support :attr:`~.on_color`.

        Prefers returning sequence for capability ``setab``, "Set background color to #1, using ANSI
        escape". If the given terminal does not support such sequence, fallback to returning
        attribute ``setb``, "Set background color #1".
        """
        return self.setab or self.setb

    def ljust(self, text: str, width: Optional[SupportsIndex] = None, fillchar: str = ' ') -> str:
        """
        Left-align ``text``, which may contain terminal sequences.

        :arg str text: String to be aligned
        :arg int width: Total width to fill with aligned text. If
            unspecified, the whole width of the terminal is filled.
        :arg str fillchar: String for padding the right of ``text``
        :rtype: str
        :returns: String of ``text``, left-aligned by ``width``.
        """
        # Left justification is different from left alignment, but we continue
        # the vocabulary error of the str method for polymorphism.
        if width is None:
            width = self.width
        return Sequence(text, self).ljust(width, fillchar)

    def rjust(self, text: str, width: Optional[SupportsIndex] = None, fillchar: str = ' ') -> str:
        """
        Right-align ``text``, which may contain terminal sequences.

        :arg str text: String to be aligned
        :arg int width: Total width to fill with aligned text. If
            unspecified, the whole width of the terminal is used.
        :arg str fillchar: String for padding the left of ``text``
        :rtype: str
        :returns: String of ``text``, right-aligned by ``width``.
        """
        if width is None:
            width = self.width
        return Sequence(text, self).rjust(width, fillchar)

    def center(self, text: str, width: Optional[SupportsIndex] = None, fillchar: str = ' ') -> str:
        """
        Center ``text``, which may contain terminal sequences.

        :arg str text: String to be centered
        :arg int width: Total width in which to center text. If
            unspecified, the whole width of the terminal is used.
        :arg str fillchar: String for padding the left and right of ``text``
        :rtype: str
        :returns: String of ``text``, centered by ``width``
        """
        if width is None:
            width = self.width
        return Sequence(text, self).center(width, fillchar)

    def truncate(self, text: str, width: Optional[SupportsIndex] = None) -> str:
        r"""
        Truncate ``text`` to maximum ``width`` printable characters, retaining terminal sequences.

        :arg str text: Text to truncate
        :arg int width: The maximum width to truncate it to
        :rtype: str
        :returns: ``text`` truncated to at most ``width`` printable characters

        >>> term.truncate('xyz\x1b[0;3m', 2)
        'xy\x1b[0;3m'
        """
        if width is None:
            width = self.width
        return Sequence(text, self).truncate(width)

    def length(self, text: str) -> int:
        """
        Return printable length of a string containing sequences.

        :arg str text: String to measure. May contain terminal sequences.
        :rtype: int
        :returns: The number of terminal character cells the string will occupy
            when printed

        Wide characters that consume 2 character cells are supported:

        >>> term = Terminal()
        >>> term.length(term.clear + term.red('コンニチハ'))
        10

        .. note:: Sequences such as 'clear', which is considered as a
            "movement sequence" because it would move the cursor to
            (y, x)(0, 0), are evaluated as a printable length of
            *0*.
        """
        return Sequence(text, self).length()

    def strip(self, text: str, chars: Optional[str] = None) -> str:
        r"""
        Return ``text`` without sequences and leading or trailing whitespace.

        :rtype: str
        :returns: Text with leading and trailing whitespace removed

        >>> term.strip(' \x1b[0;3m xyz ')
        'xyz'
        """
        return Sequence(text, self).strip(chars)

    def rstrip(self, text: str, chars: Optional[str] = None) -> str:
        r"""
        Return ``text`` without terminal sequences or trailing whitespace.

        :rtype: str
        :returns: Text with terminal sequences and trailing whitespace removed

        >>> term.rstrip(' \x1b[0;3m xyz ')
        '  xyz'
        """
        return Sequence(text, self).rstrip(chars)

    def lstrip(self, text: str, chars: Optional[str] = None) -> str:
        r"""
        Return ``text`` without terminal sequences or leading whitespace.

        :rtype: str
        :returns: Text with terminal sequences and leading whitespace removed

        >>> term.lstrip(' \x1b[0;3m xyz ')
        'xyz '
        """
        return Sequence(text, self).lstrip(chars)

    def strip_seqs(self, text: str) -> str:
        r"""
        Return ``text`` stripped of only its terminal sequences.

        :rtype: str
        :returns: Text with terminal sequences removed

        >>> term.strip_seqs('\x1b[0;3mxyz')
        'xyz'
        >>> term.strip_seqs(term.cuf(5) + term.red('test'))
        '     test'

        .. note:: Non-destructive sequences that adjust horizontal distance
            (such as ``\b`` or ``term.cuf(5)``) are replaced by destructive
            space or erasing.
        """
        return Sequence(text, self).strip_seqs()

    def split_seqs(self, text: str, maxsplit: int = 0) -> List[str]:
        r"""
        Return ``text`` split by individual character elements and sequences.

        :arg str text: String containing sequences
        :arg int maxsplit: When maxsplit is nonzero, at most maxsplit splits
            occur, and the remainder of the string is returned as the final element
            of the list (same meaning is argument for :func:`re.split`).
        :rtype: list[str]
        :returns: List of sequences and individual characters

        >>> term.split_seqs(term.underline('xyz'))
        ['\x1b[4m', 'x', 'y', 'z', '\x1b(B', '\x1b[m']

        >>> term.split_seqs(term.underline('xyz'), 1)
        ['\x1b[4m', r'xyz\x1b(B\x1b[m']
        """
        pattern = self._caps_unnamed_any
        result = []
        for idx, match in enumerate(re.finditer(pattern, text)):
            result.append(match.group())
            if maxsplit and idx == maxsplit:
                remaining = text[match.end():]
                if remaining:
                    result[-1] += remaining
                break
        return result

    def wrap(self, text: str, width: Optional[int] = None, **kwargs: object) -> List[str]:
        r"""
        Text-wrap a string, returning a list of wrapped lines.

        :arg str text: Unlike :func:`textwrap.wrap`, ``text`` may contain
            terminal sequences, such as colors, bold, or underline. By
            default, tabs in ``text`` are expanded by
            :func:`string.expandtabs`.
        :arg int width: Unlike :func:`textwrap.wrap`, ``width`` will
            default to the width of the attached terminal.
        :arg \**kwargs: See :py:class:`textwrap.TextWrapper`
        :rtype: list
        :returns: List of wrapped lines

        See :class:`textwrap.TextWrapper` for keyword arguments that can
        customize wrapping behaviour.
        """
        width = self.width if width is None else width
        wrapper = SequenceTextWrapper(width=width, term=self, **kwargs)
        lines: List[str] = []
        for line in text.splitlines():
            lines.extend(iter(wrapper.wrap(line)) if line.strip() else ('',))

        return lines

    def getch(self, decoder: Optional[codecs.IncrementalDecoder] = None) -> str:
        """
        Read, decode, and return the next byte from the keyboard stream.

        :arg decoder: Optional decoder, used when parsing some types of escape sequences.
        :type decoder: codecs.IncrementalDecoder or None
        :rtype: unicode
        :returns: a single unicode character, or ``''`` if a multi-byte
            sequence has not yet been fully received.

        This method name and behavior mimics curses ``getch(void)``, and
        it supports :meth:`inkey`, reading only one byte from
        the keyboard string at a time. This method should always return
        without blocking if called after :meth:`kbhit` has returned True.

        Implementers of alternate input stream methods should override
        this method.
        """
        assert self._keyboard_fd is not None
        byte = os.read(self._keyboard_fd, 1)
        return (decoder or self._keyboard_decoder).decode(byte, final=False)

    def ungetch(self, text: str) -> None:
        """
        Buffer input data to be discovered by next call to :meth:`~.inkey`.

        :arg str text: String to be buffered as keyboard input.
        """
        self._keyboard_buf.extendleft(text)

    def kbhit(self, timeout: Optional[float] = None) -> bool:
        """
        Return whether a keypress has been detected on the keyboard.

        This method is used by :meth:`inkey` to determine if a byte may
        be read using :meth:`getch` without blocking.  The standard
        implementation simply uses the :func:`select.select` call on stdin.

        :arg float timeout: When ``timeout`` is 0, this call is
            non-blocking, otherwise blocking indefinitely until keypress
            is detected when None (default). When ``timeout`` is a
            positive number, returns after ``timeout`` seconds have
            elapsed (float).
        :rtype: bool
        :returns: True if a keypress is awaiting to be read on the keyboard
            attached to this terminal.  When input is not a terminal, False is
            always returned.
        """
        ready_r = [None, ]
        check_r = [self._keyboard_fd] if self._keyboard_fd is not None else []

        if HAS_TTY:
            ready_r, _, _ = select.select(check_r, [], [], timeout)
            # Ensure boolean return type - check_r equals ready_r means key is available
            if self._keyboard_fd is not None and check_r == ready_r:
                return True
        return False

    @contextlib.contextmanager
    def cbreak(self) -> Generator[None, None, None]:
        """
        Allow each keystroke to be read immediately after it is pressed.

        This is a context manager for :func:`tty.setcbreak`.

        This context manager activates 'rare' mode, the opposite of 'cooked'
        mode: On entry, :func:`tty.setcbreak` mode is activated disabling
        line-buffering of keyboard input and turning off automatic echo of
        input as output.

        .. note:: You must explicitly print any user input you would like
            displayed.  If you provide any kind of editing, you must handle
            backspace and other line-editing control functions in this mode
            as well!

        **Normally**, characters received from the keyboard cannot be read
        by Python until the *Return* key is pressed. Also known as *cooked* or
        *canonical input* mode, it allows the tty driver to provide
        line-editing before shuttling the input to your program and is the
        (implicit) default terminal mode set by most unix shells before
        executing programs.

        Technically, this context manager sets the :mod:`termios` attributes
        of the terminal attached to :obj:`sys.__stdin__`.

        .. note:: :func:`tty.setcbreak` sets ``VMIN = 1`` and ``VTIME = 0``,
            see http://www.unixwiz.net/techtips/termios-vmin-vtime.html
        """
        if HAS_TTY and self._keyboard_fd is not None:
            # Save current terminal mode:
            save_mode = termios.tcgetattr(self._keyboard_fd)
            save_line_buffered = self._line_buffered
            # pylint: disable-next=possibly-used-before-assignment
            tty.setcbreak(self._keyboard_fd, termios.TCSANOW)
            try:
                self._line_buffered = False
                yield
            finally:
                # Restore prior mode:
                termios.tcsetattr(self._keyboard_fd,
                                  termios.TCSAFLUSH,
                                  save_mode)
                self._line_buffered = save_line_buffered
        else:
            yield

    @contextlib.contextmanager
    def raw(self) -> Generator[None, None, None]:
        r"""
        A context manager for :func:`tty.setraw`.

        Although both :meth:`cbreak` and :meth:`raw` modes allow each keystroke
        to be read immediately after it is pressed, Raw mode disables
        processing of input and output by the terminal driver.

        In cbreak mode, special input characters such as ``^C`` or ``^S`` are
        interpreted by the terminal driver and excluded from the stdin stream.
        In raw mode these values are received by the :meth:`inkey` method.

        Because output processing is not done by the terminal driver, the
        newline ``'\n'`` is not enough, you must also print carriage return to
        ensure that the cursor is returned to the first column::

            with term.raw():
                print("printing in raw mode", end="\r\n")
        """
        if HAS_TTY and self._keyboard_fd is not None:
            # Save current terminal mode:
            save_mode = termios.tcgetattr(self._keyboard_fd)
            save_line_buffered = self._line_buffered
            tty.setraw(self._keyboard_fd, termios.TCSANOW)
            try:
                self._line_buffered = False
                yield
            finally:
                # Restore prior mode:
                termios.tcsetattr(self._keyboard_fd,
                                  termios.TCSAFLUSH,
                                  save_mode)
                self._line_buffered = save_line_buffered
        else:
            yield

    @contextlib.contextmanager
    def keypad(self) -> Generator[None, None, None]:
        r"""
        Context manager that enables directional keypad input.

        On entrying, this puts the terminal into "keyboard_transmit" mode by
        emitting the keypad_xmit (smkx) capability. On exit, it emits
        keypad_local (rmkx).

        On an IBM-PC keyboard with numeric keypad of terminal-type *xterm*,
        with numlock off, the lower-left diagonal key transmits sequence
        ``\\x1b[F``, translated to :class:`~.Terminal` attribute
        ``KEY_END``.

        However, upon entering :meth:`keypad`, ``\\x1b[OF`` is transmitted,
        translating to ``KEY_LL`` (lower-left key), allowing you to determine
        diagonal direction keys.
        """
        try:
            self.stream.write(self.smkx)
            self.stream.flush()
            yield
        finally:
            self.stream.write(self.rmkx)
            self.stream.flush()

    @contextlib.contextmanager
    def enable_kitty_keyboard(self, *, disambiguate: bool = True, report_events: bool = False,
                              report_alternates: bool = False, report_all_keys: bool = False,
                              report_text: bool = False, mode: int = 1,
                              timeout: Optional[float] = None,
                              force: bool = False) -> Generator[None, None, None]:
        """
        Context manager that enables Kitty keyboard protocol features.

        :arg bool disambiguate: Enable disambiguated escape codes (fixes issues
            with Esc vs sequences)
        :arg bool report_events: Report key repeat and release events
        :arg bool report_alternates: Report shifted and base layout keys for shortcuts
        :arg bool report_all_keys: Report all keys as escape codes (including text keys)
        :arg bool report_text: Report associated text with key events (requires report_all_keys)
        :arg int mode: Protocol mode (1=set/clear specified flags, 2=set only, 3=clear only)
        :arg float timeout: Timeout for querying current flags before setting new ones
        :arg bool force: Force sequences to be emitted even if timeout previously occurred

        Always queries current state before setting new flags and restores previous state on exit.

        Example::

            with term.enable_kitty_keyboard(disambiguate=True):
                # Now Alt+C won't conflict with Ctrl+C
                key = term.inkey()
                if key.alt and key.is_alt('c'):
                    print("Alt+C pressed")
        """
        if not self.does_styling:
            yield
            return

        # When not a real TTY (like StringIO), don't emit sequences unless force=True
        if not self.is_a_tty and not force:
            yield
            return

        # Check if timeout occurred before and force is not set
        if self._kitty_kb_first_query_failed and not force:
            yield
            return

        # Compute flags based on parameters
        flags = 0
        if disambiguate:
            flags |= 1
        if report_events:
            flags |= 2
        if report_alternates:
            flags |= 4
        if report_all_keys:
            flags |= 8
        if report_text:
            flags |= 16

        # Always query current flags before setting new ones
        previous_flags = self.get_kitty_keyboard_state(timeout=timeout, force=force)

        try:
            # Set new flags
            self.stream.write(f'\x1b[={flags};{mode}u')  # Set flags with specified mode
            self.stream.flush()
            yield

        finally:
            # Restore previous state
            if previous_flags is not None:
                # Restore to specific previous flags
                self.stream.write(f'\x1b[={previous_flags.value};1u')  # Mode 1 = set flags exactly
                self.stream.flush()

    @contextlib.contextmanager
    def modify_other_keys(self, level: int = 2) -> Generator[None, None, None]:
        """
        Context manager that enables xterm's modifyOtherKeys feature.

        :arg int level: ModifyOtherKeys level (0=disable, 1=enable for function
            keys, 2=enable for all)

        This enables modified keys like Ctrl+, and Ctrl+. to be distinguished from their
        unmodified counterparts. Level 2 provides the broadest support.

        Example::

            with term.modify_other_keys(level=2):
                key = term.inkey()
                if key.is_ctrl(','):
                    print("Ctrl+comma detected")
        """
        if not self.does_styling:
            yield
            return

        try:
            # Enable modifyOtherKeys at specified level
            self.stream.write(f'\x1b[>4;{level}m')
            self.stream.flush()

            yield

        finally:
            # Disable modifyOtherKeys
            self.stream.write('\x1b[>4;0m')
            self.stream.flush()

    def _is_known_input_prefix(self, text: str) -> bool:
        """
        Check if the given text could be the start of a known input sequence.

        :arg str text: Text to check
        :rtype: bool
        :returns: True if there are any known input sequences that start with this text
        """
        # Check if any known keyboard sequence starts with our text
        for sequence in self._keymap.keys():
            if sequence.startswith(text):
                return True

        # Check if text could be the start of specific DEC event patterns
        # Be very precise to avoid interfering with terminal response sequences
        if text.startswith('\x1b['):
            # Bracketed paste: \x1b[200~...text...\x1b[201~
            if text.startswith('\x1b[200~'):
                return True
            # Focus events: \x1b[I or \x1b[O (exactly 3 characters)
            if len(text) >= 3 and text[2] in 'IO':
                return True
            # Mouse sequences (legacy format): \x1b[M followed by 3 bytes
            if len(text) >= 3 and text[2] == 'M':
                return True
            # SGR mouse sequences: \x1b[<button;x;y;m or \x1b[<button;x;y;M
            # Only check for the specific SGR format starting with \x1b[<
            if len(text) >= 3 and text.startswith('\x1b[<'):
                return True

        return False

    def flushinp(self, timeout: float = 0) -> str:
        r"""
        Unbuffer and return all input available within ``timeout``.

        When CSI ``'\x1b['`` is detected in input stream, all remaining bytes
        are decoded as latin1.
        """
        ucs = ''
        while self._keyboard_buf:
            ucs += self._keyboard_buf.pop()

        def _getch() -> str:
            decoder = None
            if '\x1b[' in ucs:
                decoder = self._keyboard_decoder_latin1
            return self.getch(decoder)

        # and receive all immediately available bytes
        while self.kbhit(timeout=timeout):
            ucs += _getch()
        return ucs

    def inkey(self, timeout: Optional[float] = None,
              esc_delay: float = DEFAULT_ESCDELAY) -> Keystroke:
        r"""
        Read and return the next keyboard event within given timeout.

        Generally, this should be used inside the :meth:`raw` context manager.

        :arg float timeout: Number of seconds to wait for a keystroke before
            returning.  When ``None`` (default), this method may block
            indefinitely.
        :arg float esc_delay: Time in seconds to block after Escape key
           is received to await another key sequence beginning with
           escape such as *KEY_LEFT*, sequence ``'\x1b[D'``], before returning a
           :class:`~.Keystroke` instance for ``KEY_ESCAPE``.

           Users may override the default value of ``esc_delay`` in seconds,
           using environment value of ``ESCDELAY`` as milliseconds, see
           `ncurses(3)`_ section labeled *ESCDELAY* for details.  Setting
           the value as an argument to this function will override any
           such preference.
        :rtype: :class:`~.Keystroke`.
        :returns: :class:`~.Keystroke`, which may be empty (``''``) if
           ``timeout`` is specified and keystroke is not received.

        .. note:: When used without the context manager :meth:`cbreak`, or
            :meth:`raw`, :obj:`sys.__stdin__` remains line-buffered, and this
            function will block until the return key is pressed!

        .. note:: On Windows, a 10 ms sleep is added to the key press detection loop to reduce CPU
            load. Due to the behavior of :py:func:`time.sleep` on Windows, this will actually
            result in a 15.6 ms delay when using the default `time resolution
            <https://docs.microsoft.com/en-us/windows/win32/api/timeapi/nf-timeapi-timebeginperiod>`_.
            Decreasing the time resolution will reduce this to 10 ms, while increasing it, which
            is rarely done, will have a perceptable impact on the behavior.

        _`ncurses(3)`: https://www.man7.org/linux/man-pages/man3/ncurses.3x.html
        """
        stime = time.time()

        ucs = ''
        mode_1016_active = self._dec_mode_cache.get(1016) == DecModeResponse.SET

        def _getch() -> str:
            decoder = None
            if ucs.startswith('\x1b['):
                # CSI sequence forthcoming, decode as latin1
                decoder = self._keyboard_decoder_latin1
            return self.getch(decoder)

        # unbuffer and resolve buffered input
        ucs = self.flushinp()
        ks = resolve_sequence(ucs, self._keymap, self._keycodes, self._keymap_prefixes,
                              final=False, mode_1016_active=mode_1016_active)

        # Without any buffered input, blocking wait for enough bytes to complete
        # at least one full unicode character until timeout is exceeded.
        while not ks and self.kbhit(timeout=_time_left(stime, timeout)):
            # receive any next byte,
            ucs += _getch()

            # and all other immediately available bytes
            while self.kbhit(timeout=0):
                ucs += _getch()

            # and then resolve for sequence
            ks = resolve_sequence(ucs, self._keymap, self._keycodes, self._keymap_prefixes,
                                  final=False, mode_1016_active=mode_1016_active)

        if ks and ks.code == self.KEY_ESCAPE:
            # The escape key on input kicks off the most complex part of our
            # codebase, mainly because we must be able to receive *all* kinds of
            # legacy and modern *keyboard* input sequence schemes for special
            # keys as well as other events like mouse tracking.
            #
            # Although negotiation for these modes exist and they can be queried
            # about, there are varying degrees of support for consistent encoding
            # scheme and response across all terminals, except to take the
            # approach of supporting as many legacy, modern, and special events
            # as possible.
            #
            # In the case of modes that are "known" to be entered, any small
            # amount of latency can still cause sequences to be received in
            # input an indeterminate amount of time and bytes after the sequence
            # to enter or exit those modes have been written to output -- and so
            # we only take the approach of determining whether mode 1016
            # Pixel-coordinated Extended SGR Mouse event is active to re-cast
            # the 1006 Cell-coordinated Extended SGR Mouse events.
            #
            # That is to say, we match for *all* possible input event patterns,
            # except for the patterns negotiated here through the
            # _query_response method.
            final = False
            esctime = time.time()
            while ks.code == self.KEY_ESCAPE and not final:
                # set 'final' attribute for resolver if bytes received so far do
                # not appear to be any known sequence keyboard / "event", this
                # is mostly to quickly return for metaSendsEscape, alt+Char, and
                # for unsupported sequences without prolonged esc_delay.
                if len(ucs) > 1 and not self._is_known_input_prefix(ucs):
                    final = True
                elif not self.kbhit(timeout=_time_left(esctime, esc_delay)):
                    # otherwise, await the completion of a sequence using
                    # esc_delay, and, if no further bytes are received, then
                    # this is either an incomplete sequence, or something that
                    # can be confused as one, fe. ESC-O as alt+O instead of
                    # keypad 'enter' ESC-OM we awaited for
                    final = True
                else:
                    # successful receipt of any next character under esc_delay,
                    ucs += _getch()
                    while self.kbhit(timeout=0):
                        ucs += _getch()
                    # re-check 'final' check after reading more bytes
                    final = bool(ucs) and not self._is_known_input_prefix(ucs)

                ks = resolve_sequence(ucs, self._keymap, self._keycodes, self._keymap_prefixes,
                                      final=final, mode_1016_active=mode_1016_active)

        # re-buffer any remaining unmatched sequence text
        self.ungetch(ucs[len(ks):])
        return ks


#: _CUR_TERM = None
#: From libcurses/doc/ncurses-intro.html (ESR, Thomas Dickey, et. al)::
#:
#:   "After the call to setupterm(), the global variable cur_term is set to
#:    point to the current structure of terminal capabilities. By calling
#:    setupterm() for each terminal, and saving and restoring cur_term, it
#:    is possible for a program to use two or more terminals at once."
#:
#: However, if you study Python's ``./Modules/_cursesmodule.c``, you'll find::
#:
#:   if (!initialised_setupterm && setupterm(termstr,fd,&err) == ERR) {
#:
#: Python - perhaps wrongly - will not allow for re-initialisation of new
#: terminals through :func:`curses.setupterm`, so the value of cur_term cannot
#: be changed once set: subsequent calls to :func:`curses.setupterm` have no
#: effect.
#:
#: Therefore, the :attr:`Terminal.kind` of each :class:`Terminal` is
#: essentially a singleton. This global variable reflects that, and a warning
#: is emitted if somebody expects otherwise.
