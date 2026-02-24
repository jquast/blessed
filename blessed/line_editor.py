"""
Headless line editor with history, auto-suggest, and grapheme-aware editing.

This module provides :class:`LineEditor` for single-line input with readline-style
editing, :class:`History` for command recall and file persistence, and
:class:`LiveLineEditor` for rendering the editor at a fixed terminal position using
an asyncio ``(reader, writer)`` pair or a :class:`~.Terminal` instance.

Grapheme cluster boundaries are used for all cursor movement and display width
calculations via :func:`wcwidth.iter_graphemes` and :func:`wcwidth.width`.

Example usage with blessed Terminal::

    import asyncio
    from blessed import Terminal
    from blessed.line_editor import LineEditor, History

    async def main():
        term = Terminal()
        history = History()
        editor = LineEditor(history=history)
        with term.cbreak():
            while True:
                key = await term.async_inkey()
                result = editor.feed_key(key)
                if result.line is not None:
                    print(f"\\nYou typed: {result.line}")
                    break

Example usage with asyncio reader/writer::

    editor = LiveLineEditor(reader=stdin_reader, writer=stdout_writer,
                            row=23, col=0, width=80, history=history)
    line = await editor.readline()
"""

import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Union

from wcwidth import iter_graphemes, width as wcswidth

PASSWORD_CHAR = "\u25cf"

__all__ = (
    "InputStyle",
    "LineEditResult",
    "LineHistory",
    "LineEditor",
)


@dataclass
class InputStyle:
    """SGR styling for the input line, changeable at runtime.

    .. py:attribute:: text_sgr

        SGR sequence applied to main input text.

    .. py:attribute:: suggestion_sgr

        SGR sequence applied to auto-suggest suffix.

    .. py:attribute:: bg_sgr

        SGR sequence for the whole input line background.

    .. py:attribute:: ellipsis_sgr

        SGR sequence applied to overflow ellipsis characters.

    .. py:attribute:: cursor_seq

        DECSCUSR sequence for cursor shape (e.g. ``"\\x1b[5 q"``).
    """

    text_sgr: str = ""
    suggestion_sgr: str = ""
    bg_sgr: str = ""
    ellipsis_sgr: str = ""
    cursor_seq: str = ""


@dataclass
class LineEditResult:
    """Result of processing a keystroke.

    .. py:attribute:: line

        The accepted line text when Enter was pressed, otherwise ``None``.

    .. py:attribute:: eof

        ``True`` when Ctrl+D pressed on an empty line.

    .. py:attribute:: interrupt

        ``True`` when Ctrl+C pressed.

    .. py:attribute:: changed

        ``True`` when the display needs redrawing.

    .. py:attribute:: bell

        Bell string to emit (e.g. ``"\\a"``), empty when silent.
    """

    line: Optional[str] = None
    eof: bool = False
    interrupt: bool = False
    changed: bool = False
    bell: str = ""


@dataclass
class DisplayState:
    """Current visual state of the editor for rendering.

    When the :class:`LineEditor` has a ``max_width`` set, text and suggestion
    are clipped to fit, ``cursor`` is adjusted for the visible window, and
    ``clipped_left`` / ``clipped_right`` indicate overflow.

    .. py:attribute:: text

        Buffer text (masked with :data:`PASSWORD_CHAR` if password mode).
        When ``max_width`` is active this is the visible slice only.

    .. py:attribute:: cursor

        0-indexed cursor position in display columns within the visible
        window (already adjusted for horizontal scroll).

    .. py:attribute:: suggestion

        Auto-suggest suffix (to be rendered dim/grey after text).
        Clipped to remaining space when ``max_width`` is active.

    .. py:attribute:: clipped_left

        ``True`` when content extends beyond the left edge of the visible
        window (i.e. text has been scrolled right).

    .. py:attribute:: clipped_right

        ``True`` when content extends beyond the right edge of the visible
        window.

    .. py:attribute:: text_sgr

        SGR sequence for main input text (copied from :class:`InputStyle`).

    .. py:attribute:: suggestion_sgr

        SGR sequence for auto-suggest suffix.

    .. py:attribute:: bg_sgr

        SGR sequence for the whole input line background.

    .. py:attribute:: ellipsis_sgr

        SGR sequence for overflow ellipsis characters.

    .. py:attribute:: cursor_seq

        DECSCUSR sequence for cursor shape.
    """

    text: str = ""
    cursor: int = 0
    suggestion: str = ""
    clipped_left: bool = False
    clipped_right: bool = False
    text_sgr: str = ""
    suggestion_sgr: str = ""
    bg_sgr: str = ""
    ellipsis_sgr: str = ""
    cursor_seq: str = ""


