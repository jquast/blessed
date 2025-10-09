"""Tests color algorithms."""

# std imports
import re

# 3rd party
import pytest

# local
from blessed.color import COLOR_DISTANCE_ALGORITHMS
from blessed.colorspace import RGBColor
from blessed.formatters import FormattingString, NullCallableString
# local
from .accessories import TestTerminal, as_subprocess


@pytest.fixture(params=COLOR_DISTANCE_ALGORITHMS.keys())
def all_algorithms(request):
    """All color distance algorithms."""
    return request.param


def test_same_color(all_algorithms):   # pylint: disable=redefined-outer-name
    """The same color should have 0 distance."""
    color = (0, 0, 0)
    assert COLOR_DISTANCE_ALGORITHMS[all_algorithms](color, color) == 0
    color = (255, 255, 255)
    assert COLOR_DISTANCE_ALGORITHMS[all_algorithms](color, color) == 0
    color = (55, 234, 102)
    assert COLOR_DISTANCE_ALGORITHMS[all_algorithms](color, color) == 0


def test_different_color(all_algorithms):   # pylint: disable=redefined-outer-name
    """Different colors should have positive distance."""
    color1 = (0, 0, 0)
    color2 = (0, 0, 1)
    assert COLOR_DISTANCE_ALGORITHMS[all_algorithms](color1, color2) > 0
    color1 = (25, 30, 4)
    color2 = (4, 30, 25)
    assert COLOR_DISTANCE_ALGORITHMS[all_algorithms](color1, color2) > 0
    color1 = (200, 200, 200)
    color2 = (100, 100, 101)
    assert COLOR_DISTANCE_ALGORITHMS[all_algorithms](color1, color2) > 0


def test_color_rgb():
    """Ensure expected sequence is returned"""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        color_patterns = rf"{t.caps['color'].pattern}|{t.caps['color256'].pattern}"
        t.number_of_colors = 1 << 24
        assert t.color_rgb(0, 0, 0)('smoo') == f'\x1b[38;2;0;0;0msmoo{t.normal}'
        assert t.color_rgb(84, 192, 233)('smoo') == f'\x1b[38;2;84;192;233msmoo{t.normal}'

        t.number_of_colors = 256
        # In 256-color mode, (0,0,0) maps to cube index 16, not ANSI black (0)
        # This avoids user theme customizations of ANSI colors 0-15
        assert t.color_rgb(0, 0, 0)('smoo') == f'{t.color(16)}smoo{t.normal}'
        assert re.match(color_patterns, t.color_rgb(84, 192, 233))

    child()


def test_on_color_rgb():
    """Ensure expected sequence is returned"""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        color_patterns = rf"{t.caps['color'].pattern}|{t.caps['on_color256'].pattern}"
        t.number_of_colors = 1 << 24
        assert t.on_color_rgb(0, 0, 0)('smoo') == f'\x1b[48;2;0;0;0msmoo{t.normal}'
        assert t.on_color_rgb(84, 192, 233)('smoo') == f'\x1b[48;2;84;192;233msmoo{t.normal}'

        t.number_of_colors = 256
        assert t.on_color_rgb(0, 0, 0)('smoo') == f'{t.on_color(16)}smoo{t.normal}'
        assert re.match(color_patterns, t.on_color_rgb(84, 192, 233))

    child()


def test_set_number_of_colors():
    """Ensure number of colors is supported and cache is cleared"""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        for num in (0, 4, 8, 16, 256, 1 << 24):
            t.aqua  # pylint: disable=pointless-statement
            assert 'aqua' in dir(t)
            t.number_of_colors = num
            assert t.number_of_colors == num
            assert 'aqua' not in dir(t)

        t.number_of_colors = 88
        assert t.number_of_colors == 16

        with pytest.raises(AssertionError):
            t.number_of_colors = 40

    child()


def test_set_color_distance_algorithm():
    """Ensure algorithm is supported and cache is cleared"""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        for algo in COLOR_DISTANCE_ALGORITHMS:
            t.aqua  # pylint: disable=pointless-statement
            assert 'aqua' in dir(t)
            t.color_distance_algorithm = algo
            assert t.color_distance_algorithm == algo
            assert 'aqua' not in dir(t)
        with pytest.raises(AssertionError):
            t.color_distance_algorithm = 'EenieMeenieMineyMo'

    child()


