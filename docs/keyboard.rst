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

Getting Started
---------------

Here's a simple example that reads a single keystroke:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        key = term.inkey()
        print(f"You pressed: {key!r}")

The :meth:`~.Terminal.cbreak` context manager enables immediate key detection.

Inside this context, :meth:`~.Terminal.inkey` returns a :class:`~.Keystroke`
object representing the key that was immediately pressed.

Keystroke
---------

The :class:`~.Keystroke` class makes it easy to work with keyboard input. It
inherits from :class:`str`, so you can compare it directly to characters, but it
also provides special properties for detecting modifier keys and special
sequences.

* Use :meth:`~.Terminal.inkey` with ``timeout`` for non-blocking input
* Use :attr:`~.Keystroke.is_sequence` to detect special keys
* Use :attr:`~.Keystroke.name` to identify keys by name (e.g., ``KEY_F1``, ``KEY_CTRL_Q``)
* Or, by magic methods like ``keystroke.is_f1()`` or ``keystroke.is_key_ctrl('q')``.

Special Keys
~~~~~~~~~~~~

The :attr:`~.Keystroke.is_sequence` property returns ``True`` for arrow keys,
function keys, and any key combination with modifiers (Ctrl, Alt, Shift):

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        key = term.inkey()
        
        if key.is_sequence:
            print(f"Special key: {key.name}")
        else:
            print(f"Regular character: {key}")

name: Identifying Keys
~~~~~~~~~~~~~~~~~~~~~~

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
                position[0] = max(term.height, position[0] + 1)
            elif key.name == 'KEY_RIGHT':
                position[1] = max(term.width, position[1] + 1)

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
---------

Blessed detects modifier keys (Ctrl, Alt, Shift) combined with regular keys or
special keys. The :attr:`~.Keystroke.name` property represents these
combinations:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        print("Try Ctrl+Q or Alt+X:")
        while True:
            key = term.inkey()
            
            if key.name == 'KEY_CTRL_Q':
                print("Quitting with Ctrl+Q")
                break
            elif key.name == 'KEY_ALT_X':
                print("You pressed Alt+X")
            elif key.name == 'KEY_CTRL_ALT_S':
                print("Ctrl+Alt+S detected, nice!")

Standard keys with modifiers follow the pattern:

* ``KEY_CTRL_<char>`` - Control + character (e.g., ``KEY_CTRL_C``)
* ``KEY_ALT_<char>`` - Alt + character (e.g., ``KEY_ALT_F``)
* ``KEY_SHIFT_<char>`` - Shift + letter (e.g., ``KEY_ALT_SHIFT_A``)
* ``KEY_CTRL_ALT_<char>`` - Ctrl + Alt + character

And application keys:

* ``KEY_SHIFT_LEFT`` - Shift + Left Arrow
* ``KEY_CTRL_BACKSPACE`` - Ctrl + Backspace
* ``KEY_ALT_DELETE`` - Alt + Delete
* ``KEY_CTRL_SHIFT_F3`` - Ctrl + Shift + F3
* ``KEY_CTRL_ALT_SHIFT_F9`` - Ctrl + Alt + Shift + F9

When multiple modifiers are specified, they are always in the order of ``CTRL``,
``ALT``, and then ``SHIFT``.


Magic Methods
-------------

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


Some examples:

.. code-block:: python

    key.is_ctrl('x')
    key.is_alt('q')
    key.is_ctrl_alt('s')
    key.is_ctrl_shift_alt('a')
    key.is_f1()
    key.is_up()
    key.is_enter()
    key.is_backspace()
    key.is_ctrl_left()
    key.is_alt_backspace()
    key.is_shift_f5()

By default, character matching is case-insensitive. You can change this with the
``ignore_case`` parameter:

.. code-block:: python

    from blessed import Terminal
    term = Terminal()
    term.ungetch('\x1bU')

    assert key.is_alt('u')
    assert key.is_alt_shift('u')
    assert not key.is_alt('u', ignore_case=False)

Timeouts
--------

The :meth:`~.Terminal.inkey` method accepts a ``timeout`` parameter (in seconds)
for non-blocking input:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        print("Press any key (waiting 3 seconds)...")
        key = term.inkey(timeout=3)
        
        if key:
            print(f"You pressed: {key!r}")
        else:
            print("No key pressed (timeout)")

A timeout of ``0`` checks for immediately available input:

.. code-block:: python

    from blessed import Terminal
    import time

    term = Terminal()
    print("Very fast cross animation, press any key to stop: ", end="", flush=True)
    with term.cbreak(), term.hidden_cursor():
        cross = '|'
        
        while True:
            key = term.inkey(timeout=0)
            if key:
                break

            cross = {'|':'-', '-':'|'}[cross]
            print(f'{cross}\b', end='', flush=True)


Character Value
~~~~~~~~~~~~~~~

The :attr:`~.Keystroke.value` property returns the text character for keys that
produce text, stripping away modifier information. Special keys like ``KEY_UP``
or ``KEY_F1``, have an empty :attr:`~.Keystroke.value` string.


.. code-block:: python

    from blessed import Terminal

    def prompt(question, max_length=15):
        print(f'{question} ', end='', flush=True)
        text = ""

        term = Terminal()
        with term.cbreak():
            while True:
                key = term.inkey()
                
                if key.name == 'KEY_ENTER':
                    print()
                    return text
                if key.name in ('KEY_BACKSPACE', 'KEY_DELETE'):
                    if text:
                        text = text[:-1]
                        print(f"\b \b", end='', flush=True)
                elif key.value and len(text) < max_length:
                    text += key.value
                    print(key.value, end='', flush=True)
        
    fruit = prompt("What is your favorite fruit?")

    flavor = 'sweet' if sum(map(ord,fruit)) % 2 == 0 else 'sour'

    yn = prompt(f"Never heard of {fruit}, is it {flavor}?")
    if yn.lower().startswith('y'):
        print("I thought so!")
    else:
        print("Sounds tasty!")


Flushing Input
~~~~~~~~~~~~~~

Sometimes you need to clear any pending keyboard input, such as when switching
screens or to "debounce" input after a long processing delay. Use
:meth:`~.Terminal.flushinp` to discard buffered input:

.. code-block:: python

    from blessed import Terminal
    import time

    term = Terminal()
    
    with term.cbreak():
        print("Processing... (please wait)")
        time.sleep(2)
        
        # Discard any keys pressed during the delay
        term.flushinp()
        
        print("Ready! Press any key:")
        key = term.inkey()


Key Codes
~~~~~~~~~

For compatibility with Legacy curses applications, :attr:`~.Keystroke.code` may
be be compared with attributes of :class:`~.Terminal`, which are duplicated from
those found in :linuxman:`curses(3)`, or those `constants
<https://docs.python.org/3/library/curses.html#constants>`_ in :mod:`curses`
beginning with phrase *KEY_*. These have numeric values that can be used for all
basic application keys.

.. include:: all_the_keys.txt

However, these keys do not represent the full range of keys that can be detected
with their modifiers, such as ``KEY_LEFT`` as ``KEY_CTRL_LEFT``,
``KEY_CTRL_SHIFT_LEFT``, and ``KEY_CTRL_ALT_SHIFT_LEFT`` are only matchable
by their names.
