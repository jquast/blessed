#!/usr/bin/env python
"""
Determines and prints COLUMNS and LINES of the attached window width.

A strange problem: programs that perform screen addressing incorrectly
determine the screen margins.  Calls to reset(1) do not resolve the
issue.

This may often happen because the transport is incapable of communicating
the terminal size, such as over a serial line.  To resolve the issue,
simply call this program:

This demonstration program produces output that must be evaluated as
part of a bourne-like shell command::

        $ eval `$HOME/bin/resize.py`

The following remote login protocols communicate the connecting window size:

 - ssh protocol reserves on the session channel, such as in
   ``paramiko.ServerInterface.check_channel_window_change_request``.
 - telnet protocol sends window size through NAWS
   (negotiate about window size, RFC 1073), such as in
   ``telnetlib3.TelnetServer.naws_receive``.
 - the rlogin protocol may only send initial window size.

This is a simplified version of `resize.c
<https://github.com/joejulian/xterm/blob/master/resize.c>`_ provided by the
xterm package.
"""
# std imports
from __future__ import print_function
import collections

# local
from blessed import Terminal


def main():
    """Program entry point."""

    Position = collections.namedtuple('Position', ('row', 'column'))

    term = Terminal()

    # Move the cursor to the farthest lower-right hand corner that is
    # reasonable.  Due to word size limitations in older protocols, 999,999
    # is our most reasonable and portable edge boundary.  Telnet NAWS is just
    # two unsigned shorts: ('!HH' in python struct module format).
    with term.location(999, 999):

        # We're not likely at (999, 999), but a well behaved terminal emulator
        # will do its best to accommodate our request, positioning the cursor
        # to the farthest lower-right corner.  By requesting the current
        # position, we may negotiate about the window size directly with the
        # terminal emulator connected at the distant end.
        pos = Position(*term.get_location(timeout=5.0))

        if -1 not in pos:
            # true size was determined
            lines, columns = pos.row, pos.column

        else:
            # size could not be determined. Oh well, the built-in blessed
            # properties will use termios if available, falling back to
            # existing environment values if it has to.
            lines, columns = term.height, term.width

    print("COLUMNS={columns};\nLINES={lines};\nexport COLUMNS LINES;"
          .format(columns=columns, lines=lines))


if __name__ == '__main__':
    exit(main())
