"""Tests for DECSCUSR cursor shape support."""

# std imports
from io import StringIO

# 3rd party
import pytest

# local
from blessed.cursor_shape import CursorShape
from .accessories import TestTerminal, as_subprocess


class TestCursorShapeConstants:
    """CursorShape class constants."""

    def test_constant_values(self):
        assert CursorShape.DEFAULT == 0
        assert CursorShape.BLINKING_BLOCK == 1
        assert CursorShape.STEADY_BLOCK == 2
        assert CursorShape.BLINKING_UNDERLINE == 3
        assert CursorShape.STEADY_UNDERLINE == 4
        assert CursorShape.BLINKING_BAR == 5
        assert CursorShape.STEADY_BAR == 6

    def test_default_style(self):
        assert CursorShape.DEFAULT_STYLE == 2

    def test_color_reset_osc(self):
        assert CursorShape.COLOR_RESET_OSC == '\x1b]112\x07'

    def test_styles_dict_keys(self):
        expected = {
            'blinking_block', 'steady_block',
            'blinking_underline', 'steady_underline',
            'blinking_bar', 'steady_bar',
            'default',
        }
        assert set(CursorShape.STYLES) == expected

    def test_styles_dict_values(self):
        assert CursorShape.STYLES['blinking_block'] == 1
        assert CursorShape.STYLES['steady_block'] == 2
        assert CursorShape.STYLES['blinking_underline'] == 3
        assert CursorShape.STYLES['steady_underline'] == 4
        assert CursorShape.STYLES['blinking_bar'] == 5
        assert CursorShape.STYLES['steady_bar'] == 6
        assert CursorShape.STYLES['default'] == 0


class TestCursorShapeSequence:
    """CursorShape.sequence() method."""

    @pytest.mark.parametrize("value,expected", [
        (0, '\x1b[0 q'),
        (1, '\x1b[1 q'),
        (2, '\x1b[2 q'),
        (3, '\x1b[3 q'),
        (4, '\x1b[4 q'),
        (5, '\x1b[5 q'),
        (6, '\x1b[6 q'),
    ])
    def test_sequence_from_int(self, value, expected):
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
    def test_sequence_from_string(self, name, expected):
        assert CursorShape.sequence(name) == expected

    def test_sequence_string_case_insensitive(self):
        assert CursorShape.sequence('BLINKING_BAR') == '\x1b[5 q'
        assert CursorShape.sequence('Steady_Block') == '\x1b[2 q'

    def test_sequence_invalid_int(self):
        with pytest.raises(ValueError, match="invalid cursor shape value"):
            CursorShape.sequence(7)
        with pytest.raises(ValueError, match="invalid cursor shape value"):
            CursorShape.sequence(-1)

    def test_sequence_invalid_string(self):
        with pytest.raises(ValueError, match="unknown cursor shape name"):
            CursorShape.sequence('zigzag')


class TestCursorShapeContextManager:
    """Terminal.cursor_shape() context manager."""

    def test_cursor_shape_writes_sequence(self, all_terms):
        @as_subprocess
        def child(kind):
            t = TestTerminal(stream=StringIO(), force_styling=True)
            with t.cursor_shape(t.CursorShape.BLINKING_BAR):
                pass
            output = t.stream.getvalue()
            assert output == '\x1b[5 q' + '\x1b[0 q'

        child(all_terms)

    def test_cursor_shape_string_name(self, all_terms):
        @as_subprocess
        def child(kind):
            t = TestTerminal(stream=StringIO(), force_styling=True)
            with t.cursor_shape('steady_underline'):
                pass
            output = t.stream.getvalue()
            assert output == '\x1b[4 q' + '\x1b[0 q'

        child(all_terms)

    def test_cursor_shape_default_style(self, all_terms):
        @as_subprocess
        def child(kind):
            t = TestTerminal(stream=StringIO(), force_styling=True)
            with t.cursor_shape():
                pass
            output = t.stream.getvalue()
            assert output == '\x1b[2 q' + '\x1b[0 q'

        child(all_terms)

    def test_cursor_shape_no_styling(self, all_terms):
        @as_subprocess
        def child(kind):
            t = TestTerminal(stream=StringIO(), force_styling=False)
            with t.cursor_shape(t.CursorShape.BLINKING_BAR):
                pass
            assert t.stream.getvalue() == ''

        child(all_terms)

    def test_cursor_shape_accessible_as_class_attr(self):
        from blessed import Terminal
        assert hasattr(Terminal, 'CursorShape')
        assert Terminal.CursorShape is CursorShape


class TestCursorShapeSequenceLength:
    """DECSCUSR sequences are stripped for length measurement."""

    @pytest.mark.parametrize("style", [0, 1, 2, 3, 4, 5, 6])
    def test_length_strips_decscusr(self, all_terms, style):
        @as_subprocess
        def child(kind):
            t = TestTerminal(force_styling=True)
            text = CursorShape.sequence(style) + 'hello'
            assert t.length(text) == 5

        child(all_terms)

    def test_length_strips_color_reset_osc(self, all_terms):
        @as_subprocess
        def child(kind):
            t = TestTerminal(force_styling=True)
            text = CursorShape.COLOR_RESET_OSC + 'hello'
            assert t.length(text) == 5

        child(all_terms)