def _graphemes(text: str) -> List[str]:
    """Split *text* into grapheme clusters."""
    return list(iter_graphemes(text))


def _display_width(text: str) -> int:
    """Return the display column width of *text*, ignoring control codes."""
    return wcswidth(text, control_codes="ignore")


def _grapheme_width(grapheme: str) -> int:
    """Return the display column width of a single grapheme cluster."""
    w = wcswidth(grapheme, control_codes="ignore")
    return max(0, w)


def _is_displayable_grapheme(grapheme: str) -> bool:
    """Return whether a grapheme cluster is displayable (not a C0/C1 control)."""
    w = wcswidth(grapheme, control_codes="ignore")
    if w > 0:
        return True
    return all(ch.isprintable() or ch == "\t" for ch in grapheme)


class LineHistory:
    """
    In-memory command history with optional file persistence.

    :param max_entries: Maximum number of history entries retained.
    """

    def __init__(self, max_entries: int = 5000) -> None:
        self._entries: List[str] = []
        self._max_entries = max_entries
        self._nav_idx: int = -1
        self._nav_saved: str = ""

    @property
    def entries(self) -> List[str]:
        """Return the history entries list (most recent last)."""
        return self._entries

    def add(self, line: str) -> None:
        """
        Append a line to history, skipping consecutive duplicates.

        :param line: Line text to add.
        """
        if not line:
            return
        if self._entries and self._entries[-1] == line:
            return
        self._entries.append(line)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

    def search_prefix(self, prefix: str) -> Optional[str]:
        """
        Find the most recent history entry matching *prefix*.

        :param prefix: Prefix to match.
        :returns: The matching entry, or ``None``.
        """
        if not prefix:
            return None
        for entry in reversed(self._entries):
            if entry.startswith(prefix) and entry != prefix:
                return entry
        return None

    def load_file(self, path: str) -> None:
        """
        Load history entries from a file (one per line).

        :param path: Path to the history file.
        """
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line.rstrip("\n")
                if line:
                    self._entries.append(line)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

    def save_entry(self, line: str, path: str) -> None:
        """
        Append a single entry to the history file.

        :param line: Line text to save.
        :param path: Path to the history file.
        """
        if not line:
            return
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def nav_start(self, current_line: str) -> None:
        """
        Begin history navigation, saving the current line.

        :param current_line: The current editor buffer to preserve.
        """
        self._nav_idx = len(self._entries)
        self._nav_saved = current_line

    def nav_up(self) -> Optional[str]:
        """
        Navigate to the previous (older) history entry.

        :returns: The history entry text, or ``None`` if at the beginning.
        """
        if self._nav_idx <= 0:
            return None
        self._nav_idx -= 1
        return self._entries[self._nav_idx]

    def nav_down(self) -> Optional[str]:
        """
        Navigate to the next (newer) history entry.

        :returns: The history entry, the saved current line, or ``None``.
        """
        if self._nav_idx >= len(self._entries):
            return None
        self._nav_idx += 1
        if self._nav_idx >= len(self._entries):
            return self._nav_saved
        return self._entries[self._nav_idx]


