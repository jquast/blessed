| |docs| |travis| |coveralls|
| |pypi| |downloads| |gitter|
| |linux| |windows| |mac| |bsd|

.. |docs| image:: https://img.shields.io/readthedocs/blessed.svg?logo=read-the-docs
    :target: https://blessed.readthedocs.org
    :alt: Documentation Status

.. |travis| image:: https://img.shields.io/travis/jquast/blessed/master.svg?logo=travis
    :alt: Travis Continuous Integration
    :target: https://travis-ci.org/jquast/blessed/

.. |coveralls| image:: https://img.shields.io/coveralls/github/jquast/blessed/master?logo=coveralls
    :alt: Coveralls Code Coverage
    :target: https://coveralls.io/github/jquast/blessed?branch=master

.. |pypi| image:: https://img.shields.io/pypi/v/blessed.svg?logo=pypi
    :alt: Latest Version
    :target: https://pypi.python.org/pypi/blessed

.. |downloads| image:: https://img.shields.io/pypi/dm/blessed.svg?logo=pypi
    :alt: Downloads
    :target: https://pypi.python.org/pypi/blessed

.. |gitter| image:: https://img.shields.io/badge/gitter-Join%20Chat-mediumaquamarine?logo=gitter
    :alt: Join Chat
    :target: https://gitter.im/jquast/blessed

.. |linux| image:: https://img.shields.io/badge/Linux-yes-success?logo=linux
    :alt: Linux supported
    :target: https://pypi.python.org/pypi/enlighten

.. |windows| image:: https://img.shields.io/badge/Windows-NEW-success?logo=windows
    :alt: Windows supported
    :target: https://pypi.python.org/pypi/enlighten

.. |mac| image:: https://img.shields.io/badge/MacOS-yes-success?logo=apple
    :alt: MacOS supported
    :target: https://pypi.python.org/pypi/enlighten

.. |bsd| image:: https://img.shields.io/badge/BSD-yes-success?logo=freebsd
    :alt: BSD supported
    :target: https://pypi.python.org/pypi/enlighten

Introduction
============

Blessed is a thin, practical wrapper around terminal capabilities in Python.

Coding with *Blessed* looks like this...

.. code-block:: python

    from blessed import Terminal

    t = Terminal()

    print(t.bold('Hi there!'))
    print(t.bold_red_on_bright_green('It hurts my eyes!'))

    with t.location(0, t.height - 1):
        print(t.center(t.blink('press any key to continue.')))

    with t.cbreak():
        inp = t.inkey()
    print('You pressed ' + repr(inp))


Brief Overview
--------------

*Blessed* is a more simplified wrapper around curses_, providing :

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

Before And After
----------------

With the built-in curses_ module, this is how you would typically
print some underlined text at the bottom of the screen:

.. code-block:: python

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

The same program with *Blessed* is simply:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.location(0, term.height - 1):
        print('This is' + term.underline('underlined') + '!')

Requirements
------------

*Blessed* is tested with Python 2.7, 3.4, 3.5, 3.6, and 3.7 on Linux, Mac, and
FreeBSD.  Windows support was just added in October 2019, give it a try, and
please report any strange issues!

Further Documentation
---------------------

More documentation can be found at http://blessed.readthedocs.org/en/latest/

Bugs, Contributing, Support
---------------------------

**Bugs** or suggestions? Visit the `issue tracker`_ and file an issue.
We welcome your bug reports and feature suggestions!

Would you like to **contribute**?  That's awesome!  We've written a
`guide <http://blessed.readthedocs.org/en/latest/contributing.html>`_
to help you.

Are you stuck and need **support**?  Give `stackoverflow`_ a try.  If
you're still having trouble, we'd like to hear about it!  Open an issue
in the `issue tracker`_ with a well-formed question.

License
-------

*Blessed* is under the MIT License. See the LICENSE file.

Forked
------

*Blessed* is a fork of `blessings <https://github.com/erikrose/blessings>`_.
Changes since 1.7 have all been proposed but unaccepted upstream.

Enhancements only in *Blessed*:
  * 24-bit color support with :meth:`~Terminal.color_rgb` and :meth:`~Terminal.on_color_rgb` methods
  * X11 color name attributes
  * Windows support
  * :meth:`~.Terminal.length` to determine printable length of text containing sequences
  * :meth:`~.Terminal.strip`, :meth:`~.Terminal.rstrip`, :meth:`~.Terminal.rstrip`,
    and :meth:`~.Terminal.strip_seqs` for removing sequences from text
  * :meth:`Terminal.wrap` for wrapping text containing sequences at a specified width
  * :meth:`~.Terminal.center`, :meth:`~.Terminal.rjust`, and :meth:`~.Terminal.ljust`
    for alignment of text containing sequences
  * :meth:`~.cbreak` and :meth:`~.raw` context managers for keyboard input
  * :meth:`~.inkey` for keyboard event detection

Furthermore, a project in the node.js language of the `same name
<https://github.com/chjj/blessed>`_ is **not** related, or a fork
of each other in any way.

.. _`issue tracker`: https://github.com/jquast/blessed/issues/
.. _curses: https://docs.python.org/3/library/curses.html
.. _tigetstr: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man3/tigetstr.3
.. _tparm: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man3/tparm.3
.. _ansi: https://github.com/tehmaze/ansi
.. _colorama: https://pypi.python.org/pypi/colorama
.. _PDCurses: http://www.lfd.uci.edu/~gohlke/pythonlibs/#curses
.. _`terminfo(5)`: http://invisible-island.net/ncurses/man/terminfo.5.html
.. _`stackoverflow`: http://stackoverflow.com/
