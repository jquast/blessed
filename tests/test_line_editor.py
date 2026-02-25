"""Tests for blessed.line_editor."""

# 3rd party
import pytest
from wcwidth import iter_graphemes, width as wcswidth

# local
from blessed.line_editor import PASSWORD_CHAR, LineEditor
from blessed.line_editor import LineHistory as History
from blessed.line_editor import (DisplayState,
                                 LineEditResult,
                                 _apply_hscroll)


class MockTerminal:  # pylint: disable=too-few-public-methods
    """Minimal terminal stub for render method tests."""

    normal = "<NORMAL>"

    @staticmethod
    def move_yx(row: int, col: int) -> str:
        """Return a position marker string."""
        return f"<MV:{row},{col}>"


def _key(name: str) -> str:
    """Create a fake Keystroke-like object with a .name attribute."""

    class FakeKey(str):  # pylint: disable=missing-class-docstring
        pass

    k = FakeKey("")
    k.name = name  # type: ignore[attr-defined]  # pylint: disable=attribute-defined-outside-init
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
    """Test grapheme splitting and display width helpers."""

    def test_graphemes_ascii(self) -> None:
        """Test grapheme splitting of ASCII text."""
        assert list(iter_graphemes("hello")) == ["h", "e", "l", "l", "o"]

    def test_graphemes_emoji(self) -> None:
        """Test grapheme splitting of emoji with ZWJ sequence."""
        result = list(iter_graphemes("\U0001f468\u200d\U0001f33e"))
        assert len(result) == 1

    @pytest.mark.parametrize("text,expected", [
        ("hello", 5),
        ("\u4e16\u754c", 4),
        ("", 0),
    ])
    def test_display_width(self, text: str, expected: int) -> None:
        """Test display width of various text inputs."""
        assert wcswidth(text) == expected


class TestLineEditResult:
    """Test LineEditResult and DisplayState dataclasses."""

    def test_defaults(self) -> None:
        """Test LineEditResult default field values."""
        r = LineEditResult()
        assert r.line is None
        assert r.eof is False
        assert r.interrupt is False
        assert r.changed is False

    def test_accept(self) -> None:
        """Test LineEditResult with accepted line and changed flag."""
        r = LineEditResult(line="hello", changed=True)
        assert r.line == "hello"
        assert r.changed is True

    def test_display_state_defaults(self) -> None:
        """Test DisplayState default field values."""
        d = DisplayState()
        assert d.text == ""
        assert d.cursor == 0
        assert d.suggestion == ""


class TestHistory:
    """Test LineHistory add, search, and navigation."""

    def test_add_and_entries(self) -> None:
        """Test adding entries to history."""
        h = History()
        h.add("alpha")
        h.add("bravo")
        assert h.entries == ["alpha", "bravo"]

    def test_add_skips_empty(self) -> None:
        """Test that empty strings are not added to history."""
        h = History()
        h.add("")
        assert not h.entries

    def test_add_deduplicates_consecutive(self) -> None:
        """Test that consecutive duplicate entries are deduplicated."""
        h = History()
        h.add("x")
        h.add("x")
        h.add("y")
        h.add("y")
        assert h.entries == ["x", "y"]

    def test_max_entries(self) -> None:
        """Test that history respects max_entries limit."""
        h = History(max_entries=3)
        for i in range(5):
            h.add(str(i))
        assert h.entries == ["2", "3", "4"]

    def test_search_prefix(self) -> None:
        """Test prefix search returns most recent match."""
        h = History()
        h.add("east")
        h.add("enter cave")
        h.add("eat bread")
        assert h.search_prefix("ea") == "eat bread"
        assert h.search_prefix("ent") == "enter cave"
        assert h.search_prefix("xyz") is None
        assert h.search_prefix("") is None

    def test_search_prefix_skips_exact_match(self) -> None:
        """Test prefix search skips exact match of query."""
        h = History()
        h.add("hello")
        assert h.search_prefix("hello") is None

    def test_nav_up_down(self) -> None:
        """Test history navigation up and down through entries."""
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
        """Test navigation returns None with empty history."""
        h = History()
        h.nav_start("")
        assert h.nav_up() is None


