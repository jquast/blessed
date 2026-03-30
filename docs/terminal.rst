Terminal
========

.. image:: https://dxtz6bzwq9sxx.cloudfront.net/demo_terminal_walkthrough.gif
    :alt: A visual example of the below interaction with the Terminal class, in IPython.

Blessed provides just **one** top-level object: :class:`~.Terminal`.  Instantiating a
:class:`~.Terminal` figures out whether you're on a terminal at all and, if so, does any necessary
setup:

    >>> import blessed
    >>> term = blessed.Terminal()

This is the only object, named ``term`` here, that you should need from blessed, for all of the
remaining examples in our documentation.

You can proceed to ask it all sorts of things about the terminal, such as its size:

    >>> term.height, term.width
    (34, 102)

Support for :doc:`colors`:

    >>> term.number_of_colors
    256

And create printable strings containing sequences_ for :doc:`colors`:

    >>> term.green_reverse('ALL SYSTEMS GO')
    '\x1b[32m\x1b[7mALL SYSTEMS GO\x1b[m'

When printed, these codes make your terminal go to work:

    >>> print(term.white_on_firebrick3('SYSTEM OFFLINE'))

And thanks to `f-strings`_ since python 3.6, it's very easy to mix attributes and strings together:

    >>> print(f"{term.yellow}Yellow is brown, {term.bright_yellow}"
              f"Bright yellow is actually yellow!{term.normal}")

.. _f-strings: https://docs.python.org/3/reference/lexical_analysis.html#f-strings
.. _sequences: https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_(Control_Sequence_Introducer)_sequences

Capabilities
------------

*Any capability* in the :linuxman:`terminfo(5)` manual, under column **Cap-name** can be an
attribute of the :doc:`terminal` class, such as 'smul' for 'begin underline mode'.

There are **a lot** of interesting capabilities in the :linuxman:`terminfo(5)` manual page, but many
of these will return an empty string, as they are not supported by your terminal. They can still be
used, but have no effect. For example, ``blink`` only works on a few terminals, does yours?

    >>> print(term.blink("Insert System disk into drive A:"))

Compound Formatting
-------------------

If you want to do lots of crazy formatting all at once, you can just mash it
all together::

    >>> print(term.underline_bold_green_on_yellow('They live! In sewers!'))

This compound notation comes in handy for users & configuration to customize your app, too!

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

Suggest to always combine ``home`` and ``clear``, and, in almost all emulators,
clearing the screen after setting the background color will repaint the background
of the screen:

    >>> print(term.home + term.on_blue + term.clear)

.. _hyperlinks:

Hyperlinks
----------

Maybe you haven't noticed, because it's a recent addition to terminal emulators, is
that they can now support hyperlinks, like to HTML, or even ``file://`` URLs, which
allows creating clickable links of text.

    >>> print(f"blessed {term.link('https://blessed.readthedocs.org', 'documentation')}")
    blessed documentation

Hover your cursor over ``documentation``, and it should highlight as a clickable URL.

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/demo_basic_hyperlink.gif
   :alt: Animation of running code example and clicking a hyperlink

Window Title
------------

You can set the terminal window title using
:meth:`~.Terminal.set_window_title`, which returns the appropriate xterm OSC
escape sequence:

    >>> print(term.set_window_title('My Application'))

The ``mode`` parameter controls what is set: 0 (default) sets both icon name
and window title, 1 sets icon name only, 2 sets window title only.

For temporary title changes, use the :meth:`~.Terminal.window_title` context
manager, which pushes the current title onto the xterm title stack and restores
it on exit:

.. code-block:: python

    with term.window_title('Working...'):
        do_long_task()
    # previous title is restored

Sixel Graphics Support
----------------------

Sixel is a bitmap graphics format supported by some modern terminal emulators
(including xterm with ``-ti vt340``, mlterm, WezTerm, and others), allowing
applications to display inline images directly in the terminal.

