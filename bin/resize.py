#!/usr/bin/env python
"""
Determines and prints COLUMNS and LINES of the attached window width.

A strange problem: programs that perform screen addressing incorrectly
determine the screen margins.  Calls to reset(1) do not resolve the
issue.

This may often happen because the transport is incapable of communicating
the terminal size, such as over a serial line.  This demonstration program
determines true screen dimensions and produces output suitable for evaluation
by a bourne-like shell::

        $ eval `./resize.py`

The following remote login protocols communicate window size:

 - ssh: notifies on dedicated session channel, see for example,
   ``paramiko.ServerInterface.check_channel_window_change_request``.

 - telnet: sends window size through NAWS (negotiate about window
   size, RFC 1073), see for example,
   ``telnetlib3.TelnetServer.naws_receive``.

 - rlogin: protocol sends only initial window size, and does not notify
   about size changes.

This is a simplified version of `resize.c
<https://github.com/joejulian/xterm/blob/master/resize.c>`_ provided by the
xterm package.
"""

# std imports
import sys
import collections

# local
from blessed import Terminal


def main():
    """Program entry point."""
    # pylint: disable=invalid-name
    #         Invalid variable name "Position"
    Position = collections.namedtuple('Position', ('row', 'column'))

    # particularly strange, we use sys.stderr as our output stream device,
    # this 'stream' file descriptor is only used for side effects, of which
    # this application uses two: the term.location() has an implied write,
    # as does get_position().
    #
    # the reason we chose stderr is to ensure that the terminal emulator
    # receives our bytes even when this program is wrapped by shell eval
    # `resize.py`; backticks gather stdout but not stderr in this case.
    term = Terminal(stream=sys.stderr)

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
        pos = Position(*term.get_location())

        if -1 not in pos:
            # true size was determined
            lines, columns = pos.row, pos.column

        else:
            # size could not be determined. Oh well, the built-in blessed
            # properties will use termios if available, falling back to
            # existing environment values if it has to.
            lines, columns = term.height, term.width

    print(f"COLUMNS={columns};\nLINES={lines};\nexport COLUMNS LINES;"
          )


if __name__ == '__main__':
    exit(main())
