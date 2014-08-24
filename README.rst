.. image:: https://img.shields.io/travis/jquast/blessed.svg
    :alt: Travis Continous Integration
    :target: https://travis-ci.org/jquast/blessed

.. image:: https://img.shields.io/coveralls/jquast/blessed.svg
    :alt: Coveralls Code Coverage
    :target: https://coveralls.io/r/jquast/blessed

.. image:: https://img.shields.io/pypi/v/blessed.svg
    :alt: Latest Version
    :target: https://pypi.python.org/pypi/blessed

.. image:: https://pypip.in/license/blessed/badge.svg
    :alt: License
    :target: http://opensource.org/licenses/MIT

.. image:: https://img.shields.io/pypi/dm/blessed.svg
    :alt: Downloads

=======
Blessed
=======

Coding with *Blessed* looks like this... ::

    from blessed import Terminal

    t = Terminal()

    print(t.bold('Hi there!'))
    print(t.bold_red_on_bright_green('It hurts my eyes!'))

    with t.location(0, t.height - 1):
        print(t.center(t.blink('press any key to continue.')))

    with t.cbreak():
        t.inkey()


The Pitch
=========

*Blessed* is a more simplified wrapper around curses_, providing :

* Styles, color, and maybe a little positioning without necessarily
  clearing the whole screen first.
* Leave more than one screenful of scrollback in the buffer after your program
  exits, like a well-behaved command-line application should.
* No more C-like calls to tigetstr_ and `tparm`_.
* Act intelligently when somebody redirects your output to a file, omitting
  all of the terminal sequences such as styling, colors, or positioning.
* Dead-simple keyboard handling, modeled after the Basic language's *INKEY$*

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
    print(sc)  # Save cursor position.
    if cup:
        # tigetnum('lines') doesn't always update promptly, hence this:
        height = struct.unpack('hhhh', ioctl(0, TIOCGWINSZ, '\000' * 8))[0]
        print(tparm(cup, height - 1, 0))  # Move cursor to bottom.
    print('This is {under}underlined{normal}!'.format(under=underline,
                                                      normal=normal))
    print(rc)  # Restore cursor position.

The same program with *Blessed* is simply::

    from blessed import Terminal

    term = Terminal()
    with term.location(0, term.height - 1):
        print('This is', term.underline('pretty!'))


Screenshots
===========

.. image:: http://jeffquast.com/blessed-weather.png
   :target: http://jeffquast.com/blessed-weather.png
   :scale: 50 %
   :alt: Weather forecast demo (by @jquast)

.. image:: http://jeffquast.com/blessed-tetris.png
   :target: http://jeffquast.com/blessed-tetris.png
   :scale: 50 %
   :alt: Tetris game demo (by @johannesl)

.. image:: http://jeffquast.com/blessed-wall.png
   :target: http://jeffquast.com/blessed-wall.png
   :scale: 50 %
   :alt: bbs-scene.org api oneliners demo (art by xzip!impure)

.. image:: http://jeffquast.com/blessed-quick-logon.png
   :target: http://jeffquast.com/blessed-quick-logon.png
   :scale: 50 %
   :alt: x/84 bbs quick logon screen (art by xzip!impure)


What It Provides
================

Blessed provides just **one** top-level object: *Terminal*. Instantiating a
*Terminal* figures out whether you're on a terminal at all and, if so, does
any necessary setup. After that, you can proceed to ask it all sorts of things
about the terminal, such as its size and color support, and use its styling
to construct strings containing color and styling. Also, the special sequences
inserted with application keys (arrow and function keys) are understood and
decoded, as well as your locale-specific encoded multibyte input.


Simple Formatting
-----------------

Lots of handy formatting codes are available as attributes on a *Terminal* class
instance. For example::

    from blessed import Terminal

    term = Terminal()
    print('I am ' + term.bold + 'bold' + term.normal + '!')

These capabilities (*bold*, *normal*) are translated to their sequences, which
when displayed simply change the video attributes.  And, when used as a callable,
automatically wraps the given string with this sequence, and terminates it with
*normal*.

The same can be written as::

    print('I am' + term.bold('bold') + '!')