class TestLineEditorBasicEditing:
    """Test basic character insertion, deletion, and line submission."""

    def test_insert_chars(self) -> None:
        """Test inserting characters into the buffer."""
        ed = LineEditor()
        ed.feed_key("h")
        ed.feed_key("i")
        assert ed.line == "hi"
        assert ed.display.cursor == 2

    def test_enter_returns_line(self) -> None:
        """Test enter key returns the current line."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        r = ed.feed_key(_ENTER)
        assert r.line == "ab"
        assert r.changed is True
        assert ed.line == ""

    def test_enter_empty_line(self) -> None:
        """Test enter on empty buffer returns empty string."""
        ed = LineEditor()
        r = ed.feed_key(_ENTER)
        assert r.line == ""

    def test_backspace(self) -> None:
        """Test backspace removes last character."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key("c")
        r = ed.feed_key(_BACKSPACE)
        assert r.changed is True
        assert ed.line == "ab"

    def test_delete(self) -> None:
        """Test delete removes character at cursor."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_HOME)
        r = ed.feed_key(_DELETE)
        assert r.changed is True
        assert ed.line == "b"

    def test_insert_text(self) -> None:
        """Test bulk text insertion via insert_text."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.insert_text("bcd")
        assert ed.line == "abcd"
        assert ed.display.cursor == 4

    def test_clear(self) -> None:
        """Test clear resets buffer and cursor."""
        ed = LineEditor()
        ed.feed_key("h")
        ed.feed_key("i")
        ed.clear()
        assert ed.line == ""
        assert ed.display.cursor == 0

    def test_unknown_key_unchanged(self) -> None:
        """Test unrecognized key reports no change."""
        ed = LineEditor()
        r = ed.feed_key("\x00")
        assert r.changed is False
        assert r.line is None

    def test_ctrl_c_clears_and_interrupts(self) -> None:
        """Test Ctrl-C clears buffer and sets interrupt flag."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        r = ed.feed_key(_CTRL_C)
        assert r.interrupt is True
        assert r.changed is True
        assert ed.line == ""

    def test_ctrl_d_eof_on_empty(self) -> None:
        """Test Ctrl-D on empty buffer sets EOF flag."""
        ed = LineEditor()
        r = ed.feed_key(_CTRL_D)
        assert r.eof is True

    def test_ctrl_d_deletes_on_nonempty(self) -> None:
        """Test Ctrl-D on non-empty buffer deletes character at cursor."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_HOME)
        r = ed.feed_key(_CTRL_D)
        assert r.eof is False
        assert r.changed is True
        assert ed.line == "b"

    def test_ctrl_d_single_undo(self) -> None:
        """Test Ctrl-D delete pushes exactly one undo entry."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_HOME)
        before = len(ed._undo_stack)
        ed.feed_key(_CTRL_D)
        assert len(ed._undo_stack) - before == 1

    def test_feed_key_multi_grapheme_hits_limit(self) -> None:
        """Test feed_key with multi-char string stops at limit."""
        ed = LineEditor(limit=2)
        ed.feed_key("abc")
        assert ed.line == "ab"

    def test_insert_text_hits_limit(self) -> None:
        """Test insert_text stops at character limit."""
        ed = LineEditor(limit=2)
        ed.insert_text("abc")
        assert ed.line == "ab"

    def test_insert_text_already_at_limit(self) -> None:
        """Test insert_text when buffer is already at limit."""
        ed = LineEditor(limit=2)
        ed.feed_key("a")
        ed.feed_key("b")
        r = ed.insert_text("x")
        assert r.changed is False
        assert ed.line == "ab"

    @pytest.mark.parametrize("text,expected", [
        ("a\x01b", "ab"),
        ("", ""),
        ("\x01\x02", ""),
    ])
    def test_insert_text_filtering(self, text: str, expected: str) -> None:
        """Test insert_text filters control characters."""
        ed = LineEditor()
        ed.insert_text(text)
        assert ed.line == expected


@pytest.mark.parametrize("setup_text,key", [
    ("", _BACKSPACE),
    ("x", _DELETE),
    ("", _LEFT),
    ("", _WORD_LEFT),
    ("x", _WORD_RIGHT),
    ("", _HOME),
    ("a", _END),
    ("", _CTRL_Y),
    ("", _CTRL_Z),
    ("", _DOWN),
])
def test_no_change_boundary(setup_text: str, key: str) -> None:
    """Test key at boundary reports changed=False."""
    ed = LineEditor()
    for ch in setup_text:
        ed.feed_key(ch)
    r = ed.feed_key(key)
    assert r.changed is False


class TestLineEditorCursorMovement:
    """Test cursor movement keys and word navigation."""

    def test_left_right(self) -> None:
        """Test left and right arrow cursor movement."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_LEFT)
        assert ed.display.cursor == 1
        ed.feed_key(_RIGHT)
        assert ed.display.cursor == 2

    @pytest.mark.parametrize("key", [_HOME, _CTRL_A])
    def test_home_keys(self, key: str) -> None:
        """Test Home/Ctrl-A moves cursor to start."""
        ed = LineEditor()
        for ch in "abc":
            ed.feed_key(ch)
        ed.feed_key(key)
        assert ed.display.cursor == 0

    @pytest.mark.parametrize("key", [_END, _CTRL_E])
    def test_end_keys(self, key: str) -> None:
        """Test End/Ctrl-E moves cursor to end."""
        ed = LineEditor()
        for ch in "abc":
            ed.feed_key(ch)
        ed.feed_key(_HOME)
        ed.feed_key(key)
        assert ed.display.cursor == 3

    def test_word_left(self) -> None:
        """Test word-left jumps to previous word boundary."""
        ed = LineEditor()
        for ch in "hello world":
            ed.feed_key(ch)
        ed.feed_key(_WORD_LEFT)
        assert ed.line[ed._cursor:] == "world"
        ed.feed_key(_WORD_LEFT)
        assert ed._cursor == 0

    def test_word_right(self) -> None:
        """Test word-right jumps to next word boundary."""
        ed = LineEditor()
        for ch in "hello world":
            ed.feed_key(ch)
        ed.feed_key(_HOME)
        ed.feed_key(_WORD_RIGHT)
        assert ed.line[:ed._cursor] == "hello"
        ed.feed_key(_WORD_RIGHT)
        assert ed._cursor == 11

    def test_insert_at_cursor(self) -> None:
        """Test inserting a character at mid-buffer cursor position."""
        ed = LineEditor()
        for ch in "ac":
            ed.feed_key(ch)
        ed.feed_key(_LEFT)
        ed.feed_key("b")
        assert ed.line == "abc"
        assert ed.display.cursor == 2

    def test_ctrl_f_at_end(self) -> None:
        """Test Ctrl-F at end reports no change."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key(_key("KEY_CTRL_F"))
        r = ed.feed_key(_key("KEY_CTRL_F"))
        assert r.changed is False


class TestLineEditorGraphemeEditing:
    """Test editing operations on multi-codepoint grapheme clusters."""

    def test_backspace_emoji_with_skin_tone(self) -> None:
        """Test backspace removes entire emoji with skin tone modifier."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("\U0001f44b\U0001f3fb")
        assert len(ed._buf) == 2
        ed.feed_key(_BACKSPACE)
        assert ed.line == "a"
        assert len(ed._buf) == 1

    def test_backspace_flag_emoji(self) -> None:
        """Test backspace removes entire flag emoji."""
        ed = LineEditor()
        ed.feed_key("\U0001f1fa\U0001f1f8")
        ed.feed_key(_BACKSPACE)
        assert ed.line == ""

    def test_insert_text_grapheme_clusters(self) -> None:
        """Test insert_text splits ZWJ sequences into grapheme clusters."""
        ed = LineEditor()
        ed.insert_text("a\U0001f468\u200d\U0001f33eb")
        assert len(ed._buf) == 3
        assert ed._buf[1] == "\U0001f468\u200d\U0001f33e"

    def test_cursor_movement_over_grapheme_clusters(self) -> None:
        """Test cursor moves over grapheme clusters as single units."""
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
        """Test display width accounts for double-width CJK characters."""
        ed = LineEditor()
        ed.feed_key("\u4e16")
        ed.feed_key("\u754c")
        assert ed.display.cursor == 4
        assert ed.display.text == "\u4e16\u754c"

    def test_cjk_cursor_after_left(self) -> None:
        """Test cursor position after left over CJK character."""
        ed = LineEditor()
        ed.feed_key("\u4e16")
        ed.feed_key("\u754c")
        ed.feed_key(_LEFT)
        assert ed.display.cursor == 2

    def test_backspace_cjk(self) -> None:
        """Test backspace removes a CJK character."""
        ed = LineEditor()
        ed.feed_key("\u4e16")
        ed.feed_key("\u754c")
        ed.feed_key(_BACKSPACE)
        assert ed.line == "\u4e16"
        assert ed.display.cursor == 2