#: Alias for backward compatibility.
History = LineHistory


class LineEditor:
    """
    Headless single-line editor with grapheme-aware cursor movement.

    Feed keystrokes via :meth:`feed_key`, read display state via
    :attr:`display`.  The editor stores its buffer as a list of grapheme
    clusters, ensuring that cursor movement never splits a grapheme.

    Accepts blessed :class:`~.Keystroke` objects directly (dispatching on
    ``.name``), or plain strings for testing and non-blessed usage.

    :param history: Optional :class:`History` for up/down and auto-suggest.
    :param is_password: Optional callable returning ``True`` in password mode.
    :param max_width: When set, :attr:`display` clips text to this many
        columns with horizontal scrolling.  ``0`` means unlimited.
    :param ellipsis: Character shown at clipped edges (default ``\u2026``).
    :param limit: Maximum grapheme clusters allowed; ``0`` means unlimited.
    :param limit_bell: String emitted once when the limit is reached
        (default ``"\\a"``).  Set to ``""`` to silence.
    :param scroll_trigger_pct: Fraction of *max_width* used as the scroll
        trigger zone near each edge (default ``0.10``).
    :param scroll_factor: How many trigger-zone widths to scroll at once
        (default ``2.0``).
    :param style: Optional :class:`InputStyle` for runtime-changeable SGR
        styling.  Fields are copied into :class:`DisplayState` on each
        :attr:`display` access.
    """

    def __init__(
        self,
        history: Optional[History] = None,
        is_password: Optional[Callable[[], bool]] = None,
        max_width: int = 0,
        ellipsis: str = "\u2026",
        limit: int = 65536,
        limit_bell: str = "\a",
        scroll_trigger_pct: float = 0.10,
        scroll_factor: float = 2.0,
        style: Optional[InputStyle] = None,
    ) -> None:
        self._buf: List[str] = []  # list of grapheme clusters
        self._cursor: int = 0      # index into _buf (grapheme position)
        self._history: History = history or History()
        self._is_password: Optional[Callable[[], bool]] = is_password
        self._kill_ring: List[str] = []
        self._undo_stack: List[tuple[List[str], int]] = []
        self._in_history: bool = False
        self._password_mode: bool = False
        self.max_width: int = max_width
        self.ellipsis: str = ellipsis
        self.limit: int = limit
        self.limit_bell: str = limit_bell
        self._limit_bell_fired: bool = False
        self.scroll_trigger_pct: float = scroll_trigger_pct
        self.scroll_factor: float = scroll_factor
        self.style: InputStyle = style if style is not None else InputStyle()

    @property
    def history(self) -> History:
        """Return the attached :class:`History` instance."""
        return self._history

    @property
    def line(self) -> str:
        """Return the current buffer contents as a string."""
        return "".join(self._buf)

    @property
    def password_mode(self) -> bool:
        """Return whether password mode is currently active."""
        if self._is_password is not None:
            return self._is_password()
        return self._password_mode

    def _copy_style(self, ds: DisplayState) -> DisplayState:
        """Copy :attr:`style` fields into a :class:`DisplayState`."""
        ds.text_sgr = self.style.text_sgr
        ds.suggestion_sgr = self.style.suggestion_sgr
        ds.bg_sgr = self.style.bg_sgr
        ds.ellipsis_sgr = self.style.ellipsis_sgr
        ds.cursor_seq = self.style.cursor_seq
        return ds

    def _needs_hscroll(self) -> bool:
        """Return whether horizontal scrolling is needed.

        When the limit is set and fits within ``max_width``, the text can
        never exceed the window — no scrolling needed.
        """
        if self.max_width <= 0:
            return False
        if self.limit > 0 and self.limit <= self.max_width:
            return False
        return True

    @property
    def display(self) -> DisplayState:
        """Return the current :class:`DisplayState` for rendering.

        When :attr:`max_width` is set (> 0), the returned state has text
        and suggestion clipped to fit, with ``clipped_left`` and
        ``clipped_right`` indicating overflow.  The ``cursor`` value is
        relative to the visible window.
        """
        line = self.line
        cursor_col = self._cursor_display_col()
        if self.password_mode:
            pw_text = PASSWORD_CHAR * len(self._buf)
            if self._needs_hscroll():
                return self._copy_style(_apply_hscroll(
                    pw_text, "", cursor_col, self.max_width, self.ellipsis,
                    self.scroll_trigger_pct, self.scroll_factor,
                ))
            return self._copy_style(
                DisplayState(text=pw_text, cursor=cursor_col)
            )
        suggestion = self._get_suggestion()
        if self._needs_hscroll():
            return self._copy_style(_apply_hscroll(
                line, suggestion, cursor_col, self.max_width, self.ellipsis,
                self.scroll_trigger_pct, self.scroll_factor,
            ))
        return self._copy_style(
            DisplayState(text=line, cursor=cursor_col, suggestion=suggestion)
        )

    def feed_key(self, key: Union["Keystroke", str]) -> LineEditResult:
        """
        Process one keystroke event.

        Accepts a blessed :class:`~.Keystroke` (dispatching on its ``.name``
        attribute) or a plain string for testing.

        :param key: A :class:`~.Keystroke` or a string.
        :returns: :class:`LineEditResult` describing what happened.
        """
        name = getattr(key, "name", None)
        if name:
            handler = _KEY_DISPATCH.get(name)
            if handler is not None:
                return handler(self)

        key_str = str(key)
        if key_str and _is_displayable_grapheme(key_str):
            if self._at_limit():
                return LineEditResult(
                    changed=False, bell=self._fire_limit_bell(),
                )
            self._save_undo()
            for grapheme in _graphemes(key_str):
                if self._at_limit():
                    break
                self._buf.insert(self._cursor, grapheme)
                self._cursor += 1
            self._in_history = False
            return LineEditResult(changed=True)

        return LineEditResult()

    def insert_text(self, text: str) -> LineEditResult:
        """
        Insert text at cursor position (for bracketed paste).

        :param text: Text to insert.
        :returns: :class:`LineEditResult` with ``changed=True``, or
            ``changed=False`` with a bell if the limit blocks insertion.
        """
        if self._at_limit():
            return LineEditResult(
                changed=False, bell=self._fire_limit_bell(),
            )
        self._save_undo()
        for grapheme in _graphemes(text):
            if self._at_limit():
                break
            if _is_displayable_grapheme(grapheme):
                self._buf.insert(self._cursor, grapheme)
                self._cursor += 1
        return LineEditResult(changed=True)

    def clear(self) -> None:
        """Clear the buffer and reset cursor to start."""
        self._buf.clear()
        self._cursor = 0
        self._in_history = False

    def set_password_mode(self, enabled: bool) -> None:
        """
        Set password mode directly (used when no ``is_password`` callable).

        :param enabled: Whether to mask input display.
        """
        self._password_mode = enabled

    def _at_limit(self) -> bool:
        """Return ``True`` when the buffer is at or above the input limit."""
        return self.limit > 0 and len(self._buf) >= self.limit

    def _fire_limit_bell(self) -> str:
        """Return the bell string if limit just reached, else empty."""
        if not self._limit_bell_fired:
            self._limit_bell_fired = True
            return self.limit_bell
        return ""

    def _maybe_reset_limit_bell(self) -> None:
        """Reset the bell-fired flag if buffer has shrunk below limit."""
        if self._limit_bell_fired and not self._at_limit():
            self._limit_bell_fired = False

    def _cursor_display_col(self) -> int:
        """Return the display column of the cursor (sum of widths before it)."""
        return sum(_grapheme_width(g) for g in self._buf[:self._cursor])

    def _save_undo(self) -> None:
        self._undo_stack.append((list(self._buf), self._cursor))
        if len(self._undo_stack) > 100:
            self._undo_stack = self._undo_stack[-100:]

    def _undo(self) -> LineEditResult:
        if not self._undo_stack:
            return LineEditResult()
        self._buf, self._cursor = self._undo_stack.pop()
        return LineEditResult(changed=True)

    def _handle_enter(self) -> LineEditResult:
        line = self.line
        if line and not self.password_mode:
            self._history.add(line)
        self.clear()
        self._undo_stack.clear()
        return LineEditResult(line=line, changed=True)

    def _handle_ctrl_c(self) -> LineEditResult:
        self.clear()
        self._undo_stack.clear()
        return LineEditResult(interrupt=True, changed=True)

    def _handle_ctrl_d(self) -> LineEditResult:
        if not self._buf:
            return LineEditResult(eof=True)
        self._save_undo()
        self._delete_at_cursor()
        return LineEditResult(changed=True)

    def _move_left(self) -> LineEditResult:
        if self._cursor > 0:
            self._cursor -= 1
            return LineEditResult(changed=True)
        return LineEditResult()

    def _move_right(self) -> LineEditResult:
        if self._cursor < len(self._buf):
            self._cursor += 1
            return LineEditResult(changed=True)
        return LineEditResult()

    def _move_home(self) -> LineEditResult:
        if self._cursor > 0:
            self._cursor = 0
            return LineEditResult(changed=True)
        return LineEditResult()

    def _move_end(self) -> LineEditResult:
        if self._cursor < len(self._buf):
            self._cursor = len(self._buf)
            return LineEditResult(changed=True)
        return LineEditResult()

    def _move_word_left(self) -> LineEditResult:
        if self._cursor == 0:
            return LineEditResult()
        pos = self._cursor - 1
        while pos > 0 and not self._buf[pos - 1].isalnum():
            pos -= 1
        while pos > 0 and self._buf[pos - 1].isalnum():
            pos -= 1
        self._cursor = pos
        return LineEditResult(changed=True)

    def _move_word_right(self) -> LineEditResult:
        n = len(self._buf)
        if self._cursor >= n:
            return LineEditResult()
        pos = self._cursor
        while pos < n and not self._buf[pos].isalnum():
            pos += 1
        while pos < n and self._buf[pos].isalnum():
            pos += 1
        self._cursor = pos
        return LineEditResult(changed=True)

    def _backspace(self) -> LineEditResult:
        if self._cursor > 0:
            self._save_undo()
            self._cursor -= 1
            del self._buf[self._cursor]
            self._maybe_reset_limit_bell()
            return LineEditResult(changed=True)
        return LineEditResult()

    def _delete_at_cursor(self) -> LineEditResult:
        if self._cursor < len(self._buf):
            del self._buf[self._cursor]
            self._maybe_reset_limit_bell()
            return LineEditResult(changed=True)
        return LineEditResult()

    def _kill_to_end(self) -> LineEditResult:
        if self._cursor < len(self._buf):
            self._save_undo()
            killed = "".join(self._buf[self._cursor:])
            del self._buf[self._cursor:]
            self._kill_ring.append(killed)
            self._maybe_reset_limit_bell()
            return LineEditResult(changed=True)
        return LineEditResult()

    def _kill_line(self) -> LineEditResult:
        if self._buf:
            self._save_undo()
            killed = "".join(self._buf[:self._cursor])
            del self._buf[:self._cursor]
            self._cursor = 0
            if killed:
                self._kill_ring.append(killed)
            self._maybe_reset_limit_bell()
            return LineEditResult(changed=True)
        return LineEditResult()

    def _kill_word_back(self) -> LineEditResult:
        if self._cursor == 0:
            return LineEditResult()
        self._save_undo()
        end = self._cursor
        pos = self._cursor - 1
        while pos > 0 and not self._buf[pos - 1].isalnum():
            pos -= 1
        while pos > 0 and self._buf[pos - 1].isalnum():
            pos -= 1
        killed = "".join(self._buf[pos:end])
        del self._buf[pos:end]
        self._cursor = pos
        self._kill_ring.append(killed)
        self._maybe_reset_limit_bell()
        return LineEditResult(changed=True)

    def _yank(self) -> LineEditResult:
        if not self._kill_ring:
            return LineEditResult()
        self._save_undo()
        text = self._kill_ring[-1]
        for grapheme in _graphemes(text):
            self._buf.insert(self._cursor, grapheme)
            self._cursor += 1
        return LineEditResult(changed=True)

    def _history_prev(self) -> LineEditResult:
        if not self._in_history:
            self._history.nav_start(self.line)
            self._in_history = True
        entry = self._history.nav_up()
        if entry is not None:
            self._set_text(entry)
            return LineEditResult(changed=True)
        return LineEditResult()

    def _history_next(self) -> LineEditResult:
        if not self._in_history:
            return LineEditResult()
        entry = self._history.nav_down()
        if entry is not None:
            self._set_text(entry)
            return LineEditResult(changed=True)
        return LineEditResult()

    def _accept_suggestion(self) -> LineEditResult:
        """Accept auto-suggest when cursor is at end, otherwise move right."""
        if self._cursor == len(self._buf):
            suggestion = self._get_suggestion()
            if suggestion:
                self._save_undo()
                for grapheme in _graphemes(suggestion):
                    self._buf.append(grapheme)
                self._cursor = len(self._buf)
                return LineEditResult(changed=True)
        if self._cursor < len(self._buf):
            self._cursor += 1
            return LineEditResult(changed=True)
        return LineEditResult()

    def _set_text(self, text: str) -> None:
        self._buf = _graphemes(text)
        self._cursor = len(self._buf)

    def _get_suggestion(self) -> str:
        if self.password_mode:
            return ""
        line = self.line
        if not line or self._cursor != len(self._buf):
            return ""
        match = self._history.search_prefix(line)
        if match is not None:
            return match[len(line):]
        return ""


