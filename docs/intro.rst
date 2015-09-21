.. image:: https://img.shields.io/travis/erikrose/blessings.svg
    :alt: Travis Continous Integration
    :target: https://travis-ci.org/erikrose/blessings/

.. image:: https://img.shields.io/teamcity/http/teamcity-master.pexpect.org/s/Blessings_BuildHead.png
    :alt: TeamCity Build status
    :target: https://teamcity-master.pexpect.org/viewType.html?buildTypeId=Blessings_BuildHead&branch_Blessings=%3Cdefault%3E&tab=buildTypeStatusDiv

.. image:: https://coveralls.io/repos/erikrose/blessings/badge.png?branch=master
    :alt: Coveralls Code Coverage
    :target: https://coveralls.io/r/erikrose/blessings?branch=master

.. image:: https://img.shields.io/pypi/v/blessings.svg
    :alt: Latest Version
    :target: https://pypi.python.org/pypi/blessings

.. image:: https://pypip.in/license/blessings/badge.svg
    :alt: License
    :target: http://opensource.org/licenses/MIT

.. image:: https://img.shields.io/pypi/dm/blessings.svg
    :alt: Downloads
    :target: https://pypi.python.org/pypi/blessings

Introduction
============

Blessings is a thin, practical wrapper around terminal capabilities in Python.

Coding with *Blessings* looks like this... ::

    from blessings import Terminal

    t = Terminal()

    print(t.bold('Hi there!'))
    print(t.bold_red_on_bright_green('It hurts my eyes!'))

    with t.location(0, t.height - 1):
        print(t.center(t.blink('press any key to continue.')))

    with t.keystroke_input():
        inp = t.keystroke()
    print('You pressed ' + repr(inp))


Brief Overview
--------------

*Blessings* is a more simplified wrapper around curses_, providing :

* Styles, color, and maybe a little positioning without necessarily
  clearing the whole screen first.
* Works great with standard Python string formatting.
* Provides up-to-the-moment terminal height and width, so you can respond to
  terminal size changes.
* Avoids making a mess if the output gets piped to a non-terminal:
  outputs to any file-like object such as *StringIO*, files, or pipes.
* Uses the `terminfo(5)`_ database so it works with any terminal type
  and supports any terminal capability: No more C-like calls to tigetstr_
  and tparm_.
* Keeps a minimum of internal state, so you can feel free to mix and match with
  calls to curses or whatever other terminal libraries you like.
* Provides plenty of context managers to safely express terminal modes,
  automatically restoring the terminal to a safe state on exit.
* Act intelligently when somebody redirects your output to a file, omitting
  all of the terminal sequences such as styling, colors, or positioning.
* Dead-simple keyboard handling: safely decoding unicode input in your
  system's preferred locale and supports application/arrow keys.
* Allows the printable length of strings containing sequences to be
  determined.

Blessings **does not** provide...

* Windows command prompt support.  A PDCurses_ build of python for windows
  provides only partial support at this time -- there are plans to merge with
  the ansi_ module in concert with colorama_ to resolve this.  `Patches welcome
  <https://github.com/erikrose/blessings/issues/21>`_!


Before And After
----------------

With the built-in curses_ module, this is how you would typically
print some underlined text at the bottom of the screen::

    from curses import tigetstr, setupterm, tparm
    from fcntl import ioctl
    from os import isatty
    import struct
    import sys
    from termios import TIOCGWINSZ

    # If we want to tolerate having our output piped to other commands or
    # files without crashing, we need to do all this branching:
    if hasattr(sys.stdout, 'fileno') and isatty(sys.stdout.fileno()):
        setupterm()
        sc = tigetstr('sc')
        cup = tigetstr('cup')
        rc = tigetstr('rc')
        underline = tigetstr('smul')
        normal = tigetstr('sgr0')
    else:
        sc = cup = rc = underline = normal = ''

    # Save cursor position.
    print(sc)

    if cup:
        # tigetnum('lines') doesn't always update promptly, hence this:
        height = struct.unpack('hhhh', ioctl(0, TIOCGWINSZ, '\000' * 8))[0]

        # Move cursor to bottom.
        print(tparm(cup, height - 1, 0))

    print('This is {under}underlined{normal}!'
          .format(under=underline, normal=normal))

    # Restore cursor position.
    print(rc)

The same program with *Blessings* is simply::

    from blessings import Terminal

    term = Terminal()
    with term.location(0, term.height - 1):
        print('This is' + term.underline('underlined') + '!')

Further Documentation
---------------------

More documentation can be found at http://blessings.readthedocs.org/en/latest/

Bugs, Contributing, Support
---------------------------

**Bugs** or suggestions? Visit the `issue tracker`_ and file an issue.
We welcome your bug reports and feature suggestions!

Would you like to **contribute**?  That's awesome!  We've written a
`guide <http://blessings.readthedocs.org/en/latest/contributing.html>`_
to help you.

Are you stuck and need **support**?  Give `stackoverflow`_ a try.  If
you're still having trouble, we'd like to hear about it!  Open an issue
in the `issue tracker`_ with a well-formed question.

License
-------

Blessings is under the MIT License. See the LICENSE file.

.. _`issue tracker`: https://github.com/erikrose/blessings/issues/
.. _curses: https://docs.python.org/3/library/curses.html
.. _tigetstr: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man3/tigetstr.3
.. _tparm: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man3/tparm.3
.. _ansi: https://github.com/tehmaze/ansi
.. _colorama: https://pypi.python.org/pypi/colorama
.. _PDCurses: http://www.lfd.uci.edu/~gohlke/pythonlibs/#curses
.. _`terminfo(5)`: http://invisible-island.net/ncurses/man/terminfo.5.html
.. _`stackoverflow`: http://stackoverflow.com/