You may also use the *Terminal* instance as an argument for ``.format`` string
method, so that capabilities can be displayed in-line for more complex strings::

    print('{t.red_on_yellow}Candy corn{t.normal} for everyone!'.format(t=term))


Capabilities
------------

The basic capabilities supported by most terminals are:

``bold``
  Turn on 'extra bright' mode.
``reverse``
  Switch fore and background attributes.
``blink``
  Turn on blinking.
``normal``
  Reset attributes to default.

The less commonly supported capabilities:

``dim``
  Enable half-bright mode.
``underline``
  Enable underline mode.
``no_underline``
  Exit underline mode.
``italic``
  Enable italicized text.
``no_italic``
  Exit italics.
``shadow``
  Enable shadow text mode (rare).
``no_shadow``
  Exit shadow text mode.
``standout``
  Enable standout mode (often, an alias for ``reverse``.).
``no_standout``
  Exit standout mode.
``subscript``
  Enable subscript mode.
``no_subscript``
  Exit subscript mode.
``superscript``
  Enable superscript mode.
``no_superscript``
  Exit superscript mode.
``flash``
  Visual bell, flashes the screen.

Note that, while the inverse of *underline* is *no_underline*, the only way
to turn off *bold* or *reverse* is *normal*, which also cancels any custom
colors.

Many of these are aliases, their true capability names (such as 'smul' for
'begin underline mode') may still be used. Any capability in the `terminfo(5)`_
manual, under column **Cap-name**, may be used as an attribute to a *Terminal*
instance. If it is not a supported capability, or a non-tty is used as an
output stream, an empty string is returned.


Colors
------

Color terminals are capable of at least 8 basic colors.

* ``black``
* ``red``
* ``green``
* ``yellow``
* ``blue``
* ``magenta``
* ``cyan``
* ``white``

The same colors, prefixed with *bright_* (synonymous with *bold_*),
such as *bright_blue*, provides 16 colors in total.

The same colors, prefixed with *on_* sets the background color, some
terminals also provide an additional 8 high-intensity versions using
*on_bright*, some example compound formats::

    from blessed import Terminal

    term = Terminal()

    print(term.on_bright_blue('Blue skies!'))
    print(term.bright_red_on_bright_yellow('Pepperoni Pizza!'))

There is also a numerical interface to colors, which takes an integer from
0-15.::

    from blessed import Terminal

    term = Terminal()

    for n in range(16):
        print(term.color(n)('Color {}'.format(n)))

If the terminal defined by the **TERM** environment variable does not support
colors, these simply return empty strings, or the string passed as an argument
when used as a callable, without any video attributes. If the **TERM** defines
a terminal that does support colors, but actually does not, they are usually
harmless.

Colorless terminals, such as the amber or monochrome *vt220*, do not support
colors but do support reverse video. For this reason, it may be desirable in
some applications, such as a selection bar, to simply select a foreground
color, followed by reverse video to achieve the desired background color
effect::

    from blessed import Terminal

    term = Terminal()

    print('some terminals {standout} more than others'.format(
        standout=term.green_reverse('standout')))

Which appears as *bright white on green* on color terminals, or *black text
on amber or green* on monochrome terminals.  You can check whether the terminal
definition used supports colors, and how many, using the ``number_of_colors``
property, which returns any of *0* *8* or *256* for terminal types
such as *vt220*, *ansi*, and *xterm-256color*, respectively.

**NOTE**: On most color terminals, *bright_black* is actually a very dark
shade of gray!

Compound Formatting
-------------------

If you want to do lots of crazy formatting all at once, you can just mash it
all together::

    from blessed import Terminal

    term = Terminal()

    print(term.bold_underline_green_on_yellow('Woo'))

I'd be remiss if I didn't credit couleur_, where I probably got the idea for
all this mashing.  This compound notation comes in handy if you want to allow
users to customize formatting, just allow compound formatters, like *bold_green*,
as a command line argument or configuration item::

    #!/usr/bin/env python
    import argparse

    parser = argparse.ArgumentParser(
        description='displays argument as specified style')
    parser.add_argument('style', type=str, help='style formatter')
    parser.add_argument('text', type=str, nargs='+')

    from blessed import Terminal

    term = Terminal()
    args = parser.parse_args()

    style = getattr(term, args.style)

    print(style(' '.join(args.text)))