def _apply_hscroll(
    text: str,
    suggestion: str,
    cursor_col: int,
    max_width: int,
    ellipsis: str = "\u2026",
    scroll_trigger_pct: float = 0.10,
    scroll_factor: float = 2.0,
) -> DisplayState:
    """
    Clip *text* and *suggestion* to *max_width* with horizontal scrolling.

    The cursor is kept visible within the window.  An ellipsis character is
    shown at the clipped edge(s).

    :param text: Full buffer text.
    :param suggestion: Auto-suggest suffix.
    :param cursor_col: Cursor position in display columns (full text).
    :param max_width: Available display columns.
    :param ellipsis: Overflow indicator character.
    :param scroll_trigger_pct: Fraction of *max_width* for the trigger zone.
    :param scroll_factor: Multiplier on trigger zone for scroll amount.
    :returns: A :class:`DisplayState` with clipped text and adjusted cursor.
    """
    ellipsis_w = _grapheme_width(ellipsis) if ellipsis else 0
    text_w = _display_width(text)
    suggest_w = _display_width(suggestion) if suggestion else 0
    total_w = text_w + suggest_w

    if total_w <= max_width:
        return DisplayState(
            text=text, cursor=cursor_col, suggestion=suggestion,
        )

    trigger_cols = max(1, int(max_width * scroll_trigger_pct))
    scroll_amount = max(1, int(trigger_cols * scroll_factor))
    usable = max_width

    scroll_offset = 0
    if cursor_col >= usable - trigger_cols:
        scroll_offset = cursor_col - usable + scroll_amount + 1

    # Adjust for left ellipsis taking up space.
    clipped_left = scroll_offset > 0
    if clipped_left:
        usable -= ellipsis_w

    # Slice graphemes from the combined text+suggestion.
    combined = text + suggestion
    vis_parts: List[str] = []
    vis_width = 0
    col = 0

    for grapheme in iter_graphemes(combined):
        g_w = _grapheme_width(grapheme)
        if col + g_w <= scroll_offset:
            col += g_w
            continue
        if vis_width + g_w > usable:
            break
        vis_parts.append(grapheme)
        vis_width += g_w
        col += g_w

    clipped_right = (scroll_offset + usable) < total_w
    if clipped_right:
        # Make room for right ellipsis by removing last grapheme(s).
        while vis_parts and vis_width + ellipsis_w > usable:
            removed = vis_parts.pop()
            vis_width -= _grapheme_width(removed)

    # Split visible parts back into text and suggestion portions.
    vis_text_parts: List[str] = []
    vis_suggest_parts: List[str] = []
    pos = 0
    for grapheme in vis_parts:
        g_w = _grapheme_width(grapheme)
        src_col = scroll_offset + pos
        if src_col < text_w:
            vis_text_parts.append(grapheme)
        else:
            vis_suggest_parts.append(grapheme)
        pos += g_w

    vis_cursor = cursor_col - scroll_offset
    if clipped_left:
        vis_cursor += ellipsis_w

    return DisplayState(
        text="".join(vis_text_parts),
        cursor=vis_cursor,
        suggestion="".join(vis_suggest_parts),
        clipped_left=clipped_left,
        clipped_right=clipped_right,
    )


