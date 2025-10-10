#!/usr/bin/env python
"""Display known information about our terminal."""
# pylint: disable=invalid-name
#         Invalid module name "display-terminalinfo"

# std imports
import os
import sys
import locale
import platform

BITMAP_IFLAG = {
    'IGNBRK': 'ignore BREAK condition',
    'BRKINT': 'map BREAK to SIGINTR',
    'IGNPAR': 'ignore (discard) parity errors',
    'PARMRK': 'mark parity and framing errors',
    'INPCK': 'enable checking of parity errors',
    'ISTRIP': 'strip 8th bit off chars',
    'INLCR': 'map NL into CR',
    'IGNCR': 'ignore CR',
    'ICRNL': 'map CR to NL (ala CRMOD)',
    'IXON': 'enable output flow control',
    'IXOFF': 'enable input flow control',
    'IXANY': 'any char will restart after stop',
    'IMAXBEL': 'ring bell on input queue full',
    'IUCLC': 'translate upper case to lower case',
}

BITMAP_OFLAG = {
    'OPOST': 'enable following output processing',
    'ONLCR': 'map NL to CR-NL (ala CRMOD)',
    'OXTABS': 'expand tabs to spaces',
    'ONOEOT': 'discard EOT\'s `^D\' on output)',
    'OCRNL': 'map CR to NL',
    'OLCUC': 'translate lower case to upper case',
    'ONOCR': 'No CR output at column 0',
    'ONLRET': 'NL performs CR function',
}

BITMAP_CFLAG = {
    'CSIZE': 'character size mask',
    'CS5': '5 bits (pseudo)',
    'CS6': '6 bits',
    'CS7': '7 bits',
    'CS8': '8 bits',
    'CSTOPB': 'send 2 stop bits',
    'CREAD': 'enable receiver',
    'PARENB': 'parity enable',
    'PARODD': 'odd parity, else even',
    'HUPCL': 'hang up on last close',
    'CLOCAL': 'ignore modem status lines',
    'CCTS_OFLOW': 'CTS flow control of output',
    'CRTSCTS': 'same as CCTS_OFLOW',
    'CRTS_IFLOW': 'RTS flow control of input',
    'MDMBUF': 'flow control output via Carrier',
}

BITMAP_LFLAG = {
    'ECHOKE': 'visual erase for line kill',
    'ECHOE': 'visually erase chars',
    'ECHO': 'enable echoing',
    'ECHONL': 'echo NL even if ECHO is off',
    'ECHOPRT': 'visual erase mode for hardcopy',
    'ECHOCTL': 'echo control chars as ^(Char)',
    'ISIG': 'enable signals INTR, QUIT, [D]SUSP',
    'ICANON': 'canonicalize input lines',
    'ALTWERASE': 'use alternate WERASE algorithm',
    'IEXTEN': 'enable DISCARD and LNEXT',
    'EXTPROC': 'external processing',
    'TOSTOP': 'stop background jobs from output',
    'FLUSHO': 'output being flushed (state)',
    'NOKERNINFO': 'no kernel output from VSTATUS',
    'PENDIN': 'XXX retype pending input (state)',
    'NOFLSH': 'don\'t flush after interrupt',
}

CTLCHAR_INDEX = {
    'VEOF': 'EOF',
    'VEOL': 'EOL',
    'VEOL2': 'EOL2',
    'VERASE': 'ERASE',
    'VWERASE': 'WERASE',
    'VKILL': 'KILL',
    'VREPRINT': 'REPRINT',
    'VINTR': 'INTR',
    'VQUIT': 'QUIT',
    'VSUSP': 'SUSP',
    'VDSUSP': 'DSUSP',
    'VSTART': 'START',
    'VSTOP': 'STOP',
    'VLNEXT': 'LNEXT',
    'VDISCARD': 'DISCARD',
    'VMIN': '---',
    'VTIME': '---',
    'VSTATUS': 'STATUS',
}


