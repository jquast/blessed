.. _kitty:

Kitty Keyboard Protocol
=======================

The `Kitty Keyboard Protocol`_ provides enhanced keyboard input capabilities.

It allows your application to distinguish between some special kinds of keys,
between key press, repeat, and release events, and provides improved support for
modifiers and special characters.

.. _Kitty Keyboard Protocol: https://sw.kovidgoyal.net/kitty/keyboard-protocol/

The Kitty keyboard protocol is known to be supported by many popular terminals:
Kitty, alacritty, foot, ghostty, iTerm2, rio, WezTerm.

On terminals that do not support the protocol, the
:meth:`~.Terminal.enable_kitty_keyboard` context manager gracefully does
nothing, and keyboard input continues to work normally, application code does
not need to change.

Overview
--------

This protocol is designed mainly to resolve ambiguity, such as those related to
the Escape key, application keys, Control keys, and Alt+Key sequences. For
example, Ctrl+I and TAB key both send ``\t``, but, with disambiguation mode
enabled, these are detected separately with unique sequences and names,
``KEY_TAB`` and ``KEY_CTRL_I``.

The protocol is automatically detected and enabled when you use the
:meth:`~.Terminal.enable_kitty_keyboard` context manager. If the terminal
doesn't support it, your code continues to work normally using standard
keyboard input.

Unlike standard keyboard input where :attr:`~.Keystroke.name` is ``None``
for plain characters, the Kitty protocol synthesizes names for all ASCII
alphanumeric and punctuation keys. See :ref:`kitty_name_synthesis` for
details.

Getting Started
---------------

Here's a simple example showing key press, repeat, and release events:

.. literalinclude:: ../bin/keyboard_kitty_simple.py
   :language: python
   :linenos:

In this example, pressing and holding a key will show "pressed" once, then
multiple "repeating" messages while held, and finally "released" when you let
go. On terminals that don't support the Kitty protocol, you'll only see
"pressed" events.

Event Types
-----------

When ``report_events=True`` is enabled, the :class:`~.Keystroke` class provides
three properties to distinguish between key event types:

* :attr:`~.Keystroke.pressed` - ``True`` if this is a key press event
* :attr:`~.Keystroke.repeated` - ``True`` if this is a key repeat event
  (repeat events issued by OS when held down)
* :attr:`~.Keystroke.released` - ``True`` if this is a key release event

These properties are only meaningful when Kitty keyboard protocol is enabled
with ``report_events=True``. Without the protocol, all keystrokes will have
``pressed=True`` and ``repeated=False``, ``released=False``.

The :attr:`~.Keystroke.name` attribute also includes event type suffixes:
``KEY_CTRL_J`` for press, ``KEY_CTRL_J_REPEATED`` for repeat, and
``KEY_CTRL_J_RELEASED`` for release events.

For press/release tracking (e.g., key maps), use :attr:`~.Keystroke.key_name`
instead -- it returns the same name regardless of event type (``KEY_CTRL_J``
for press, repeat, and release).  Similarly, :attr:`~.Keystroke.key_value`
returns the character even for release events, where :attr:`~.Keystroke.value`
returns ``''``.

**Note:** To distinguish press, repeat, and release for plain text keys like
``a`` or ``5``, you must also enable ``report_all_keys=True``. Without it, only
release events are encoded with the protocol -- press and repeat arrive as plain
characters with no event-type information.

Example use case - detect only initial key presses and ignore repeats:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()

    with term.enable_kitty_keyboard(report_events=True):
        with term.cbreak():
            while True:
                key = term.inkey()

                # Only respond to initial keypress, ignoring repeat and release
                if key.pressed:
                    if key == 'q':
                        break
                    print(f"Key {key!r} pressed")

Protocol Features
-----------------

The :meth:`~.Terminal.enable_kitty_keyboard` context manager accepts any
combination of the following feature flags as keyword arguments of type bool:

**disambiguate**
  Enables disambiguated escape codes. With this enabled, pressing the Escape
  keys, control, and some application keys produce distinct sequences that more
  correctly identify the user's keypress. For example, Ctrl+I and Tab can be
  distinguished as ``KEY_CTRL_I`` and ``KEY_TAB``.

**report_events**
  Reports key repeat and release events in addition to key press events. This
  allows detecting when keys are held down or released.

**report_alternates**
  Reports both the shifted and base layout keys for keyboard shortcuts. Useful
  for handling shortcuts consistently across different keyboard layouts (e.g.,
  matching both Ctrl+Shift+Equal and Ctrl+Plus as the same shortcut).

**report_all_keys**
  Reports all keys as escape codes, including normal text keys that would
  normally be sent as plain characters.

**report_text**
  Reports the associated text with key events (requires ``report_all_keys``).
  This provides the actual character that would be typed alongside the key code.

Basic usage:

.. code-block:: python

    with term.enable_kitty_keyboard(disambiguate=True, report_events=True):
        # Your code here
        pass

