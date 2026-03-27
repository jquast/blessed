.. _cursor shapes:

Cursor Shapes
=============

DECSCUSR (DEC Set Cursor Style) escape sequences allow changing the cursor
shape between block, underline, and bar styles, with optional blinking.

The blessed library provides:

* A :class:`~blessed.cursor_shape.CursorShape` class with constants for each style
* A :meth:`~blessed.Terminal.cursor_shape` context manager for temporary changes

Available Shapes
----------------

.. list-table::
   :header-rows: 1

   * - Constant
     - Value
     - Description
   * - ``DEFAULT``
     - 0
     - Reset to terminal default
   * - ``BLINKING_BLOCK``
     - 1
     - Blinking block cursor
   * - ``STEADY_BLOCK``
     - 2
     - Steady (non-blinking) block
   * - ``BLINKING_UNDERLINE``
     - 3
     - Blinking underline cursor
   * - ``STEADY_UNDERLINE``
     - 4
     - Steady underline cursor
   * - ``BLINKING_BAR``
     - 5
     - Blinking bar (line) cursor
   * - ``STEADY_BAR``
     - 6
     - Steady bar (line) cursor

Usage
-----

Use the :meth:`~blessed.Terminal.cursor_shape` context manager to temporarily
change the cursor shape. The cursor is automatically restored to the terminal
default on exit::

    from blessed import Terminal

    term = Terminal()

    with term.cursor_shape(term.CursorShape.BLINKING_BAR):
        # cursor is a blinking bar
        val = term.inkey()

String names are also accepted::

    with term.cursor_shape('steady_underline'):
        val = term.inkey()

Direct Sequences
----------------

You can also use :meth:`~blessed.cursor_shape.CursorShape.sequence` to get the
raw escape string for manual use::

    import sys
    from blessed.cursor_shape import CursorShape

    sys.stdout.write(CursorShape.sequence(CursorShape.STEADY_BAR))
    sys.stdout.flush()

    # ... do work ...

    sys.stdout.write(CursorShape.sequence(CursorShape.DEFAULT))
    sys.stdout.flush()

Example
-------

.. literalinclude:: ../bin/cursor_shape.py
