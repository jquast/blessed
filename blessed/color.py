# encoding: utf-8
"""
Sub-module providing color functions.

References,
- https://en.wikipedia.org/wiki/Color_difference
- http://www.easyrgb.com/en/math.php
- Measuring Colour by R.W.G. Hunt and M.R. Pointer
"""

# std imports
from math import sqrt


def rgb_to_xyz(red, green, blue):
    """
    Convert standard RGB color to XYZ color.

    :arg red: RGB value of Red.
    :arg green: RGB value of Green.
    :arg blue: RGB value of Blue.
    :returns: Tuple (X, Y, Z) representing XYZ color
    :rtype: tuple

    D65/2° standard illuminant
    """
    rgb = []
    for val in red, green, blue:
        val /= 255
        if val > 0.04045:
            val = pow((val + 0.055) / 1.055, 2.4)
        else:
            val /= 12.92
        val *= 100
        rgb.append(val)

    red, green, blue = rgb  # pylint: disable=unbalanced-tuple-unpacking
    x_val = red * 0.4124 + green * 0.3576 + blue * 0.1805
    y_val = red * 0.2126 + green * 0.7152 + blue * 0.0722
    z_val = red * 0.0193 + green * 0.1192 + blue * 0.9505

    return x_val, y_val, z_val


def xyz_to_lab(x_val, y_val, z_val):
    """
    Convert XYZ color to CIE-Lab color.

    :arg x_val: XYZ value of X.
    :arg y_val: XYZ value of Y.
    :arg z_val: XYZ value of Z.
    :returns: Tuple (L, a, b) representing CIE-Lab color
    :rtype: tuple

    D65/2° standard illuminant
    """
    xyz = []
    for val, ref in (x_val, 95.047), (y_val, 100.0), (z_val, 108.883):
        val /= ref
        if val > 0.008856:
            val = pow(val, 1 / 3)
        else:
            val = 7.787 * val + 16 / 116
        xyz.append(val)

    x_val, y_val, z_val = xyz  # pylint: disable=unbalanced-tuple-unpacking
    cie_l = 116 * y_val - 16
    cie_a = 500 * (x_val - y_val)
    cie_b = 200 * (y_val - z_val)

    return cie_l, cie_a, cie_b


def rgb_to_lab(red, green, blue):
    """
    Convert RGB color to CIE-Lab color.

    :arg red: RGB value of Red.
    :arg green: RGB value of Green.
    :arg blue: RGB value of Blue.
    :returns: Tuple (L, a, b) representing CIE-Lab color
    :rtype: tuple

    D65/2° standard illuminant
    """
    return xyz_to_lab(*rgb_to_xyz(red, green, blue))


def dist_rgb(rgb1, rgb2):
    """
    Determine distance between two rgb colors.

    :arg tuple rgb1: RGB color definition
    :arg tuple rgb2: RGB color definition
    :returns: Square of the distance between provided colors
    :rtype: float

    This works by treating RGB colors as coordinates in three dimensional
    space and finding the closest point within the configured color range
    using the formula::

        d^2 = (r2 - r1)^2 + (g2 - g1)^2 + (b2 - b1)^2

    For efficiency, the square of the distance is returned
    which is sufficient for comparisons
    """
    return sum(pow(rgb1[idx] - rgb2[idx], 2) for idx in (0, 1, 2))


def dist_rgb_weighted(rgb1, rgb2):
    """
    Determine the weighted distance between two rgb colors.

    :arg tuple rgb1: RGB color definition
    :arg tuple rgb2: RGB color definition
    :returns: Square of the distance between provided colors
    :rtype: float

    Similar to a standard distance formula, the values are weighted
    to approximate human perception of color differences

    For efficiency, the square of the distance is returned
    which is sufficient for comparisons
    """
    red_mean = (rgb1[0] + rgb2[0]) / 2

    return ((2 + red_mean / 256) * pow(rgb1[0] - rgb2[0], 2) +
            4 * pow(rgb1[1] - rgb2[1], 2) +
            (2 + (255 - red_mean) / 256) * pow(rgb1[2] - rgb2[2], 2))


def dist_cie76(rgb1, rgb2):
    """
    Determine distance between two rgb colors using the CIE94 algorithm.

    :arg tuple rgb1: RGB color definition
    :arg tuple rgb2: RGB color definition
    :returns: Square of the distance between provided colors
    :rtype: float

    For efficiency, the square of the distance is returned
    which is sufficient for comparisons
    """
    l_1, a_1, b_1 = rgb_to_lab(*rgb1)
    l_2, a_2, b_2 = rgb_to_lab(*rgb2)
    return pow(l_1 - l_2, 2) + pow(a_1 - a_2, 2) + pow(b_1 - b_2, 2)


def dist_cie94(rgb1, rgb2):
    # pylint: disable=too-many-locals
    """
    Determine distance between two rgb colors using the CIE94 algorithm.

    :arg tuple rgb1: RGB color definition
    :arg tuple rgb2: RGB color definition
    :returns: Square of the distance between provided colors
    :rtype: float

    For efficiency, the square of the distance is returned
    which is sufficient for comparisons
    """
    l_1, a_1, b_1 = rgb_to_lab(*rgb1)
    l_2, a_2, b_2 = rgb_to_lab(*rgb2)

    s_l = k_l = k_c = k_h = 1
    k_1 = 0.045
    k_2 = 0.015

    delta_l = l_1 - l_2
    delta_a = a_1 - a_2
    delta_b = b_1 - b_2
    c_1 = sqrt(a_1 ** 2 + b_1 ** 2)
    c_2 = sqrt(a_2 ** 2 + b_2 ** 2)
    delta_c = c_1 - c_2
    delta_h = sqrt(delta_a ** 2 + delta_b ** 2 + delta_c ** 2)
    s_c = 1 + k_1 * c_1
    s_h = 1 + k_2 * c_1

    return ((delta_l / (k_l * s_l)) ** 2 +
            (delta_c / (k_c * s_c)) ** 2 +
            (delta_h / (k_h * s_h)) ** 2)


COLOR_DISTANCE_ALGORITHMS = {'rgb': dist_rgb,
                             'rgb-weighted': dist_rgb_weighted,
                             'cie76': dist_cie76,
                             'cie94': dist_cie94}
