"""Module providing DECSCUSR cursor shape support."""
from __future__ import annotations


class CursorShape:
    """
    DECSCUSR (DEC Set Cursor Style) cursor shape constants.

    Each constant corresponds to a cursor style parameter (0-6) used in
    the DECSCUSR escape sequence ``CSI Ps SP q``.

    Usage with the :meth:`~.Terminal.cursor_shape` context manager::

        with term.cursor_shape(term.CursorShape.BLINKING_BAR):
            # cursor is a blinking bar
            main()
        # cursor is restored to terminal default

    String names are also accepted::

        with term.cursor_shape('blinking_bar'):
            main()

    Available shapes:

    ====================== =====  ============================
    Constant               Value  Description
    ====================== =====  ============================
    ``DEFAULT``            0      Reset to terminal default
    ``BLINKING_BLOCK``     1      Blinking block cursor
    ``STEADY_BLOCK``       2      Steady (non-blinking) block
    ``BLINKING_UNDERLINE`` 3      Blinking underline cursor
    ``STEADY_UNDERLINE``   4      Steady underline cursor
    ``BLINKING_BAR``       5      Blinking bar (line) cursor
    ``STEADY_BAR``         6      Steady bar (line) cursor
    =====================  =====  ============================
    """

    DEFAULT = 0
    BLINKING_BLOCK = 1
    STEADY_BLOCK = 2
    BLINKING_UNDERLINE = 3
    STEADY_UNDERLINE = 4
    BLINKING_BAR = 5
    STEADY_BAR = 6

    DEFAULT_STYLE = 2

    COLOR_RESET_OSC = '\x1b]112\x07'

    STYLES: dict[str, int] = {
        'blinking_block': BLINKING_BLOCK,
        'steady_block': STEADY_BLOCK,
        'blinking_underline': BLINKING_UNDERLINE,
        'steady_underline': STEADY_UNDERLINE,
        'blinking_bar': BLINKING_BAR,
        'steady_bar': STEADY_BAR,
        'default': DEFAULT,
    }

    _VALID_VALUES = frozenset(range(7))

    @staticmethod
    def sequence(style: int | str) -> str:
        """
        Return the DECSCUSR escape sequence for the given cursor style.

        :arg style: An integer constant (0-6) or a string name (e.g. ``'blinking_bar'``).
        :returns: The escape sequence string.
        :raises ValueError: If *style* is not a valid cursor shape.
        """
        if isinstance(style, str):
            name = style.lower()
            if name not in CursorShape.STYLES:
                raise ValueError(
                    f"unknown cursor shape name {style!r}, expected one of: "
                    f"{', '.join(sorted(CursorShape.STYLES))}")
            style = CursorShape.STYLES[name]
        if style not in CursorShape._VALID_VALUES:
            raise ValueError(
                f"invalid cursor shape value {style!r}, expected 0-6")
        return f'\x1b[{style} q'
