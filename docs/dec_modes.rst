DEC Private Modes
=================

DEC Private Modes are terminal control sequences that enable or disable specific
terminal behaviors. The blessed library provides a clean API for:

- Query using the :meth:`~blessed.Terminal.get_dec_mode` ("DECRQM") method.
- Enable using the :meth:`~blessed.Terminal.dec_modes_enabled` ("DECSET")
  context manager.
- Disable using the :meth:`~blessed.Terminal.dec_modes_disabled` ("DECRST")
  context manager.

Each mode is identified by a numeric value, and can be found as a static
attribute of :class:`~blessed.dec_modes.DecPrivateMode`. Our list of modes
was derived from https://wiki.tau.garden/dec-modes/

Using get_dec_mode (DECRQM)
---------------------------

DEC Private Modes control various terminal features like cursor visibility,
mouse tracking, alternate screen buffers, and modern features like synchronized
output. For example we can test support for mode 1000, "Basic mouse click
reporting", :attr:`~blessed.dec_mode.DecPrivateMode.MOUSE_REPORT_CLICK` like so:

.. code-block:: python

    from blessed import Terminal
    from blessed.dec_modes import DecPrivateMode
    
    term = Terminal()
    
    response = term.get_dec_mode(DecPrivateMode.MOUSE_REPORT_CLICK, timeout=1.0)
    print("Status of basic mouse click reporting: ", end='')
    if response.is_supported():
        print('supported, currently ',end='')
        if response.is_enabled():
            print("enabled ", end='')
        else:
            print("disabled ", end='')
        if response.is_permanent():
            print('permanently (cannot be changed)')
        else:
            print('temporarily (can be changed)')
    elif response.is_failed():
        print("this terminal is not DEC Private Mode capable!")
    else:
        print("Not supported.")

This may produce output::

    Status of MOUSE_REPORT_CLICK(1000) is RESET(2): supported, currently disabled temporarily (can be changed)

The :class:`~blessed.dec_modes.DecModeResponse` object provides several helper methods:

- :meth:`~blessed.dec_modes.DecModeResponse.is_supported`: Mode is recognized by terminal
- :meth:`~blessed.dec_modes.DecModeResponse.is_enabled`: Mode is currently active
- :meth:`~blessed.dec_modes.DecModeResponse.is_disabled`: Mode is currently inactive
- :meth:`~blessed.dec_modes.DecModeResponse.is_permanent`: Mode setting cannot be changed
- :meth:`~blessed.dec_modes.DecModeResponse.is_failed`: Query failed or timed out

Context Managers
~~~~~~~~~~~~~~~~

The recommended way to temporarily enable or disable modes is through the
context managers :meth:`~blessed.Terminal.dec_modes_enabled` ("DECSET") and
:meth:`~blessed.Terminal.dec_modes_disabled` ("DECRST").

.. code-block:: python

    # Use synchronized output to reduce "tearing" (warning! This will blink the
    # screen extremely rapidly, be careful!)
    for _ in range(1000):
        with term.dec_modes_enabled(DecPrivateMode.SYNCHRONIZED_OUTPUT):
            print(term.home + "O" * term.height * term.width)
        with term.dec_modes_enabled(DecPrivateMode.SYNCHRONIZED_OUTPUT):
            print(term.home + " " * term.height * term.width)
    # Mode automatically restored to previous state

    # Temporarily disable cursor
    with term.dec_modes_disabled(DecPrivateMode.DECTCEM):
        # Cursor is hidden
        print("Working...")
        time.sleep(2)
    # Cursor visibility restored

    # Enable multiple modes at once
    with term.dec_modes_enabled(
        DecPrivateMode.MOUSE_REPORT_CLICK,
        DecPrivateMode.BRACKETED_PASTE,
        timeout=0.5
    ):
        # Both mouse tracking and bracketed paste enabled
        handle_interactive_input()

Timeouts and Caching
~~~~~~~~~~~~~~~~~~~~~

DEC Private Mode queries involve terminal communication and *may* timeout:

.. code-block:: python

    # Set a timeout to avoid hanging
    response = term.get_dec_mode(DecPrivateMode.DECTCEM, timeout=1.0)
    
    if response.is_failed():
        print("Query timed out or failed")

Query results are cached automatically. Use ``force=True`` to bypass the cache:

.. code-block:: python

    # Force a fresh query
    response = term.get_dec_mode(DecPrivateMode.DECTCEM, force=True)

Receiving DEC Events
~~~~~~~~~~~~~~~~~~~~

When DEC Private Modes are enabled, the terminal sends special event sequences that can be received 
through :meth:`~blessed.Terminal.inkey`. These events have an :attr:`~blessed.keyboard.Keystroke.event_mode` 
property and provide structured data through :meth:`~blessed.keyboard.Keystroke.mode_values`.

Bracketed Paste Events
^^^^^^^^^^^^^^^^^^^^^^

When bracketed paste mode is enabled, pasted content is automatically detected:

.. code-block:: python

    from blessed import Terminal
    from blessed.dec_modes import DecPrivateMode
    from blessed.keyboard import BracketedPasteEvent
    
    term = Terminal()
    
    with term.dec_modes_enabled(DecPrivateMode.BRACKETED_PASTE):
        print("Paste some text...")
        ks = term.inkey()
        
        if ks.event_mode == DecPrivateMode.BRACKETED_PASTE:
            event = ks.mode_values()
            print(f"Pasted: {repr(event.text)}")
        else:
            print(f"Regular key: {ks}")

Mouse Events
^^^^^^^^^^^^

Mouse tracking modes send detailed mouse event information:

.. code-block:: python

    from blessed import Terminal
    from blessed.dec_modes import DecPrivateMode
    from blessed.keyboard import MouseSGREvent
    
    term = Terminal()
    
    with term.dec_modes_enabled(DecPrivateMode.MOUSE_EXTENDED_SGR):
        print("Click, drag, or scroll...")
        while True:
            ks = term.inkey()
            
            if ks.event_mode == DecPrivateMode.MOUSE_EXTENDED_SGR:
                event = ks.mode_values()
                action = "release" if event.is_release else "press" 
                print(f"Mouse {action}: button={event.button} at ({event.x}, {event.y})")
                
                if event.shift:
                    print("  + Shift modifier")
                if event.is_wheel:
                    direction = "up" if event.button == 64 else "down"
                    print(f"  Wheel {direction}")
            elif ks == 'q':
                break

Focus Events  
^^^^^^^^^^^^

Focus tracking reports when the terminal window gains or loses focus:

.. code-block:: python

    from blessed import Terminal
    from blessed.dec_modes import DecPrivateMode
    from blessed.keyboard import FocusEvent
    
    term = Terminal()
    
    with term.dec_modes_enabled(DecPrivateMode.FOCUS_IN_OUT_EVENTS):
        print("Switch focus to/from terminal window...")
        while True:
            ks = term.inkey()
            
            if ks.event_mode == DecPrivateMode.FOCUS_IN_OUT_EVENTS:
                event = ks.mode_values()
                status = "gained" if event.gained else "lost"
                print(f"Focus {status}")
            elif ks == 'q':
                break
