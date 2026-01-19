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
    """Test rgb_downconvert when number_of_colors == 0 returns color 7."""
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


def test_hex_to_rgb():
    """Test hex to RGB conversion across formats."""
    from blessed.colorspace import hex_to_rgb

    # 3-digit format (each digit doubled: a->aa, b->bb, c->cc)
    assert hex_to_rgb('#abc') == (170, 187, 204)

    # 6-digit format, with and without '#' prefix
    assert hex_to_rgb('#5a05cb') == (90, 5, 203)
    assert hex_to_rgb('5a05cb') == (90, 5, 203)

    # 12-digit format (16-bit per channel, high byte kept)
    assert hex_to_rgb('#28992c993499') == (40, 44, 52)


def test_hex_to_rgb_invalid():
    """Test invalid hex color raises ValueError."""
    from blessed.colorspace import hex_to_rgb

    with pytest.raises(ValueError):
        hex_to_rgb('#gg')
    with pytest.raises(ValueError):
        hex_to_rgb('#12345')
    with pytest.raises(ValueError):
        hex_to_rgb('#1234567')


def test_rgb_to_hex():
    """Test RGB to hex conversion."""
    from blessed.colorspace import rgb_to_hex

    assert rgb_to_hex(90, 5, 203) == '#5a05cb'

    # maybe_short: can shorten when digits repeat (aa->a, bb->b, cc->c)
    assert rgb_to_hex(170, 187, 204, maybe_short=True) == '#abc'

    # maybe_short: cannot shorten when digits don't repeat (cd != cc)
    assert rgb_to_hex(170, 187, 205, maybe_short=True) == '#aabbcd'


def test_xparse_color():
    """Test XParseColor scaling for terminal color responses."""
    from blessed.colorspace import xparse_color

    # 4 hex digits (16-bit) - unchanged
    assert xparse_color('e5e5') == 0xe5e5

    # 2 hex digits (8-bit) - replicate 2x: 'e5' -> 'e5e5'
    assert xparse_color('e5') == 0xe5e5

    # 1 hex digit (4-bit) - replicate 4x: 'a' -> 'aaaa'
    assert xparse_color('a') == 0xaaaa

    # 3 hex digits (12-bit) - shift left 4, add top nibble: '123' -> '1230' | '1' -> '1231'
    assert xparse_color('123') == 0x1231

    # bits=8 conversion (lower byte discarded via >> 8): 'e599' -> 0xe5
    assert xparse_color('e599', bits=8) == 0xe5


def test_xparse_color_errors():
    """Test xparse_color raises errors for invalid input."""
    from blessed.colorspace import xparse_color

    with pytest.raises(ValueError):
        xparse_color('')

    with pytest.raises(ValueError):
        xparse_color('fffff')

    with pytest.raises(ValueError):
        xparse_color('ff', bits=32)


def test_color_hex():
    """Test color_hex with 3, 6, and 12 digit formats."""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        t.number_of_colors = 1 << 24
        assert t.color_hex('#fff')('x') == f'\x1b[38;2;255;255;255mx{t.normal}'
        assert t.color_hex('#ffffff')('x') == f'\x1b[38;2;255;255;255mx{t.normal}'
        assert t.color_hex('#ffffffffffff')('x') == f'\x1b[38;2;255;255;255mx{t.normal}'
        assert t.color_hex('#000')('x') == f'\x1b[38;2;0;0;0mx{t.normal}'
        assert t.color_hex('#5a05cb')('x') == f'\x1b[38;2;90;5;203mx{t.normal}'
    child()


def test_on_color_hex():
    """Test on_color_hex with 3, 6, and 12 digit formats."""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        t.number_of_colors = 1 << 24
        assert t.on_color_hex('#000')('x') == f'\x1b[48;2;0;0;0mx{t.normal}'
        assert t.on_color_hex('#000000')('x') == f'\x1b[48;2;0;0;0mx{t.normal}'
        assert t.on_color_hex('#000000000000')('x') == f'\x1b[48;2;0;0;0mx{t.normal}'
        assert t.on_color_hex('#fff')('x') == f'\x1b[48;2;255;255;255mx{t.normal}'
    child()


def test_get_fgcolor_hex():
    """Test get_fgcolor_hex returns hex string."""
    from io import StringIO

    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=True, is_a_tty=True)
        t.ungetch('\x1b]10;rgb:ffff/ffff/ffff\x07')
        assert t.get_fgcolor_hex(timeout=0.01) == '#ffffff'

        t.ungetch('\x1b]10;rgb:2828/2c2c/3434\x07')
        assert t.get_fgcolor_hex(timeout=0.01) == '#282c34'

        # XParseColor shorthand formats (1, 2, 3 hex digits)
        t.ungetch('\x1b]10;rgb:f/f/f\x07')
        assert t.get_fgcolor_hex(timeout=0.01) == '#ffffff'

        t.ungetch('\x1b]10;rgb:e5/e5/e5\x07')
        assert t.get_fgcolor_hex(timeout=0.01) == '#e5e5e5'

        t.ungetch('\x1b]10;rgb:abc/abc/abc\x07')
        assert t.get_fgcolor_hex(timeout=0.01) == '#ababab'
    child()


def test_get_fgcolor_hex_timeout():
    """Test get_fgcolor_hex returns empty string on timeout."""
    from io import StringIO

    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO())
        result = t.get_fgcolor_hex(timeout=0)
        assert result == ''
    child()


def test_get_bgcolor_hex():
    """Test get_bgcolor_hex returns hex string."""
    from io import StringIO

    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=True, is_a_tty=True)
        t.ungetch('\x1b]11;rgb:2828/2c2c/3434\x07')
        assert t.get_bgcolor_hex(timeout=0.01) == '#282c34'

        t.ungetch('\x1b]11;rgb:aaaa/bbbb/cccc\x07')
        assert t.get_bgcolor_hex(timeout=0.01, maybe_short=True) == '#abc'

        # XParseColor shorthand: 3 digits have nibble wrap (abc -> abca -> ab)
        t.ungetch('\x1b]11;rgb:abc/de0/123\x07')
        assert t.get_bgcolor_hex(timeout=0.01) == '#abde12'
    child()


def test_get_bgcolor_hex_timeout():
    """Test get_bgcolor_hex returns empty string on timeout."""
    from io import StringIO

    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO())
        result = t.get_bgcolor_hex(timeout=0)
        assert result == ''
    child()
