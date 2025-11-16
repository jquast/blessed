Location
========

If you just want to move the location of the cursor before writing text, and aren't worried about
returning, do something like this:

    >>> print(term.home + term.clear, end='')
    >>> print(term.move_down(2) + term.move_right(20) + term.bright_red('fire!'), end='')
    >>> print(term.move_xy(20, 7) + term.bold('Direct hit!'), end='')
    >>> print(term.move_y(term.height - 3), end='')

Note our use of ``end=''`` to the built-in :func:`print` function, this is
because the default ``end='\n'`` value causes the cursor to move to the first
column of the next row.

There are four direct movement capabilities:

``move_xy(x, y)``
  Position cursor at given **x**, **y**.
``move_x(x)``
  Position cursor at column **x**.
``move_y(y)``
  Position cursor at row **y**.
``home``
  Position cursor at (0, 0).

And four relative capabilities:

``move_up`` or ``move_up(y)``
  Position cursor 1 or **y** row cells above the current position.
``move_down(y)``
  Position cursor 1 or **y** row cells below the current position.

  .. note:: ``move_down`` or is often valued as *\\n*, which additionally returns the carriage to
     column 0, and, depending on your terminal emulator, may also destroy any characters to end of
     line.

    ``move_down(1)`` is always a safe non-destructive one-notch movement in the downward direction.

``move_left`` or ``move_left(x)``
  Position cursor 1 or **x** column cells left of the current position.
``move_right`` or ``move_right(x)``
  Position cursor 1 or **x** column cells right of the current position.


Example
-------

The source code of :ref:`bounce.py` combines a small bit of :doc:`keyboard` input with many of the
Terminal location capabilities, ``home``, ``width``, ``height``, and ``move_xy`` are used to create
a classic game of tennis:

.. literalinclude:: ../bin/bounce.py
   :language: python
   :lines: 3-
   :emphasize-lines: 17,22,25,27,34

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/demo_basic_bounce.gif
   :alt: Animated screenshot of :ref:`bounce.py`

Context Manager
---------------

A :func:`contextlib.contextmanager`, :meth:`~.Terminal.location` is provided to move the cursor to
an *(x, y)* screen position and *restore the previous position* on exit:

.. code-block:: python

    with term.location(0, term.height - 1):
        print('Here is the bottom.')

    print('This is back where I came from.')

All parameters to :meth:`~.Terminal.location` are **optional**, we can use
it without any arguments at all to restore the cursor location:

.. code-block:: python

    with term.location():
        print(term.move_xy(1, 1) + 'Hi Mom!' + term.clear_eol)

.. note:: calls to :meth:`~.Terminal.location` may not be nested.

Finding The Cursor
------------------

We can determine the cursor's current position at anytime using
:meth:`~.get_location`. The default ``timeout`` value of 1 second will return
coordinates ``(-1, -1)`` if no response was received in time.

This uses a kind of "answer back" sequence that *all* terminal emulators
automatically respond to.

    >>> term.get_location()
    (32, 0)

The return value of :meth:`~.Terminal.get_location` mirrors the arguments of
:meth:`~Terminal.location`:

.. code-block:: python

    with term.location(12, 12):
         val = term.get_location()
    print(val)

Produces output, ``(12, 12)``

Although this wouldn't be suggested in most applications because of its latency, it certainly
simplifies many applications, and, can also be timed, to make a determination of the round-trip
time, perhaps even the bandwidth constraints, of a remote terminal!
