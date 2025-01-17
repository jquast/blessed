#!/usr/bin/env python
"""
A tool which uses pexpect to test expected Canonical mode length.

All systems use the value of MAX_CANON which can be found using fpathconf(3) value PC_MAX_CANON --
with the exception of Linux and FreeBSD.

Linux, though defining a value of 255, actually honors the value of 4096 from linux kernel include
file tty.h definition N_TTY_BUF_SIZE.

Linux also does not honor IMAXBEL. termios(3) states, "Linux does not implement this bit, and acts
as if it is always set." Although these tests ensure it is enabled, this is a non-op for Linux.

FreeBSD supports neither, and instead uses a fraction (1/5) of the tty speed which is always 9600.
Therefore, the maximum limited input line length is 9600 / 5 = 1920.

In other words, the only way to determine the true MAX_CANON in a cross-platform manner is through
this systems integrated test: the given system definitions are misleading on some operating systems.
"""
# pylint: disable=invalid-name
#         Invalid module name "display-sighandlers"
from __future__ import print_function

# std imports
import os
import sys


def detect_maxcanon():
    """Program entry point."""
    import pexpect
    bashrc = os.path.join(
        # reuse pexpect/replwrap.py's bashrc file,
        os.path.dirname(__file__), os.path.pardir, 'pexpect', 'bashrc.sh')

    child = pexpect.spawn('bash', ['--rcfile', bashrc],
                          echo=True, encoding='utf8',
                          timeout=3)

    child.sendline(u'echo -n READY_; echo GO')
    child.expect_exact(u'READY_GO')

    child.sendline(u'stty icanon imaxbel erase ^H; echo -n retval: $?')
    child.expect_exact(u'retval: 0')

    child.sendline(u'echo -n GO_; echo AGAIN')
    child.expect_exact(u'GO_AGAIN')
    child.sendline(u'cat')

    child.delaybeforesend = 0

    column, blocksize = 0, 64
    ch_marker = u'_'

    print('auto-detecting MAX_CANON: ', end='')
    sys.stdout.flush()

    while True:
        child.send(ch_marker * blocksize)
        result = child.expect([ch_marker * blocksize, u'\a', pexpect.TIMEOUT])
        if result == 0:
            # entire block fit without emitting bel
            column += blocksize
        elif result == 1:
            # an '\a' was emitted, count the number of ch_markers
            # found since last blocksize, determining our MAX_CANON
            column += child.before.count(ch_marker)
            break
        elif result == 3:
            print('Undetermined (Timeout) !')
            print(('child.before: ', child.before))
    print(column)


if __name__ == '__main__':
    try:
        detect_maxcanon()
    except ImportError:
        # we'd like to use this with CI -- but until we integrate
        # with tox, we can't determine a period in testing when
        # the pexpect module has been installed
        print('warning: pexpect not in module path, MAX_CANON '
              'could not be determined by systems test.',
              file=sys.stderr)
