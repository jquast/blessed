DEC Private Modes
=================

DEC Private Modes are terminal control sequences that enable or disable specific
terminal behaviors. The blessed library provides a clean API for:

- *Query* using the :meth:`~blessed.Terminal.get_dec_mode` ("DECRQM") method.
- *Enable* using the :meth:`~blessed.Terminal.dec_modes_enabled` ("DECSET")
  context manager.
- and *Disable* using the :meth:`~blessed.Terminal.dec_modes_disabled` ("DECRST")
  context manager.

Each mode is identified by a numeric value, and can be accessed as a class
attribute via :attr:`Terminal.DecPrivateMode <blessed.Terminal.DecPrivateMode>`.
Our list of modes was derived from https://wiki.tau.garden/dec-modes/

A simple example:

.. code-block:: python
   :emphasize-lines: 7,11,13,17,22

   from blessed import Terminal

   term = Terminal()

   # Temporarily disable cursor
   with term.dec_modes_disabled(term.DecPrivateMode.DECTCEM):
        # Cursor is hidden
        print("Working...")
        time.sleep(2)


Using get_dec_mode (DECRQM)
---------------------------

DEC Private Modes control various terminal features like cursor visibility,
mouse tracking, alternate screen buffers, and modern features like synchronized
output. For example we can test support for mode 1000, "Basic mouse click
reporting", :attr:`~blessed.dec_mode.DecPrivateMode.MOUSE_REPORT_CLICK` like so:

.. code-block:: python
   :emphasize-lines: 7,11,13,17,22

   from blessed import Terminal

   term = Terminal()

   # make query
   response = term.get_dec_mode(term.DecPrivateMode.MOUSE_REPORT_CLICK, timeout=1.0)

   # display response
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

"With" modes (DECSET, DECRST)
-----------------------------

The recommended way to temporarily enable or disable modes is through the
context managers :meth:`~blessed.Terminal.dec_modes_enabled` ("DECSET") and
:meth:`~blessed.Terminal.dec_modes_disabled` ("DECRST").

An unsupported mode may be requested, but you may wish to independently check
for its activation by the :meth:`~blessed.Terminal.get_dec_mode` ("DECRQM")
method.

Because a terminal may not respond (ever!), it is suggested to set an
appropriate timeout.

Timeouts and Caching
~~~~~~~~~~~~~~~~~~~~~

DEC Private Mode queries involve terminal communication and *may* timeout:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    mode = term.DecPrivateMode.DECTCEM
    resp = term.get_dec_mode(mode, timeout=1.0)

    if resp.is_failed():
        print("Query failed for mode", repr(mode))

    if resp.is_supported():
        print(mode, "is supported by your terminal!")

Query results are cached automatically. Use ``force=True`` to bypass the cache:

.. code-block:: python

    # Force a fresh query
    response = term.get_dec_mode(term.DecPrivateMode.DECTCEM, force=True)

Because queries are cached, it is possible to repeatedly change modes using the
context managers, and the timeout cost is only incurred on the first call, as
done in the next example.

Synchronized Output
~~~~~~~~~~~~~~~~~~~

For fast frame or video-like operations, such as in the :ref:`plasma.py` demo,
the modern DEC Private Mode 2026 :attr:`~.DecPrivateMode.SYNCHRONIZED_OUTPUT`
can be used to reduce a simple kind of "tearing", when the frame displayed to
the user is partially drawn to the screen.  Some people prefer to "clear" a
screen and draw over it, but, when done in rapid successes, causes a kind of
"blinking" effect when rendering to the screen.

When Synchronized Output is implemented by the terminal emulator, it allow us to
"paint" onto a hidden screen while entering this context, and to have it
switched and painted immediately as a single frame, without any cursor movement
or half-frames:

.. code-block:: python
   :emphasize-lines: 7,11,13,17,22

    from blessed import Terminal

    term = Terminal()
    # WARNING! This may rapidly blink your screen !!
    fillblocks = "█" * term.height * term.width
    emptyblocks = " " * term.height * term.width
    for _ in range(1000):
        with term.dec_modes_enabled(term.DecPrivateMode.SYNCHRONIZED_OUTPUT, timeout=1):
            print(term.home + emptyblocks, flush=True)
            print(term.home + fillblocks, flush=True)

If your terminal supports this mode, it will quickly be negotiated about and
re-enabled the first and every call to
:meth:`~blessed.Terminal.dec_modes_enabled`. A timeout parameter of ``1`` is
used, causing a 1 second delay on first loop.


   # Cursor visibility restored

    # Enable multiple modes at once
    with term.dec_modes_enabled(
        term.DecPrivateMode.MOUSE_REPORT_CLICK,
        term.DecPrivateMode.BRACKETED_PASTE,
        timeout=0.5
    ):
        # Both mouse tracking and bracketed paste enabled
        handle_interactive_input()


Receiving DEC Events
~~~~~~~~~~~~~~~~~~~~

When DEC Private Modes are enabled, the terminal sends special event sequences
that can be received through :meth:`~blessed.Terminal.inkey`. These events have
an :attr:`~blessed.keyboard.Keystroke.event_mode` property and provide
structured data through :meth:`~blessed.keyboard.Keystroke.mode_values`.

Bracketed Paste Events
^^^^^^^^^^^^^^^^^^^^^^

Pasted content that is sent using special "Bracketed Paste" sequence can be
received by a :class:`Keystroke` from the :meth:`~Terminal.inkey` method.

.. code-block:: python

    from blessed import Terminal
    from blessed.keyboard import BracketedPasteEvent

    term = Terminal()

    with term.dec_modes_enabled(term.DecPrivateMode.BRACKETED_PASTE):
        print("Paste some text...")
        ks = term.inkey()

        if ks.event_mode == term.DecPrivateMode.BRACKETED_PASTE:
            event = ks.mode_values()
            print(f"Pasted: {repr(event.text)}")
        else:
            print(f"Regular key: {ks}")

Mouse Events
^^^^^^^^^^^^

Mouse tracking modes send detailed mouse event information:

.. code-block:: python

    from blessed import Terminal
    from blessed.keyboard import MouseSGREvent

    term = Terminal()

    with term.dec_modes_enabled(term.DecPrivateMode.MOUSE_EXTENDED_SGR):
        print("Click, drag, or scroll...")
        while True:
            ks = term.inkey()

            if ks.event_mode == term.DecPrivateMode.MOUSE_EXTENDED_SGR:
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
    from blessed.keyboard import FocusEvent

    term = Terminal()

    with term.dec_modes_enabled(term.DecPrivateMode.FOCUS_IN_OUT_EVENTS):
        print("Switch focus to/from terminal window...")
        while True:
            ks = term.inkey()

            if ks.event_mode == term.DecPrivateMode.FOCUS_IN_OUT_EVENTS:
                event = ks.mode_values()
                status = "gained" if event.gained else "lost"
                print(f"Focus {status}")
            elif ks == 'q':
                break


Focus Events
------------

As a bonus, blessed also supports focus tracking! Enable
:attr:`DecPrivateMode.FOCUS_IN_OUT_EVENTS` to receive events when the terminal
window gains or loses focus:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()

    with term.cbreak(), term.dec_modes_enabled(term.DecPrivateMode.FOCUS_IN_OUT_EVENTS):
        print("Switch to another window and back...")

        while True:
            event = term.inkey()

            if event.mode == term.DecPrivateMode.FOCUS_IN_OUT_EVENTS:
                focus = event.mode_values()
                if focus.gained:
                    print("Window gained focus!")
                else:
                    print("Window lost focus!")
                break

This can be useful for pausing animations or updating status when the user
switches away from your application.

Summary
-------


