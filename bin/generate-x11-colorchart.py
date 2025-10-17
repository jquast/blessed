# generate images and tables for inclusion in docs/colors.rst
# std imports
import os
import re
import math
import colorsys
from functools import reduce

# 3rd party
from PIL import Image

# local
from blessed.colorspace import X11_COLORNAMES_TO_RGB

rgb_folder = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, 'docs', '_static', 'rgb'))

color_alias_fmt = """
.. |{color_name}| image:: _static/rgb/{color_name}.png
   :width: 48pt
   :height: 12pt"""

csv_table = """.. csv-table:: All Terminal colors, by name
   :header: "Name", "Image", "R", "G", "B", "H", "S", "V"
   :name: Color chart
"""


def sort_colors():
    colors = {}
    for color_name, rgb_color in X11_COLORNAMES_TO_RGB.items():
        if rgb_color in colors:
            colors[rgb_color].append(color_name)
        else:
            colors[rgb_color] = [color_name]

    def sortby_hv(rgb_item):
        # sort by hue rounded to nearest %,
        # then by color name & number
        # except shades of grey -- by name & number, only
        rgb, name = rgb_item
        digit = 0
        match = re.match(r'(.*)(\d+)', name[0])
        if match is not None:
            name = match.group(1)
            digit = int(match.group(2))
        else:
            name = name[0]
        hash_name = reduce(int.__mul__, map(ord, name))

        hsv = colorsys.rgb_to_hsv(*rgb)
        if rgb[0] == rgb[1] == rgb[2]:
            return 100, hsv[2], hash_name, digit

        return int(math.floor(hsv[0] * 100)), hash_name, digit, hsv[2]

    return sorted(colors.items(), key=sortby_hv)


def main():
    aliases, csv_rows = '', ''
    for rgb, x11_colors in sort_colors():
        x11_color = sorted(x11_colors)[0]
        fname = os.path.join(rgb_folder, f'{x11_color}.png')
        if not os.path.exists(os.path.join(fname)):
            img = Image.new('RGB', (1, 1), color=rgb)
            img.save(fname)
        aliases += color_alias_fmt.format(color_name=x11_color)
        hsv = colorsys.rgb_to_hsv(*rgb)
        csv_rows += ('   '
                     f'{x11_color}, |{x11_color}|, '
                     f'{rgb[0] / 255:0.1%}, {rgb[1] / 255:0.1%}, {rgb[2] / 255:0.1%}, '
                     f'{hsv[0]:0.1%}, {hsv[1]:0.1%}, {hsv[2] / 255:0.1%}\n')

    output = aliases + '\n\n' + csv_table + '\n' + csv_rows
    filepath_txt = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, 'docs',
                                                'all_the_colors.txt'))
    with open(filepath_txt, 'w') as fout:
        print(f'write: {fout.name}')
        fout.write(output.lstrip())


if __name__ == '__main__':
    main()
