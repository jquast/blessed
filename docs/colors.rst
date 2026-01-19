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

If you have an exact color in mind, you can use direct ``(r, g, b)`` values of
0-255 with :meth:`~.Terminal.color_rgb` and :meth:`~.Terminal.on_color_rgb` for
foreground and background colors, and, :meth:`~.Terminal.color_hex` and
:meth:`~.Terminal.on_color_hex` with popular html color codes:

    >>> print(term.color_rgb(255, 0, 255)("Bright Magenta"))
    >>> print(term.color_hex("#cafe00")("green goo"))

24-bit Colors
-------------

Most Terminal emulators, even Windows, has supported 24-bit colors since roughly 2016. To test or
whether the terminal emulator supports 24-bit colors, check terminal attribute
:meth:`~Terminal.number_of_colors`:

    >>> print(term.number_of_colors == 1 << 24)
    True

This value is automatically determined 24-bit when environment ``COLORTERM`` is
set to ``truecolor`` or ``24bit``. The attribute can be modified directly for
the desired color depth.

Even if the terminal only supports ``256``, or worse, ``16`` colors, the nearest
color supported by the terminal is automatically mapped:

    >>> term.number_of_colors = 1 << 24
    >>> term.darkolivegreen
    '\x1b[38;2;85;107;47m'

    >>> term.number_of_colors = 256
    >>> term.darkolivegreen
    '\x1b[38;5;58m'

    >>> term.number_of_colors = 16
    >>> term.darkolivegreen
    '\x1b[90m'

Hex Colors
----------

For convenience, colors can be specified in standard web hex format using
:meth:`~.Terminal.color_hex` and :meth:`~.Terminal.on_color_hex`:

    >>> print(term.color_hex('#ff5733')('Warning!'))
    >>> print(term.on_color_hex('#ff5733')('System Error!'))

These methods accept multiple hex formats, and the ``#`` prefix is optional:

- **3-digit**: ``#RGB`` expands to ``#RRGGBB`` (e.g., ``#faf`` -> ``#ffaaff``)
- **6-digit**: ``#RRGGBB`` standard web format (e.g., ``#ff5733``)
- **12-digit**: ``#RRRRGGGGBBBB``

Querying Terminal Colors
-------------------------

You can query the terminal's default foreground and background colors using
:meth:`~.Terminal.get_fgcolor` and :meth:`~.Terminal.get_bgcolor`, or use
:meth:`~.Terminal.get_fgcolor_hex` and :meth:`~.Terminal.get_bgcolor_hex` for
hex string output. These return the colors used for default, uncolored text -
not any currently active color set by escape sequences:

.. literalinclude:: ../bin/color_query.py
   :language: python

.. note:: The keyword argument ``bits=8`` is recommended for the more common RGB
   return values in range of 0-255 with :meth:`~.Terminal.get_fgcolor` and
   :meth:`~.Terminal.get_bgcolor` as demonstrated here.

   These methods otherwise return 16-bit RGB values (0-65535) per the
   XParseColor specification used by the underlying protocol.

These methods are useful for adapting your application's color scheme to match the user's terminal
theme, or for detecting whether the terminal has a light or dark background. The RGB methods
return ``(-1, -1, -1)`` on timeout, while the hex methods return an empty string.

256 Colors
----------

The built-in capability :meth:`~.Terminal.color` accepts a numeric index of any
value between 0 and 254, you could call this "Color by number..." and is the
highest color depth for some legacy terminals and systems. It not recommended to
use directly.  It is better to use RGB and Hex value methods, which map to the
nearest color automatically.

16 Colors
---------

Recommended for common CLI applications, where the user's preferred color
palette is used.

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
    displayed at https://en.wikipedia.org/wiki/ANSI_escape_code#3-bit_and_4-bit. Users can customize
    these 16 colors as a common "theme", so that one CLI application appears of the same color theme
    as the next.

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

Color chart
-----------

.. include:: all_the_colors.txt
