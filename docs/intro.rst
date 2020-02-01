| |pypi_downloads| |codecov| |windows| |linux| |mac| |bsd|

Introduction
============

Blessed is an easy, practical library for making terminal apps, by providing Colors_, interactive
Keyboard_ input, and screen Positioning_ capabilities.

.. code-block:: python

    from blessed import Terminal

    t = Terminal()

    print(t.home + t.clear + t.move_y(t.height // 2))
    print(t.black_on_darkkhaki(t.center('press any key to continue.')))

    with t.cbreak(), t.hidden_cursor():
        inp = t.inkey()

    print(t.move_down(2) + 'You pressed ' + t.bold(repr(inp)))

It's meant to be *fun* and *easy*, to do basic terminal graphics and styling with Python, making CLI
applications, games, editors, or other terminal utilities easy. Whatever it is, we hope you have
a blast making it!

Examples
--------

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/blessed_demo_intro.gif
   :alt: Animations of x11-colorpicker.py, bounce.py, worms.py, and plasma.py

   x11-colorpicker.py_, bounce.py_, worms.py_, and plasma.py_, from our repository.

Exemplary 3rd-party examples which use *blessed*,

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/demo_3rdparty_voltron.png
   :alt: Screenshot of 'Voltron' (By the author of Voltron, from their README).

   Voltron_ is an extensible debugger UI toolkit written in Python

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/demo_3rdparty_cursewords.gif
   :alt: Animation of 'cursewords' (By the author of cursewords, from their README).

   cursewords_ is "graphical" command line program for solving crossword puzzles in the terminal.

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/demo_3rdparty_githeat.gif
   :alt: Animation of 'githeat.interactive', using blessed repository at the time of capture.

   GitHeat_ builds an interactive heatmap of git history.

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/demo_3rdparty_dashing.gif
   :alt: Animations from 'Dashing' (By the author of Dashing, from their README)

   Dashing_ is a library to quickly create terminal-based dashboards.

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/demo_3rdparty_enlighten.gif
   :alt: Animations from 'Enlighten' (By the author of Enlighten, from their README)

   Enlighten_ Progress Bar is a console progress bar module.

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/blessed_3rdparty_macht.gif
   :alt: Demonstration of 'macht', a 2048 clone

   macht_ is a clone of the (briefly popular) puzzle game, 2048.

Requirements
------------

*Blessed* works with Windows, Mac, Linux, and BSD's, on Python 2.7, 3.4, 3.5, 3.6, 3.7, and 3.8.

Brief Overview
--------------

*Blessed* is more than just a Python wrapper around curses_:

* Styles, color, and maybe a little positioning without necessarily clearing the whole screen first.
* Works great with standard Python string formatting.
* Provides up-to-the-moment terminal height and width, so you can respond to terminal size changes.
* Avoids making a mess if the output gets piped to a non-terminal: outputs to any file-like object
  such as *StringIO*, files, or pipes.
* Uses the `terminfo(5)`_ database so it works with any terminal type and supports any terminal
  capability: No more C-like calls to tigetstr_ and tparm_.
* Keeps a minimum of internal state, so you can feel free to mix and match with calls to curses or
  whatever other terminal libraries you like.
* Provides context managers to safely express terminal modes `Terminal.fullscreen()`
  and `Terminal.hidden_cursor()`.
* Act intelligently when somebody redirects your output to a file, omitting all of the terminal
  sequences such as styling, colors, or positioning.
* Dead-simple keyboard handling: safely decoding unicode input in your system's preferred locale and
  supports application/arrow keys.

*Blessed* is a fork of `blessings <https://github.com/erikrose/blessings>`_, which does all of
the same above with the same API, as well as following **enhancements**:

* Windows support, new since Dec. 2019!
* Allows sequences to be removed from strings that contain them, using `Terminal.strip_seqs()`_ or
  sequences and whitespace using `Terminal.strip()`_.
* Allows the *printable length* of strings that contain sequences to be determined by
  `Terminal.length()`_, supporting additional methods `Terminal.wrap()`_ and `Terminal.center()`_,
  terminal-aware variants of the built-in function `textwrap.wrap()`_ and method `str.center()`_,
  respectively.
* 24-bit color support, using `Terminal.color_rgb()`_ and `Terminal.on_color_rgb()`_ and all X11
  Colors_ by name, and not by number.
* Determine cursor location using `Terminal.location()`, enter key-at-a-time input mode using
  `Terminal.cbreak()`_ or `Terminal.raw()`_ context managers, and read timed key presses using
  `Terminal.inkey()`_.

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




Further Documentation
---------------------

Full documentation at http://blessed.readthedocs.org/en/latest/

.. _curses: https://docs.python.org/3/library/curses.html
.. _tigetstr: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man3/tigetstr.3
.. _tparm: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man3/tparm.3
.. _`terminfo(5)`: http://invisible-island.net/ncurses/man/terminfo.5.html
.. _str.center(): https://docs.python.org/3/library/stdtypes.html#str.center
.. _textwrap.wrap(): https://docs.python.org/3/library/textwrap.html#textwrap.wrap
.. _`Terminal.color_rgb()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.color_rgb
.. _`Terminal.on_color_rgb()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.on_color_rgb
.. _`Terminal.length()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.length
.. _`Terminal.strip()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.strip
.. _`Terminal.rstrip()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.rstrip
.. _`Terminal.lstrip()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.lstrip
.. _`Terminal.strip_seqs()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.strip_seqs
.. _`Terminal.wrap()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.wrap
.. _`Terminal.center()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.center
.. _`Terminal.rjust()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.rjust
.. _`Terminal.ljust()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.ljust
.. _`Terminal.cbreak()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.cbreak
.. _`Terminal.raw()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.raw
.. _`Terminal.inkey()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.inkey
.. _Colors: https://blessed.readthedocs.io/en/stable/colors.html
.. _Keyboard: https://blessed.readthedocs.io/en/stable/keyboard.html
.. _Positioning: https://blessed.readthedocs.io/en/stable/positioning.html
.. _Examples: https://blessed.readthedocs.io/en/stable/examples.html
.. _x11-colorpicker.py: https://blessed.readthedocs.io/en/stable/examples.html#x11-colorpicker-py
.. _bounce.py: https://blessed.readthedocs.io/en/stable/examples.html#bounce-py
.. _worms.py: https://blessed.readthedocs.io/en/stable/examples.html#worms-py
.. _plasma.py: https://blessed.readthedocs.io/en/stable/examples.html#plasma-py
.. _Voltron: https://github.com/snare/voltron
.. _cursewords: https://github.com/thisisparker/cursewords
.. _GitHeat: https://github.com/AmmsA/Githeat
.. _Dashing: https://github.com/FedericoCeratto/dashing
.. _Enlighten: https://github.com/Rockhopper-Technologies/enlighten
.. _macht: https://github.com/rolfmorel/macht
.. |pypi_downloads| image:: https://img.shields.io/pypi/dm/blessed.svg?logo=pypi
    :alt: Downloads
    :target: https://pypi.python.org/pypi/blessed
.. |codecov| image:: https://codecov.io/gh/jquast/blessed/branch/master/graph/badge.svg
    :alt: codecov.io Code Coverage
    :target: https://codecov.io/gh/jquast/blessed
.. |linux| image:: https://img.shields.io/badge/Linux-yes-success?logo=linux
    :alt: Linux supported
.. |windows| image:: https://img.shields.io/badge/Windows-NEW-success?logo=windows
    :alt: Windows supported
.. |mac| image:: https://img.shields.io/badge/MacOS-yes-success?logo=apple
    :alt: MacOS supported
.. |bsd| image:: https://img.shields.io/badge/BSD-yes-success?logo=freebsd
    :alt: BSD supported