def display_bitmask(kind, bitmap, value):
    """Display all matching bitmask values for ``value`` given ``bitmap``."""
    import termios
    col1_width = max(map(len, list(bitmap.keys()) + [kind]))
    col2_width = 7
    fmt = '{name:>{col1_width}} {value:>{col2_width}}   {description}'
    print(fmt.format(name=kind,
                     value='Value',
                     description='Description',
                     col1_width=col1_width,
                     col2_width=col2_width))
    print(f"{'-' * col1_width} {'-' * col2_width}   "
          f"{'-' * max(map(len, bitmap.values()))}")
    for flag_name, description in bitmap.items():
        try:
            bitmask = getattr(termios, flag_name)
            bit_val = 'on' if bool(value & bitmask) else 'off'
        except AttributeError:
            bit_val = 'undef'
        print(fmt.format(name=flag_name,
                         value=bit_val,
                         description=description,
                         col1_width=col1_width,
                         col2_width=col2_width))
    print()


def display_ctl_chars(index, ctlc):
    """Display all control character indices, names, and values."""
    import termios
    title = 'Special Character'
    col1_width = len(title)
    col2_width = max(map(len, index.values()))
    fmt = '{idx:<{col1_width}}   {name:<{col2_width}} {value}'
    print('Special line Characters'.center(40).rstrip())
    print(fmt.format(idx='Index',
                     name='Name',
                     value='Value',
                     col1_width=col1_width,
                     col2_width=col2_width))
    print(f"{'-' * col1_width}   {'-' * col2_width} {'-' * 10}")
    for index_name, name in index.items():
        try:
            index = getattr(termios, index_name)
            value = ctlc[index]
            value = '_POSIX_VDISABLE' if value == b'\xff' else repr(value)
        except AttributeError:
            value = 'undef'
        print(fmt.format(idx=index_name,
                         name=name,
                         value=value,
                         col1_width=col1_width,
                         col2_width=col2_width))
    print()


def display_pathconf(names, getter):
    """Helper displays results of os.pathconf_names values."""
    col1_width = max(map(len, names))
    fmt = '{name:>{col1_width}}  {value}'
    print(fmt.format(name='pathconf'.ljust(col1_width), value='value',
                     col1_width=col1_width))
    print(f"{'-' * col1_width}  {'-' * 27}")
    for name in names:
        try:
            value = getter(name)
        except OSError as err:
            value = f'OSErrno {err.errno}'
        print(fmt.format(name=name, value=value, col1_width=col1_width))
    print()


def main():
    """Program entry point."""
    if platform.system() == 'Windows':
        print('No terminal on windows systems!')
        exit(0)

    import termios
    fd = sys.stdin.fileno()
    locale.setlocale(locale.LC_ALL, '')
    encoding = locale.getpreferredencoding()

    print(f'os.isatty({fd}) => {os.isatty(fd)}')
    print(f'locale.getpreferredencoding() => {encoding}')

    display_pathconf(names=os.pathconf_names,
                     getter=lambda name: os.fpathconf(fd, name))

    try:
        (iflag, oflag, cflag, lflag,
         _, _,  # input / output speed (bps macros)
         ctlc) = termios.tcgetattr(fd)
    except termios.error as err:
        print(f'stdin is not a typewriter: {err}')
    else:
        display_bitmask(kind='  Input Mode',
                        bitmap=BITMAP_IFLAG,
                        value=iflag)
        display_bitmask(kind=' Output Mode',
                        bitmap=BITMAP_OFLAG,
                        value=oflag)
        display_bitmask(kind='Control Mode',
                        bitmap=BITMAP_CFLAG,
                        value=cflag)
        display_bitmask(kind='  Local Mode',
                        bitmap=BITMAP_LFLAG,
                        value=lflag)
        display_ctl_chars(index=CTLCHAR_INDEX,
                          ctlc=ctlc)
        print(f'os.ttyname({fd}) => {os.ttyname(fd)}')
        print(f'os.ctermid() => {os.ttyname(fd)}')


if __name__ == '__main__':
    main()
