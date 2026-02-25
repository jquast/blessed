"""Tests for blessed.line_editor."""

# local
from blessed.line_editor import PASSWORD_CHAR, LineEditor
from blessed.line_editor import LineHistory as History
from blessed.line_editor import (DisplayState,
                                 LineEditResult,
                                 _apply_hscroll)
from wcwidth import iter_graphemes, width as wcswidth


class MockTerminal:
    """Minimal terminal stub for render method tests."""

    normal = "<NORMAL>"

    @staticmethod
    def move_yx(row: int, col: int) -> str:
        return f"<MV:{row},{col}>"


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
        assert list(iter_graphemes("hello")) == ["h", "e", "l", "l", "o"]

    def test_graphemes_emoji(self) -> None:
        result = list(iter_graphemes("\U0001f468\u200d\U0001f33e"))
        assert len(result) == 1

    def test_display_width_ascii(self) -> None:
        assert wcswidth("hello") == 5

    def test_display_width_cjk(self) -> None:
        assert wcswidth("\u4e16\u754c") == 4

    def test_display_width_empty(self) -> None:
        assert wcswidth("") == 0


class TestLineEditResult:
    def test_defaults(self) -> None:
        r = LineEditResult()
        assert r.line is None
        assert r.eof is False
        assert r.interrupt is False
        assert r.changed is False

    def test_accept(self) -> None:
        r = LineEditResult(line="hello", changed=True)
        assert r.line == "hello"
        assert r.changed is True

    def test_display_state_defaults(self) -> None:
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

    def test_ctrl_d_single_undo(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_HOME)
        before = len(ed._undo_stack)
        ed.feed_key(_CTRL_D)
        assert len(ed._undo_stack) - before == 1

    def test_feed_key_multi_grapheme_hits_limit_mid_insertion(self) -> None:
        ed = LineEditor(limit=2)
        ed.feed_key("abc")
        assert ed.line == "ab"

    def test_insert_text_hits_limit_mid_insertion(self) -> None:
        ed = LineEditor(limit=2)
        ed.insert_text("abc")
        assert ed.line == "ab"

    def test_insert_text_already_at_limit(self) -> None:
        ed = LineEditor(limit=2)
        ed.feed_key("a")
        ed.feed_key("b")
        r = ed.insert_text("x")
        assert r.changed is False
        assert ed.line == "ab"

    def test_insert_text_filters_control_chars(self) -> None:
        ed = LineEditor()
        ed.insert_text("a\x01b")
        assert ed.line == "ab"

    def test_insert_text_empty_string(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        r = ed.insert_text("")
        assert r.changed is False
        assert ed.line == "a"

    def test_insert_text_only_control_chars(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        r = ed.insert_text("\x01\x02")
        assert r.changed is False
        assert ed.line == "a"


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

    def test_move_right_at_end(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key(_key("KEY_CTRL_F"))
        r = ed.feed_key(_key("KEY_CTRL_F"))
        assert r.changed is False

    def test_home_already_at_start(self) -> None:
        ed = LineEditor()
        r = ed.feed_key(_HOME)
        assert r.changed is False

    def test_end_already_at_end(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        r = ed.feed_key(_END)
        assert r.changed is False


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

    def test_kill_line_at_position_zero(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_HOME)
        r = ed.feed_key(_CTRL_U)
        assert r.changed is False
        assert ed.line == "ab"
        assert len(ed._kill_ring) == 0

    def test_kill_line_empty_buffer(self) -> None:
        ed = LineEditor()
        r = ed.feed_key(_CTRL_U)
        assert r.changed is False

    def test_kill_ring_capped_at_64(self) -> None:
        ed = LineEditor()
        for i in range(70):
            ed.feed_key(str(i % 10))
            ed.feed_key(_CTRL_K)
            ed.feed_key(_HOME)
        assert len(ed._kill_ring) == 64

    def test_kill_word_back_at_start(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key(_HOME)
        r = ed.feed_key(_CTRL_W)
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

    def test_undo_delete(self) -> None:
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_HOME)
        ed.feed_key(_DELETE)
        assert ed.line == "b"
        ed.feed_key(_CTRL_Z)
        assert ed.line == "ab"

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
        ed = LineEditor(history=h, password=True)
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
        ed = LineEditor(history=h, password=True)
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

    def test_accept_suggestion_at_end_no_match(self) -> None:
        ed = LineEditor()
        for ch in "hello":
            ed.feed_key(ch)
        r = ed.feed_key(_RIGHT)
        assert r.changed is False
        assert ed.line == "hello"

    def test_accept_suggestion_mid_line(self) -> None:
        h = History()
        h.add("hello world")
        ed = LineEditor(history=h)
        for ch in "hello":
            ed.feed_key(ch)
        ed.feed_key(_LEFT)
        r = ed.feed_key(_RIGHT)
        assert r.changed is True
        assert ed._cursor == 5
        assert ed.line == "hello"


class TestLineEditorPasswordMode:
    def test_masked_display(self) -> None:
        ed = LineEditor(password=True)
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

    def test_password_cursor_with_wide_char(self) -> None:
        ed = LineEditor(password=True, password_char="\u4e16")
        ed.feed_key("a")
        ed.feed_key("b")
        ds = ed.display
        assert ds.cursor == 4
        assert wcswidth(ds.text) == 4

    def test_password_cursor_after_left(self) -> None:
        ed = LineEditor(password=True, password_char="\u4e16")
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key("c")
        ed.feed_key(_LEFT)
        ds = ed.display
        assert ds.cursor == 4

    def test_password_enter_not_saved(self) -> None:
        h = History()
        ed = LineEditor(history=h)
        ed.set_password_mode(True)
        ed.feed_key("p")
        ed.feed_key("w")
        r = ed.feed_key(_ENTER)
        assert r.line == "pw"
        assert h.entries == []


class TestLineEditorKeymap:
    def test_custom_keymap_override(self) -> None:
        called = []

        def custom_handler(editor):
            called.append(True)
            return LineEditResult()

        ed = LineEditor(keymap={"KEY_ENTER": custom_handler})
        ed.feed_key("a")
        ed.feed_key(_ENTER)
        assert called == [True]
        assert ed.line == "a"

    def test_custom_keymap_adds_binding(self) -> None:
        called = []

        def custom_handler(editor):
            called.append(True)
            return LineEditResult()

        _F1 = _key("KEY_F1")
        ed = LineEditor(keymap={"KEY_F1": custom_handler})
        ed.feed_key(_F1)
        assert called == [True]

    def test_custom_keymap_disable_binding(self) -> None:
        ed = LineEditor(keymap={"KEY_CTRL_C": None})
        ed.feed_key("a")
        r = ed.feed_key(_CTRL_C)
        assert r.interrupt is False
        assert r.changed is False
        assert ed.line == "a"


class TestApplyHscroll:
    def test_no_scroll_needed(self) -> None:
        ds = _apply_hscroll("hello", "", 5, 20)
        assert ds.text == "hello"
        assert ds.cursor == 5
        assert ds.suggestion == ""
        assert ds.overflow_left is False
        assert ds.overflow_right is False

    def test_text_with_suggestion_fits(self) -> None:
        ds = _apply_hscroll("he", "llo world", 2, 20)
        assert ds.text == "he"
        assert ds.suggestion == "llo world"
        assert ds.overflow_left is False
        assert ds.overflow_right is False

    def test_text_overflows_right(self) -> None:
        ds = _apply_hscroll("abcdefghij", "", 3, 5)
        assert ds.overflow_right is True
        assert len(ds.text) <= 5

    def test_cursor_at_end_scrolls(self) -> None:
        text = "a" * 30
        ds = _apply_hscroll(text, "", 30, 10)
        assert ds.overflow_left is True
        assert ds.cursor >= 0
        assert ds.cursor <= 10

    def test_cursor_at_start_no_left_clip(self) -> None:
        text = "a" * 30
        ds = _apply_hscroll(text, "", 0, 10)
        assert ds.overflow_left is False
        assert ds.overflow_right is True
        assert ds.cursor == 0

    def test_suggestion_clipped(self) -> None:
        ds = _apply_hscroll("ab", "cdefghijklmnop", 2, 8)
        assert ds.overflow_right is True
        total = wcswidth(ds.text) + wcswidth(ds.suggestion)
        assert total <= 8

    def test_custom_ellipsis(self) -> None:
        ds = _apply_hscroll("a" * 20, "", 20, 10, ellipsis="...")
        assert ds.overflow_left is True

    def test_empty_text(self) -> None:
        ds = _apply_hscroll("", "", 0, 10)
        assert ds.text == ""
        assert ds.cursor == 0
        assert ds.overflow_left is False
        assert ds.overflow_right is False


class TestLineEditorMaxWidth:
    def test_no_max_width_no_clipping(self) -> None:
        ed = LineEditor()
        for ch in "hello world this is a long line":
            ed.feed_key(ch)
        ds = ed.display
        assert ds.overflow_left is False
        assert ds.overflow_right is False

    def test_max_width_clips(self) -> None:
        ed = LineEditor(max_width=10)
        for ch in "abcdefghijklmnop":
            ed.feed_key(ch)
        ds = ed.display
        assert ds.overflow_left is True
        total = wcswidth(ds.text) + wcswidth(ds.suggestion)
        assert total <= 10

    def test_max_width_short_text_no_clip(self) -> None:
        ed = LineEditor(max_width=20)
        for ch in "hi":
            ed.feed_key(ch)
        ds = ed.display
        assert ds.overflow_left is False
        assert ds.overflow_right is False
        assert ds.text == "hi"

    def test_max_width_cursor_stays_visible(self) -> None:
        ed = LineEditor(max_width=10)
        for ch in "a" * 50:
            ed.feed_key(ch)
        ds = ed.display
        assert 0 <= ds.cursor <= 10

    def test_max_width_home_shows_start(self) -> None:
        ed = LineEditor(max_width=10)
        for ch in "abcdefghijklmnop":
            ed.feed_key(ch)
        ed.feed_key(_HOME)
        ds = ed.display
        assert ds.overflow_left is False
        assert ds.cursor == 0

    def test_max_width_updated_dynamically(self) -> None:
        ed = LineEditor(max_width=5)
        for ch in "abcdefghij":
            ed.feed_key(ch)
        assert ed.display.overflow_left is True
        ed.max_width = 20
        ds = ed.display
        assert ds.overflow_left is False

    def test_max_width_password_mode(self) -> None:
        ed = LineEditor(max_width=5, password=True)
        for ch in "abcdefghij":
            ed.feed_key(ch)
        ds = ed.display
        assert PASSWORD_CHAR in ds.text
        assert wcswidth(ds.text) <= 5

    def test_limit_bell_fires_once_then_resets(self) -> None:
        ed = LineEditor(limit=2)
        ed.feed_key("a")
        ed.feed_key("b")
        r = ed.feed_key("c")
        assert r.bell == "\a"
        r = ed.feed_key("d")
        assert r.bell == ""
        ed.feed_key(_BACKSPACE)
        r = ed.feed_key("x")
        r = ed.feed_key("y")
        assert r.bell == "\a"

    def test_needs_hscroll_false_when_limit_fits(self) -> None:
        ed = LineEditor(max_width=10, limit=5)
        assert ed._needs_hscroll() is False
        ds = ed.display
        assert ds.overflow_left is False
        assert ds.overflow_right is False


class TestStatefulHScroll:
    def test_no_scroll_while_inside_window(self) -> None:
        ed = LineEditor(max_width=20)
        for ch in "abcdef":
            ed.feed_key(ch)
        ds = ed.display
        assert ed._scroll_offset == 0
        assert ds.cursor == 6
        assert ds.overflow_left is False

    def test_first_scroll_at_field_boundary(self) -> None:
        ed = LineEditor(max_width=20)
        for ch in "a" * 19:
            ed.feed_key(ch)
        ds = ed.display
        assert ed._scroll_offset == 0
        assert ds.cursor == 19
        ed.feed_key("b")
        ds = ed.display
        assert ed._scroll_offset > 0
        assert ds.cursor < 15

    def test_typing_across_full_width_then_jump(self) -> None:
        ed = LineEditor(max_width=40)
        for i in range(50):
            ed.feed_key(chr(ord("a") + (i % 26)))
            ds = ed.display
        assert ed._scroll_offset > 0
        assert 0 <= ds.cursor <= 40

    def test_scroll_left_on_home(self) -> None:
        ed = LineEditor(max_width=20)
        for ch in "a" * 40:
            ed.feed_key(ch)
        _ = ed.display
        assert ed._scroll_offset > 0
        ed.feed_key(_HOME)
        ds = ed.display
        assert ed._scroll_offset == 0
        assert ds.cursor == 0
        assert ds.overflow_left is False

    def test_large_jump_fewer_scrolls(self) -> None:
        ed = LineEditor(max_width=40, scroll_jump=0.75)
        scrolls = 0
        for ch in "a" * 80:
            old = ed._scroll_offset
            ed.feed_key(ch)
            _ = ed.display
            if ed._scroll_offset != old:
                scrolls += 1
        assert scrolls < 5

    def test_small_jump_more_scrolls(self) -> None:
        ed = LineEditor(max_width=40, scroll_jump=0.1)
        scrolls = 0
        for ch in "a" * 80:
            old = ed._scroll_offset
            ed.feed_key(ch)
            _ = ed.display
            if ed._scroll_offset != old:
                scrolls += 1
        assert scrolls > 5

    def test_default_jump_makes_room(self) -> None:
        ed = LineEditor(max_width=40)
        for ch in "a" * 40:
            ed.feed_key(ch)
        ds = ed.display
        assert ed._scroll_offset > 0
        assert ds.cursor < 25

    def test_scroll_left_near_left_edge(self) -> None:
        ed = LineEditor(max_width=20)
        for ch in "a" * 30:
            ed.feed_key(ch)
        _ = ed.display
        right_offset = ed._scroll_offset
        for _ in range(25):
            ed.feed_key(_LEFT)
        _ = ed.display
        assert ed._scroll_offset < right_offset

    def test_apply_hscroll_with_explicit_scroll_offset(self) -> None:
        ds = _apply_hscroll("a" * 30, "", 25, 10, scroll_offset=20)
        assert ds.overflow_left is True
        assert ds.cursor == 25 - 20 + wcswidth("\u2026")

    def test_apply_hscroll_scroll_offset_zero(self) -> None:
        ds = _apply_hscroll("a" * 30, "", 3, 10, scroll_offset=0)
        assert ds.overflow_left is False
        assert ds.overflow_right is True
        assert ds.cursor == 3

    def test_enter_resets_scroll_offset(self) -> None:
        ed = LineEditor(max_width=10)
        for ch in "a" * 20:
            ed.feed_key(ch)
        _ = ed.display
        assert ed._scroll_offset > 0
        ed.feed_key(_ENTER)
        assert ed._scroll_offset == 0

    def test_ctrl_c_resets_scroll_offset(self) -> None:
        ed = LineEditor(max_width=10)
        for ch in "a" * 20:
            ed.feed_key(ch)
        _ = ed.display
        assert ed._scroll_offset > 0
        ed.feed_key(_CTRL_C)
        assert ed._scroll_offset == 0

    def test_small_field_width_10(self) -> None:
        ed = LineEditor(max_width=10)
        for ch in "a" * 15:
            ed.feed_key(ch)
        ds = ed.display
        assert 0 <= ds.cursor <= 10
        assert ed._scroll_offset > 0

    def test_password_mode_stateful_scroll(self) -> None:
        ed = LineEditor(max_width=10, password=True)
        for ch in "a" * 20:
            ed.feed_key(ch)
        ds = ed.display
        assert ed._scroll_offset > 0
        assert 0 <= ds.cursor <= 10

    def test_clear_resets_scroll_offset(self) -> None:
        ed = LineEditor(max_width=10)
        for ch in "a" * 30:
            ed.feed_key(ch)
        _ = ed.display
        assert ed._scroll_offset > 0
        ed.clear()
        assert ed._scroll_offset == 0


class TestRender:
    def test_render_basic(self) -> None:
        mt = MockTerminal()
        ed = LineEditor()
        for ch in "hello":
            ed.feed_key(ch)
        out = ed.render(mt, 3, 40)
        assert "<MV:3,0>" in out
        assert "hello" in out
        assert "<MV:3,5>" in out
        assert "<NORMAL>" in out

    def test_render_with_suggestion(self) -> None:
        mt = MockTerminal()
        h = History()
        h.add("hello world")
        ed = LineEditor(history=h)
        for ch in "he":
            ed.feed_key(ch)
        out = ed.render(mt, 0, 40)
        assert "he" in out
        assert "llo world" in out
        assert ed.suggestion_sgr in out

    def test_render_overflow_left_right(self) -> None:
        mt = MockTerminal()
        ed = LineEditor(max_width=10)
        for ch in "abcdefghijklmnop":
            ed.feed_key(ch)
        ed.feed_key(_HOME)
        ed.feed_key(_RIGHT)
        for ch in "xyz":
            ed.feed_key(ch)
        out = ed.render(mt, 0, 10)
        ds = ed.display
        if ds.overflow_left:
            assert ed.ellipsis in out
        if ds.overflow_right:
            assert ed.ellipsis in out

    def test_render_updates_prev_state(self) -> None:
        mt = MockTerminal()
        ed = LineEditor()
        for ch in "abc":
            ed.feed_key(ch)
        ed.render(mt, 0, 40)
        assert ed._prev_cursor == 3
        assert ed._prev_content_w == 3
        assert ed._prev_overflow == (False, False)

    def test_render_padding(self) -> None:
        mt = MockTerminal()
        ed = LineEditor()
        ed.feed_key("a")
        out = ed.render(mt, 0, 10)
        assert " " * 9 in out

    def test_render_empty_text(self) -> None:
        mt = MockTerminal()
        ed = LineEditor()
        out = ed.render(mt, 0, 10)
        assert "<MV:0,0>" in out
        assert " " * 10 in out


class TestRenderInsert:
    def test_render_insert_at_end(self) -> None:
        mt = MockTerminal()
        ed = LineEditor()
        for ch in "hel":
            ed.feed_key(ch)
        ed.render(mt, 0, 40)
        ed.feed_key("l")
        result = ed.render_insert(mt, 0, "l")
        assert result is not None
        assert "l" in result

    def test_render_insert_mid_buffer_returns_none(self) -> None:
        mt = MockTerminal()
        ed = LineEditor()
        for ch in "abc":
            ed.feed_key(ch)
        ed.render(mt, 0, 40)
        ed.feed_key(_LEFT)
        ed.feed_key("x")
        result = ed.render_insert(mt, 0, "x")
        assert result is None

    def test_render_insert_overflow_change_returns_none(self) -> None:
        mt = MockTerminal()
        ed = LineEditor(max_width=5)
        for ch in "abcd":
            ed.feed_key(ch)
        ed.render(mt, 0, 5)
        ed.feed_key("e")
        ed.feed_key("f")
        result = ed.render_insert(mt, 0, "f")
        assert result is None

    def test_render_insert_returns_none_when_scroll_changes(self) -> None:
        mt = MockTerminal()
        ed = LineEditor(max_width=10)
        for ch in "a" * 9:
            ed.feed_key(ch)
        ed.render(mt, 0, 10)
        old_offset = ed._scroll_offset
        for ch in "bbb":
            ed.feed_key(ch)
        _ = ed.display
        assert ed._scroll_offset != old_offset
        result = ed.render_insert(mt, 0, "b")
        assert result is None

    def test_render_insert_clears_stale_suggestion(self) -> None:
        mt = MockTerminal()
        h = History()
        h.add("hello world")
        ed = LineEditor(history=h)
        for ch in "he":
            ed.feed_key(ch)
        ed.render(mt, 0, 40)
        ed.feed_key("l")
        result = ed.render_insert(mt, 0, "l")
        assert result is not None

    def test_render_insert_updates_prev_state(self) -> None:
        mt = MockTerminal()
        ed = LineEditor()
        for ch in "ab":
            ed.feed_key(ch)
        ed.render(mt, 0, 40)
        ed.feed_key("c")
        ed.render_insert(mt, 0, "c")
        assert ed._prev_cursor == 3
        assert ed._prev_content_w == 3
        assert ed._prev_overflow == (False, False)


class TestRenderBackspace:
    def test_render_backspace_at_end(self) -> None:
        mt = MockTerminal()
        ed = LineEditor()
        for ch in "abc":
            ed.feed_key(ch)
        ed.render(mt, 0, 40)
        ed.feed_key(_BACKSPACE)
        result = ed.render_backspace(mt, 0)
        assert result is not None

    def test_render_backspace_mid_buffer_returns_none(self) -> None:
        mt = MockTerminal()
        ed = LineEditor()
        for ch in "abc":
            ed.feed_key(ch)
        ed.render(mt, 0, 40)
        ed.feed_key(_LEFT)
        ed.feed_key(_BACKSPACE)
        result = ed.render_backspace(mt, 0)
        assert result is None

    def test_render_backspace_overflow_change_returns_none(self) -> None:
        mt = MockTerminal()
        ed = LineEditor(max_width=5)
        for ch in "abcdef":
            ed.feed_key(ch)
        ed.render(mt, 0, 5)
        for _ in range(4):
            ed.feed_key(_BACKSPACE)
        result = ed.render_backspace(mt, 0)
        assert result is None

    def test_render_backspace_returns_none_when_scroll_changes(self) -> None:
        mt = MockTerminal()
        ed = LineEditor(max_width=10)
        for ch in "a" * 20:
            ed.feed_key(ch)
        ed.render(mt, 0, 10)
        old_offset = ed._scroll_offset
        for _ in range(15):
            ed.feed_key(_BACKSPACE)
        _ = ed.display
        assert ed._scroll_offset != old_offset
        result = ed.render_backspace(mt, 0)
        assert result is None

    def test_render_backspace_erases_trailing(self) -> None:
        mt = MockTerminal()
        ed = LineEditor()
        for ch in "abc":
            ed.feed_key(ch)
        ed.render(mt, 0, 40)
        ed.feed_key(_BACKSPACE)
        result = ed.render_backspace(mt, 0)
        assert result is not None
        assert " " in result

    def test_render_backspace_updates_prev_state(self) -> None:
        mt = MockTerminal()
        ed = LineEditor()
        for ch in "abc":
            ed.feed_key(ch)
        ed.render(mt, 0, 40)
        ed.feed_key(_BACKSPACE)
        ed.render_backspace(mt, 0)
        assert ed._prev_cursor == 2
        assert ed._prev_content_w == 2
        assert ed._prev_overflow == (False, False)

    def test_render_backspace_with_suggestion(self) -> None:
        mt = MockTerminal()
        h = History()
        h.add("hello world")
        ed = LineEditor(history=h)
        for ch in "hel":
            ed.feed_key(ch)
        ed.render(mt, 0, 40)
        ed.feed_key(_BACKSPACE)
        result = ed.render_backspace(mt, 0)
        assert result is not None
        assert ed.suggestion_sgr in result
