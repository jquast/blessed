import colorsys
import blessed

hsv_sorted_colors = sorted(
    blessed.colorspace.X11_COLORNAMES_TO_RGB.items(),
    key=lambda rgb: colorsys.rgb_to_hsv(*rgb[1]),
    reverse=True)


def render(term, idx):
    color_name, rgb_color = hsv_sorted_colors[idx]
    result = term.home + term.normal + ''.join(
        getattr(term, hsv_sorted_colors[i][0]) + '◼'
        for i in range(len(hsv_sorted_colors))
    )
    result += term.clear_eos + '\n'
    result += getattr(term, 'on_' + color_name) + term.clear_eos + '\n'
    result += term.normal + term.center(f'{color_name}: {rgb_color}') + '\n'
    result += term.normal + term.center(
        f'{term.number_of_colors} colors - '
        f'{term.color_distance_algorithm}')

    result += term.move(idx // term.width, idx % term.width)
    result += term.on_color_rgb(*rgb_color)(' \b')
    return result


def next_algo(algo, forward):
    algos = tuple(sorted(blessed.color.COLOR_DISTANCE_ALGORITHMS))
    next_index = algos.index(algo) + (1 if forward else -1)
    if next_index == len(algos):
        next_index = 0
    return algos[next_index]


def next_color(color, forward):
    colorspaces = (4, 8, 16, 256, 1 << 24)
    next_index = colorspaces.index(color) + (1 if forward else -1)
    if next_index == len(colorspaces):
        next_index = 0
    return colorspaces[next_index]


def main():
    term = blessed.Terminal()
    with term.cbreak(), term.hidden_cursor(), term.fullscreen():
        idx = len(hsv_sorted_colors) // 2
        dirty = True
        while True:
            if dirty:
                outp = render(term, idx)
                print(outp, end='', flush=True)
            with term.hidden_cursor():
                inp = term.inkey()
            dirty = True
            if inp.code == term.KEY_LEFT or inp == 'h':
                idx -= 1
            elif inp.code == term.KEY_DOWN or inp == 'j':
                idx += term.width
            elif inp.code == term.KEY_UP or inp == 'k':
                idx -= term.width
            elif inp.code == term.KEY_RIGHT or inp == 'l':
                idx += 1
            elif inp.code in (term.KEY_TAB, term.KEY_BTAB):
                term.number_of_colors = next_color(
                    term.number_of_colors, inp.code == term.KEY_TAB)
            elif inp in ('[', ']'):
                term.color_distance_algorithm = next_algo(
                    term.color_distance_algorithm, inp == '[')
            elif inp == '\x0c':
                pass
            else:
                dirty = False

            while idx < 0:
                idx += len(hsv_sorted_colors)
            while idx >= len(hsv_sorted_colors):
                idx -= len(hsv_sorted_colors)


if __name__ == '__main__':
    main()
