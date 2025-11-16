Measuring
=========

Any string containing sequences can be measured by blessed using the :meth:`~.Terminal.length`
method. This means that blessed can measure, right-align, center, truncate, or word-wrap its
own output!

The :attr:`~.Terminal.height` and :attr:`~.Terminal.width` properties always provide a current
readout of the size of the window in character cells:

    >>> term.height, term.width
    (34, 102)

The :attr:`~.Terminal.pixel_height` and :attr:`~.Terminal.pixel_width` properties provide the
window size in pixels when available:

    >>> term.pixel_height, term.pixel_width
    (1080, 1920)

.. note::

   For sixel graphics, use :meth:`~.Terminal.get_sixel_height_and_width` instead,
   which returns the actual drawable area by accounting for margins. See
   :doc:`sixel` for details.

By combining the measure of the printable width of strings containing sequences with the terminal
width, the :meth:`~.Terminal.center`, :meth:`~.Terminal.ljust`, :meth:`~.Terminal.rjust`,
:meth:`~Terminal.truncate`, and :meth:`~Terminal.wrap` methods "just work" for strings that
contain sequences.

.. code-block:: python

    with term.location(y=term.height // 2):
        print(term.center(term.bold('press return to begin!')))
        term.inkey()

In the following example, :meth:`~Terminal.wrap` word-wraps a short poem containing sequences:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()

    poem = (term.bold_cyan('Plan difficult tasks'),
            term.cyan('through the simplest tasks'),
            term.bold_cyan('Achieve large tasks'),
            term.cyan('through the smallest tasks'))

    for line in poem:
        print('\n'.join(term.wrap(line, width=25, subsequent_indent=' ' * 4)))

Resizing
--------

The terminal can notify your application when the window size changes. Blessed provides a modern
cross-platform method using in-band resize notifications, with SIGWINCH_ as a fallback for older
terminals.

Checking for support
~~~~~~~~~~~~~~~~~~~~

Use :meth:`~.Terminal.does_inband_resize` to check if the terminal supports in-band resize
notifications (DEC mode 2048):

.. code-block:: python

    from blessed import Terminal

    term = Terminal()

    if term.does_inband_resize():
        print('In-band resize notifications are supported!')
    else:
        print('Falling back to SIGWINCH or polling')

.. note::

    In-band resize notification support (DEC mode 2048) is currently **very limited** among
    terminal emulators. Most terminals do not support this feature yet. Always check with
    :meth:`~.Terminal.does_inband_resize` and provide a fallback using SIGWINCH on Unix systems
    (see example below)

Using :meth:`~.Terminal.notify_on_resize` (recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :meth:`~.Terminal.notify_on_resize` context manager enables automatic resize event reporting.
When the window is resized, :meth:`~.Terminal.inkey` will return a keystroke with
:attr:`~.Keystroke.name` equal to ``'RESIZE_EVENT'``. The new dimensions are immediately available
through :attr:`~.Terminal.height`, :attr:`~.Terminal.width`, :attr:`~.Terminal.pixel_height`, and
:attr:`~.Terminal.pixel_width`.

This method is preferred because it:

- Works cross-platform (Linux, Mac, BSD, Windows)
- Avoids race conditions inherent in signal handlers
- Delivers resize events in-band with other input
- Automatically caches dimensions for fast access

Combined with signals
~~~~~~~~~~~~~~~~~~~~~

The following example demonstrates checking for support, using in-band resize notifications when
available, but **falling back to SIGWINCH on Unix systems**:

.. literalinclude:: ../bin/on_resize.py
   :language: python

Make note of these designs:

1. **Signal handlers only set a flag**: The ``on_resize()`` signal handler only calls
   ``_resize_pending.set()`` and does nothing else. Signal handlers should never
   perform I/O operations, terminal queries, or other complex work, because
   these callbacks can occur *at any time* in your code, even part-way through
   drawing, for example.

2. **Main loop processes events**: The main event loop checks if
   ``_resize_pending.is_set()`` periodically, every 100ms by timed input delay,
   ``inkey(timeout=0.1)`` to aides with debouncing.

3. **Signal debouncing**: When signals are received, ``_resize_pending.set()``
   is set, and main loop displays only one size notification for any number
   of signals received within 100ms.

4. **Input debouncing**: When input is received through
   :meth:`~.Terminal.inkey` method as ``RESIZE_EVENT``` for terminals supporting
   :meth:`~Terminal.notify_on_resize`, a pending event is set but it is not
   immediately processed -- another 100ms delay is incurred, effectively
   de-bouncing rapidly received resize events, there.

This pattern avoids race conditions. Although Python's GIL may provide some
protection, signal handlers can still interrupt code at inconvenient times, and
doing complex work in handlers can lead to subtle bugs.

Note the use of ``force=True`` when calling :meth:`~.Terminal.get_sixel_height_and_width`, the
return value is cached, so ``force=True`` ensures updated dimensions are retrieved after a resize
event. See :doc:`sixel` for more on caching behavior.

SIGWINCH (fallback for older terminals)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For terminals that don't support in-band resize notifications (DEC mode 2048), you can use
SIGWINCH_ signals on Unix systems. See the example above for a complete implementation with
automatic fallback

.. image:: https://dxtz6bzwq9sxx.cloudfront.net/demo_resize_window.gif
    :alt: A visual animated example of the on_resize() function callback

.. warning:: SIGWINCH has limitations:

    - Not compatible with Windows
    - Signal handlers should avoid blocking operations
    - Race conditions can occur between signal delivery and terminal state
    - Requires careful synchronization with application state

    For new code, prefer :meth:`~.Terminal.notify_on_resize` instead.

Sometimes it is necessary to make sense of sequences, and to distinguish them
from plain text.  The :meth:`~.Terminal.split_seqs` method can allow us to
iterate over a terminal string by its characters or sequences:

    >>> term.split_seqs(term.bold('bbq'))
    ['\x1b[1m', 'b', 'b', 'q', '\x1b(B', '\x1b[m']

Will display something like, ``['\x1b[1m', 'b', 'b', 'q', '\x1b(B', '\x1b[m']``

Method :meth:`~.Terminal.strip_seqs` can remove all sequences from a string:

    >>> phrase = term.bold_black('coffee')
    >>> phrase
    '\x1b[1m\x1b[30mcoffee\x1b(B\x1b[m'
    >>> term.strip_seqs(phrase)
    'coffee'

.. _SIGWINCH: https://en.wikipedia.org/wiki/SIGWINCH
