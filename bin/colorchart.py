# std imports
import re

# local
import blessed
from blessed.colorspace import X11_COLORNAMES_TO_RGB

RE_NATURAL = re.compile(r'(dark|light|)(.+?)(\d*)$')


def naturalize(string):

    intensity, word, num = RE_NATURAL.match(string).groups()

    if intensity == 'light':
        intensity = -1
    elif intensity == 'medium':
        intensity = 1
    elif intensity == 'dark':
        intensity = 2
    else:
        intensity = 0

    return word, intensity, int(num) if num else 0


def color_table(term):

    output = {}
    for color, code in X11_COLORNAMES_TO_RGB.items():

        if code in output:
            output[code] = '%s %s' % (output[code], color)
            continue

        chart = ''
        for noc in (1 << 24, 256, 16, 8):
            term.number_of_colors = noc
            chart += getattr(term, color)(u'█')

        output[code] = '%s %s' % (chart, color)

    for color in sorted(X11_COLORNAMES_TO_RGB, key=naturalize):
        code = X11_COLORNAMES_TO_RGB[color]
        if code in output:
            print(output.pop(code))


def color_chart(term):

    output = {}
    for color, code in X11_COLORNAMES_TO_RGB.items():

        if code in output:
            continue

        chart = ''
        for noc in (1 << 24, 256, 16, 8):
            term.number_of_colors = noc
            chart += getattr(term, color)(u'█')

        output[code] = chart

    width = term.width

    line = ''
    line_len = 0
    for color in sorted(X11_COLORNAMES_TO_RGB, key=naturalize):
        code = X11_COLORNAMES_TO_RGB[color]
        if code in output:
            chart = output.pop(code)
            if line_len + 5 > width:
                print(line)
                line = ''
                line_len = 0

            line += ' %s' % chart
            line_len += 5

    print(line)

    for color in sorted(X11_COLORNAMES_TO_RGB, key=naturalize):
        code = X11_COLORNAMES_TO_RGB[color]
        if code in output:
            print(output.pop(code))


if __name__ == '__main__':

    # color_table(blessed.Terminal())
    color_chart(blessed.Terminal())