class TestLineEditorKillRing:
    """Test kill, yank, and kill ring operations."""

    def test_kill_to_end(self) -> None:
        """Test Ctrl-K removes text from cursor to end."""
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
        """Test Ctrl-U removes text from start to cursor."""
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
        """Test Ctrl-W removes previous word."""
        ed = LineEditor()
        for ch in "hello world":
            ed.feed_key(ch)
        r = ed.feed_key(_CTRL_W)
        assert r.changed is True
        assert ed.line == "hello "

    def test_yank(self) -> None:
        """Test Ctrl-Y yanks last killed text back."""
        ed = LineEditor()
        for ch in "hello world":
            ed.feed_key(ch)
        ed.feed_key(_CTRL_W)
        ed.feed_key(_CTRL_Y)
        assert ed.line == "hello world"

    def test_kill_to_end_at_end(self) -> None:
        """Test Ctrl-K at end of buffer reports no change."""
        ed = LineEditor()
        ed.feed_key("a")
        r = ed.feed_key(_CTRL_K)
        assert r.changed is False

    def test_kill_line_at_position_zero(self) -> None:
        """Test Ctrl-U at position zero reports no change."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_HOME)
        r = ed.feed_key(_CTRL_U)
        assert r.changed is False
        assert ed.line == "ab"
        assert len(ed._kill_ring) == 0

    def test_kill_line_empty_buffer(self) -> None:
        """Test Ctrl-U on empty buffer reports no change."""
        ed = LineEditor()
        r = ed.feed_key(_CTRL_U)
        assert r.changed is False

    def test_kill_ring_capped_at_64(self) -> None:
        """Test kill ring is capped at 64 entries."""
        ed = LineEditor()
        for i in range(70):
            ed.feed_key(str(i % 10))
            ed.feed_key(_CTRL_K)
            ed.feed_key(_HOME)
        assert len(ed._kill_ring) == 64

    def test_kill_word_back_at_start(self) -> None:
        """Test Ctrl-W at start reports no change."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key(_HOME)
        r = ed.feed_key(_CTRL_W)
        assert r.changed is False