You can check whether your terminal supports sixel graphics using the
:meth:`~.Terminal.does_sixel` method:

    >>> if term.does_sixel():
    ...     display_sixel_image()
    ... else:
    ...     display_text_fallback()

Default ``timeout`` argument of 1 second is used to avoid blocking indefinitely
when the terminal fails to respond to DA1 queries.

OSC 52 Clipboard
-----------------

The OSC 52 protocol allows terminal applications to read from and write to the
system clipboard without requiring platform-specific clipboard tools. Many
modern terminals support this protocol, including xterm, kitty, WezTerm, and
iTerm2.

Detection
~~~~~~~~~

Use :meth:`~.Terminal.does_osc52_clipboard` to check whether your terminal
advertises OSC 52 support:

    >>> if term.does_osc52_clipboard():
    ...     print("Terminal supports clipboard access")

Detection uses DA1 extension 52 and XTGETTCAP ``Ms`` queries, which do not
trigger user-facing clipboard permission dialogs. Detection indicates the
terminal *understands* OSC 52, not that any particular read will succeed.

Copying to Clipboard
~~~~~~~~~~~~~~~~~~~~

Use :meth:`~.Terminal.clipboard_copy` to copy text to the system clipboard:

    >>> term.clipboard_copy('Hello from blessed!')

Most modern terminals accept clipboard writes without any user prompt, even
when clipboard reads are restricted. No detection query is needed for
write-only use -- the sequence is silently ignored by terminals that do not
support it.

Reading from Clipboard
~~~~~~~~~~~~~~~~~~~~~~

Use :meth:`~.Terminal.clipboard_paste` to read the clipboard contents:

    >>> text = term.clipboard_paste()
    >>> if text is not None:
    ...     print(f"Clipboard: {text}")

.. warning::

    Many modern terminals display a permission dialog when an application
    reads the clipboard. The user must approve the dialog before the
    terminal sends a response. The default timeout of 10 seconds allows
    time for this interaction. If the user denies the dialog or the
    terminal does not support clipboard reads, ``None`` is returned.

Example program demonstrating clipboard copy and paste:

.. literalinclude:: ../bin/clipboard.py
   :language: python

Styled and Colored Underlines
------------------------------

Modern terminals can render underline styles beyond the standard single
underline, such as curly (``CSI 4:3 m``), dotted, and dashed underlines.
Some also support colored underlines (``CSI 58;2;r;g;b m``), where the
underline color differs from the text color.

You can detect these capabilities via XTGETTCAP:

    >>> if term.does_styled_underlines():
    ...     print("Curly, dotted, and dashed underlines supported")

    >>> if term.does_colored_underlines():
    ...     print("Colored underlines supported")

These methods query the terminal's ``Smulx`` and ``Setulc`` terminfo
capabilities, respectively. Default ``timeout`` argument of 1 second is used.

Color Scheme Detection
----------------------

Some terminals can report whether they are in dark or light mode via the
color-scheme DSR query (``CSI ? 996 n``). This is supported by Contour,
Ghostty, Kitty (0.38.1+), and VTE (0.82.0+).

Use :meth:`~.Terminal.get_color_scheme` to query the current preference:

    >>> scheme = term.get_color_scheme()
    >>> if scheme == 'dark':
    ...     use_dark_palette()
    ... elif scheme == 'light':
    ...     use_light_palette()
    ... else:
    ...     use_default_palette()

Returns ``'dark'``, ``'light'``, or ``None`` if the terminal does not support
the query. Default ``timeout`` argument of 1 second is used.

Unlike most detection methods, the result value is not cached -- only whether
the terminal *supports* the query is remembered. This means repeated calls
always return the current scheme, while terminals that do not respond only incur
the timeout delay once.

To receive unsolicited notifications when the color scheme changes, enable DEC
private mode 2031 (``COLOR_PALETTE_UPDATES``) separately.

Kitty Query Extensions
----------------------

