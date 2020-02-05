Keyboard
========

The built-in function :func:`input` (or :func:`raw_input`) is pretty good for a basic game:

.. code-block:: python

    name = input("What is your name? ")
    if sum(map(ord, name)) % 2:
        print(f"{name}?! What a beautiful name!")
    else:
        print(f"How interesting, {name} you say?")

But it has drawbacks -- it's no good for interactive apps!  This function **will not return until
the return key is pressed**, so we can't do any exciting animations, and we can't understand or
detect arrow keys and others required to make awesome, interactive apps and games!

*Blessed* fixes this issue with a context manager, :meth:`~Terminal.cbreak`, and a single
function for all keyboard input, :meth:`~.Terminal.inkey`.

inkey()
-------

Let's just dive right into a rich "event loop", that awaits a keypress for 3 seconds and tells us
what key we pressed.

.. code-block:: python
   :emphasize-lines: 3,6

   print(f"{term.home}{term.black_on_skyblue}{term.clear}")
   print("press 'q' to quit.")
   with term.cbreak():
       val = ''
       while val.lower() != 'q':
           val = term.inkey(timeout=3)
           if not val:
              print("It sure is quiet in here ...")
           elif val.is_sequence:
              print("got sequence: {0}.".format((str(val), val.name, val.code)))
           elif val:
              print("got {0}.".format(val))
       print(f'bye!{term.normal}')

.. image:: https://dxtz6bzwq9sxx.cloudfront.net/demo_cbreak_inkey.gif
    :alt: A visual example of interacting with the Terminal.inkey() and cbreak() methods.

:meth:`~.Terminal.cbreak` enters a special mode_ that ensures :func:`os.read` on an input stream
will return as soon as input is available, as explained in :linuxman:`cbreak(3)`. This mode is
combined with :meth:`~.Terminal.inkey` to decode multibyte sequences, such as ``\0x1bOA``, into
a unicode-derived :class:`~.Keystroke` instance.

The :class:`~.Keystrok` returned by :meth:`~.Terminal.inkey` is unicode -- it may be printed, joined
with, or compared to any other unicode strings. It also has these provides the special attributes:

- :attr:`~.Keystroke.is_sequence` (bool): Whether it is an "application" key.
- :attr:`~.Keystroke.code` (int): the keycode, for equality testing.
- :attr:`~.Keystroke.name` (str): a human-readable name of any "application" key.

Keycodes
--------

.. note(jquast): a graphical chart of the keyboard, with KEY_CODE names on the labels, maybe?  at
   least, just a table of all the keys would be better, we should auto-generate it though, like the
   colors.

When the :attr:`~.Keystroke.is_sequence` property tests *True*, the value of
:attr:`~.Keystroke.code` represents a unique application key of the keyboard.

:attr:`~.Keystroke.code` may then be compared with attributes of :class:`~.Terminal`,
which are duplicated from those found in :linuxman:`curses(3)`, or those `constants
<https://docs.python.org/3/library/curses.html#constants>`_ in :mod:`curses` beginning with phrase
*KEY_*, as follows:

.. include:: all_the_keys.txt

All such keystrokes can be decoded by blessed, there is a demonstration program, :ref:`keymatrix.py`
that tests how many of them you can find !

delete
------

Typically, backspace is ``^H`` (8, or 0x08) and delete is ^? (127, or 0x7f).

On some systems however, the key for backspace is actually labeled and transmitted as "delete",
though its function in the operating system behaves just as backspace. Blessed usually returns
"backspace" in most situations.

It is highly recommend to accept **both** ``KEY_DELETE`` and ``KEY_BACKSPACE`` as having the same
meaning except when implementing full screen editors, and provide a choice to enable the delete mode
by configuration.

Alt/meta
--------

Programs with GNU readline, like bash, have *Alt* combinators, such as *ALT+u* to uppercase the word
after cursor.  This is achieved by the configuration option altSendsEscape or `metaSendsEscape
<https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h2-Alt-and-Meta-Keys>`_ in xterm.

The default for most terminals, however, is for this key to be bound by the operating system, or,
used for inserting international keys, (where the combination *ALT+u, a* is used to insert the
character ``ä``).

It is therefore a recommendation to **avoid alt or meta keys entirely** in applications.

And instead prefer the ctrl-key combinations, maybe along with :meth:`~.Terminal.raw`, to avoid
instructing users to custom-configure their terminal emulators to communicate *Alt* sequences.

If you still wish to optionall decode them, *ALT+z* becomes *Escape + z* (or, in raw form
``\x1bz``). This is detected by blessings as two keystrokes, ``KEY_ESCAPE`` and ``'z'``.  Blessings
currently provides no further assistance in detecting these key combinations.

.. _mode: https://en.wikipedia.org/wiki/Terminal_mode
