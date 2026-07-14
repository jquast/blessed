#!/usr/bin/env python
import sys
import unicodedata

import wcwidth

from blessed import Terminal


def main():
    term = Terminal()

    print('reading...' + term.clear_eol, end='', file=sys.stdout)
    all_codepoints = set()
    for filepath in sys.argv[1:]:
        with open(filepath, 'r') as f:
            all_codepoints.update(unicodedata.normalize('NFC', f.read()))

    print('\rtesting...' + term.clear_eol, end='', file=sys.stdout)
    codepoints_to_test = {cp for cp in all_codepoints if wcwidth.wcwidth(cp) != 0}
    codepoints_str = ''.join(sorted(codepoints_to_test))
    supported_str = ''
    _batchsize = 100
    for i in range(0, len(codepoints_str), _batchsize):
        bs = '' if i == 0 else len(str(i - _batchsize)) * '\b'
        print(f'{bs}{i}', end='', file=sys.stdout)
        batch = codepoints_str[i:i + _batchsize]
        result = term.does_font_have_codepoints(batch)
        if result is None:
            print('\rFont glyph protocol not supported by this terminal.',
                  file=sys.stderr)
            return 1
        supported_str += result

    unsupported = set(codepoints_to_test) - set(supported_str)

    print('\rreporting' + term.clear_eol + '\r', end='', file=sys.stdout)
    if not unsupported:
        return 0

    tofu_count = 0
    for filepath in sys.argv[1:]:
        with open(filepath, 'r') as f:
            for lineno, line in enumerate(f, 1):
                line = unicodedata.normalize('NFC', line.rstrip('\n'))
                line_unsupported = [cp for cp in line if cp in unsupported]
                n = len(line_unsupported)
                if n == 0:
                    continue
                tofu_count += n
                decorated = ''.join(
                    term.bold_red(cp) if cp in unsupported else cp
                    for cp in line)
                print(f'{n} {filepath}:{lineno} {decorated}')

    return 1 if tofu_count else 0


if __name__ == '__main__':
    sys.exit(main())
