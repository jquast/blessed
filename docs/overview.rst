Overview
========

Blessed provides just **one** top-level object: :class:`~.Terminal`.
Instantiating a :class:`~.Terminal` figures out whether you're on a terminal at
all and, if so, does any necessary setup:

    >>> term = Terminal()

After that, you can proceed to ask it all sorts of things about the terminal,
such as its size:

    >>> term.height, term.width
    (34, 102)

Its color support:

    >>> term.number_of_colors
    256

And use construct strings containing color and styling:

    >>> term.green_reverse('ALL SYSTEMS GO')
    u'\x1b[32m\x1b[7mALL SYSTEMS GO\x1b[m'

Furthermore, the special sequences inserted with application keys
(arrow and function keys) are understood and decoded, as well as your
locale-specific encoded multibyte input, such as utf-8 characters.


Styling and Formatting
----------------------

Lots of handy formatting codes are available as attributes on a
:class:`~.Terminal` class instance. For example::

    from blessed import Terminal

    term = Terminal()

    print('I am ' + term.bold + 'bold' + term.normal + '!')

These capabilities (*bold*, *normal*) are translated to their sequences, which
when displayed simply change the video attributes.  And, when used as a
callable, automatically wraps the given string with this sequence, and
terminates it with *normal*.

The same can be written as::

    print('I am' + term.bold('bold') + '!')

