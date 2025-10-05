Mouse Input
===========

Blessed supports mouse input in the terminal! Your terminal apps can respond to
clicks, drags, or track live mouse movement, think of the exciting possibilities
for creating interactive games and apps.

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
            DecPrivateMode.MOUSE_EXTENDED_SGR, timeout=1):
        
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

A brief overview:

* Use :meth:`~.Terminal.inkey` to receive both keyboard and mouse events
* Enable mouse modes with :meth:`~.Terminal.dec_modes_enabled`.
* Always use :attr:`DecPrivateMode.MOUSE_EXTENDED_SGR` for reliable mouse tracking
* Combine with :attr:`DecPrivateMode.MOUSE_REPORT_CLICK` for only clicks, or,
  :attr:`DecPrivateMode.MOUSE_ALL_MOTION` for all motion.
* Test for support with :meth:`~.Terminal.get_dec_mode`
* Always use an appropriate timeout value for :meth:`~.Terminal.get_dec_mode`
  and :meth:`~.Terminal.dec_modes_enabled` for unsupported terminals.

Testing for Mouse Support
--------------------------

Not all terminals support mouse modes. You can test for DEC Private Mode,
:attr:`~.DecPrivateMode.MOUSE_EXTENDED_SGR`:

.. code-block:: python

   from blessed import Terminal, DecPrivateMode

   term = Terminal()
   
   # Query mouse support with a 1 second timeout
   mode_test = DecPrivateMode.MOUSE_EXTENDED_SGR
   response = term.get_dec_mode(mode_test, timeout=1)
   
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

Note that a ``timeout`` value is used to account for some terminals that may
never respond, those terminals will return True for method ``is_failed()``.

Mouse Tracking Modes
---------------------

Blessed supports several mouse tracking modes that can be enabled together in
combination.  The most common primary mode is
:attr:`DecPrivateMode.MOUSE_EXTENDED_SGR` (Mode 1006), combined with any of the
following:

- :attr:`DecPrivateMode.MOUSE_REPORT_CLICK` (1000) - Sends Mouse X & Y
  coordinates and button value when clicked
- :attr:`DecPrivateMode.MOUSE_REPORT_DRAG` (1002) - Extends 1000; also reports
  motion while a button is held down (drag events).
- :attr:`DecPrivateMode.MOUSE_ALL_MOTION` (1003) - Report all mouse movement.
- :attr:`DecPrivateMode.MOUSE_SGR_PIXELS` (1016) - Report coordinates in pixels
  rather than character cells.

A demonstration program, :ref:`keymatrix.py` offers a UI to see raw mouse events
for each mode. Use the function keys in this program to enable these modes and
see their effects.

Understanding Mouse Events
--------------------------

Mouse events come through :meth:`~.Terminal.inkey` just like keyboard events.

A :meth:`~.Keystroke` object is identified as a mouse event by matching
a :attr:`~.Keystroke.mode` value matching it with one of the `Mouse Tracking
Modes`_ that enabled it.

A call to :meth:`~.Keystroke.mode_values` returns a :class:`~.MouseEvent`
instance with details of the mouse event.

The :class:`~.MouseEvent` fields are:

- ``button``: Which button (0=left, 1=middle, 2=right, or 64-65 for wheel events)
- ``x``, ``y``: Mouse position in terminal cells (0-indexed), or pixels when using SGR-Pixels mode
- ``is_release``: Whether this is a button release event
- ``is_motion``: Whether motion is being reported (True whenever the mouse moves)
- ``is_wheel``: Whether this is a scroll wheel event
- ``shift``, ``ctrl``, ``meta``: Whether modifier keys are pressed

.. code-block:: python

    from blessed import Terminal, DecPrivateMode

    term = Terminal()
    with term.cbreak(), term.dec_modes_enabled(
            DecPrivateMode.MOUSE_REPORT_CLICK,
            DecPrivateMode.MOUSE_EXTENDED_SGR, timeout=1):

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

MOUSE_REPORT_CLICK
~~~~~~~~~~~~~~~~~~

Reports only button press and release events:

This example shows the details of a Mouse Event after enabling
:attr:`DecPrivateMode.MOUSE_REPORT_CLICK` and
:attr:`DecPrivateMode.MOUSE_SGR_PIXELS` together:

.. code-block:: python

    from blessed import Terminal, DecPrivateMode

    term = Terminal()
    with term.cbreak(), term.dec_modes_enabled(
            DecPrivateMode.MOUSE_REPORT_CLICK,
            DecPrivateMode.MOUSE_EXTENDED_SGR, timeout=1):
        
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

* Using :meth:`~.Terminal.fullscreen` and :meth:`~.Terminal.hidden_cursor`
  for an empty canvas to paint on
* Enables both :attr:`DecPrivateMode.MOUSE_ALL_MOTION` and
  :attr:`DecPrivateMode.MOUSE_EXTENDED_SGR`
* Evaluates :class:`~.MouseEvent` object ``mouse`` returned by
  :meth:`~.Keystroke.mode_values` to determine mouse state

.. note:: When enabling any mouse mode it is important to check for and process
   all input events quickly using :class:`~.Keystroke.inkey:`, Just a few
   seconds of unprocessed mouse events with
   :attr:`DecPrivateMode.MOUSE_ALL_MOTION` can rapidly fill your input buffer
   and bog down your programs if input is not quickly processed!

MOUSE_SGR_PIXELS
~~~~~~~~~~~~~~~~

Most mouse tracking uses **character cell coordinates** - each position is a
single character cell in the terminal grid. This is perfect for most terminal
applications.

For higher-precision needs, especially when combined with Sixel_, some terminals
support :attr:`DecPrivateMode.MOUSE_SGR_PIXELS` (1016), which reports mouse
position in pixels instead of cells.

The :class:`~.MouseSGREvent` structure is identical for both cell and pixel
modes - only the meaning of the ``x`` and ``y`` values changes.

.. _Sixel: https://en.wikipedia.org/wiki/Sixel