Saved as **tprint.py**, this could be called simply::

    $ ./tprint.py bright_blue_reverse Blue Skies


Moving The Cursor
-----------------

When you want to move the cursor, you have a few choices, the
``location(y=None, x=None)`` context manager, ``move(y, x)``, ``move_y(row)``,
and ``move_x(col)`` attributes.


Moving Temporarily
~~~~~~~~~~~~~~~~~~

A context manager, ``location`` is provided to move the cursor to a *(x, y)*
screen position and restore the previous position upon exit::

    from blessed import Terminal

    term = Terminal()
    with term.location(0, term.height - 1):
        print('Here is the bottom.')
    print('This is back where I came from.')

Parameters to *location()* are **optional** *x* and/or *y*::

    with term.location(y=10):
        print('We changed just the row.')

When omitted, it saves the cursor position and restore it upon exit::

    with term.location():
        print(term.move(1, 1) + 'Hi')
        print(term.move(9, 9) + 'Mom')

*NOTE*: calls to *location* may not be nested, as only one location may be saved.


Moving Permanently
~~~~~~~~~~~~~~~~~~

If you just want to move and aren't worried about returning, do something like
this::

    from blessed import Terminal

    term = Terminal()
    print(term.move(10, 1) + 'Hi, mom!')

``move``
  Position the cursor, parameter in form of *(y, x)*
``move_x``
  Position the cursor at given horizontal column.
``move_y``
  Position the cursor at given vertical column.

*NOTE*: The *location* method receives arguments in form of *(x, y)*,
where the *move* argument receives arguments in form of *(y, x)*.  This is a
flaw in the original `erikrose/blessings`_ implementation, kept for
compatibility.


One-Notch Movement
~~~~~~~~~~~~~~~~~~

Finally, there are some parameterless movement capabilities that move the
cursor one character in various directions:

* ``move_left``
* ``move_right``
* ``move_up``
* ``move_down``

**NOTE**: *move_down* is often valued as *\\n*, which additionally returns
the carriage to column 0, depending on your terminal emulator.


Height And Width
----------------

Use the *height* and *width* properties of the *Terminal* class instance::

    from blessed import Terminal

    term = Terminal()
    height, width = term.height, term.width
    with term.location(x=term.width / 3, y=term.height / 3):
        print('1/3 ways in!')

These are always current, so they may be used with a callback from SIGWINCH_ signals.::

    import signal
    from blessed import Terminal

    term = Terminal()

    def on_resize(sig, action):
        print('height={t.height}, width={t.width}'.format(t=term))

    signal.signal(signal.SIGWINCH, on_resize)

    term.inkey()


Clearing The Screen
-------------------

Blessed provides syntactic sugar over some screen-clearing capabilities:

``clear``
  Clear the whole screen.
``clear_eol``
  Clear to the end of the line.
``clear_bol``
  Clear backward to the beginning of the line.
``clear_eos``
  Clear to the end of screen.


Full-Screen Mode
----------------

If you've ever noticed a program, such as an editor, restores the previous
screen (such as your shell prompt) after exiting, you're seeing the
*enter_fullscreen* and *exit_fullscreen* attributes in effect.

``enter_fullscreen``
    Switch to alternate screen, previous screen is stored by terminal driver.
``exit_fullscreen``
    Switch back to standard screen, restoring the same terminal state.

There's also a context manager you can use as a shortcut::

    from blessed import Terminal

    term = Terminal()
    with term.fullscreen():
        print(term.move_y(term.height/2) +
              term.center('press any key'))
        term.inkey()

Pipe Savvy
----------

If your program isn't attached to a terminal, such as piped to a program
like *less(1)* or redirected to a file, all the capability attributes on
*Terminal* will return empty strings. You'll get a nice-looking file without
any formatting codes gumming up the works.

If you want to override this, such as when piping output to ``less -r``, pass
argument ``force_styling=True`` to the *Terminal* constructor.

In any case, there is a *does_styling* attribute on *Terminal* that lets
you see whether the terminal attached to the output stream is capable of
formatting.  If it is *False*, you may refrain from drawing progress
bars and other frippery and just stick to content::

    from blessed import Terminal

    term = Terminal()
    if term.does_styling:
        with term.location(0, term.height - 1):
            print('Progress: [=======>   ]')
    print(term.bold('Important stuff'))