You may also use the :class:`~.Terminal` instance as an argument for
the :meth:`str.format`` method, so that capabilities can be displayed in-line
for more complex strings::

    print('{t.red_on_yellow}Candy corn{t.normal} for everyone!'.format(t=term))


Capabilities
~~~~~~~~~~~~

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
  Enable standout mode (often, an alias for ``reverse``).
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
manual, under column **Cap-name**, may be used as an attribute of a
:class:`~.Terminal` instance. If it is not a supported capability, or a non-tty
is used as an output stream, an empty string is returned.


Colors
~~~~~~

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

Prefixed with *on_*, the given color is used as the background color.
Some terminals also provide an additional 8 high-intensity versions using
*on_bright*, some example compound formats::

    from blessed import Terminal

    term = Terminal()

    print(term.on_bright_blue('Blue skies!'))

    print(term.bright_red_on_bright_yellow('Pepperoni Pizza!'))

You may also specify the :meth:`~.Terminal.color` index by number, which
should be within the bounds of value returned by
:attr:`~.Terminal.number_of_colors`::

    from blessed import Terminal

    term = Terminal()

    for idx in range(term.number_of_colors):
        print(term.color(idx)('Color {0}'.format(idx)))

You can check whether the terminal definition used supports colors, and how
many, using the :attr:`~.Terminal.number_of_colors` property, which returns
any of *0*, *8* or *256* for terminal types such as *vt220*, *ansi*, and
*xterm-256color*, respectively.

Colorless Terminals
~~~~~~~~~~~~~~~~~~~

If the terminal defined by the Environment variable **TERM** does not support
colors, these simply return empty strings.  When used as a callable, the string
passed as an argument is returned as-is.  Most sequences emitted to a terminal
that does not support them are usually harmless and have no effect.

Colorless terminals (such as the amber or green monochrome *vt220*) do not
support colors but do support reverse video. For this reason, it may be
desirable in some applications to simply select a foreground color, followed
by reverse video to achieve the desired background color effect::

    from blessed import Terminal

    term = Terminal()

    print(term.green_reverse('some terminals standout more than others'))

Which appears as *black on green* on color terminals, but *black text
on amber or green* on monochrome terminals. Whereas the more declarative
formatter *black_on_green* would remain colorless.

.. note:: On most color terminals, *bright_black* is not invisible -- it is
    actually a very dark shade of gray!

Compound Formatting
~~~~~~~~~~~~~~~~~~~

If you want to do lots of crazy formatting all at once, you can just mash it
all together::

    from blessed import Terminal

    term = Terminal()

    print(term.bold_underline_green_on_yellow('Woo'))

I'd be remiss if I didn't credit couleur_, where I probably got the idea for
all this mashing.

This compound notation comes in handy if you want to allow users to customize
formatting, just allow compound formatters, like *bold_green*, as a command
line argument or configuration item such as in the :ref:`tprint.py`
demonstration script.

Moving The Cursor
-----------------

When you want to move the cursor, you have a few choices:

- ``location(x=None, y=None)`` context manager.
- ``move(row, col)`` capability.
- ``move_y(row)`` capability.
- ``move_x(col)`` capability.

.. warning:: The :meth:`~.Terminal.location` method receives arguments in
   positional order *(x, y)*, whereas the ``move()`` capability receives
   arguments in order *(y, x)*.  Please use keyword arguments as a later
   release may correct the argument order of :meth:`~.Terminal.location`.

Finding The Cursor
------------------

We can determine the cursor's current position at anytime using
:meth:`~.get_location`, returning the current (y, x) location.  This uses a
kind of "answer back" sequence that your terminal emulator responds to.  If
the terminal may not respond, the :paramref:`~.get_location.timeout` keyword
argument can be specified to return coordinates (-1, -1) after a blocking
timeout::

    from blessed import Terminal

    term = Terminal()

    row, col = term.get_location(timeout=5)

    if row < term.height:
        print(term.move_y(term.height) + 'Get down there!')

Moving Temporarily
~~~~~~~~~~~~~~~~~~

A context manager, :meth:`~.Terminal.location` is provided to move the cursor
to an *(x, y)* screen position and restore the previous position upon exit::

    from blessed import Terminal

    term = Terminal()

    with term.location(0, term.height - 1):
        print('Here is the bottom.')

    print('This is back where I came from.')

Parameters to :meth:`~.Terminal.location` are the **optional** *x* and/or *y*
keyword arguments::

    with term.location(y=10):
        print('We changed just the row.')

When omitted, it saves the cursor position and restore it upon exit::

    with term.location():
        print(term.move(1, 1) + 'Hi')
        print(term.move(9, 9) + 'Mom')

.. note:: calls to :meth:`~.Terminal.location` may not be nested.


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

One-Notch Movement
~~~~~~~~~~~~~~~~~~

Finally, there are some parameterless movement capabilities that move the
cursor one character in various directions:

* ``move_left``
* ``move_right``
* ``move_up``
* ``move_down``

.. note:: *move_down* is often valued as *\\n*, which additionally returns
   the carriage to column 0, depending on your terminal emulator, and may
   also destructively destroy any characters at the given position to the
   end of margin.


Height And Width
----------------

Use the :attr:`~.Terminal.height` and :attr:`~.Terminal.width` properties to
determine the size of the window::

    from blessed import Terminal

    term = Terminal()
    height, width = term.height, term.width
    with term.location(x=term.width / 3, y=term.height / 3):
        print('1/3 ways in!')

These values are always current.  To detect when the size of the window
changes, you may author a callback for SIGWINCH_ signals::

    import signal
    from blessed import Terminal

    term = Terminal()

    def on_resize(sig, action):
        print('height={t.height}, width={t.width}'.format(t=term))

    signal.signal(signal.SIGWINCH, on_resize)

    # wait for keypress
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

    from __future__ import division
    from blessed import Terminal

    term = Terminal()
    with term.fullscreen():
        print(term.move_y(term.height // 2) +
              term.center('press any key').rstrip())
        term.inkey()


Pipe Savvy
----------

If your program isn't attached to a terminal, such as piped to a program
like *less(1)* or redirected to a file, all the capability attributes on
:class:`~.Terminal` will return empty strings. You'll get a nice-looking
file without any formatting codes gumming up the works.

If you want to override this, such as when piping output to *less -r*, pass
argument value *True* to the :paramref:`~.Terminal.force_styling` parameter.

In any case, there is a :attr:`~.Terminal.does_styling` attribute that lets
you see whether the terminal attached to the output stream is capable of
formatting.  If it is *False*, you may refrain from drawing progress
bars and other frippery and just stick to content::

    from blessed import Terminal

    term = Terminal()
    if term.does_styling:
        with term.location(x=0, y=term.height - 1):
            print('Progress: [=======>   ]')
    print(term.bold("60%"))


Sequence Awareness
------------------

Blessed may measure the printable width of strings containing sequences,
providing :meth:`~.Terminal.center`, :meth:`~.Terminal.ljust`, and
:meth:`~.Terminal.rjust` methods, using the terminal screen's width as
the default *width* value::

    from __future__ import division
    from blessed import Terminal

    term = Terminal()
    with term.location(y=term.height // 2):
        print(term.center(term.bold('bold and centered')))

Any string containing sequences may have its printable length measured using
the :meth:`~.Terminal.length` method.

Additionally, a sequence-aware version of :func:`textwrap.wrap` is supplied as
class as method :meth:`~.Terminal.wrap` that is also sequence-aware, so now you
may word-wrap strings containing sequences.  The following example displays a
poem word-wrapped to 25 columns::

    from blessed import Terminal

    term = Terminal()

    poem = (term.bold_cyan('Plan difficult tasks'),
            term.cyan('through the simplest tasks'),
            term.bold_cyan('Achieve large tasks'),
            term.cyan('through the smallest tasks'))

    for line in poem:
        print('\n'.join(term.wrap(line, width=25, subsequent_indent=' ' * 4)))


Keyboard Input
--------------

The built-in python function :func:`raw_input` does not return a value until
the return key is pressed, and is not suitable for detecting each individual
keypress, much less arrow or function keys.

Furthermore, when calling :func:`os.read` on input stream, only bytes are
received, which must be decoded to unicode using the locale-preferred encoding.
Finally, multiple bytes may be emitted which must be paired with some verb like
``KEY_LEFT``: blessed handles all of these special cases for you!

cbreak
~~~~~~

The context manager :meth:`~.Terminal.cbreak` can be used to enter
*key-at-a-time* mode: Any keypress by the user is immediately consumed by read
calls::

    from blessed import Terminal
    import sys

    term = Terminal()

    with term.cbreak():
        # block until any single key is pressed.
        sys.stdin.read(1)

The mode entered using :meth:`~.Terminal.cbreak` is called
`cbreak(3)`_ in curses:

  The cbreak routine disables line buffering and erase/kill
  character-processing (interrupt and flow control characters are unaffected),
  making characters typed by the user immediately available to the program.

:meth:`~.Terminal.raw` is similar to cbreak, but not recommended.

inkey
~~~~~

The method :meth:`~.Terminal.inkey` combined with cbreak_
completes the circle of providing key-at-a-time keyboard input with multibyte
encoding and awareness of application keys.

:meth:`~.Terminal.inkey` resolves many issues with terminal input by
returning a unicode-derived :class:`~.Keystroke` instance.  Its return value
may be printed, joined with, or compared like any other unicode strings, it
also provides the special attributes :attr:`~.Keystroke.is_sequence`,
:attr:`~.Keystroke.code`, and :attr:`~.Keystroke.name`::

    from blessed import Terminal

    term = Terminal()

    print("press 'q' to quit.")
    with term.cbreak():
        val = u''
        while val not in (u'q', u'Q',):
            val = term.inkey(timeout=5)
            if not val:
               # timeout
               print("It sure is quiet in here ...")
            elif val.is_sequence:
               print("got sequence: {0}.".format((str(val), val.name, val.code)))
            elif val:
               print("got {0}.".format(val))
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

A :paramref:`~.Terminal.inkey.timeout` value of *None* (default) will block
forever until a keypress is received. Any other value specifies the length of
time to poll for input: if no input is received after the given time has
elapsed, an empty string is returned. A :paramref:`~.Terminal.inkey.timeout`
value of *0* is non-blocking.

keyboard codes
~~~~~~~~~~~~~~

When the :attr:`~.Keystroke.is_sequence` property tests *True*, the value
is a special application key of the keyboard.  The :attr:`~.Keystroke.code`
attribute may then be compared with attributes of :class:`~.Terminal`,
which are duplicated from those found in `curs_getch(3)`_, or those
`constants <https://docs.python.org/3/library/curses.html#constants>`_
in :mod:`curses` beginning with phrase *KEY_*.

