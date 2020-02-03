Colors
======

Doing colors with blessed is easy, pick a color name from the :ref:`Color chart` below, any of these
named are also attributes of the :doc:`terminal`!

These attributes can be printed directly, causing the terminal to switch into the given color.  Or,
as a callable, which terminates the string with the ``normal`` attribute.  The following three
statements are equivalent:

    >>> print(term.orangered + 'All systems are offline' + term.normal)
    >>> print(f'{term.orangered}All systems are offline{term.normal}')
    >>> print(term.orangered('All systems are offline'))

To use a background color, prefix any color with ``on_``:

    >>> print(term.on_darkolivegreen('welcome to the army'))

And combine two colors using "``_on_``", as in "``foreground_on_background``":

    >>> print(term.peru_on_seagreen('All systems functioning within defined parameters.'))

24-bit Colors
-------------

Most Terminal emulators, even Windows, has supported 24-bit colors since roughly 2016. To test or
force-set whether the terminal emulator supports 24-bit colors, check or set the terminal attribute
:meth:`~Terminal.number_of_colors`:

    >>> print(term.number_of_colors == 1 << 24)
    True

Even if the terminal only supports ``256``, or worse, ``16`` colors, the nearest color supported by
the terminal is automatically mapped:

    >>> term.number_of_colors = 1 << 24
    >>> term.darkolivegreen
    '\x1b[38;2;85;107;47m'

    >>> term.number_of_colors = 256
    >>> term.darkolivegreen
    '\x1b[38;5;58m'

    >>> term.number_of_colors = 16
    >>> term.darkolivegreen
    '\x1b[90m'

And finally, the direct ``(r, g, b)`` values of 0-255 can be used for :meth:`~.Terminal.color_rgb`
and :meth:`~.Terminal.on_color_rgb` for foreground and background colors, to access each and every
color!

.. _Color chart:

.. include:: all_the_colors.txt

256 Colors
----------

The built-in capability :meth:`~.Terminal.color` accepts a numeric index of any value
between 0 and 254, I guess you could call this "Color by number...", it not recommended, there are
many common cases where the colors do not match across terminals!

16 Colors
---------

Recommended for common CLI applications.

Traditional terminals are only capable of 8 colors:

* ``black``
* ``red``
* ``green``
* ``yellow``
* ``blue``
* ``magenta``
* ``cyan``
* ``white``

Prefixed with *on_*, the given color is used as the background color:

* ``on_black``
* ``on_red``
* ``on_green``
* ``on_yellow``
* ``on_blue``
* ``on_magenta``
* ``on_cyan``
* ``on_white``

The same colors, prefixed with *bright_* or *bold_*, such as *bright_blue*, provides the other 8
colors of a 16-color terminal:

* ``bright_black``
* ``bright_red``
* ``bright_green``
* ``bright_yellow``
* ``bright_blue``
* ``bright_magenta``
* ``bright_cyan``
* ``bright_white``

Combined, there are actually **three shades of grey** for 16-color terminals, in ascending order of
intensity:

* ``bright_black``: is dark grey.
* ``white``: a mild white.
* ``bright_white``: pure white (``#ffffff``).

.. note::

   - *bright_black* is actually a very dark shade of grey!
   - *yellow is brown*, only high-intensity yellow (``bright_yellow``) is yellow!
   - purple is magenta.

.. warning::

    Terminal emulators use different values for any of these 16 colors, the most common of these are
    displayed at https://en.wikipedia.org/wiki/ANSI_escape_code#3/4_bit. Users can customize these
    16 colors as a common "theme", so that one CLI application appears of the same color theme as
    the next.

    When exact color values are needed, `24-bit Colors`_ should be preferred, by their name or RGB
    value.

Monochrome
----------

One small consideration for targeting legacy terminals, such as a *vt220*, which do not support
colors but do support reverse video: select a foreground color, followed by reverse video, rather
than selecting a background color directly:: the same desired background color effect as
``on_background``:

>>>  print(term.on_green('This will not standout on a vt220'))
>>>  print(term.green_reverse('Though some terminals standout more than others'))

The second phrase appears as *black on green* on both color terminals and a green monochrome vt220.
