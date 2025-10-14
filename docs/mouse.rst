Mouse Input
===========

Blessed supports mouse input in the terminal! Your applications can respond to
clicks, drags, or track live mouse movement for creating interactive games and
apps.

The blessed library provides a clean API for mouse tracking:

* Enable mouse modes with :meth:`~blessed.Terminal.dec_modes_enabled`
* Receive events through :meth:`~blessed.Terminal.inkey`
* Query support with :meth:`~blessed.Terminal.get_dec_mode`

Mouse events work seamlessly with keyboard events - both come through the same
:meth:`~blessed.Terminal.inkey` method.

Getting Started
---------------

Here's a simple example that waits for a click:

.. literalinclude:: ../bin/mouse_simple.py
   :language: python
   :linenos:

The :meth:`~.Terminal.dec_modes_enabled` context manager enables mouse tracking
and automatically disables it when done. Mouse events arrive through
:meth:`~.Terminal.inkey` just like keyboard events.

Checking Mouse Support
-----------------------

Not all terminals support mouse modes. You can check before enabling:

.. literalinclude:: ../bin/mouse_query.py
   :language: python
   :linenos:

The :meth:`~.Terminal.get_dec_mode` method queries terminal capabilities. A
``timeout`` parameter prevents blocking on terminals that don't respond. This is
used in many examples later.

Understanding Mouse Events
---------------------------

Mouse events come through :meth:`~.Terminal.inkey` just like keyboard events.

A :class:`~.Keystroke` object is a mouse event when :attr:`~.Keystroke.mode`
matches one of the enabled mouse modes.

Call :meth:`~.Keystroke.mode_values` to get a :class:`~.MouseEvent` instance
with event details:

* ``button`` - Which button (0=left, 1=middle, 2=right, or 64-65 for wheel)
* ``x``, ``y`` - Mouse position (0-indexed cells, or pixels with SGR_PIXELS)
* ``is_release`` - Whether this is a button release event
* ``is_motion`` - Whether motion is being reported
* ``is_wheel`` - Whether this is a scroll wheel event
* ``shift``, ``ctrl``, ``meta`` - Whether modifier keys are pressed

Understanding Mouse Modes
-------------------------

Most modern terminals support mouse tracking, and can be enabled using our
support of `DEC Private Modes`_.

The key Dec Private Modes are:

* :attr:`~Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR` (1006):
  Modern mouse reporting format (always use this)
* :attr:`~Terminal.DecPrivateMode.MOUSE_REPORT_CLICK` (1000):
  Reports button press and release events
* :attr:`~Terminal.DecPrivateMode.MOUSE_REPORT_DRAG` (1002):
  Also reports motion while button is held
* :attr:`~Terminal.DecPrivateMode.MOUSE_ALL_MOTION` (1003):
  Reports all mouse movement
* :attr:`~Terminal.DecPrivateMode.MOUSE_SGR_PIXELS` (1016):
  Reports position in pixels instead of cells

MOUSE_EXTENDED_SGR
~~~~~~~~~~~~~~~~~~

This is the recommended base protocol type. When supported the mouse protocol
data is transmitted in a modern format with fewest limitations.

.. note::

   Always combine :attr:`~Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR` with one
   of the *tracking* modes, as it does not enable anything interesting on its
   own.

MOUSE_REPORT_CLICK
~~~~~~~~~~~~~~~~~~

Reports button press and release events only:

.. literalinclude:: ../bin/mouse_clicks.py
   :language: python
   :linenos:

This is the most common mode for handling button clicks. It doesn't report
motion unless combined with :attr:`~Terminal.DecPrivateMode.MOUSE_REPORT_DRAG`
or :attr:`~Terminal.DecPrivateMode.MOUSE_ALL_MOTION`.

MOUSE_REPORT_DRAG
~~~~~~~~~~~~~~~~~

Extends :attr:`~Terminal.DecPrivateMode.MOUSE_REPORT_CLICK` by also reporting
motion while a button is held down. This is perfect for drag operations and
drawing:

.. literalinclude:: ../bin/mouse_drag.py
   :language: python
   :linenos:

MOUSE_ALL_MOTION
~~~~~~~~~~~~~~~~

Reports all mouse movement, even without buttons pressed. This is great for
hover effects but generates many events.

Here's a simple drawing program where you can paint by moving the mouse with a
button held down:

.. literalinclude:: ../bin/mouse_paint.py
   :language: python
   :linenos:

This example demonstrates using :meth:`~.Terminal.fullscreen` and
:meth:`~.Terminal.hidden_cursor` for a clean canvas, and evaluating the
:class:`~.MouseEvent` to determine mouse state.

.. note::

   When using :attr:`~Terminal.DecPrivateMode.MOUSE_ALL_MOTION`, process events
   quickly! Mouse movement generates many events that can fill the input buffer
   if not consumed promptly.

MOUSE_SGR_PIXELS
~~~~~~~~~~~~~~~~

Most mouse tracking uses character cell coordinates - each position corresponds
to a single character in the terminal grid. This works well for most
applications.

For higher precision, many terminals support
:attr:`~blessed.Terminal.DecPrivateMode.MOUSE_SGR_PIXELS` (1016), which reports
position in pixels instead of cells. This is especially useful when combined
with graphics protocols like Sixel:

.. literalinclude:: ../bin/mouse_pixels.py
   :language: python
   :linenos:

The :class:`~.MouseEvent` structure is identical for both modes - only the
meaning of ``x`` and ``y`` values changes.

See Also
--------

* :doc:`keyboard` - Keyboard input handling
* :doc:`dec_modes` - DEC Private Modes overview
* :meth:`Terminal.inkey` - Read keyboard and mouse events
* :meth:`Terminal.get_dec_mode` - Query mode support
* :meth:`Terminal.dec_modes_enabled` - Enable modes temporarily
* :attr:`Terminal.DecPrivateMode` - Available mode constants
* :ref:`keymatrix.py` - Interactive demo showing raw mouse events
