"""Tests for Terminal.text_sized()."""
# std imports
import io

# 3rd party
import pytest

try:
    from unittest import mock
except ImportError:
    import mock

# local
from .accessories import TestTerminal, as_subprocess


def test_string_vertical_align_top():
    """vertical_align='top' produces no v= key (default 0)."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            result = term.text_sized('Hi', vertical_align='top')
            assert result.startswith('\x1b]66;')
            assert result.endswith('\x07')
            assert 'v=' not in result
    child()


def test_string_vertical_align_bottom():
    """vertical_align='bottom' produces v=1."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            result = term.text_sized('Hi', vertical_align='bottom')
            assert 'v=1' in result
    child()


def test_string_vertical_align_center():
    """vertical_align='center' produces v=2."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            result = term.text_sized('Hi', vertical_align='center')
            assert 'v=2' in result
    child()


def test_string_horizontal_align_left():
    """horizontal_align='left' produces no h= key (default 0)."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            result = term.text_sized('Hi', horizontal_align='left')
            assert 'h=' not in result
    child()


def test_string_horizontal_align_right():
    """horizontal_align='right' produces h=1."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            result = term.text_sized('Hi', horizontal_align='right')
            assert 'h=1' in result
    child()


def test_string_horizontal_align_center():
    """horizontal_align='center' produces h=2."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            result = term.text_sized('Hi', horizontal_align='center')
            assert 'h=2' in result
    child()


def test_int_align_still_works():
    """Integer alignment values still work as before."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            result = term.text_sized('Hi', vertical_align=2, horizontal_align=1)
            assert 'v=2' in result
            assert 'h=1' in result
    child()


def test_string_vertical_align_default():
    """vertical_align='default' produces no v= key."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            result = term.text_sized('Hi', vertical_align='default')
            assert 'v=' not in result
    child()


def test_string_horizontal_align_default():
    """horizontal_align='default' produces no h= key."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            result = term.text_sized('Hi', horizontal_align='default')
            assert 'h=' not in result
    child()


@pytest.mark.parametrize('name,value', [
    ('vertical_align', 'invalid'),
    ('horizontal_align', 'invalid'),
    ('vertical_align', 'left'),
    ('vertical_align', 'right'),
    ('horizontal_align', 'top'),
    ('horizontal_align', 'bottom'),
])
def test_invalid_string_align_raises_valueerror(name, value):
    """Invalid string alignment values raise ValueError."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            with pytest.raises(ValueError):
                term.text_sized('Hi', **{name: value})
    child()


def test_graceful_degradation_without_support():
    """text_sized returns plain text when does_text_sizing is False."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=False):
            assert term.text_sized('Hello') == 'Hello'
    child()


@pytest.mark.parametrize('value', [3, -1, 999])
def test_vertical_align_int_out_of_range(value):
    """vertical_align int outside 0--2 raises ValueError."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            with pytest.raises(ValueError):
                term.text_sized('Hi', vertical_align=value)
    child()


@pytest.mark.parametrize('value', [3, -1, 999])
def test_horizontal_align_int_out_of_range(value):
    """horizontal_align int outside 0--2 raises ValueError."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            with pytest.raises(ValueError):
                term.text_sized('Hi', horizontal_align=value)
    child()


def test_text_with_esc_raises_valueerror():
    """Text containing ESC raises ValueError."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            with pytest.raises(ValueError):
                term.text_sized('Hello\x1bWorld')
    child()


def test_text_exactly_4096_bytes():
    """Text at exactly 4096 UTF-8 bytes does not raise ValueError."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        with mock.patch.object(term, 'does_text_sizing', return_value=True):
            result = term.text_sized('x' * 4096)
            assert '\x1b]66;' in result
    child()
