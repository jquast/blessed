Keyboard
========

Although the built-in function :func:`input` (or :func:`raw_input`) is pretty
good for reading a *line* of input:

.. code-block:: python

    name = input("What is your name? ")
    if sum(map(ord, name)) % 2:
        print(f"{name}?! What a beautiful name!")
    else:
        print(f"How interesting, {name} you say?")

It has drawbacks -- it's no good for interactive apps!  This function **will not return until
the return key is pressed**, so we can't do any exciting animations, and we can't understand or
detect arrow keys.

*Blessed* fixes this issue with a context manager, :meth:`~Terminal.cbreak`, and a single
function for all keyboard input, :meth:`~.Terminal.inkey`.

inkey()
-------

The :meth:`~.Terminal.inkey` method checks the keyboard for any input, and
returns it as a :class:`~.Keystroke` object. Combined with
:meth:`~Terminal.cbreak`, single keystrokes can be immediately received with an
optional timeout.

.. code-block:: python
   :emphasize-lines: 4,7

   from blessed import Terminal

   term = Terminal()
   with term.cbreak():
       print("press the 'Q' or F1 key to stop this loop!")
       while True:
           ks = term.inkey(timeout=3)

           if ks is None:  # timeout exceeded
              print("It sure is quiet in here ...")
              continue

           if ks.lower() == 'q' or ks.name == 'KEY_F1':
               break

           elif ks.is_sequence:
              # application keys have "synthesized" names
              print(f"ks.name={ks.name!r} ks={ks!r}")

           else:
              # standard input keys have string values
              print(f"ks={ks!r}")

   print(f'bye! Exited using ks={ks!r} (name={ks.name})')


:meth:`~.Terminal.cbreak` enters a special mode that ensures :func:`os.read` on
an input stream will return as soon as input is available, as explained in
:linuxman:`cbreak(3)`.

This mode is combined with :meth:`~.Terminal.inkey` to decode multibyte
sequences, such as ``\0x1bOA``, into a unicode-derived :class:`~.Keystroke`
instance that is given *name* attribute of ``KEY_UP``. 

Or, if you prefer by method call ``is_key_up()``.

Keystroke
---------

The :class:`~.Keystroke` object returned by `inkey()`_ may be printed, joined
with, or compared to any other unicode strings. Be careful to print it directly,
though, our example uses format string, ``f'{ks!r}'`` for ``repr()``, because
the input may contain input that begins with the escape key, (``KEY_ESCAPE``)
and are generally unprintable.

The :class:`~.Keystroke` object returned by :meth:`~.Terminal.inkey` may
also be ``None``, letting us know that the ``timeout`` value has elapsed
without any input. Smaller values can be used to create "animations"
while also periodically checking in for input.

Modifiers
---------

Programs with GNU readline, like bash, support *Alt* modifiers, such as *ALT+u*
to uppercase the word after cursor with input sequence ``'\x1bu``.  This
sequence can be sent using configuration option altSendsEscape or
`metaSendsEscape <https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h2-Alt-and-Meta-Keys>`_
in xterm. Many other terminals send these sequences in their default
configuration and modes.

Use the :attr:`~.Keystroke.is_sequence` (bool) attribute to determine whether
this key should be evaluated by its :attr:`~.name`, which should be non-None.

The :attr:`~.Keystroke.value` displays its value without modifiers or sequences.
For example, Ctrl+A has a value of ``'a'``. Application keys like ``KEY_LEFT``
have an empty value.

Methods
-------

If you prefer, a dynamic :meth:`~.Keystroke:__getattr__` allows for more
advanced compound tests of modifiers and application keys, given a return **ks**
:class:`~.Keystroke` value from :meth:`~.Terminal.inkey`.

Methods begin with ``is_``, contain any number of modifiers ``ctrl``, ``alt``,
``shift``, conditionally ending with a lowercase application key name, such as
``f1``, or ``left``:

- ``ks.is_ctrl('x')``
- ``ks.is_f1()``
- ``ks.is_left()``
- ``ks.is_ctrl_alt('x')``
- ``ks.is_shift_left()``
- ``ks.is_ctrl_shift_alt('x')``

These "magic methods" of :meth:`~.Keystroke:__getattr__` take optional arguments
``ignore_case`` (bool), defaults to *True*


instead of testing for string equality ``ks.name == 'KEY_CTRL_ALT_X'``.

Names
-----

:attr:`~.Keystroke.name` is all you really need to to match an "application"
key.  All keystrokes begin with ``'KEY_'``, some examples:

    - ``'KEY_UP'``
    - ``'KEY_DOWN'``
    - ``'KEY_LEFT'``
    - ``'KEY_RIGHT'``
    - ``'KEY_ENTER'``
    - ``'KEY_BACKSPACE'`` and ``'KEY_DELETE'``
    - ``'KEY_TAB'`` and ``'KEY_BTAB'``
    - ``'KEY_F1'``, ``'KEY_F12'``

Or, with modifiers,

    - ``'KEY_ALT_a'``
    - ``'KEY_ALT_SHIFT_A'``
    - ``'KEY_ALT_LEFT'``
    - ``'KEY_ALT_BACKSPACE'``
    - ``'KEY_CTRL_ALT_SHIFT_F1'``
    - ``'KEY_CTRL_ALT_DELETE'``
    - ``'KEY_CTRL_C'``

And, for Kitty_ modes, they may additionally have or ``_RELEASED``, ``_REPEATED`` suffix:

    - ``'KEY_ALT_F4_PRESSED'``
    - ``'KEY_ALT_F4_RELEASED'``
    - ``'KEY_ALT_a_RELEASED'``
    - ``'KEY_ALT_a_REPEATED'``
    - ``'KEY_ALT_SHIFT_A_RELEASED'``
    - ``'KEY_CTRL_ALT_SHIFT_F1_RELEASED'``
    - ``'KEY_CTRL_ALT_DELETE_REPEATED'``

The escape sequence, ``'\x1b['``, is always decoded as name ``CSI`` when it
arrives without any known matching sequence. There is no ``KEY_ALT_[`` except
when Kitty_ mode is active.

Use the demonstration program, :ref:`keymatrix.py` to try them out.

Keycodes
--------

For Legacy API of classic curses applications, :attr:`~.Keystroke.code` may be
be compared with attributes of :class:`~.Terminal`, which are duplicated from
those found in :linuxman:`curses(3)`, or those `constants
<https://docs.python.org/3/library/curses.html#constants>`_ in :mod:`curses`
beginning with phrase *KEY_*. These have numeric values that can be used for
all basic application keys.

.. include:: all_the_keys.txt

However, this does not represent the full range of keys that can be detected
with their modifiers, such as ``KEY_LEFT`` as ``KEY_CTRL_LEFT``,
``KEY_CTRL_SHIFT_LEFT``, and ``KEY_CTRL_ALT_SHIFT_LEFT`` are only matchable
by their names.

delete
------

Typically, backspace is ``^H`` (8, or 0x08) and delete is ^? (127, or 0x7f).

On some systems however, the key for backspace is actually labeled and transmitted as "delete",
though its function in the operating system behaves just as backspace. Blessed usually returns
"backspace" in most situations.

It is highly recommend to accept **both** ``KEY_DELETE`` and ``KEY_BACKSPACE`` as having the same
meaning except when implementing full screen editors, and provide a choice to enable the delete mode
by configuration.

.. _mode: https://en.wikipedia.org/wiki/Terminal_mode