# Dispatch table keyed by blessed Keystroke.name values.
_KEY_DISPATCH = {
    "KEY_ENTER": LineEditor._handle_enter,
    "KEY_CTRL_C": LineEditor._handle_ctrl_c,
    "KEY_CTRL_D": LineEditor._handle_ctrl_d,
    "KEY_LEFT": LineEditor._move_left,
    "KEY_CTRL_B": LineEditor._move_left,
    "KEY_RIGHT": LineEditor._accept_suggestion,
    "KEY_CTRL_F": LineEditor._move_right,
    "KEY_HOME": LineEditor._move_home,
    "KEY_CTRL_A": LineEditor._move_home,
    "KEY_END": LineEditor._move_end,
    "KEY_CTRL_E": LineEditor._move_end,
    "KEY_SLEFT": LineEditor._move_word_left,
    "KEY_SRIGHT": LineEditor._move_word_right,
    "KEY_CTRL_LEFT": LineEditor._move_word_left,
    "KEY_CTRL_RIGHT": LineEditor._move_word_right,
    "KEY_BACKSPACE": LineEditor._backspace,
    "KEY_DELETE": LineEditor._delete_at_cursor,
    "KEY_CTRL_K": LineEditor._kill_to_end,
    "KEY_CTRL_U": LineEditor._kill_line,
    "KEY_CTRL_W": LineEditor._kill_word_back,
    "KEY_CTRL_Y": LineEditor._yank,
    "KEY_UP": LineEditor._history_prev,
    "KEY_CTRL_P": LineEditor._history_prev,
    "KEY_DOWN": LineEditor._history_next,
    "KEY_CTRL_N": LineEditor._history_next,
    "KEY_CTRL_Z": LineEditor._undo,
}


