"""Tests for Terminal.progress_bar()."""
# 3rd party
import pytest

# local
from .accessories import TestTerminal, as_subprocess


def test_progress_bar_normal():
    """Test progress_bar with state=1 returns OSC 9;4 set sequence."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        assert term.progress_bar(1, 42) == '\x1b]9;4;1;42\x07'
        assert term.progress_bar('normal', 0) == '\x1b]9;4;1;0\x07'
        assert term.progress_bar('normal', 100) == '\x1b]9;4;1;100\x07'
    child()


def test_progress_bar_states_no_value():
    """Test progress_bar for non-normal states returns correct sequence."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        assert term.progress_bar(0) == '\x1b]9;4;0;\x07'
        assert term.progress_bar('clear') == '\x1b]9;4;0;\x07'
        assert term.progress_bar(2) == '\x1b]9;4;2;\x07'
        assert term.progress_bar('error') == '\x1b]9;4;2;\x07'
        assert term.progress_bar(3) == '\x1b]9;4;3;\x07'
        assert term.progress_bar('indeterminate') == '\x1b]9;4;3;\x07'
        assert term.progress_bar(4) == '\x1b]9;4;4;\x07'
        assert term.progress_bar('paused') == '\x1b]9;4;4;\x07'
    child()


def test_progress_bar_nostyling():
    """Test progress_bar returns empty string when does_styling is False."""
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=None)
        assert term.progress_bar('normal', 50) == ''
        assert term.progress_bar('clear') == ''
    child()


@pytest.mark.parametrize("state", [5, 'unknown', -1])
def test_progress_bar_invalid_state(state):
    """Test progress_bar raises ValueError for invalid state."""
    @as_subprocess
    def child(state=state):
        term = TestTerminal(force_styling=True)
        with pytest.raises(ValueError):
            term.progress_bar(state)
    child()


@pytest.mark.parametrize("state, value", [
    ('normal', -1),
    ('normal', 101),
    ('normal', None),
    ('unknown', 1999),
    ('unknown', None),
    (99, None),
])
def test_progress_bar_invalid_value(state, value):
    """Test progress_bar raises ValueError for invalid or missing value."""
    @as_subprocess
    def child(state=state, value=value):
        term = TestTerminal(force_styling=True)
        with pytest.raises(ValueError):
            term.progress_bar(state, value)
    child()