class TestLineEditorUndo:
    """Test undo for insert, backspace, delete, and kill operations."""

    def test_undo_insert(self) -> None:
        """Test undo reverses character insertion."""
        ed = LineEditor()
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key(_CTRL_Z)
        assert ed.line == "a"
        ed.feed_key(_CTRL_Z)
        assert ed.line == ""

    @pytest.mark.parametrize("action_keys,mid_line,restored_line", [
        (["a", "b", _BACKSPACE], "a", "ab"),
        (list("hello") + [_CTRL_U], "", "hello"),
        (["a", "b", _HOME, _DELETE], "b", "ab"),
    ])
    def test_undo_action(
        self, action_keys: list, mid_line: str, restored_line: str
    ) -> None:
        """Test undo reverses backspace, kill, and delete operations."""
        ed = LineEditor()
        for k in action_keys:
            ed.feed_key(k)
        assert ed.line == mid_line
        ed.feed_key(_CTRL_Z)
        assert ed.line == restored_line

    def test_undo_empty_stack(self) -> None:
        """Test undo with empty stack reports no change."""
        ed = LineEditor()
        r = ed.feed_key(_CTRL_Z)
        assert r.changed is False


class TestLineEditorHistory:
    """Test history navigation and submission within the editor."""

    def test_up_down(self) -> None:
        """Test up and down keys navigate history entries."""
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
        """Test up key at oldest entry reports no change."""
        h = History()
        h.add("only")
        ed = LineEditor(history=h)
        ed.feed_key(_UP)
        assert ed.line == "only"
        r = ed.feed_key(_UP)
        assert r.changed is False

    def test_enter_adds_to_history(self) -> None:
        """Test enter adds submitted line to history."""
        h = History()
        ed = LineEditor(history=h)
        ed.feed_key("x")
        ed.feed_key(_ENTER)
        assert h.entries == ["x"]

    def test_enter_password_mode_skips_history(self) -> None:
        """Test enter in password mode does not add to history."""
        h = History()
        ed = LineEditor(history=h, password=True)
        ed.feed_key("s")
        ed.feed_key("e")
        ed.feed_key("c")
        ed.feed_key(_ENTER)
        assert not h.entries