# incomplete
#
#class LiveLineEditor:
#    """
#    Line editor with async rendering to a terminal region.
#
#    Renders the editor at a fixed ``(row, col)`` position using an asyncio
#    writer for output and :meth:`~.Terminal.async_inkey` for input.  If *row*
#    and *col* are not specified, renders at the current cursor position.
#
#    :param terminal: A :class:`~.Terminal` instance for keystroke reading.
#    :param writer: An :class:`asyncio.StreamWriter` for terminal output.
#        If ``None``, output is written to *terminal*'s stream.
#    :param row: 0-indexed row for the input line (``None`` = current position).
#    :param col: 0-indexed column for the input line (default ``0``).
#    :param width: Maximum display width (default: terminal width minus *col*).
#    :param history: :class:`History` instance for command recall.
#    :param is_password: Callable returning ``True`` when in password mode.
#    :param prompt: Prompt string displayed before the input area.
#    :param suggestion_style: SGR escape for auto-suggest text (default: dim).
#    """
#
#    def __init__(
#        self,
#        terminal: "Any",
#        writer: "Any" = None,
#        row: Optional[int] = None,
#        col: int = 0,
#        width: Optional[int] = None,
#        history: Optional[History] = None,
#        is_password: Optional[Callable[[], bool]] = None,
#        prompt: str = "",
#        suggestion_style: str = "\x1b[2m",
#    ) -> None:
#        self._term = terminal
#        self._writer = writer
#        self._row = row
#        self._col = col
#        self._width = width
#        self._prompt = prompt
#        self._suggestion_style = suggestion_style
#        self._editor = LineEditor(history=history, is_password=is_password)
#
#    @property
#    def editor(self) -> LineEditor:
#        """Return the underlying :class:`LineEditor`."""
#        return self._editor
#
#    def _write(self, data: bytes) -> None:
#        """Write bytes to the output stream."""
#        if self._writer is not None:
#            self._writer.write(data)
#        else:
#            self._term.stream.write(data.decode("utf-8", errors="replace"))
#            self._term.stream.flush()
#
#    def render(self) -> None:
#        """Render the current editor state to the terminal."""
#        state = self._editor.display
#        prompt_width = _display_width(self._prompt) if self._prompt else 0
#        term_width = getattr(self._term, "width", 80)
#        width = self._width if self._width is not None else (term_width - self._col)
#
#        parts: List[bytes] = []
#
#        if self._row is not None:
#            parts.append(f"\x1b[{self._row + 1};{self._col + 1}H".encode())
#
#        parts.append(b"\x1b[K")
#
#        if self._prompt:
#            parts.append(self._prompt.encode("utf-8", errors="replace"))
#
#        available = width - prompt_width
#        text = state.text
#        text_width = _display_width(text)
#        if text_width <= available:
#            parts.append(text.encode("utf-8", errors="replace"))
#            if state.suggestion:
#                remaining = available - text_width
#                suggestion = state.suggestion
#                if _display_width(suggestion) > remaining:
#                    suggestion = _truncate_to_width(suggestion, remaining)
#                parts.append(self._suggestion_style.encode())
#                parts.append(suggestion.encode("utf-8", errors="replace"))
#                parts.append(b"\x1b[0m")
#        else:
#            parts.append(_truncate_to_width(text, available).encode(
#                "utf-8", errors="replace"))
#
#        cursor_col = self._col + prompt_width + state.cursor
#        if self._row is not None:
#            parts.append(f"\x1b[{self._row + 1};{cursor_col + 1}H".encode())
#
#        self._write(b"".join(parts))
#
#    async def readline(self) -> Optional[str]:
#        """
#        Read a complete line of input asynchronously.
#
#        Reads keystrokes via :meth:`~.Terminal.async_inkey`, feeds them
#        directly to the underlying :class:`LineEditor`, and renders after
#        each change.
#
#        :returns: The accepted line, or ``None`` on EOF (Ctrl+D).
#        :raises KeyboardInterrupt: On Ctrl+C.
#        """
#        self.render()
#        while True:
#            key = await self._term.async_inkey()
#            result = self._editor.feed_key(key)
#
#            if result.eof:
#                return None
#            if result.interrupt:
#                self.render()
#                raise KeyboardInterrupt
#            if result.line is not None:
#                return result.line
#            if result.changed:
#                self.render()
#
#
#def _truncate_to_width(text: str, max_width: int) -> str:
#    """Truncate *text* to fit within *max_width* display columns."""
#    result: List[str] = []
#    used = 0
#    for grapheme in iter_graphemes(text):
#        w = _grapheme_width(grapheme)
#        if used + w > max_width:
#            break
#        result.append(grapheme)
#        used += w
#    return "".join(result)
