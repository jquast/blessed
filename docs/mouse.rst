Mouse Input
===========

Blessed supports mouse input in the terminal! Your applications can respond to
clicks, drags, or track live mouse movement for creating interactive games and
apps.

The blessed library provides a simple API for mouse tracking:

* Check support with :meth:`~blessed.Terminal.does_mouse`
* Enable mouse tracking with :meth:`~blessed.Terminal.mouse_enabled`
* Receive events through :meth:`~blessed.Terminal.inkey`

Mouse events work seamlessly with keyboard events - both come through the same
:meth:`~blessed.Terminal.inkey` method.

Getting Started
---------------

Here's a simple example that waits for a click:

.. literalinclude:: ../bin/mouse_simple.py
   :language: python
   :linenos:

The :meth:`~.Terminal.mouse_enabled` context manager enables mouse tracking
and automatically disables it when done. Mouse events arrive through
:meth:`~.Terminal.inkey` just like keyboard events.

Understanding mouse_enabled()
------------------------------

The :meth:`~blessed.Terminal.mouse_enabled` context manager automatically
selects and enables the appropriate terminal modes based on what you need to
track.

Basic Usage
~~~~~~~~~~~

.. code-block:: python

    # Basic click tracking (default)
    with term.mouse_enabled():
        inp = term.inkey()
        if inp.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
            mouse = inp.mode_values
            print(f"Clicked at ({mouse.y}, {mouse.x})")

Parameters
~~~~~~~~~~

The method accepts these keyword-only parameters:

* ``clicks=True`` - Enable basic click reporting (default)
* ``report_drag=False`` - Also report motion while a button is held
* ``report_motion=False`` - Report all mouse movement (even without buttons)
* ``report_pixels=False`` - Report position in pixels instead of cells
* ``timeout=1.0`` - Timeout for mode queries in seconds

**Parameter Precedence**

The tracking modes have precedence: ``report_motion`` > ``report_drag`` > ``clicks``.
When you enable a higher-precedence mode, it automatically includes the functionality
of lower modes. For example, ``report_motion=True`` will also track drags and clicks.

Tracking Clicks
~~~~~~~~~~~~~~~

Default behavior - tracks button press and release events:

.. code-block:: python

    with term.mouse_enabled():
        inp = term.inkey()
        if inp.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
            mouse = inp.mode_values
            if not mouse.is_release:
                print(f"Button {mouse.button} pressed at ({mouse.y}, {mouse.x})")

Tracking Drags (report_drag=True)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Also reports motion while a button is held down:

.. code-block:: python

    with term.mouse_enabled(report_drag=True):
        inp = term.inkey()
        if inp.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
            mouse = inp.mode_values
            if mouse.is_motion:
                print(f"Dragging at ({mouse.y}, {mouse.x})")

Tracking All Motion (report_motion=True)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Reports all mouse movement, even without buttons pressed. This is great for
hover effects but generates many events.

Here's a drawing program that paints when you move the mouse with a button held:

.. literalinclude:: ../bin/mouse_paint.py
   :language: python
   :linenos:

This example uses :meth:`~.Terminal.fullscreen` and
:meth:`~.Terminal.hidden_cursor` for a clean canvas, and checks
:attr:`~.MouseEvent.is_motion` to distinguish movement from clicks.

.. note::

   When using ``report_motion=True``, process events quickly! Mouse movement
   generates many events that can fill the input buffer if not consumed promptly.

Pixel Coordinates (report_pixels=True)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, mouse positions are reported in character cell coordinates - each
position corresponds to a single character in the terminal grid.

For higher precision, use ``report_pixels=True`` to get pixel coordinates instead.
This is especially useful when combined with graphics protocols like Sixel:

.. literalinclude:: ../bin/mouse_pixels.py
   :language: python
   :linenos:

When using pixel mode, events come through
:attr:`~Terminal.DecPrivateMode.MOUSE_SGR_PIXELS` instead. The
:class:`~.MouseEvent` structure is identical - only the meaning of ``x`` and
``y`` values changes from cells to pixels.

Checking Mouse Support
-----------------------

Not all terminals support mouse tracking. Use :meth:`~blessed.Terminal.does_mouse`
to check before enabling:

.. code-block:: python

    if term.does_mouse():
        with term.mouse_enabled():
            # Use mouse tracking
            pass
    else:
        print("Mouse tracking not supported")

The :meth:`~.Terminal.does_mouse` method accepts the same parameters as
:meth:`~.Terminal.mouse_enabled` and returns ``True`` if all required modes
are supported:

.. code-block:: python

    # Check for drag support
    if term.does_mouse(report_drag=True):
        with term.mouse_enabled(report_drag=True):
            # Track drags
            pass

    # Check for pixel coordinate support
    if term.does_mouse(report_pixels=True):
        with term.mouse_enabled(report_pixels=True):
            # Use pixel coordinates
            pass

**Low-level mode queries**

For advanced use cases, you can query specific DEC modes directly:

.. literalinclude:: ../bin/mouse_query.py
   :language: python
   :linenos:

The :meth:`~.Terminal.get_dec_mode` method provides detailed information about
individual modes. The ``timeout`` parameter prevents blocking on terminals that
don't respond.

Understanding Mouse Events
---------------------------

Mouse events come through :meth:`~.Terminal.inkey` just like keyboard events.

A :class:`~.Keystroke` object is a mouse event when :attr:`~.Keystroke.mode`
matches one of the enabled mouse modes
(:attr:`~Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR` or
:attr:`~Terminal.DecPrivateMode.MOUSE_SGR_PIXELS`).

Call :meth:`~.Keystroke.mode_values` to get a :class:`~.MouseEvent` instance
with event details:

* ``button`` - Which button (0=left, 1=middle, 2=right, or 64-65 for wheel)
* ``x``, ``y`` - Mouse position (0-indexed cells, or pixels with ``report_pixels=True``)
* ``is_release`` - Whether this is a button release event
* ``is_motion`` - Whether motion is being reported
* ``is_wheel`` - Whether this is a scroll wheel event
* ``shift``, ``ctrl``, ``meta`` - Whether modifier keys are pressed

Example
~~~~~~~

.. code-block:: python

    with term.cbreak(), term.mouse_enabled(report_drag=True):
        while True:
            inp = term.inkey()

            if inp == 'q':
                break

            if inp.mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
                mouse = inp.mode_values

                # Check button state
                if mouse.button == 0 and not mouse.is_release:
                    print(f"Left click at ({mouse.y}, {mouse.x})")

                # Check if dragging
                if mouse.is_motion and mouse.button == 0:
                    print(f"Dragging at ({mouse.y}, {mouse.x})")

                # Check modifiers
                if mouse.shift:
                    print("Shift key held")

Advanced: Manual Mode Control
------------------------------

For fine-grained control, you can enable specific DEC Private Modes manually
using :meth:`~blessed.Terminal.dec_modes_enabled`:

.. code-block:: python

    with term.dec_modes_enabled(
        term.DecPrivateMode.MOUSE_EXTENDED_SGR,
        term.DecPrivateMode.MOUSE_ALL_MOTION,
    ):
        # Mouse tracking active here
        pass

The key DEC Private Modes for mouse tracking are:

* ``MOUSE_EXTENDED_SGR`` (1006) - Modern mouse reporting format
* ``MOUSE_REPORT_CLICK`` (1000) - Button press and release events
* ``MOUSE_REPORT_DRAG`` (1002) - Motion while button held
* ``MOUSE_ALL_MOTION`` (1003) - All mouse movement
* ``MOUSE_SGR_PIXELS`` (1016) - Pixel coordinates instead of cells

See :doc:`dec_modes` for more details on working with DEC Private Modes.

See Also
--------

* :doc:`keyboard` - Keyboard input handling
* :doc:`dec_modes` - DEC Private Modes overview
* :meth:`Terminal.does_mouse` - Check mouse support
* :meth:`Terminal.mouse_enabled` - Convenient mouse tracking
* :meth:`Terminal.inkey` - Read keyboard and mouse events
* :meth:`Terminal.get_dec_mode` - Query mode support
* :meth:`Terminal.dec_modes_enabled` - Enable modes manually
* :attr:`Terminal.DecPrivateMode` - Available mode constants
* :ref:`keymatrix.py` - Interactive demo showing raw mouse events