Sequence Awareness
------------------

Blessed may measure the printable width of strings containing sequences,
providing ``.center``, ``.ljust``, and ``.rjust`` methods, using the
terminal screen's width as the default *width* value::

    from blessed import Terminal

    term = Terminal()
    with term.location(y=term.height / 2):
        print (term.center(term.bold('X'))

Any string containing sequences may have its printable length measured using the
``.length`` method. Additionally, ``textwrap.wrap()`` is supplied on the Terminal
class as method ``.wrap`` method that is also sequence-aware, so now you may
word-wrap strings containing sequences.  The following example displays a poem
from Tao Te Ching, word-wrapped to 25 columns::

    from blessed import Terminal

    term = Terminal()

    poem = (term.bold_blue('Plan difficult tasks'),
            term.blue('through the simplest tasks'),
            term.bold_cyan('Achieve large tasks'),
            term.cyan('through the smallest tasks'))

    for line in poem:
        print('\n'.join(term.wrap(line, width=25, subsequent_indent=' ' * 4)))

Keyboard Input
--------------

The built-in python *raw_input* function does not return a value until the return
key is pressed, and is not suitable for detecting each individual keypress, much
less arrow or function keys that emit multibyte sequences.  Special `termios(4)`_
routines are required to enter Non-canonical, known in curses as `cbreak(3)`_.
These functions also receive bytes, which must be incrementally decoded to unicode.

Blessed handles all of these special cases with the following simple calls.

cbreak
~~~~~~

The context manager ``cbreak`` can be used to enter *key-at-a-time* mode: Any
keypress by the user is immediately consumed by read calls::

    from blessed import Terminal
    import sys

    t = Terminal()

    with t.cbreak():
        # blocks until any key is pressed.
        sys.stdin.read(1)

raw
~~~

The context manager ``raw`` is the same as ``cbreak``, except interrupt (^C),
quit (^\\), suspend (^Z), and flow control (^S, ^Q) characters are not trapped,
but instead sent directly as their natural character. This is necessary if you
actually want to handle the receipt of Ctrl+C

inkey
~~~~~

The method ``inkey`` resolves many issues with terminal input by returning
a unicode-derived *Keypress* instance. Although its return value may be
printed, joined with, or compared to other unicode strings, it also provides
the special attributes ``is_sequence`` (bool), ``code`` (int),
and ``name`` (str)::

    from blessed import Terminal

    t = Terminal()

    print("press 'q' to quit.")
    with t.cbreak():
        val = None
        while val not in (u'q', u'Q',):
            val = t.inkey(timeout=5)
            if not val:
               # timeout
               print("It sure is quiet in here ...")
            elif val.is_sequence:
               print("got sequence: {}.".format((str(val), val.name, val.code)))
            elif val:
               print("got {}.".format(val))
        print('bye!')

Its output might appear as::

    got sequence: ('\x1b[A', 'KEY_UP', 259).
    got sequence: ('\x1b[1;2A', 'KEY_SUP', 337).
    got sequence: ('\x1b[17~', 'KEY_F6', 270).
    got sequence: ('\x1b', 'KEY_ESCAPE', 361).
    got sequence: ('\n', 'KEY_ENTER', 343).
    got /.
    It sure is quiet in here ...
    got sequence: ('\x1bOP', 'KEY_F1', 265).
    It sure is quiet in here ...
    got q.
    bye!

A *timeout* value of None (default) will block forever. Any other value specifies
the length of time to poll for input, if no input is received after such time
has elapsed, an empty string is returned. A timeout value of 0 is nonblocking.

keyboard codes
~~~~~~~~~~~~~~

The return value of the *Terminal* method ``inkey`` is an instance of the
class ``Keystroke``, and may be inspected for its property *is_sequence*
(bool).  When *True*, it means the value is a *multibyte sequence*,
representing a special non-alphanumeric key of your keyboard.

The *code* property (int) may then be compared with attributes of the
*Terminal* instance, which are equivalent to the same of those listed
by `curs_getch(3)`_ or the curses_ module, with the following helpful
aliases:

* use ``KEY_DELETE`` for ``KEY_DC`` (chr(127)).
* use ``KEY_TAB`` for chr(9).
* use ``KEY_INSERT`` for ``KEY_IC``.
* use ``KEY_PGUP`` for ``KEY_PPAGE``.
* use ``KEY_PGDOWN`` for ``KEY_NPAGE``.
* use ``KEY_ESCAPE`` for ``KEY_EXIT``.
* use ``KEY_SUP`` for ``KEY_SR`` (shift + up).
* use ``KEY_SDOWN`` for ``KEY_SF`` (shift + down).
* use ``KEY_DOWN_LEFT`` for ``KEY_C1`` (keypad lower-left).
* use ``KEY_UP_RIGHT`` for ``KEY_A1`` (keypad upper-left).
* use ``KEY_DOWN_RIGHT`` for ``KEY_C3`` (keypad lower-left).
* use ``KEY_UP_RIGHT`` for ``KEY_A3`` (keypad lower-right).
* use ``KEY_CENTER`` for ``KEY_B2`` (keypad center).
* use ``KEY_BEGIN`` for ``KEY_BEG``.

The *name* property of the return value of ``inkey()`` will prefer
these aliases over the built-in curses_ names.

The following are not available in the curses_ module, but provided
for distinguishing a keypress of those keypad keys where num lock is
enabled and the ``keypad()`` context manager is used:

* ``KEY_KP_MULTIPLY``
* ``KEY_KP_ADD``
* ``KEY_KP_SEPARATOR``
* ``KEY_KP_SUBTRACT``
* ``KEY_KP_DECIMAL``
* ``KEY_KP_DIVIDE``
* ``KEY_KP_0`` through ``KEY_KP_9``

Shopping List
=============

There are decades of legacy tied up in terminal interaction, so attention to
detail and behavior in edge cases make a difference. Here are some ways
*Blessed* has your back:

* Uses the `terminfo(5)`_ database so it works with any terminal type
* Provides up-to-the-moment terminal height and width, so you can respond to
  terminal size changes (*SIGWINCH* signals). (Most other libraries query the
  ``COLUMNS`` and ``LINES`` environment variables or the ``cols`` or ``lines``
  terminal capabilities, which don't update promptly, if at all.)
* Avoids making a mess if the output gets piped to a non-terminal.
* Works great with standard Python string formatting.
* Provides convenient access to **all** terminal capabilities.
* Outputs to any file-like object (*StringIO*, file), not just *stdout*.
* Keeps a minimum of internal state, so you can feel free to mix and match with
  calls to curses or whatever other terminal libraries you like
* Safely decodes internationalization keyboard input to their unicode equivalents.
* Safely decodes multibyte sequences for application/arrow keys.
* Allows the printable length of strings containing sequences to be determined.
* Provides plenty of context managers to safely express various terminal modes,
  restoring to a safe state upon exit.

Blessed does not provide...

* Native color support on the Windows command prompt.  A PDCurses_ build
  of python for windows provides only partial support at this time -- there
  are plans to merge with the ansi_ module in concert with colorama_ to
  resolve this.  Patches welcome!


Devlopers, Bugs
===============

Bugs or suggestions? Visit the `issue tracker`_.
`API Documentation`_ is available.

For patches, please construct a test case if possible.

To test, execute ``./setup.py develop`` followed by command ``tox``.

Pull requests are tested by Travis-CI.


License
=======

Blessed is derived from Blessings, which is under the MIT License, and
shares the same. See the LICENSE file.


Version History
===============
1.9
  * workaround: ignore 'tparm() returned NULL', this occurs on win32
    platforms using PDCurses_ where tparm() is not implemented.
  * enhancement: new context manager ``keypad()``, which enables
    keypad application keys such as the diagonal keys on the numpad.
  * bugfix: translate keypad application keys correctly to their
    diagonal movement directions ``KEY_LL``, ``KEY_LR``, ``KEY_UL``,
    ``KEY_LR``, and ``KEY_CENTER``.

1.8
  * enhancement: export keyboard-read function as public method ``getch()``,
    so that it may be overridden by custom terminal implementers.
  * enhancement: allow ``inkey()`` and ``kbhit()`` to return early when
    interrupted by signal by passing argument ``_intr_continue=False``.
  * enhancement: allow ``hpa`` and ``vpa`` (*move_x*, *move_y*) to work on
    tmux(1) or screen(1) by forcibly emulating their support by a proxy.
  * enhancement: ``setup.py develop`` ensures virtualenv and installs tox,
    and ``setup.py test`` calls tox. Requires pythons defined by tox.ini.
  * enhancement: add ``rstrip()`` and ``lstrip()``, strips both sequences
    and trailing or leading whitespace, respectively.
  * enhancement: include wcwidth_ library support for ``length()``, the
    printable width of many kinds of CJK (Chinese, Japanese, Korean) ideographs
    are more correctly determined.
  * enhancement: better support for detecting the length or sequences of
    externally-generated *ecma-48* codes when using ``xterm`` or ``aixterm``.
  * bugfix: if ``locale.getpreferredencoding()`` returns empty string or an
    encoding that is not a valid encoding for ``codecs.getincrementaldecoder``,
    fallback to ascii and emit a warning.
  * bugfix: ensure ``FormattingString`` and ``ParameterizingString`` may be
    pickled.
  * bugfix: allow ``term.inkey()`` and related to be called without a keyboard.
  * **change**: ``term.keyboard_fd`` is set ``None`` if ``stream`` or
    ``sys.stdout`` is not a tty, making ``term.inkey()``, ``term.cbreak()``,
    ``term.raw()``, no-op.
  * bugfix: ``\x1bOH`` (KEY_HOME) was incorrectly mapped as KEY_LEFT.

1.7
  * Forked github project `erikrose/blessings`_ to `jquast/blessed`_, this
    project was previously known as **blessings** version 1.6 and prior.
  * introduced: context manager ``cbreak()`` and ``raw()``, which is equivalent
    to ``tty.setcbreak()`` and ``tty.setraw()``, allowing input from stdin to
    be read as each key is pressed.
  * introduced: ``inkey()`` and ``kbhit()``, which will return 1 or more
    characters as a unicode sequence, with attributes ``.code`` and ``.name``,
    with value non-``None`` when a multibyte sequence is received, allowing
    application keys (such as UP/DOWN) to be detected. Optional value
    ``timeout`` allows timed asynchronous polling or blocking.
  * introduced: ``center()``, ``rjust()``, ``ljust()``, ``strip()``, and
    ``strip_seqs()`` methods.  Allows text containing sequences to be aligned
    to screen, or ``width`` specified.
  * introduced: ``wrap()`` method.  Allows text containing sequences to be
    word-wrapped without breaking mid-sequence, honoring their printable width.
  * bugfix: cannot call ``setupterm()`` more than once per process -- issue a
    warning about what terminal kind subsequent calls will use.
  * bugfix: resolved issue where ``number_of_colors`` fails when
    ``does_styling`` is ``False``.  Resolves issue where piping tests
    output would fail.
  * bugfix: warn and set ``does_styling`` to ``False`` when TERM is unknown.
  * bugfix: allow unsupported terminal capabilities to be callable just as
    supported capabilities, so that the return value of ``term.color(n)`` may
    be called on terminals without color capabilities.
  * bugfix: for terminals without underline, such as vt220,
    ``term.underline('text')``.  Would be ``u'text' + term.normal``, now is
    only ``u'text'``.
  * enhancement: some attributes are now properties, raise exceptions when
    assigned.
  * enhancement: pypy is now a supported python platform implementation.
  * enhancement: removed pokemon ``curses.error`` exceptions.
  * enhancement: converted nose tests to pytest, merged travis and tox.
  * enhancement: pytest fixtures, paired with a new ``@as_subprocess``
    decorator
    are used to test a multitude of terminal types.
  * enhancement: test accessories ``@as_subprocess`` resolves various issues
    with different terminal types that previously went untested.
  * deprecation: python2.5 is no longer supported (as tox does not supported).

1.6
  * Add ``does_styling`` property. This takes ``force_styling`` into account
    and should replace most uses of ``is_a_tty``.
  * Make ``is_a_tty`` a read-only property, like ``does_styling``. Writing to
    it never would have done anything constructive.
  * Add ``fullscreen()`` and ``hidden_cursor()`` to the auto-generated docs.

1.5.1
  * Clean up fabfile, removing the redundant ``test`` command.
  * Add Travis support.
  * Make ``python setup.py test`` work without spurious errors on 2.6.
  * Work around a tox parsing bug in its config file.
  * Make context managers clean up after themselves even if there's an
    exception. (Vitja Makarov)
  * Parameterizing a capability no longer crashes when there is no tty. (Vitja
    Makarov)

1.5
  * Add syntactic sugar and documentation for ``enter_fullscreen`` and
    ``exit_fullscreen``.
  * Add context managers ``fullscreen()`` and ``hidden_cursor()``.
  * Now you can force a *Terminal* never to emit styles by passing
    ``force_styling=None``.

1.4
  * Add syntactic sugar for cursor visibility control and single-space-movement
    capabilities.
  * Endorse the ``location()`` idiom for restoring cursor position after a
    series of manual movements.
  * Fix a bug in which ``location()`` wouldn't do anything when passed zeros.
  * Allow tests to be run with ``python setup.py test``.

1.3
  * Added ``number_of_colors``, which tells you how many colors the terminal
    supports.
  * Made ``color(n)`` and ``on_color(n)`` callable to wrap a string, like the
    named colors can. Also, make them both fall back to the ``setf`` and
    ``setb`` capabilities (like the named colors do) if the ANSI ``setaf`` and
    ``setab`` aren't available.
  * Allowed ``color`` attr to act as an unparametrized string, not just a
    callable.
  * Made ``height`` and ``width`` examine any passed-in stream before falling
    back to stdout. (This rarely if ever affects actual behavior; it's mostly
    philosophical.)
  * Made caching simpler and slightly more efficient.
  * Got rid of a reference cycle between Terminals and FormattingStrings.
  * Updated docs to reflect that terminal addressing (as in ``location()``) is
    0-based.

1.2
  * Added support for Python 3! We need 3.2.3 or greater, because the curses
    library couldn't decide whether to accept strs or bytes before that
    (http://bugs.python.org/issue10570).
  * Everything that comes out of the library is now unicode. This lets us
    support Python 3 without making a mess of the code, and Python 2 should
    continue to work unless you were testing types (and badly). Please file a
    bug if this causes trouble for you.
  * Changed to the MIT License for better world domination.
  * Added Sphinx docs.

1.1
  * Added nicely named attributes for colors.
  * Introduced compound formatting.
  * Added wrapper behavior for styling and colors.
  * Let you force capabilities to be non-empty, even if the output stream is
    not a terminal.
  * Added the ``is_a_tty`` attribute for telling whether the output stream is a
    terminal.
  * Sugared the remaining interesting string capabilities.
  * Let ``location()`` operate on just an x *or* y coordinate.

1.0
  * Extracted Blessings from `nose-progressive`_.

.. _`nose-progressive`: http://pypi.python.org/pypi/nose-progressive/
.. _`erikrose/blessings`: https://github.com/erikrose/blessings
.. _`jquast/blessed`: https://github.com/jquast/blessed
.. _`issue tracker`: https://github.com/jquast/blessed/issues/
.. _curses: https://docs.python.org/library/curses.html
.. _couleur: https://pypi.python.org/pypi/couleur
.. _colorama: https://pypi.python.org/pypi/colorama
.. _wcwidth: https://pypi.python.org/pypi/wcwidth
.. _`cbreak(3)`: http://www.openbsd.org/cgi-bin/man.cgi?query=cbreak&apropos=0&sektion=3
.. _`curs_getch(3)`: http://www.openbsd.org/cgi-bin/man.cgi?query=curs_getch&apropos=0&sektion=3
.. _`termios(4)`: http://www.openbsd.org/cgi-bin/man.cgi?query=termios&apropos=0&sektion=4
.. _`terminfo(5)`: http://www.openbsd.org/cgi-bin/man.cgi?query=terminfo&apropos=0&sektion=5
.. _tigetstr: http://www.openbsd.org/cgi-bin/man.cgi?query=tigetstr&sektion=3
.. _tparm: http://www.openbsd.org/cgi-bin/man.cgi?query=tparm&sektion=3
.. _SIGWINCH: https://en.wikipedia.org/wiki/SIGWINCH
.. _`API Documentation`: http://blessed.rtfd.org
.. _`PDCurses`: http://www.lfd.uci.edu/~gohlke/pythonlibs/#curses