Some of these mnemonics are shorthand or predate modern PC terms and
are difficult to recall. The following helpful aliases are provided
instead:

=================== ============= ====================
blessed             curses        note
=================== ============= ====================
``KEY_DELETE``      ``KEY_DC``    chr(127).
``KEY_TAB``                       chr(9)
``KEY_INSERT``      ``KEY_IC``
``KEY_PGUP``        ``KEY_PPAGE``
``KEY_PGDOWN``      ``KEY_NPAGE``
``KEY_ESCAPE``      ``KEY_EXIT``
``KEY_SUP``         ``KEY_SR``    (shift + up)
``KEY_SDOWN``       ``KEY_SF``    (shift + down)
``KEY_DOWN_LEFT``   ``KEY_C1``    (keypad lower-left)
``KEY_UP_RIGHT``    ``KEY_A1``    (keypad upper-left)
``KEY_DOWN_RIGHT``  ``KEY_C3``    (keypad lower-left)
``KEY_UP_RIGHT``    ``KEY_A3``    (keypad lower-right)
``KEY_CENTER``      ``KEY_B2``    (keypad center)
``KEY_BEGIN``       ``KEY_BEG``
=================== ============= ====================

The :attr:`~.Keystroke.name` property will prefer these
aliases over the built-in :mod:`curses` names.

The following are **not** available in the :mod:`curses` module, but are
provided for keypad support, especially where the :meth:`~.Terminal.keypad`
context manager is used with numlock on:

* ``KEY_KP_MULTIPLY``
* ``KEY_KP_ADD``
* ``KEY_KP_SEPARATOR``
* ``KEY_KP_SUBTRACT``
* ``KEY_KP_DECIMAL``
* ``KEY_KP_DIVIDE``
* ``KEY_KP_0`` through ``KEY_KP_9``

.. _couleur: https://pypi.python.org/pypi/couleur
.. _`cbreak(3)`: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man3/cbreak.3
.. _`raw(3)`: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man3/raw.3
.. _`curs_getch(3)`: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man3/curs_getch.3
.. _`terminfo(5)`: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man4/termios.3
.. _SIGWINCH: https://en.wikipedia.org/wiki/SIGWINCH
