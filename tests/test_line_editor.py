"""Tests for blessed.line_editor."""

import os
import tempfile

import pytest

from blessed.line_editor import (
    PASSWORD_CHAR,
    DisplayState,
    EditResult,
    History,
    LineEditor,
    _display_width,
    _graphemes,
)


def _key(name: str) -> str:
    """Create a fake Keystroke-like object with a .name attribute."""

    class FakeKey(str):
        pass

    k = FakeKey("")
    k.name = name  # type: ignore[attr-defined]
    return k  # type: ignore[return-value]


# Shorthand aliases for common keys
_ENTER = _key("KEY_ENTER")
_BACKSPACE = _key("KEY_BACKSPACE")
_DELETE = _key("KEY_DELETE")
_LEFT = _key("KEY_LEFT")
_RIGHT = _key("KEY_RIGHT")
_HOME = _key("KEY_HOME")
_END = _key("KEY_END")
_UP = _key("KEY_UP")
_DOWN = _key("KEY_DOWN")
_WORD_LEFT = _key("KEY_SLEFT")
_WORD_RIGHT = _key("KEY_SRIGHT")
_CTRL_A = _key("KEY_CTRL_A")
_CTRL_C = _key("KEY_CTRL_C")
_CTRL_D = _key("KEY_CTRL_D")
_CTRL_E = _key("KEY_CTRL_E")
_CTRL_K = _key("KEY_CTRL_K")
_CTRL_U = _key("KEY_CTRL_U")
_CTRL_W = _key("KEY_CTRL_W")
_CTRL_Y = _key("KEY_CTRL_Y")
_CTRL_Z = _key("KEY_CTRL_Z")


class TestGraphemeHelpers:
    def test_graphemes_ascii(self) -> None:
        assert _graphemes("hello") == ["h", "e", "l", "l", "o"]

    def test_graphemes_emoji(self) -> None:
        result = _graphemes("\U0001f468\u200d\U0001f33e")
        assert len(result) == 1

    def test_display_width_ascii(self) -> None:
        assert _display_width("hello") == 5

    def test_display_width_cjk(self) -> None:
        assert _display_width("\u4e16\u754c") == 4

    def test_display_width_empty(self) -> None:
        assert _display_width("") == 0


class TestEditResult:
    def test_defaults(self) -> None:
        r = EditResult()
        assert r.line is None
        assert r.eof is False
        assert r.interrupt is False
        assert r.changed is False

    def test_accept(self) -> None:
        r = EditResult(line="hello", changed=True)
        assert r.line == "hello"
        assert r.changed is True


class TestDisplayState:
    def test_defaults(self) -> None:
        d = DisplayState()
        assert d.text == ""
        assert d.cursor == 0
        assert d.suggestion == ""


class TestHistory:
    def test_add_and_entries(self) -> None:
        h = History()
        h.add("alpha")
        h.add("bravo")
        assert h.entries == ["alpha", "bravo"]

    def test_add_skips_empty(self) -> None:
        h = History()
        h.add("")
        assert h.entries == []

    def test_add_deduplicates_consecutive(self) -> None:
        h = History()
        h.add("x")
        h.add("x")
        h.add("y")
        h.add("y")
        assert h.entries == ["x", "y"]

    def test_max_entries(self) -> None:
        h = History(max_entries=3)
        for i in range(5):
            h.add(str(i))
        assert h.entries == ["2", "3", "4"]

    def test_search_prefix(self) -> None:
        h = History()
        h.add("east")
        h.add("enter cave")
        h.add("eat bread")
        assert h.search_prefix("ea") == "eat bread"
        assert h.search_prefix("ent") == "enter cave"
        assert h.search_prefix("xyz") is None
        assert h.search_prefix("") is None

    def test_search_prefix_skips_exact_match(self) -> None:
        h = History()
        h.add("hello")
        assert h.search_prefix("hello") is None

    def test_nav_up_down(self) -> None:
        h = History()
        h.add("first")
        h.add("second")
        h.nav_start("current")
        assert h.nav_up() == "second"
        assert h.nav_up() == "first"
        assert h.nav_up() is None
        assert h.nav_down() == "second"
        assert h.nav_down() == "current"
        assert h.nav_down() is None

    def test_nav_empty_history(self) -> None:
        h = History()
        h.nav_start("")
        assert h.nav_up() is None

    def test_load_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("alpha\nbravo\ncharlie\n")
            f.flush()
            path = f.name
        try:
            h = History()
            h.load_file(path)
            assert h.entries == ["alpha", "bravo", "charlie"]
        finally:
            os.unlink(path)

    def test_load_file_missing(self) -> None:
        h = History()
        h.load_file("/nonexistent/path")
        assert h.entries == []

    def test_save_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub", "history.txt")
            h = History()
            h.save_entry("hello", path)
            h.save_entry("world", path)
            with open(path, "r") as f:
                assert f.read() == "hello\nworld\n"

    def test_save_entry_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.txt")
            h = History()
            h.save_entry("", path)
            assert not os.path.exists(path)