Feel free to try the demonstration program, :ref:`keymatrix.py` to experiment
with combining any or all possible kitty protocol features using Shift+F1
through Shift+F5.

.. _kitty_name_synthesis:

Key Name Synthesis
------------------

The :attr:`~.Keystroke.name` is synthesized for all ASCII alphanumeric keys, punctuation,
and symbols while in kitty keyboard mode.

Some example **Alphanumeric keys**::

    KEY_A, KEY_Z, KEY_0, KEY_9
    KEY_CTRL_A, KEY_ALT_5, KEY_CTRL_ALT_SHIFT_M

**Punctuation and symbols** use descriptive names::

    KEY_SPACE, KEY_PERIOD, KEY_COMMA, KEY_MINUS, KEY_EQUALS
    KEY_LEFT_SQUARE_BRACKET, KEY_RIGHT_SQUARE_BRACKET
    KEY_SLASH, KEY_BACKSLASH, KEY_SEMICOLON, KEY_APOSTROPHE
    KEY_GRAVE_ACCENT, KEY_TILDE, KEY_EXCLAMATION_MARK
    KEY_AT, KEY_HASH, KEY_DOLLAR, KEY_PERCENT, KEY_CARET
    KEY_AMPERSAND, KEY_ASTERISK, KEY_PLUS, KEY_PIPE
    KEY_LEFT_PARENTHESIS, KEY_RIGHT_PARENTHESIS
    KEY_LEFT_CURLY_BRACKET, KEY_RIGHT_CURLY_BRACKET
    KEY_LESS_THAN, KEY_GREATER_THAN, KEY_QUESTION_MARK
    KEY_DOUBLE_QUOTE, KEY_COLON, KEY_UNDERSCORE

Modifiers and event-type suffixes combine as expected::

    KEY_ALT_LEFT_SQUARE_BRACKET
    KEY_CTRL_PERIOD
    KEY_SPACE_RELEASED
    KEY_ALT_MINUS_REPEATED

Shifted Key Reporting
~~~~~~~~~~~~~~~~~~~~~

The Kitty protocol reports the *base key* and modifiers separately rather
than the resulting character. On a US keyboard layout, pressing Shift+3
produces ``#``, but the terminal reports codepoint 51 (digit ``3``) with the
Shift modifier. This means:

- The name is ``KEY_SHIFT_3``, not ``KEY_HASH``
- The :attr:`~.Keystroke.value` is the actual character ``#``

Symbol names like ``KEY_HASH``, ``KEY_AMPERSAND``, and ``KEY_TILDE`` are
still reachable when a terminal sends the symbol codepoint directly, but
on most layouts Shift+digit combinations will produce names based on the
base digit key.

Layout-Independent Key Handling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, the protocol reports whichever key the current keyboard layout
maps to a given position. This means the keys of a physical position on
the keyboard will produce different codepoints on different layouts,
QWERTY, Dvorak, AZERTY, or many non-US layouts.

The ``report_alternates`` flag solves this by requesting the terminal to
also report the *base layout key* -- the key identity independent of the
active layout. When ``report_alternates=True``, blessed uses the base
layout key for name synthesis, so a shortcut like ``KEY_CTRL_Z`` works
regardless of whether the user's layout places ``Z`` in the QWERTY
position or elsewhere.

.. code-block:: python

    with term.enable_kitty_keyboard(report_alternates=True):
        with term.cbreak():
            key = term.inkey()
            if key.name == 'KEY_CTRL_Z':
                undo()

This is especially useful for applications that bind shortcuts to physical
key positions (like Ctrl+Z for undo) rather than to specific characters.

Compatibility
-------------

You can optionally check for protocol support:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    state = term.get_kitty_keyboard_state()
    if state is not None:
        print("Kitty keyboard protocol is supported")
    else:
        print("No kitty protocol support.")

This check is not necessary but may be useful in some cases.

Timeout
-------

The ``timeout`` parameter of :meth:`~.Terminal.enable_kitty_keyboard` controls
how long to await negotiation, in seconds.

When negotiating, both DA1_ and Kitty protocol status request sequences are
transmitted, making it possible to automatically detect protocol support in
almost all cases, but terminals that support neither DA1_ or Kitty protocol
("dumb" terminals) will block forever unless ``timeout`` is set.

.. _DA1: https://vt100.net/docs/vt510-rm/DA1.html

See Also
--------

* :doc:`keyboard` - Basic keyboard input handling
* :meth:`Terminal.enable_kitty_keyboard` - Enable Kitty protocol features
* :meth:`Terminal.get_kitty_keyboard_state` - Query current protocol state
* :attr:`Keystroke.pressed` - Check if key was pressed
* :attr:`Keystroke.repeated` - Check if key is repeating
* :attr:`Keystroke.released` - Check if key was released
* :attr:`Keystroke.key_name` - Key identity without event-type suffix
* :attr:`Keystroke.key_value` - Character for the key, even for release events
