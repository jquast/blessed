#!/usr/bin/env python
"""Displays os.fpathconf values related to terminals."""
# pylint: disable=invalid-name
#         Invalid module name "display-sighandlers"

# std imports
import os
import sys


def display_fpathconf():
    """Program entry point."""
    if not hasattr(os, "pathconf_names"):
        return

    disp_values = (
        ('PC_MAX_CANON', ('Max no. of bytes in a '
                          'terminal canonical input line.')),
        ('PC_MAX_INPUT', ('Max no. of bytes for which '
                          'space is available in a terminal input queue.')),
        ('PC_PIPE_BUF', ('Max no. of bytes which will '
                         'be written atomically to a pipe.')),

        # to explain in more detail: PC_VDISABLE is the reference character in
        # the pairing output for bin/display-terminalinfo.py: if the value
        # matches (\xff), then that special control character is disabled, fe:
        #
        #          Index Name    Special Character    Default Value
        #          VEOF          EOF                  ^D
        #          VEOL          EOL                  _POSIX_VDISABLE
        #
        # regardless, this value is almost always \xff.
        ('PC_VDISABLE', 'Terminal character disabling value.')
    )
    fmt = '{name:<13} {value:<10} {description:<11}'

    # column header
    print(fmt.format(name='name', value='value', description='description'))
    print(fmt.replace('<', '-<').format(name='-', value='-', description='-'))

    fd = sys.stdin.fileno()
    for name, description in disp_values:
        key = os.pathconf_names.get(name, None)
        if key is None:
            value = 'UNDEF'
        else:
            try:
                value = os.fpathconf(fd, name)
                if name == 'PC_VDISABLE':
                    value = fr'\x{value:02x}'
            except OSError as err:
                value = f'OSErrno {err.errno}'

        print(fmt.format(name=name, value=value, description=description))
    print()


if __name__ == '__main__':
    display_fpathconf()