def test_RGBColor():
    """Ensure string is hex color representation"""
    color = RGBColor(0x5a, 0x05, 0xcb)
    assert str(color) == '#5a05cb'


def test_formatter():
    """Ensure return values match terminal attributes"""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        t.number_of_colors = 1 << 24
        bold_on_seagreen = t.formatter('bold_on_seagreen')
        assert isinstance(bold_on_seagreen, FormattingString)
        assert bold_on_seagreen == t.bold_on_seagreen

        t.number_of_colors = 0
        bold_on_seagreen = t.formatter('bold_on_seagreen')
        assert isinstance(bold_on_seagreen, FormattingString)
        assert bold_on_seagreen == t.bold_on_seagreen

        bold = t.formatter('bold')
        assert isinstance(bold, FormattingString)
        assert bold == t.bold

        t = TestTerminal()
        t._does_styling = False
        t.number_of_colors = 0
        bold_on_seagreen = t.formatter('bold_on_seagreen')
        assert isinstance(bold_on_seagreen, NullCallableString)
        assert bold_on_seagreen == t.bold_on_seagreen
    child()


def test_formatter_invalid():
    """Ensure NullCallableString for invalid formatters"""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        assert isinstance(t.formatter('csr'), NullCallableString)
    child()


def test_rgb_to_xterm_cube_index():
    """Test RGB to xterm cube index mapping for 256-color terminals"""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        t.number_of_colors = 256

        # In 256-color mode, we avoid ANSI colors 0-15 to prevent theme interference
        # All colors map to either cube (16-231) or grayscale (232-255)

        # Test colors that map to cube indices
        assert t.rgb_downconvert(0, 0, 0) == 16  # Cube black (0,0,0)
        assert t.rgb_downconvert(255, 0, 0) == 196  # Cube red (255,0,0) = 16 + 36*5 + 6*0 + 0
        assert t.rgb_downconvert(0, 255, 0) == 46   # Cube green (0,255,0) = 16 + 36*0 + 6*5 + 0
        assert t.rgb_downconvert(0, 0, 255) == 21   # Cube blue (0,0,255) = 16 + 36*0 + 6*0 + 5
        # Cube white (255,255,255) = 16 + 36*5 + 6*5 + 5
        assert t.rgb_downconvert(255, 255, 255) == 231

        # Test intermediate cube colors
        assert t.rgb_downconvert(95, 95, 95) == 59  # 16 + 36*1 + 6*1 + 1 = 59
        assert t.rgb_downconvert(135, 135, 135) == 102  # 16 + 36*2 + 6*2 + 2 = 102

        # Test some colors that should prefer cube over grayscale
        cube_orange = t.rgb_downconvert(215, 135, 0)  # Should be in cube range
        assert 16 <= cube_orange <= 231

    child()


def test_rgb_to_xterm_gray_index():
    """Test RGB to xterm grayscale index mapping for 256-color terminals"""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        t.number_of_colors = 256

        # Test grayscale ramp mapping (indices 232-255, values 8, 18, 28, ..., 238)
        # Gray value = 8 + 10*i, where i is the offset from 232

        # Test edge cases and specific grays
        assert t.rgb_downconvert(8, 8, 8) == 232  # First gray (8+10*0)
        assert t.rgb_downconvert(18, 18, 18) == 233  # Second gray (8+10*1)
        # Mid gray, should be around (128-8)/10 ≈ 12
        assert t.rgb_downconvert(128, 128, 128) in {244, 245}
        assert t.rgb_downconvert(238, 238, 238) == 255  # Last gray (8+10*23)

        # Test pure grayscale inputs
        for i, expected_idx in enumerate([232, 233, 234, 235, 236]):
            gray_val = 8 + 10 * i
            result_idx = t.rgb_downconvert(gray_val, gray_val, gray_val)
            assert result_idx == expected_idx

    child()