class TestLineEditorAutoSuggest:
    """Test auto-suggestion from history prefix matching."""

    def test_suggestion_from_history(self) -> None:
        """Test suggestion shows completion from history match."""
        h = History()
        h.add("hello world")
        ed = LineEditor(history=h)
        ed.feed_key("h")
        ed.feed_key("e")
        ds = ed.display
        assert ds.suggestion == "llo world"

    def test_no_suggestion_mid_line(self) -> None:
        """Test no suggestion when cursor is not at end."""
        h = History()
        h.add("hello world")
        ed = LineEditor(history=h)
        for ch in "hello":
            ed.feed_key(ch)
        ed.feed_key(_HOME)
        assert ed.display.suggestion == ""

    def test_no_suggestion_password_mode(self) -> None:
        """Test no suggestion in password mode."""
        h = History()
        h.add("secret123")
        ed = LineEditor(history=h, password=True)
        ed.feed_key("s")
        assert ed.display.suggestion == ""

    def test_accept_suggestion_via_right(self) -> None:
        """Test right arrow accepts the current suggestion."""
        h = History()
        h.add("hello world")
        ed = LineEditor(history=h)
        ed.feed_key("h")
        ed.feed_key("e")
        ed.feed_key(_RIGHT)
        assert ed.line == "hello world"

    def test_accept_suggestion_at_end_no_match(self) -> None:
        """Test right arrow at end with no suggestion reports no change."""
        ed = LineEditor()
        for ch in "hello":
            ed.feed_key(ch)
        r = ed.feed_key(_RIGHT)
        assert r.changed is False
        assert ed.line == "hello"

    def test_accept_suggestion_mid_line(self) -> None:
        """Test right arrow mid-line moves cursor without accepting."""
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
    """Test password mode display masking and behavior."""

    def test_masked_display(self) -> None:
        """Test display text is masked with password character."""
        ed = LineEditor(password=True)
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key("c")
        ds = ed.display
        assert ds.text == PASSWORD_CHAR * 3

    def test_set_password_mode(self) -> None:
        """Test enabling password mode dynamically."""
        ed = LineEditor()
        ed.set_password_mode(True)
        ed.feed_key("x")
        assert ed.display.text == PASSWORD_CHAR

    def test_password_cursor_with_wide_char(self) -> None:
        """Test cursor position with wide password character."""
        ed = LineEditor(password=True, password_char="\u4e16")
        ed.feed_key("a")
        ed.feed_key("b")
        ds = ed.display
        assert ds.cursor == 4
        assert wcswidth(ds.text) == 4

    def test_password_cursor_after_left(self) -> None:
        """Test cursor position after left in password mode."""
        ed = LineEditor(password=True, password_char="\u4e16")
        ed.feed_key("a")
        ed.feed_key("b")
        ed.feed_key("c")
        ed.feed_key(_LEFT)
        ds = ed.display
        assert ds.cursor == 4

    def test_password_enter_not_saved(self) -> None:
        """Test enter in set_password_mode does not save to history."""
        h = History()
        ed = LineEditor(history=h)
        ed.set_password_mode(True)
        ed.feed_key("p")
        ed.feed_key("w")
        r = ed.feed_key(_ENTER)
        assert r.line == "pw"
        assert not h.entries


class TestLineEditorKeymap:
    """Test custom keymap bindings and overrides."""

    def test_custom_keymap_override(self) -> None:
        """Test custom keymap overrides default key binding."""
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
        """Test custom keymap adds a new key binding."""
        called = []

        def custom_handler(editor):
            called.append(True)
            return LineEditResult()

        f1 = _key("KEY_F1")
        ed = LineEditor(keymap={"KEY_F1": custom_handler})
        ed.feed_key(f1)
        assert called == [True]

    def test_custom_keymap_disable_binding(self) -> None:
        """Test custom keymap disables a binding with None."""
        ed = LineEditor(keymap={"KEY_CTRL_C": None})
        ed.feed_key("a")
        r = ed.feed_key(_CTRL_C)
        assert r.interrupt is False
        assert r.changed is False
        assert ed.line == "a"


