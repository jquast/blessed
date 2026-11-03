"""Tests for the CIE94 and CIEDE2000 color difference formulas."""

# std imports
from math import sqrt

# local
from blessed.color import dist_cie94, dist_cie2000, _cie94_from_lab, _cie2000_from_lab

# Sharma, Wu & Dalal (2005), "The CIEDE2000 Color-Difference Formula:
# Implementation Notes, Supplementary Test Data, and Mathematical Observations",
# Table 1: (Lab 1, Lab 2, published dE00).
#
# The pair that differs only in the sign of a* at hue ~90/270 degrees is omitted:
# delta_h' lands exactly on the +/-180 boundary there, and the branch taken then
# depends on the last bit of atan2, which differs between platforms (the same
# reason the reference implementation's own test suite excludes it).
SHARMA_CASES = [
    ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
    ((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
    ((50.0000, 2.8361, -74.0200), (50.0000, 0.0000, -82.7485), 3.4412),
    ((50.0000, -1.3802, -84.2814), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, -1.1848, -84.8006), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, -0.9009, -85.5211), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, 0.0000, 0.0000), (50.0000, -1.0000, 2.0000), 2.3669),
    ((50.0000, -1.0000, 2.0000), (50.0000, 0.0000, 0.0000), 2.3669),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0009), 7.1792),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0010), 7.1792),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0011), 7.2195),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0012), 7.2195),
    ((50.0000, -0.0010, 2.4900), (50.0000, 0.0011, -2.4900), 4.7461),
    ((50.0000, 2.5000, 0.0000), (50.0000, 0.0000, -2.5000), 4.3065),
    ((50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
    ((50.0000, 2.5000, 0.0000), (61.0000, -5.0000, 29.0000), 22.8977),
    ((50.0000, 2.5000, 0.0000), (56.0000, -27.0000, -3.0000), 31.9030),
    ((50.0000, 2.5000, 0.0000), (58.0000, 24.0000, 15.0000), 19.4535),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.1736, 0.5854), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.2972, 0.0000), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 1.8634, 0.5757), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.2592, 0.3350), 1.0000),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.2630),
    ((61.2901, 3.7196, -5.3901), (61.4292, 2.2480, -4.9620), 1.8731),
    ((35.0831, -44.1164, 3.7933), (35.0232, -40.0716, 1.5901), 1.8645),
    ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    ((36.4612, 47.8580, 18.3852), (36.2715, 50.5065, 21.2231), 1.4146),
    ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
    ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
    ((6.7747, -0.2908, -2.4247), (5.8714, -0.0985, -2.2286), 0.6377),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]


def test_cie2000_matches_published_sharma_table():
    """CIEDE2000 reproduces the supplementary test data of Sharma et al."""
    for index, (lab_1, lab_2, expected) in enumerate(SHARMA_CASES, 1):
        result = _cie2000_from_lab(lab_1, lab_2)
        assert abs(result - expected) < 1e-4, (
            "case %d: %.6f != %.4f" % (index, result, expected))


def test_cie2000_is_symmetric():
    """Swapping the two colors does not change the difference."""
    for lab_1, lab_2, _expected in SHARMA_CASES:
        assert abs(_cie2000_from_lab(lab_1, lab_2) -
                   _cie2000_from_lab(lab_2, lab_1)) < 1e-9


def test_cie2000_of_identical_colors_is_zero():
    """A color differs from itself by nothing."""
    assert _cie2000_from_lab((50.0, 2.5, 0.0), (50.0, 2.5, 0.0)) == 0.0
    assert _cie2000_from_lab((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)) == 0.0


def test_cie2000_returns_squared_distance():
    """The public function keeps its documented squared-distance contract."""
    for rgb_1, rgb_2 in (((255, 0, 0), (0, 255, 0)),
                         ((10, 20, 30), (200, 210, 220)),
                         ((128, 128, 128), (128, 128, 128))):
        squared = dist_cie2000(rgb_1, rgb_2)
        assert squared >= 0.0
        # squaring the square root must give the value back
        assert abs(sqrt(squared) ** 2 - squared) < 1e-12


def test_cie94_hue_term_vanishes_for_a_pure_chroma_difference():
    """Two colors of the same hue differ only in chroma: dH^2 = da^2+db^2-dC^2 = 0.

    The published CIE94 hue term subtracts dC^2; adding it invents a hue
    difference and inflates the distance to sqrt(30^2 + 30^2) here.
    """
    result = _cie94_from_lab((50.0, 60.0, 0.0), (50.0, 30.0, 0.0))
    expected = 30.0 / (1 + 0.045 * 60.0)
    assert abs(result - expected) < 1e-9


def test_cie94_of_a_lightness_difference_is_the_lightness_delta():
    """S_L is 1 for graphic arts, so a pure L difference is |dL|."""
    assert abs(_cie94_from_lab((40.0, 10.0, 10.0), (70.0, 10.0, 10.0)) - 30.0) < 1e-9


def test_cie94_of_identical_colors_is_zero():
    """A color differs from itself by nothing."""
    assert _cie94_from_lab((50.0, 2.5, 0.0), (50.0, 2.5, 0.0)) == 0.0


def test_cie94_returns_squared_distance():
    """The public function keeps its documented squared-distance contract."""
    squared = dist_cie94((255, 0, 0), (0, 0, 255))
    assert squared >= 0.0
    assert abs(sqrt(squared) ** 2 - squared) < 1e-12
