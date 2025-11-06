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

Like standard keyboard input, Kitty protocol keystrokes provide a
:attr:`~.Keystroke.name` attribute for special keys (``KEY_ESCAPE``, ``KEY_F1``,
``KEY_UP``) and modified alphanumeric keys (``KEY_CTRL_A``, ``KEY_ALT_5``).
Plain text input like typing 'a' or '5' has no name, making it easy to
distinguish between commands and regular text.

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