class TestApplyHscroll:
    """Test _apply_hscroll horizontal scrolling and clipping."""

    def test_no_scroll_needed(self) -> None:
        """Test no scrolling when text fits within width."""
        ds = _apply_hscroll("hello", "", 5, 20)
        assert ds.text == "hello"
        assert ds.cursor == 5
        assert ds.suggestion == ""
        assert ds.overflow_left is False
        assert ds.overflow_right is False

    def test_text_with_suggestion_fits(self) -> None:
        """Test text with suggestion fits within width."""
        ds = _apply_hscroll("he", "llo world", 2, 20)
        assert ds.text == "he"
        assert ds.suggestion == "llo world"
        assert ds.overflow_left is False
        assert ds.overflow_right is False

    def test_text_overflows_right(self) -> None:
        """Test text exceeding width sets overflow_right flag."""
        ds = _apply_hscroll("abcdefghij", "", 3, 5)
        assert ds.overflow_right is True
        assert len(ds.text) <= 5

    def test_cursor_at_end_scrolls(self) -> None:
        """Test cursor at end of long text sets overflow_left flag."""
        ds = _apply_hscroll("a" * 30, "", 30, 10)
        assert ds.overflow_left is True
        assert 0 <= ds.cursor <= 10

    def test_cursor_at_start_no_left_clip(self) -> None:
        """Test cursor at start does not clip left side."""
        ds = _apply_hscroll("a" * 30, "", 0, 10)
        assert ds.overflow_left is False
        assert ds.overflow_right is True
        assert ds.cursor == 0

    def test_suggestion_clipped(self) -> None:
        """Test suggestion is clipped to fit within width."""
        ds = _apply_hscroll("ab", "cdefghijklmnop", 2, 8)
        assert ds.overflow_right is True
        total = wcswidth(ds.text) + wcswidth(ds.suggestion)
        assert total <= 8

    def test_custom_ellipsis(self) -> None:
        """Test hscroll with custom ellipsis string."""
        ds = _apply_hscroll("a" * 20, "", 20, 10, ellipsis="...")
        assert ds.overflow_left is True

    def test_empty_text(self) -> None:
        """Test hscroll with empty text string."""
        ds = _apply_hscroll("", "", 0, 10)
        assert ds.text == ""
        assert ds.cursor == 0
        assert ds.overflow_left is False
        assert ds.overflow_right is False

    def test_explicit_scroll_offset(self) -> None:
        """Test _apply_hscroll with explicit non-zero scroll offset."""
        ds = _apply_hscroll("a" * 30, "", 25, 10, scroll_offset=20)
        assert ds.overflow_left is True
        assert ds.cursor == 25 - 20 + wcswidth("\u2026")

    def test_scroll_offset_zero(self) -> None:
        """Test _apply_hscroll with zero scroll offset."""
        ds = _apply_hscroll("a" * 30, "", 3, 10, scroll_offset=0)
        assert ds.overflow_left is False
        assert ds.overflow_right is True
        assert ds.cursor == 3


