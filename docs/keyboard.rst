Keyboard Input
==============

Python's built-in :func:`input` function is great for simple prompts, but it has
one limitation: it waits for the Enter key. This makes it unsuitable for
interactive applications that need to respond to individual keystrokes, arrow
keys, or function keys.

Blessed provides a solution with :meth:`~.Terminal.inkey`, which returns
keystrokes *as they are pressed*, as :class:`~.Keystroke` objects.

Overview
--------

The :meth:`~.Terminal.cbreak` context manager enables immediate key detection.

The :meth:`~.Terminal.inkey` method returns a :class:`~.Keystroke` object
representing the key that was immediately pressed.

Getting Started
---------------

Here's a simple example that reads a single keystroke:

.. literalinclude:: ../bin/keyboard_simple.py
   :language: python
   :linenos: 1-

The :meth:`~.Terminal.inkey` method also accepts a ``timeout`` parameter (in
seconds). When timeout is exceeded without input, an empty :class:`~.Keystroke`
is returned, ``''``.

In this example, a 10Hz animation is displayed by ``timeout=0.1``, stopped
by pressing any key:

.. literalinclude:: ../bin/keyboard_animation.py
   :language: python
   :linenos: 1-

Keystroke
---------

The :class:`~.Keystroke` class makes it easy to work with keyboard input. It
inherits from :class:`str`, so you can compare it directly to other strings, but
it also provides special properties for detecting modifier keys and special
sequences.

* Use :attr:`~.Keystroke.is_sequence` to detect special keys
* Use :attr:`~.Keystroke.name` to identify special keys by name (e.g., ``KEY_F1``, ``KEY_CTRL_Q``)
* Or, by using magic methods like ``keystroke.is_f1()`` or ``keystroke.is_key_ctrl('q')``.

Be careful to print it directly, though, our examples uses format string,
``f'{ks!r}'`` for ``repr()``, because the input may contain input that begins
with the escape key, (``KEY_ESCAPE``) and are generally unprintable.

Special Keys
~~~~~~~~~~~~

The :attr:`~.Keystroke.is_sequence` property returns ``True`` for arrow keys,
function keys, and any character key combined with modifiers (Ctrl, Alt, Shift).

.. literalinclude:: ../bin/keyboard_special_keys.py
   :language: python
   :linenos: 1-

The ``str(key)`` value for :class:`~.Keystroke` should not be directly printed
when :attr:`~.Keystroke.is_sequence` is True as done in this and other examples.

The :attr:`~.Keystroke.name` property provides a readable name for special keys,
and can be used for basic equality tests, like in this "paint by arrow key" example:

.. literalinclude:: ../bin/keyboard_arrow_paint.py
   :language: python
   :linenos: 1-

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

Feel free to try the demonstration program, :ref:`keymatrix.py` to experiment
with possible keyboard inputs and combinations.

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

When multiple modifiers are specified, they are always in the following order

- ``CTRL``
- ``ALT``
- ``SHIFT``

The escape sequence, ``'\x1b['``, is always decoded as name ``CSI`` when it
arrives without any known matching sequence. There are not any matches
for Keystroke name ``KEY_ALT_[``.

The :attr:`~.Keystroke.value` property returns the text character for keys that
produce text, stripping away modifier information.

Special keys like ``KEY_UP``, ``KEY_F1``, ``KEY_BACKSPACE``
have an empty :attr:`~.Keystroke.value` string.

Control characters like ``KEY_CTRL_C`` are :attr:`~.Keystroke.value` ``c``
(lowercase). Similarly for alt, ``KEY_ALT_a`` is :attr:`~.Keystroke.value`
``a``.

Magic Methods
~~~~~~~~~~~~~

The :class:`~.Keystroke` class provides convenient "magic methods" for checking
keys with modifiers. These methods all start with ``is_``:

.. literalinclude:: ../bin/keyboard_magic_methods.py
   :language: python
   :linenos: 1-

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

To explicitly match only "Alt + u" (lowercase 'U'), set ``ignore_case``
argument to False:

- ``key.is_alt('u', ignore_case=False)``

Keycodes
--------

For Legacy API of classic curses applications, :attr:`~.Keystroke.code` may be
be compared with attributes of :class:`~.Terminal`, which are duplicated from
those found in :linuxman:`curses(3)`, or those `constants
<https://docs.python.org/3/library/curses.html#constants>`_ in :mod:`curses`
beginning with phrase *KEY_*. These have numeric values that can be used for
all basic application keys.

However, these keys do not represent the full range of keys that can be detected
with their modifiers, such as ``KEY_CTRL_LEFT`` is not matched by any Keycode
constant.

These are duplicated from those found in :linuxman:`curses(3)`, or those
`constants <https://docs.python.org/3/library/curses.html#constants>`_ in
:mod:`curses` beginning with phrase *KEY_*, as follows:

.. include:: all_the_keys.txt

