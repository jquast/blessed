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
.. _sequences: https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_sequences

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