class TestLineEditorMaxWidth:
    """Test max_width field clipping and limit bell behavior."""

    def test_no_max_width_no_clipping(self) -> None:
        """Test no clipping when max_width is not set."""
        ed = LineEditor()
        for ch in "hello world this is a long line":
            ed.feed_key(ch)
        ds = ed.display
        assert ds.overflow_left is False
        assert ds.overflow_right is False

    def test_max_width_clips(self) -> None:
        """Test display is clipped to max_width."""
        ed = LineEditor(max_width=10)
        for ch in "abcdefghijklmnop":
            ed.feed_key(ch)
        ds = ed.display
        assert ds.overflow_left is True
        total = wcswidth(ds.text) + wcswidth(ds.suggestion)
        assert total <= 10

    def test_max_width_short_text_no_clip(self) -> None:
        """Test short text within max_width is not clipped."""
        ed = LineEditor(max_width=20)
        for ch in "hi":
            ed.feed_key(ch)
        ds = ed.display
        assert ds.overflow_left is False
        assert ds.overflow_right is False
        assert ds.text == "hi"

    def test_max_width_cursor_stays_visible(self) -> None:
        """Test cursor stays within visible max_width region."""
        ed = LineEditor(max_width=10)
        for ch in "a" * 50:
            ed.feed_key(ch)
        ds = ed.display
        assert 0 <= ds.cursor <= 10

    def test_max_width_home_shows_start(self) -> None:
        """Test Home key scrolls view to show buffer start."""
        ed = LineEditor(max_width=10)
        for ch in "abcdefghijklmnop":
            ed.feed_key(ch)
        ed.feed_key(_HOME)
        ds = ed.display
        assert ds.overflow_left is False
        assert ds.cursor == 0

    def test_max_width_updated_dynamically(self) -> None:
        """Test changing max_width dynamically updates display."""
        ed = LineEditor(max_width=5)
        for ch in "abcdefghij":
            ed.feed_key(ch)
        assert ed.display.overflow_left is True
        ed.max_width = 20
        ds = ed.display
        assert ds.overflow_left is False

    def test_max_width_password_mode(self) -> None:
        """Test max_width clipping works in password mode."""
        ed = LineEditor(max_width=5, password=True)
        for ch in "abcdefghij":
            ed.feed_key(ch)
        ds = ed.display
        assert PASSWORD_CHAR in ds.text
        assert wcswidth(ds.text) <= 5

    def test_limit_bell_fires_once_then_resets(self) -> None:
        """Test bell fires once at limit and resets after backspace."""
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
        """Test hscroll is disabled when limit fits within max_width."""
        ed = LineEditor(max_width=10, limit=5)
        assert ed._needs_hscroll() is False
        ds = ed.display
        assert ds.overflow_left is False
        assert ds.overflow_right is False


class TestStatefulHScroll:
    """Test stateful horizontal scroll offset tracking."""

    def test_no_scroll_while_inside_window(self) -> None:
        """Test no scroll offset while text fits in window."""
        ed = LineEditor(max_width=20)
        for ch in "abcdef":
            ed.feed_key(ch)
        ds = ed.display
        assert ed._scroll_offset == 0
        assert ds.cursor == 6
        assert ds.overflow_left is False

    def test_first_scroll_at_field_boundary(self) -> None:
        """Test first scroll triggers at field width boundary."""
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

    def test_typing_across_full_width(self) -> None:
        """Test cursor stays visible while typing past full width."""
        ed = LineEditor(max_width=40)
        for i in range(50):
            ed.feed_key(chr(ord("a") + (i % 26)))
            ds = ed.display
        assert ed._scroll_offset > 0
        assert 0 <= ds.cursor <= 40

    def test_scroll_left_on_home(self) -> None:
        """Test Home key resets scroll offset to zero."""
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

    @pytest.mark.parametrize("jump,expect_fewer", [
        (0.75, True),
        (0.1, False),
    ])
    def test_scroll_jump_frequency(
        self, jump: float, expect_fewer: bool
    ) -> None:
        """Test scroll_jump controls scroll event frequency."""
        ed = LineEditor(max_width=40, scroll_jump=jump)
        scrolls = 0
        for ch in "a" * 80:
            old = ed._scroll_offset
            ed.feed_key(ch)
            _ = ed.display
            if ed._scroll_offset != old:
                scrolls += 1
        if expect_fewer:
            assert scrolls < 5
        else:
            assert scrolls > 5

    def test_default_jump_makes_room(self) -> None:
        """Test default scroll_jump places cursor away from edge."""
        ed = LineEditor(max_width=40)
        for ch in "a" * 40:
            ed.feed_key(ch)
        ds = ed.display
        assert ed._scroll_offset > 0
        assert ds.cursor < 25

    def test_scroll_left_near_left_edge(self) -> None:
        """Test scrolling left when cursor approaches left edge."""
        ed = LineEditor(max_width=20)
        for ch in "a" * 30:
            ed.feed_key(ch)
        _ = ed.display
        right_offset = ed._scroll_offset
        for _ in range(25):
            ed.feed_key(_LEFT)
        _ = ed.display
        assert ed._scroll_offset < right_offset

    @pytest.mark.parametrize("reset_key", [_ENTER, _CTRL_C])
    def test_key_resets_scroll_offset(self, reset_key: str) -> None:
        """Test Enter/Ctrl-C resets scroll offset to zero."""
        ed = LineEditor(max_width=10)
        for ch in "a" * 20:
            ed.feed_key(ch)
        _ = ed.display
        assert ed._scroll_offset > 0
        ed.feed_key(reset_key)
        assert ed._scroll_offset == 0

    def test_clear_resets_scroll_offset(self) -> None:
        """Test clear resets scroll offset to zero."""
        ed = LineEditor(max_width=10)
        for ch in "a" * 30:
            ed.feed_key(ch)
        _ = ed.display
        assert ed._scroll_offset > 0
        ed.clear()
        assert ed._scroll_offset == 0

    @pytest.mark.parametrize("password", [False, True])
    def test_small_field_scrolls(self, password: bool) -> None:
        """Test scrolling in a small 10-column field."""
        ed = LineEditor(max_width=10, password=password)
        for ch in "a" * 15:
            ed.feed_key(ch)
        ds = ed.display
        assert 0 <= ds.cursor <= 10
        assert ed._scroll_offset > 0


