.. _dec private modes:

DEC Private Modes
=================

DEC Private Modes are terminal control sequences that enable or disable specific
terminal behaviors like cursor visibility, mouse tracking, alternate screen
buffers, and modern features like synchronized output.

The blessed library provides a clean API for working with these modes:

* Query mode support with :meth:`~blessed.Terminal.get_dec_mode`
* Enable modes with :meth:`~blessed.Terminal.dec_modes_enabled` context manager
* Disable modes with :meth:`~blessed.Terminal.dec_modes_disabled` context manager

Each mode is identified by a constant from
:attr:`Terminal.DecPrivateMode <blessed.Terminal.DecPrivateMode>`.
Our mode catalog is derived from https://wiki.tau.garden/dec-modes/

Overview
--------

DEC Private Modes control a wide variety of terminal features. Some common
examples include:

* **DECTCEM** (25) - Cursor visibility
* **MOUSE_REPORT_CLICK** (1000) - Basic mouse click reporting
* **MOUSE_EXTENDED_SGR** (1006) - Extended mouse reporting with pixel coordinates
* **BRACKETED_PASTE** (2004) - Receive clipboard paste as a single event
* **FOCUS_IN_OUT_EVENTS** (1004) - Detect when terminal window gains/loses focus
* **SYNCHRONIZED_OUTPUT** (2026) - Eliminate screen flicker during redraws

The context managers gracefully handle unsupported modes - your code works
normally even on terminals that don't support specific features.

Getting Started
---------------

Here's a simple example that temporarily hides the cursor:

.. literalinclude:: ../bin/dec_modes_simple.py
   :language: python
   :linenos:

The cursor automatically reappears when the context exits, even if an exception
occurs.

This usually emits the same sequences recorded in the terminfo database of
modern terminals for the ``term.hide_cursor`` and ``term.normal_cursor``
attributes and offered by our context manager method,
:meth:`~Terminal.hidden_cursor`.

The difference is that we can also make inquiries into the whether the mode is
supported at all.

Querying Mode Support
----------------------

You can check if a terminal supports a specific mode using
:meth:`~blessed.Terminal.get_dec_mode`. This is useful for adapting your
application to different terminal capabilities:

.. literalinclude:: ../bin/dec_modes_query.py
   :language: python
   :linenos:

The :class:`~blessed.dec_modes.DecModeResponse` object provides helper methods:

* :meth:`~blessed.dec_modes.DecModeResponse.is_supported` - Mode is recognized
* :meth:`~blessed.dec_modes.DecModeResponse.is_enabled` - Mode is currently active
* :meth:`~blessed.dec_modes.DecModeResponse.is_disabled` - Mode is currently inactive
* :meth:`~blessed.dec_modes.DecModeResponse.is_permanent` - Mode setting cannot be changed
* :meth:`~blessed.dec_modes.DecModeResponse.is_failed` - Query failed or timed out

Query results are automatically cached. Use ``force=True`` to bypass the cache:

.. code-block:: python

    # Force a fresh query
    response = term.get_dec_mode(term.DecPrivateMode.DECTCEM, force=True)

Context Managers
----------------

The recommended way to work with modes is through context managers:

* :meth:`~blessed.Terminal.dec_modes_enabled` - Temporarily enable one or more modes
* :meth:`~blessed.Terminal.dec_modes_disabled` - Temporarily disable one or more modes

These context managers:

1. Query the mode's current state (with caching)
2. Change the mode if needed
3. Restore the original state on exit
4. Handle unsupported modes gracefully

You can pass multiple modes and set a timeout for queries:

.. code-block:: python

    with term.dec_modes_enabled(
        term.DecPrivateMode.DECTCEM,
        term.DecPrivateMode.MOUSE_REPORT_CLICK,
        timeout=1.0
    ):
        # Both modes enabled here
        pass

Synchronized Output
-------------------

Synchronized Output (mode 2026) eliminates screen flicker by buffering all
output until the mode is exited. This is perfect for animations and full-screen
redraws.

Without synchronized output, rapidly clearing and redrawing the screen creates
a visible blink effect. With it, updates appear instantly:

.. literalinclude:: ../bin/dec_modes_synchronized.py
   :language: python
   :linenos:

On terminals that support this mode, you'll see smooth animation. On terminals
that don't, the animation still works but may blink. The first loop iteration
may pause briefly (up to the timeout value) while the terminal is queried.

Bracketed Paste
---------------

Bracketed Paste (mode 2004) allows your application to receive clipboard paste
operations as a single event rather than a stream of individual characters.
This makes it easy to distinguish between typed and pasted text:

.. literalinclude:: ../bin/dec_modes_bracketed_paste.py
   :language: python
   :linenos:

When :attr:`Keystroke.mode` equals
:attr:`~blessed.dec_mode.DecPrivateMode.BRACKETED_PASTE`, the
:meth:`~.Keystroke.mode_values` method returns a
:class:`~blessed.keyboard.BracketedPasteEvent` with a ``text`` attribute
containing the pasted content.

Focus Events
------------

Focus tracking (mode 1004) reports when the terminal window gains or loses
focus. This is useful for pausing animations or updating status indicators:

.. literalinclude:: ../bin/dec_modes_focus.py
   :language: python
   :linenos:

When :attr:`Keystroke.mode` equals
:attr:`~blessed.dec_mode.DecPrivateMode.FOCUS_IN_OUT_EVENTS`, the
:meth:`~.Keystroke.mode_values` method returns a
:class:`~blessed.keyboard.FocusEvent` with a ``gained`` attribute indicating
whether focus was gained (``True``) or lost (``False``).

See Also
--------

* :doc:`keyboard` - Basic keyboard input handling
* :doc:`mouse` - Mouse event handling
* :meth:`Terminal.get_dec_mode` - Query mode support
* :meth:`Terminal.dec_modes_enabled` - Enable modes temporarily
* :meth:`Terminal.dec_modes_disabled` - Disable modes temporarily
* :attr:`Terminal.DecPrivateMode` - Available mode constants