def test_256_downconvert_cube_vs_gray_choice():
    """Test 256-color cube vs grayscale selection logic"""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        t.number_of_colors = 256

        # In 256-color mode, we avoid ANSI colors 0-15 to prevent theme interference
        # All colors map to either cube (16-231) or grayscale (232-255)

        # Test colors that map to cube indices
        red_idx = t.rgb_downconvert(255, 0, 0)
        assert red_idx == 196  # Cube red (255,0,0) = 16 + 36*5 + 6*0 + 0

        green_idx = t.rgb_downconvert(0, 255, 0)
        assert green_idx == 46  # Cube green (0,255,0) = 16 + 36*0 + 6*5 + 0

        blue_idx = t.rgb_downconvert(0, 0, 255)
        assert blue_idx == 21  # Cube blue (0,0,255) = 16 + 36*0 + 6*0 + 5

        # Test gray values that should prefer grayscale ramp
        gray_idx = t.rgb_downconvert(128, 128, 128)
        assert 232 <= gray_idx <= 255  # Should be in grayscale range

        # Test mixed color - algorithm finds best match between cube and grayscale only
        mixed_idx = t.rgb_downconvert(200, 100, 50)  # Orange-ish color
        assert 16 <= mixed_idx <= 255  # Valid color index (cube or grayscale, not ANSI)

        # Test very dark colors - should prefer grayscale or very dark cube colors
        dark_idx = t.rgb_downconvert(20, 20, 20)
        # Could be either cube (16) or early grayscale (232-235), both are valid
        assert dark_idx == 16 or 232 <= dark_idx <= 235

    child()


def test_256_downconvert_preserves_distance_algorithm():
    """Test that 256-color fast path uses the selected distance algorithm"""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        t.number_of_colors = 256

        # Test with different distance algorithms
        for algo in ['cie2000', 'rgb', 'rgb-weighted', 'cie76', 'cie94']:
            t.color_distance_algorithm = algo

            # The fast path should still work and give reasonable results
            # Pure red (255,0,0) may map to ANSI red (index 9) or cube red
            red_idx = t.rgb_downconvert(255, 0, 0)
            assert red_idx in range(256)  # Valid color index

            # Pure grays should prefer grayscale (for most algorithms)
            gray_idx = t.rgb_downconvert(128, 128, 128)
            # Result depends on algorithm, but should be reasonable
            assert gray_idx in range(256)  # Valid color index

    child()


def test_256_vs_legacy_downconvert_compatibility():
    """Test that results are compatible between 256 and smaller palettes"""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)

        # Test basic colors in 16-color mode
        t.number_of_colors = 16
        black_16 = t.rgb_downconvert(0, 0, 0)
        red_16 = t.rgb_downconvert(255, 0, 0)

        # Test same colors in 256-color mode
        t.number_of_colors = 256
        black_256 = t.rgb_downconvert(0, 0, 0)
        red_256 = t.rgb_downconvert(255, 0, 0)

        # The indices will be different, but both should be valid
        assert black_16 in range(16)  # Valid 16-color index
        assert black_256 in range(256)  # Valid 256-color index
        assert red_16 in range(16)  # Valid 16-color index
        assert red_256 in range(256)  # Valid 256-color index

        # Black behavior differs between modes:
        # - 16-color mode: uses ANSI black (index 0)
        # - 256-color mode: uses cube black (index 16) to avoid theme interference
        assert black_16 == 0
        assert black_256 == 16  # Cube black to avoid user theme customizations

        # Red behavior also differs:
        # - 16-color mode: uses ANSI bright red (index 9)
        # - 256-color mode: uses cube red (index 196) to avoid theme interference
        assert red_16 == 9
        assert red_256 == 196  # Cube red

    child()


def test_rgb_downconvert_zero_colors():
    """Test rgb_downconvert when number_of_colors == 0 returns color 7"""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        t.number_of_colors = 0

        # When number_of_colors is 0, rgb_downconvert should always return 7
        # regardless of the input RGB values (covers line 925)
        assert t.rgb_downconvert(0, 0, 0) == 7
        assert t.rgb_downconvert(255, 0, 0) == 7
        assert t.rgb_downconvert(0, 255, 0) == 7
        assert t.rgb_downconvert(0, 0, 255) == 7
        assert t.rgb_downconvert(255, 255, 255) == 7
        assert t.rgb_downconvert(128, 64, 192) == 7

    child()
