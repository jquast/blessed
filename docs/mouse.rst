Mouse Input
===========

Blessed supports mouse input in the terminal! Your terminal apps can respond to
clicks, drags, or track live mouse movement. This opens up exciting
possibilities for creating interactive games and apps.

Not all terminals support mouse tracking, but most modern ones do. Let's see how it works!

Getting Started
---------------

Here's a simple example that waits for you to click anywhere:

.. code-block:: python

    from blessed import Terminal, DecPrivateMode

    term = Terminal()
    print("Click anywhere!")
    
    # Enable mouse click tracking with modern SGR format
    with term.cbreak(), term.dec_modes_enabled(
            DecPrivateMode.MOUSE_REPORT_CLICK,
            DecPrivateMode.MOUSE_EXTENDED_SGR, timeout=0.1):
        
        while True:
            event = term.inkey()
            
            # Check if this is a mouse event
            if event.mode == DecPrivateMode.MOUSE_EXTENDED_SGR:
                mouse = event.mode_values()
                if not mouse.is_release:
                    button_name = {0: 'left', 1: 'middle', 2: 'right'}.get(mouse.button, 'unknown')
                    print(f"{button_name} button clicked at (y={mouse.y}, x={mouse.x})")
                    break

The :meth:`~.Terminal.dec_modes_enabled` context manager enables mouse tracking
modes and automatically disables them when done. We use :meth:`~.Terminal.inkey`
to read events - both keyboard and mouse!

Testing for Mouse Support
--------------------------

Not all terminals support mouse modes. You can test for DEC Private Mode,
:attr:`~.DecPrivateMode.MOUSE_EXTENDED_SGR`::

.. code-block:: python

    from blessed import Terminal, DecPrivateMode

    term = Terminal()
    
    # Query mouse support with a 1 second timeout
    mode_test = DecPrivateMode.MOUSE_EXTENDED_SGR
    response = term.get_dec_mode(mode_test, timeout=1.0)
    
    if response.is_supported():
        print("Mouse tracking is supported", end='')
        if response.is_enabled():
            print(' and enabled!')
        else:
            print(", and may be enabled")
    else:
        print("Mode not supported, {mode}")
        
The :meth:`~.Terminal.get_dec_mode` method queries the terminal's capabilities
for any particular mode with a response that can be tested with
``is_supported()`` and ``is_enabled()``.

.. code-block:: python


Understanding Mouse Events
--------------------------

Mouse events come through :meth:`~.Terminal.inkey` just like keyboard events. To
identify them, check the :attr:`~.Keystroke.mode` property. You may enable and
check for the following Mouse supported by blessed:

- :attr:`~.DecPrivateMode.MOUSE_REPORT_CLICK`: Legacy mode sends Mouse X & Y
  coordinates and button value when clicked
- :attr:`~.DecPrivateMode.MOUSE_ALL_MOTION`: Sends all Mouse state on any action
- :attr:`~.DecPrivateMode.MOUSE_EXTENDED_SGR`: Enhanced Mouse sends more details
  (extra buttons, scroll wheels) and compatible with larger screens
- :attr:`~.DecPrivateMode.MOUSE_SGR_PIXELS`: Sends pixel graphic location rather
  than text row (X) and column (Y) location

When you have a :meth:`~.Keystroke` object of a mouse event returned by
:meth:`~.Terminal.inkey`, call :meth:`~.Keystroke.mode_values` to get a
:class:`~.MouseEvent` with details of the event.

The :class:`~.MouseEvent` fields are:

- ``button``: Which button (0=left, 1=middle, 2=right, or 64-65 for wheel events)
- ``x``, ``y``: Mouse position in terminal cells (0-indexed), or pixels when using SGR-Pixels mode
- ``is_release``: Whether this is a button release event
- ``is_motion``: Whether motion is being reported (True whenever the mouse moves)
- ``is_wheel``: Whether this is a scroll wheel event
- ``shift``, ``ctrl``, ``meta``: Whether modifier keys are pressed

.. note::
   The mouse protocols don't directly indicate which button (if any) is held during motion.
   Applications should track button state themselves by monitoring press and release events.
   See the "Paint by Mouse" example below for the recommended pattern.

This example shows details of a Mouse Event after click, and a timeout value is
used and error reported for terminals that do not support it:

.. code-block:: python

    from blessed import Terminal, DecPrivateMode

    term = Terminal()
    with term.cbreak(), term.dec_modes_enabled(
            DecPrivateMode.MOUSE_REPORT_CLICK,
            DecPrivateMode.MOUSE_EXTENDED_SGR, timeout=0.1):

        if not term.get_dec_mode(DecPrivateMode.MOUSE_EXTENDED_SGR).is_supported():
            print("SGR Mouse mode not supported! This example won't work :(")
        
        event = term.inkey()
        
        if event.mode == DecPrivateMode.MOUSE_EXTENDED_SGR:
            print("This is a mouse event!")
            mouse = event.mode_values()
        elif event.is_sequence:
            print(f"This is a keyboard event: {event.name}")
        else:
            print(f"This is a character: {event}")

A more advanced demonstration program at :ref:`keymatrix.py` detects and offers
toggles for mouse modes using function keys F4 - F8 and displays the raw events.

Mouse Tracking Modes
---------------------

Blessed supports several mouse tracking modes that can be enabled together in
combination.  The most common primary mode is
:attr:`DecPrivateMode.MOUSE_EXTENDED_SGR` (Mode 1006), which is the most modern
"mouse mode" used, combined with any of the following:

- :attr:`DecPrivateMode.MOUSE_REPORT_CLICK` (1000) - Report button clicks only.
- :attr:`DecPrivateMode.MOUSE_REPORT_DRAG` (1002) - Extends 1000; also reports
  motion while a button is held down (drag events).
- :attr:`DecPrivateMode.MOUSE_ALL_MOTION` (1003) - Report all mouse movement.
- :attr:`DecPrivateMode.MOUSE_SGR_PIXELS` (1016) - Report coordinates in pixels
  rather than character cells.

MOUSE_REPORT_CLICK
~~~~~~~~~~~~~~~~~~

Reports only button press and release events:

.. code-block:: python

    from blessed import Terminal, DecPrivateMode

    term = Terminal()
    with term.cbreak(), term.dec_modes_enabled(
            DecPrivateMode.MOUSE_REPORT_CLICK,
            DecPrivateMode.MOUSE_EXTENDED_SGR):
        
        print("Click anywhere (or press 'q' to quit):")
        while True:
            event = term.inkey()
            
            if event == 'q':
                break
            
            if event.mode == DecPrivateMode.MOUSE_EXTENDED_SGR:
                mouse = event.mode_values()
                if not mouse.is_release:
                    print(f"Clicked at ({mouse.y}, {mouse.x}) with button {mouse.button}")

MOUSE_ALL_MOTION
~~~~~~~~~~~~~~~~

Reports mouse movement even without buttons pressed. This is great for hover
effects but generates many events:

Let's build a simple drawing program where you can paint by moving the mouse
with a button held down, and erase by using middle or right buttons:

.. code-block:: python

.. literalinclude:: bin/mouse_paint.py

   :language: python
   :linenos: 1-

This example demonstrates:

* Using :meth:`~.Terminal.fullscreen` and :meth:`~.Terminal.hidden_cursor` for a "clean canvas"
* Enables both :attr:`DecPrivateMode.MOUSE_ALL_MOTION` and :attr:`DecPrivateMode.MOUSE_EXTENDED_SGR`
* Evaluate :class:`~.MouseEvent` object ``mouse`` returned by :meth:`~.Keystroke.mode_values` to
  determine mouse state to determine cursor tracking, draw, or erase mode.

MOUSE_SGR_PIXELS
~~~~~~~~~~~~~~~~

Most mouse tracking uses **character cell coordinates** - each position is a
single character cell in the terminal grid. This is perfect for most terminal
applications.

For higher-precision needs, especially when combined with Sixel_, some terminals
support :attr:`DecPrivateMode.MOUSE_SGR_PIXELS` (1016), which reports mouse
position in pixels instead of cells.

.. _Sixel: https://en.wikipedia.org/wiki/Sixel

The :class:`~.MouseSGREvent` structure is identical for both cell and pixel
modes - only the meaning of the ``x`` and ``y`` values changes.

Mouse support in blessed makes it easy to create interactive terminal applications:

* Use :meth:`~.Terminal.inkey` to receive both keyboard and mouse events
* Enable mouse modes with :meth:`~.Terminal.dec_modes_enabled`
* Always use :attr:`DecPrivateMode.MOUSE_EXTENDED_SGR` for reliable mouse tracking
* Combine it with :attr:`DecPrivateMode.MOUSE_REPORT_CLICK` or :attr:`DecPrivateMode.MOUSE_ALL_MOTION`
* Use ``timeout=0`` or small timeouts with :meth:`~.Terminal.inkey` for smooth mouse tracking
* Test for support with :meth:`~.Terminal.get_dec_mode` if your app needs to work on all terminals

With these tools, you can build sophisticated terminal UIs with mouse-driven menus, drawing programs, interactive visualizations, and more!

