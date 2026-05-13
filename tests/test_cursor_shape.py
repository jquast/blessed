"""Tests for DECSCUSR cursor shape support."""

# std imports
from io import StringIO

# 3rd party
import pytest

# local
from blessed.cursor_shape import CursorShape
from .accessories import TestTerminal


def test_constant_values():
    """Verify integer values of all shape constants."""
    assert CursorShape.DEFAULT == 0
    assert CursorShape.BLINKING_BLOCK == 1
    assert CursorShape.STEADY_BLOCK == 2
    assert CursorShape.BLINKING_UNDERLINE == 3
    assert CursorShape.STEADY_UNDERLINE == 4
    assert CursorShape.BLINKING_BAR == 5
    assert CursorShape.STEADY_BAR == 6


def test_default_style():
    """Verify DEFAULT_STYLE is steady block."""
    assert CursorShape.DEFAULT_STYLE == 2


def test_color_reset_osc():
    """Verify COLOR_RESET_OSC sequence."""
    assert CursorShape.COLOR_RESET_OSC == '\x1b]112\x07'


def test_styles_dict_keys():
    """Verify STYLES dict contains all shape names."""
    expected = {
        'blinking_block', 'steady_block',
        'blinking_underline', 'steady_underline',
        'blinking_bar', 'steady_bar',
        'default',
    }
    assert set(CursorShape.STYLES) == expected


def test_styles_dict_values():
    """Verify STYLES maps names to correct integers."""
    assert CursorShape.STYLES['blinking_block'] == 1
    assert CursorShape.STYLES['steady_block'] == 2
    assert CursorShape.STYLES['blinking_underline'] == 3
    assert CursorShape.STYLES['steady_underline'] == 4
    assert CursorShape.STYLES['blinking_bar'] == 5
    assert CursorShape.STYLES['steady_bar'] == 6
    assert CursorShape.STYLES['default'] == 0


@pytest.mark.parametrize("value,expected", [
    (0, '\x1b[0 q'),
    (1, '\x1b[1 q'),
    (2, '\x1b[2 q'),
    (3, '\x1b[3 q'),
    (4, '\x1b[4 q'),
    (5, '\x1b[5 q'),
    (6, '\x1b[6 q'),
])
def test_sequence_from_int(value, expected):
    """Generate DECSCUSR sequence from integer."""
    assert CursorShape.sequence(value) == expected


@pytest.mark.parametrize("name,expected", [
    ('blinking_block', '\x1b[1 q'),
    ('steady_block', '\x1b[2 q'),
    ('blinking_underline', '\x1b[3 q'),
    ('steady_underline', '\x1b[4 q'),
    ('blinking_bar', '\x1b[5 q'),
    ('steady_bar', '\x1b[6 q'),
    ('default', '\x1b[0 q'),
])
def test_sequence_from_string(name, expected):
    """Generate DECSCUSR sequence from style name."""
    assert CursorShape.sequence(name) == expected


def test_sequence_string_case_insensitive():
    """Style name lookup is case-insensitive."""
    assert CursorShape.sequence('BLINKING_BAR') == '\x1b[5 q'
    assert CursorShape.sequence('Steady_Block') == '\x1b[2 q'


def test_sequence_invalid_int():
    """Out-of-range integer raises ValueError."""
    with pytest.raises(ValueError, match="invalid cursor shape value"):
        CursorShape.sequence(7)
    with pytest.raises(ValueError, match="invalid cursor shape value"):
        CursorShape.sequence(-1)


def test_sequence_invalid_string():
    """Unknown style name raises ValueError."""
    with pytest.raises(ValueError, match="unknown cursor shape name"):
        CursorShape.sequence('zigzag')


def test_cursor_shape_writes_sequence(any_term):
    """Context manager writes enter and reset sequences."""
    def child(kind):
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.cursor_shape(t.CursorShape.BLINKING_BAR):
            pass
        output = t.stream.getvalue()
        assert output == '\x1b[5 q' + '\x1b[0 q'

    child(any_term)


def test_cursor_shape_string_name(any_term):
    """Context manager accepts string style names."""
    def child(kind):
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.cursor_shape('steady_underline'):
            pass
        output = t.stream.getvalue()
        assert output == '\x1b[4 q' + '\x1b[0 q'

    child(any_term)


def test_cursor_shape_default_style(any_term):
    """Context manager with no argument uses DEFAULT_STYLE."""
    def child(kind):
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.cursor_shape():
            pass
        output = t.stream.getvalue()
        assert output == '\x1b[2 q' + '\x1b[0 q'

    child(any_term)


def test_cursor_shape_no_styling(any_term):
    """Context manager is a no-op when styling is disabled."""
    def child(kind):
        t = TestTerminal(stream=StringIO(), force_styling=False)
        with t.cursor_shape(t.CursorShape.BLINKING_BAR):
            pass
        assert t.stream.getvalue() == ''

    child(any_term)


def test_cursor_shape_accessible_as_class_attr():
    """CursorShape is accessible as Terminal.CursorShape."""
    from blessed import Terminal
    assert hasattr(Terminal, 'CursorShape')
    assert Terminal.CursorShape is CursorShape


@pytest.mark.parametrize("style", [0, 1, 2, 3, 4, 5, 6])
def test_length_strips_decscusr(any_term, style):
    """Terminal.length() excludes DECSCUSR sequences."""
    def child(kind):
        t = TestTerminal(force_styling=True)
        text = CursorShape.sequence(style) + 'hello'
        assert t.length(text) == 5

    child(any_term)


def test_length_strips_color_reset_osc(any_term):
    """Terminal.length() excludes COLOR_RESET_OSC sequence."""
    def child(kind):
        t = TestTerminal(force_styling=True)
        text = CursorShape.COLOR_RESET_OSC + 'hello'
        assert t.length(text) == 5

    child(any_term)
