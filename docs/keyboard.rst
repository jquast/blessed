Keyboard Input
==============

Python's built-in :func:`input` function is great for simple prompts, but it has
one limitation: it waits for the Enter key. This makes it unsuitable for
interactive applications that need to respond to individual keystrokes, arrow
keys, or function keys.

Blessed provides a solution with :meth:`~.Terminal.inkey`, which returns
keystrokes as :class:`~.Keystroke` objects. Combined with
:meth:`~.Terminal.cbreak` mode, you can build responsive, interactive terminal
applications that can respond "key at a time".

The :meth:`~.Terminal.cbreak` context manager enables immediate key detection.

The :meth:`~.Terminal.inkey` method returns a :class:`~.Keystroke` object
representing the key that was immediately pressed.

Getting Started
---------------

Here's a simple example that reads a single keystroke:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        key = term.inkey()
        print(f"You pressed: {key!r}")

The :meth:`~.Terminal.inkey` method also accepts a ``timeout`` parameter (in
seconds). When timeout is exceeded without input, an empty :class:`~.Keystroke`
is returned, ``''``

.. code-block:: python

    from blessed import Terminal
    import time

    term = Terminal()
    print("Cross animation, press any key to stop: ", end="", flush=True)
    with term.cbreak(), term.hidden_cursor():
        cross = '|'

        while True:
            key = term.inkey(timeout=0.1)
            if key:
                print(f'STOP by {key!r}')
                break

            cross = {'|':'-', '-':'|'}[cross]
            print(f'{cross}\b', end='', flush=True)


Keystroke
---------

The :class:`~.Keystroke` class makes it easy to work with keyboard input. It
inherits from :class:`str`, so you can compare it directly to other strings, but
it also provides special properties for detecting modifier keys and special
sequences.

* Use :attr:`~.Keystroke.is_sequence` to detect special keys
* Use :attr:`~.Keystroke.name` to identify special keys by name (e.g., ``KEY_F1``, ``KEY_CTRL_Q``)
* Or, by using magic methods like ``keystroke.is_f1()`` or ``keystroke.is_key_ctrl('q')``.

Special Keys
~~~~~~~~~~~~

The :attr:`~.Keystroke.is_sequence` property returns ``True`` for arrow keys,
function keys, and any character key combined with modifiers (Ctrl, Alt, Shift).

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        key = term.inkey()

        if key.is_sequence:
            print(f"Special key: {key.name}")
        else:
            print(f"Regular character: {key}")

Use the demonstration program, :ref:`keymatrix.py` to experiment further.

The :attr:`~.Keystroke.name` property provides a readable name for special keys,
and can be used for basic equality tests like in this "paint by arrow key" example:

.. code-block:: python

    from blessed import Terminal

    header_msg = "Press arrow keys (or 'q' to quit): "
    term = Terminal()
    position = [term.height // 2, term.width // 2]
    with term.cbreak(), term.fullscreen(), term.hidden_cursor():
        print(term.home + header_msg + term.clear_eos)

        while True:
            # show arrow-controlled block
            print(term.move_yx(*position) + '█', end='', flush=True)

            # get key,
            key = term.inkey()

            # take action,
            if key == 'q':
                break
            if key.name == 'KEY_UP':
                position[0] = max(0, position[0] - 1)
            elif key.name == 'KEY_LEFT':
                position[1] = max(0, position[1] - 1)
            elif key.name == 'KEY_DOWN':
                position[0] = min(term.height, position[0] + 1)
            elif key.name == 'KEY_RIGHT':
                position[1] = min(term.width, position[1] + 1)

Common key names include:

* ``KEY_UP``, ``KEY_DOWN``, ``KEY_LEFT``, ``KEY_RIGHT`` - Arrow keys
* ``KEY_ENTER`` - Enter/Return key
* ``KEY_BACKSPACE``, ``KEY_DELETE`` - Backspace and Delete keys
* ``KEY_TAB`` - Tab key
* ``KEY_ESCAPE`` - Escape key
* ``KEY_F1`` through ``KEY_F12`` - Function keys
* ``KEY_PGUP``, ``KEY_PGDOWN`` - Page Up and Page Down
* ``KEY_HOME``, ``KEY_END`` - Home and End keys

For regular characters without modifiers, :attr:`~.Keystroke.name` returns ``None``.

Modifiers
~~~~~~~~~

Standard keys with modifiers follow the pattern:

* ``KEY_CTRL_A``
* ``KEY_ALT_Q``
* ``KEY_SHIFT_X``
* ``KEY_CTRL_ALT_Y``
* ``KEY_ALT_SHIFT_Z``
* ``KEY_CTRL_ALT_SHIFT_L``

And application keys:

* ``KEY_SHIFT_LEFT``
* ``KEY_CTRL_BACKSPACE``
* ``KEY_ALT_DELETE``
* ``KEY_CTRL_SHIFT_F3``
* ``KEY_CTRL_ALT_SHIFT_F9``

When multiple modifiers are specified, they always in the following order

- ``CTRL``
- ``ALT``
- ``SHIFT``

The escape sequence, ``'\x1b['``, is always decoded as name ``CSI`` when it
arrives without any known matching sequence. There are not any matches
for Keystroke name ``KEY_ALT_[`` except when Kitty_ modes are used.

Magic Methods
~~~~~~~~~~~~~

The :class:`~.Keystroke` class provides convenient "magic methods" for checking
keys with modifiers. These methods all start with ``is_``:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    print('Press ^C or F10 to exit raw mode!')
    with term.raw():
        key = term.inkey()

        # Check for specific character with modifier
        if key.is_ctrl('c') or key.is_f10():
            print(f"Exit by key named {key.name}")
            break

        # Check for function key
        if key.is_f1():
            print("F1 pressed")

        # Check for arrow key with modifier
        if key.is_shift_left():
            print("Shift+Left arrow pressed")

Some examples, given *key* object of :class:`~.Keystroke`:

- ``key.is_ctrl('x')``
- ``key.is_alt('q')``
- ``key.is_ctrl_alt('s')``
- ``key.is_ctrl_shift_alt('a')``
- ``key.is_f1()``
- ``key.is_up()``
- ``key.is_enter()``
- ``key.is_backspace()``
- ``key.is_ctrl_left()``
- ``key.is_alt_backspace()``
- ``key.is_shift_f5()``

By default, character matching is case-insensitive. You can change this with the
``ignore_case`` parameter. For example, "Alt" with capital letter ``U`` matches
both methods:

- ``key.is_alt('u')``
- ``key.is_alt_shift('u')``

To match only To explicitly match "Alt + u" (lowercase 'U'), set ``ignore_case``
argument to False:

- ``key.is_alt('u', ignore_case=False)``

Character Value
~~~~~~~~~~~~~~~

The :attr:`~.Keystroke.value` property returns the text character for keys that
produce text, stripping away modifier information. Special keys like ``KEY_UP``
or ``KEY_F1``, have an empty :attr:`~.Keystroke.value` string. In this example,
you can type ``mango`` while holding down the Alt key:

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
              print(f"got sequence: {val}, {val.name}, {val.code}")
           elif val:
              print(f"got {val}.")
       print(f'bye!{term.normal}')

.. image:: https://dxtz6bzwq9sxx.cloudfront.net/demo_cbreak_inkey.gif
    :alt: A visual example of interacting with the Terminal.inkey() and cbreak() methods.

:meth:`~.Terminal.cbreak` enters a special mode_ that ensures :func:`os.read` on an input stream
will return as soon as input is available, as explained in :linuxman:`cbreak(3)`. This mode is
combined with :meth:`~.Terminal.inkey` to decode multibyte sequences, such as ``\0x1bOA``, into
a unicode-derived :class:`~.Keystroke` instance.

The :class:`~.Keystroke` returned by :meth:`~.Terminal.inkey` is unicode -- it may be printed,
joined with, or compared to any other unicode strings.
It also has these special attributes:

- :attr:`~.Keystroke.is_sequence` (bool): Whether it is an "application" key.
- :attr:`~.Keystroke.code` (int): The keycode, for equality testing.
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

However, these keys do not represent the full range of keys that can be detected
with their modifiers, such as ``KEY_CTRL_LEFT`` is not matched by any code.