class TestRender:
    """Test render method output sequences."""

    def test_render_basic(self) -> None:
        """Test render produces move, text, and normal sequences."""
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
        """Test render includes suggestion text with SGR styling."""
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
        """Test render shows ellipsis indicators on overflow."""
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
        """Test render updates previous state tracking fields."""
        mt = MockTerminal()
        ed = LineEditor()
        for ch in "abc":
            ed.feed_key(ch)
        ed.render(mt, 0, 40)
        assert ed._prev_cursor == 3
        assert ed._prev_content_w == 3
        assert ed._prev_overflow == (False, False)

    def test_render_padding(self) -> None:
        """Test render pads remaining width with spaces."""
        mt = MockTerminal()
        ed = LineEditor()
        ed.feed_key("a")
        out = ed.render(mt, 0, 10)
        assert " " * 9 in out

    def test_render_empty_text(self) -> None:
        """Test render with empty buffer produces blank padding."""
        mt = MockTerminal()
        ed = LineEditor()
        out = ed.render(mt, 0, 10)
        assert "<MV:0,0>" in out
        assert " " * 10 in out


class TestRenderInsert:
    """Test render_insert incremental rendering optimization."""

    def test_render_insert_at_end(self) -> None:
        """Test render_insert produces output for append at end."""
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
        """Test render_insert returns None for mid-buffer insert."""
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
        """Test render_insert returns None when overflow state changes."""
        mt = MockTerminal()
        ed = LineEditor(max_width=5)
        for ch in "abcd":
            ed.feed_key(ch)
        ed.render(mt, 0, 5)
        ed.feed_key("e")
        ed.feed_key("f")
        result = ed.render_insert(mt, 0, "f")
        assert result is None

    def test_render_insert_scroll_change_returns_none(self) -> None:
        """Test render_insert returns None when scroll offset changes."""
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
        """Test render_insert clears previous suggestion text."""
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
        """Test render_insert updates previous state tracking fields."""
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
    """Test render_backspace incremental rendering optimization."""

    def test_render_backspace_at_end(self) -> None:
        """Test render_backspace produces output for deletion at end."""
        mt = MockTerminal()
        ed = LineEditor()
        for ch in "abc":
            ed.feed_key(ch)
        ed.render(mt, 0, 40)
        ed.feed_key(_BACKSPACE)
        result = ed.render_backspace(mt, 0)
        assert result is not None

    def test_render_backspace_mid_buffer_returns_none(self) -> None:
        """Test render_backspace returns None for mid-buffer deletion."""
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
        """Test render_backspace returns None on overflow state change."""
        mt = MockTerminal()
        ed = LineEditor(max_width=5)
        for ch in "abcdef":
            ed.feed_key(ch)
        ed.render(mt, 0, 5)
        for _ in range(4):
            ed.feed_key(_BACKSPACE)
        result = ed.render_backspace(mt, 0)
        assert result is None

    def test_render_backspace_scroll_change_returns_none(self) -> None:
        """Test render_backspace returns None when scroll changes."""
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
        """Test render_backspace erases trailing character with space."""
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
        """Test render_backspace updates previous state tracking."""
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
        """Test render_backspace redraws updated suggestion."""
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