Kitty extends the standard XTGETTCAP (``DCS +q``) mechanism with
``kitty-query-*`` keys that expose runtime metadata such as the terminal name,
version, font family, DPI, and clipboard control policy.

You can detect whether these extensions are available using
:meth:`~.Terminal.does_kitty_query`:

    >>> if term.does_kitty_query():
    ...     print("Kitty query extensions available")

DECRQSS Support
---------------

DECRQSS (Request Status String) allows applications to query the current state
of terminal attributes such as SGR (Select Graphic Rendition), cursor style
(DECSCUSR), and conformance level (DECSCL). This is supported by xterm,
Contour, kitty, VTE, and others.

You can detect DECRQSS support using :meth:`~.Terminal.does_decrqss`:

    >>> if term.does_decrqss():
    ...     print("DECRQSS queries supported")

Terminal Software Version
-------------------------

Many modern terminal emulators support the XTVERSION query (CSI > q), which allows
applications to identify the terminal software name and version.

You can query the terminal's software version using the
:meth:`~.Terminal.get_software_version` method, which returns a
:class:`~.SoftwareVersion` object with ``name`` and ``version`` attributes, or,
``None`` if the terminal fails to respond.

Example program to display terminal version information:

.. literalinclude:: ../bin/display-version.py
   :language: python

Styles
------

In addition to :doc:`colors`, blessed also supports the limited amount of *styles* that terminals
can do. These are:

``bold``
  Turn on 'extra bright' mode.
``reverse``
  Switch fore and background attributes.
``normal``
  Reset attributes to default.
``underline``
  Enable underline mode.
``no_underline``
  Disable underline mode.

.. note:: While the inverse of *underline* is *no_underline*, the only way to turn off *bold* or
    *reverse* is *normal*, which also cancels any custom colors.

Full-Screen Mode
----------------

If you've ever noticed how a program like :linuxman:`vim(1)` restores you to your unix shell history
after exiting, it's actually a pretty basic trick that all terminal emulators support, that
*blessed* provides using the :meth:`~Terminal.fullscreen` context manager over these two basic
capabilities:

``enter_fullscreen``
    Switch to alternate screen, previous screen is stored by terminal driver.
``exit_fullscreen``
    Switch back to standard screen, restoring the same terminal screen.

.. code-block:: python

    with term.fullscreen(), term.cbreak():
        print(term.move_y(term.height // 2) +
              term.center('press any key').rstrip())
        term.inkey()

Line Wrap Control
-----------------

Terminals normally wrap text when reaching the right edge of the window. This context manager
temporarily disables it.

In the following example, the letter 'X' is displayed 3 times the width of the page, which would
otherwise wrap and fill 3 lines. With line-wrapping disabled, the cursor stays at the last column
and continuously "repaints" over the previous one until a newline is received, causing it to fill
only 1 line.

.. code-block:: python

    with term.no_line_wrap():
        print(term.move_x(0) + 'X' * (term.width * 3))

You can use these sequences directly as attributes ``enable_line_wrap`` and ``disable_line_wrap``
of :class:`~.Terminal`.

.. code-block:: python

    print(term.enable_line_wrap)

Pipe Savvy
----------

If your program isn't attached to a terminal, such as piped to a program like :linuxman:`less(1)` or
redirected to a file, all the capability attributes on :class:`~.Terminal` will return empty strings
for any :doc:`colors`, :doc:`location`, or other sequences.  You'll get a nice-looking file without
any formatting codes gumming up the works.

If you want to override this, such as when piping output to ``less -R``, pass argument value *True*
to the :paramref:`~.Terminal.force_styling` parameter.

In any case, there is a :attr:`~.Terminal.does_styling` attribute that lets you see whether the
terminal attached to the output stream is capable of formatting.  If it is *False*, you may refrain
from drawing progress bars and other frippery and just stick to content:

.. code-block:: python

    if term.does_styling:
        with term.location(x=0, y=term.height - 1):
            print('Progress: [=======>   ]')
    print(term.bold("60%"))