class TestLineEditorBasicEditing:
    def test_insert_chars(self) -> None:
        ed = LineEditor()
        ed.feed_key("h")
        ed.feed_key("i")
        assert ed.line == "hi"
        assert ed.display.cursor == 2

    def test_enter_returns_line(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        r = ed.feed_key(_ENTER)
        assert r.line == "ab"
        assert r.changed is True
        assert ed.line == ""

    def test_enter_empty_line(self) -> None:
        ed = LineEditor()
        r = ed.feed_key(_ENTER)
        assert r.line == ""

    def test_backspace(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key("c")
        r = ed.feed_key(_BACKSPACE)
        assert r.changed is True
        assert ed.line == "ab"

    def test_backspace_at_start(self) -> None:
        ed = LineEditor()
        r = ed.feed_key(_BACKSPACE)
        assert r.changed is False

    def test_delete(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_HOME)
        r = ed.feed_key(_DELETE)
        assert r.changed is True
        assert ed.line == "b"

    def test_delete_at_end(self) -> None:
        ed = LineEditor()
        ed.feed_key("x")
        r = ed.feed_key(_DELETE)
        assert r.changed is False

    def test_insert_text(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.insert_text("bcd")
        assert ed.line == "abcd"
        assert ed.display.cursor == 4

    def test_clear(self) -> None:
        ed = LineEditor()
        ed.feed_key("h")
        ed.feed_key("i")
        ed.clear()
        assert ed.line == ""
        assert ed.display.cursor == 0

    def test_unknown_key_unchanged(self) -> None:
        ed = LineEditor()
        r = ed.feed_key("\x00")
        assert r.changed is False
        assert r.line is None


class TestLineEditorCursorMovement:
    def test_left_right(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_LEFT)
        assert ed.display.cursor == 1
        ed.feed_key(_RIGHT)
        assert ed.display.cursor == 2

    def test_left_at_start(self) -> None:
        ed = LineEditor()
        r = ed.feed_key(_LEFT)
        assert r.changed is False

    def test_home_end(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key("c")
        ed.feed_key(_HOME)
        assert ed.display.cursor == 0
        ed.feed_key(_END)
        assert ed.display.cursor == 3

    def test_word_left(self) -> None:
        ed = LineEditor()
        for ch in "hello world":
            ed.feed_key(ch)
        ed.feed_key(_WORD_LEFT)
        assert ed.line[ed._cursor:] == "world"
        ed.feed_key(_WORD_LEFT)
        assert ed._cursor == 0

    def test_word_right(self) -> None:
        ed = LineEditor()
        for ch in "hello world":
            ed.feed_key(ch)
        ed.feed_key(_HOME)
        ed.feed_key(_WORD_RIGHT)
        assert ed.line[:ed._cursor] == "hello"
        ed.feed_key(_WORD_RIGHT)
        assert ed._cursor == 11

    def test_word_left_at_start(self) -> None:
        ed = LineEditor()
        r = ed.feed_key(_WORD_LEFT)
        assert r.changed is False

    def test_word_right_at_end(self) -> None:
        ed = LineEditor()
        ed.feed_key("x")
        r = ed.feed_key(_WORD_RIGHT)
        assert r.changed is False

    def test_insert_at_cursor(self) -> None:
        ed = LineEditor()
        for ch in "ac":
            ed.feed_key(ch)
        ed.feed_key(_LEFT)
        ed.feed_key("b")
        assert ed.line == "abc"
        assert ed.display.cursor == 2


class TestLineEditorCJK:
    def test_cjk_display_width(self) -> None:
        ed = LineEditor()
        ed.feed_key("\u4e16")
        ed.feed_key("\u754c")
        assert ed.display.cursor == 4
        assert ed.display.text == "\u4e16\u754c"

    def test_cjk_cursor_after_left(self) -> None:
        ed = LineEditor()
        ed.feed_key("\u4e16")
        ed.feed_key("\u754c")
        ed.feed_key(_LEFT)
        assert ed.display.cursor == 2

    def test_backspace_cjk(self) -> None:
        ed = LineEditor()
        ed.feed_key("\u4e16")
        ed.feed_key("\u754c")
        ed.feed_key(_BACKSPACE)
        assert ed.line == "\u4e16"
        assert ed.display.cursor == 2


class TestLineEditorGraphemeEditing:
    def test_backspace_emoji_with_skin_tone(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("\U0001f44b\U0001f3fb")
        assert len(ed._buf) == 2
        ed.feed_key(_BACKSPACE)
        assert ed.line == "a"
        assert len(ed._buf) == 1

    def test_backspace_flag_emoji(self) -> None:
        ed = LineEditor()
        ed.feed_key("\U0001f1fa\U0001f1f8")
        ed.feed_key(_BACKSPACE)
        assert ed.line == ""

    def test_insert_text_grapheme_clusters(self) -> None:
        ed = LineEditor()
        ed.insert_text("a\U0001f468\u200d\U0001f33eb")
        assert len(ed._buf) == 3
        assert ed._buf[1] == "\U0001f468\u200d\U0001f33e"

    def test_cursor_movement_over_grapheme_clusters(self) -> None:
        ed = LineEditor()
        ed.feed_key("x")
        ed.feed_key("\U0001f44b\U0001f3fb")
        ed.feed_key("y")
        ed.feed_key(_LEFT)
        ed.feed_key(_LEFT)
        assert ed._cursor == 1
        ed.feed_key(_RIGHT)
        assert ed._cursor == 2


class TestLineEditorKillRing:
    def test_kill_to_end(self) -> None:
        ed = LineEditor()
        for ch in "hello":
            ed.feed_key(ch)
        ed.feed_key(_HOME)
        ed.feed_key(_RIGHT)
        ed.feed_key(_RIGHT)
        r = ed.feed_key(_CTRL_K)
        assert r.changed is True
        assert ed.line == "he"

    def test_kill_line(self) -> None:
        ed = LineEditor()
        for ch in "hello":
            ed.feed_key(ch)
        ed.feed_key(_LEFT)
        ed.feed_key(_LEFT)
        r = ed.feed_key(_CTRL_U)
        assert r.changed is True
        assert ed.line == "lo"
        assert ed.display.cursor == 0

    def test_kill_word_back(self) -> None:
        ed = LineEditor()
        for ch in "hello world":
            ed.feed_key(ch)
        r = ed.feed_key(_CTRL_W)
        assert r.changed is True
        assert ed.line == "hello "

    def test_yank(self) -> None:
        ed = LineEditor()
        for ch in "hello world":
            ed.feed_key(ch)
        ed.feed_key(_CTRL_W)
        ed.feed_key(_CTRL_Y)
        assert ed.line == "hello world"

    def test_yank_empty_ring(self) -> None:
        ed = LineEditor()
        r = ed.feed_key(_CTRL_Y)
        assert r.changed is False

    def test_kill_to_end_empty(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        r = ed.feed_key(_CTRL_K)
        assert r.changed is False


class TestLineEditorUndo:
    def test_undo_insert(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_CTRL_Z)
        assert ed.line == "a"
        ed.feed_key(_CTRL_Z)
        assert ed.line == ""

    def test_undo_backspace(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_BACKSPACE)
        assert ed.line == "a"
        ed.feed_key(_CTRL_Z)
        assert ed.line == "ab"

    def test_undo_kill(self) -> None:
        ed = LineEditor()
        for ch in "hello":
            ed.feed_key(ch)
        ed.feed_key(_CTRL_U)
        assert ed.line == ""
        ed.feed_key(_CTRL_Z)
        assert ed.line == "hello"

    def test_undo_empty_stack(self) -> None:
        ed = LineEditor()
        r = ed.feed_key(_CTRL_Z)
        assert r.changed is False


class TestLineEditorHistory:
    def test_up_down(self) -> None:
        h = History()
        h.add("alpha")
        h.add("bravo")
        ed = LineEditor(history=h)
        ed.feed_key("c")
        ed.feed_key(_UP)
        assert ed.line == "bravo"
        ed.feed_key(_UP)
        assert ed.line == "alpha"
        ed.feed_key(_DOWN)
        assert ed.line == "bravo"
        ed.feed_key(_DOWN)
        assert ed.line == "c"

    def test_up_at_top(self) -> None:
        h = History()
        h.add("only")
        ed = LineEditor(history=h)
        ed.feed_key(_UP)
        assert ed.line == "only"
        r = ed.feed_key(_UP)
        assert r.changed is False

    def test_down_without_history_browsing(self) -> None:
        ed = LineEditor()
        r = ed.feed_key(_DOWN)
        assert r.changed is False

    def test_enter_adds_to_history(self) -> None:
        h = History()
        ed = LineEditor(history=h)
        ed.feed_key("x")
        ed.feed_key(_ENTER)
        assert h.entries == ["x"]

    def test_enter_password_mode_skips_history(self) -> None:
        h = History()
        ed = LineEditor(history=h, is_password=lambda: True)
        ed.feed_key("s")
        ed.feed_key("e")
        ed.feed_key("c")
        ed.feed_key(_ENTER)
        assert h.entries == []


class TestLineEditorAutoSuggest:
    def test_suggestion_from_history(self) -> None:
        h = History()
        h.add("hello world")
        ed = LineEditor(history=h)
        ed.feed_key("h")
        ed.feed_key("e")
        ds = ed.display
        assert ds.suggestion == "llo world"

    def test_no_suggestion_mid_line(self) -> None:
        h = History()
        h.add("hello world")
        ed = LineEditor(history=h)
        for ch in "hello":
            ed.feed_key(ch)
        ed.feed_key(_HOME)
        assert ed.display.suggestion == ""

    def test_no_suggestion_password_mode(self) -> None:
        h = History()
        h.add("secret123")
        ed = LineEditor(history=h, is_password=lambda: True)
        ed.feed_key("s")
        assert ed.display.suggestion == ""

    def test_accept_suggestion_via_right(self) -> None:
        h = History()
        h.add("hello world")
        ed = LineEditor(history=h)
        ed.feed_key("h")
        ed.feed_key("e")
        ed.feed_key(_RIGHT)
        assert ed.line == "hello world"


class TestLineEditorPasswordMode:
    def test_masked_display(self) -> None:
        ed = LineEditor(is_password=lambda: True)
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key("c")
        ds = ed.display
        assert ds.text == PASSWORD_CHAR * 3

    def test_set_password_mode(self) -> None:
        ed = LineEditor()
        ed.set_password_mode(True)
        ed.feed_key("x")
        assert ed.display.text == PASSWORD_CHAR

    def test_password_enter_not_saved(self) -> None:
        h = History()
        ed = LineEditor(history=h)
        ed.set_password_mode(True)
        ed.feed_key("p")
        ed.feed_key("w")
        r = ed.feed_key(_ENTER)
        assert r.line == "pw"
        assert h.entries == []


class TestLineEditorCtrlCD:
    def test_ctrl_c_clears_and_interrupts(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        r = ed.feed_key(_CTRL_C)
        assert r.interrupt is True
        assert r.changed is True
        assert ed.line == ""

    def test_ctrl_d_eof_on_empty(self) -> None:
        ed = LineEditor()
        r = ed.feed_key(_CTRL_D)
        assert r.eof is True

    def test_ctrl_d_deletes_on_nonempty(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_HOME)
        r = ed.feed_key(_CTRL_D)
        assert r.eof is False
        assert r.changed is True
        assert ed.line == "b"


class TestLineEditorCtrlAE:
    def test_ctrl_a_moves_home(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_CTRL_A)
        assert ed.display.cursor == 0

    def test_ctrl_e_moves_end(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_HOME)
        ed.feed_key(_CTRL_E)
        assert ed.display.cursor == 2
