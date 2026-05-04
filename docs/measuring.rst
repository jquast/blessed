Sizing & Alignment
==================

The :attr:`~.Terminal.height` and :attr:`~.Terminal.width` properties always provide a current
readout of the size of the window in character cells:

.. code-block:: python

    from blessed import Terminal
    term = Terminal()

    >>> term.height, term.width
    (34, 102)

The :attr:`~.Terminal.pixel_height` and :attr:`~.Terminal.pixel_width` properties provide the
window size in pixels when available:

.. code-block:: python

    from blessed import Terminal
    term = Terminal()

    >>> term.pixel_height, term.pixel_width
    (1080, 1920)

.. note::

   For sixel graphics, use :meth:`~.Terminal.get_sixel_height_and_width` instead,
   which returns the actual drawable area by accounting for margins. See
   :doc:`sixel` for details.

Length
------

Any string **containing sequences** can be measured using :meth:`~.Terminal.length`.

This means that blessed can measure, right-align, center, truncate, or word-wrap its own output!
Text containing colors and styling, hyperlinks, or text sizing protocol are measured for their
visual width:

.. code-block:: python

    from blessed import Terminal
    term = Terminal()

    >>> print(term.length(term.bold_blue('123')))
    3
    >>> print(term.length('abc\b\b\bxyz'))
    3
    >>> print(term.length(term.text_sized('BIG', scale=3)))
    9
    >>> print(term.length(term.link('http://example.com', 'link')))
    4
    >> phrase = (
        "\u26F9"        # PERSON WITH BALL
        "\U0001F3FB"    # EMOJI MODIFIER FITZPATRICK TYPE-1-2
        "\u200D"        # ZERO WIDTH JOINER
        "\u2640"        # FEMALE SIGN
        "\uFE0F")       # VARIATION SELECTOR-16
    >> print(term.length(phrase))
    2

The length measurements of blessed very accurately matches most popular terminals, but not all. The
python `wcwidth`_ library provides support of complex emojis, CJK, flags, and complex languages, and
support for unicode may vary by terminal, as discovered by `the results
<https://ucs-detect.readthedocs.io/results.html>`_ of the `ucs-detect`_ CLI.

:meth:`~.Terminal.length` makes a best effort without returning error, even when the cursor position
is ambiguous, such as text containing ``term.move_x(0)``, or containing vertical movement like
``'\n'`` or ``term.move_up(99)``, the text is assumed for display on the first column and vertical
sequences are ignored. Carriage return, ``'\r'`` is treated like ``term.move_x(0)``:

.. code-block:: python

    from blessed import Terminal
    term = Terminal()

    >>> print(term.length('abc' + term.move_x(0) + 'xyz'))
    3
    >>> print(term.length('abc' + term.move_up(99) + 'xyz'))
    6
    >>> print(term.length('abc' + '\r' + 'xyz'))
    3
    >>> print(term.length('abc' + '\n' + 'xyz'))
    6

Alignment
---------

By combining the measure of the printable width of strings containing sequences with the terminal
width, the :meth:`~.Terminal.center`, :meth:`~.Terminal.ljust`, :meth:`~.Terminal.rjust`,
:meth:`~Terminal.truncate`, and :meth:`~Terminal.wrap` methods "just work" for strings that
contain sequences.

.. code-block:: python

    from blessed import Terminal
    term = Terminal()

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

Text Sizing
-----------

The :meth:`~.Terminal.text_sized` method wraps text in an ``OSC 66`` escape sequence for
terminals that support the `kitty text sizing protocol`_. This enables per-character control
over cell footprint, fractional font scaling, and alignment:

.. code-block:: python

    from blessed import Terminal
    term = Terminal()

    # 'scale' is great for printing large headings
    _scale = 3
    heading = term.text_sized('Big text', scale=_scale)
    print(heading + ('\n' * (_scale)) + '=' * term.length(heading))

    # fractional scaling is great for superscript and subscript
    print('2' + term.text_sized('128', width=1, numerator=1, denominator=3))

    # text sizing sequences can bookended or wrapped by any other sequence,
    footnote_txt = term.text_sized('[2]', width=2, numerator=2, denominator=3, vertical_align='top')
    footnote_hlink = term.link('https://sw.kovidgoyal.net/kitty/text-sizing-protocol/', footnote_txt)
    print('Text sizing protocol' + footnote_hlink)

    # and it may also be aligned
    print(term.center(term.reverse_yellow(term.text_sized('Big Yellow', scale=2, vertical_align='bottom'))))

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/blessed_text_sizing_repl_output.png

.. note:: Because the first call to :meth:`Terminal.text_sized` will cause the side effect
    of writing destructive spaces to the columns and row following the current cursor
    position as required for detection of `kitty text sizing protocol`_, it is suggested
    to first call :meth:`Terminal.does_text_sizing` during program initialization.

.. seealso::

   :ref:`text_sizing_protocol.py` and :ref:`scroller.py` demonstration programs.

.. _kitty text sizing protocol: https://sw.kovidgoyal.net/kitty/text-sizing-protocol/

Detecting Resize
----------------

The terminal can notify your application when the window size changes. Blessed provides a modern
cross-platform method using in-band resize notifications, with SIGWINCH_ as a fallback for older
terminals. On Windows, native console ``WINDOW_BUFFER_SIZE_EVENT`` records are automatically
converted to in-band resize sequences.

Using SIGWINCH
--------------

For terminals that don't support in-band resize notifications (DEC mode 2048), you can use
SIGWINCH_ signals on Unix systems.

.. code-block:: python

    import signal
    import threading
    from blessed import Terminal

    term = Terminal()
    _resize_pending = threading.Event()

    def on_resize(*args):
        _resize_pending.set()

    signal.signal(signal.SIGWINCH, on_resize)

    with term.cbreak():
        while True:
            if _resize_pending.is_set():
                _resize_pending.clear()
                print(f'New size: {term.height}x{term.width}')

            inp = term.inkey(timeout=0.1)
            if inp == 'q':
                break

.. image:: https://dxtz6bzwq9sxx.cloudfront.net/demo_resize_window.gif
    :alt: A visual animated example of the on_resize() function callback

.. warning:: SIGWINCH has limitations:

    - Not available on Windows
    - Signal handlers should avoid blocking operations
    - Race conditions can occur between signal delivery and terminal state
    - Requires careful synchronization with application state

Using notify_on_resize
----------------------

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
    terminal emulators on Unix. Most terminals do not support this feature yet. Always check with
    :meth:`~.Terminal.does_inband_resize` and provide a fallback using SIGWINCH on Unix systems.

    On Windows, :meth:`~.Terminal.does_inband_resize` always returns ``True`` because the
    native console API provides ``WINDOW_BUFFER_SIZE_EVENT`` on all versions -- no DEC mode
    support is required.

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

Using both
----------

The following example demonstrates checking for support, using in-band resize notifications when
available, and **falling back to SIGWINCH on Unix systems**:

.. literalinclude:: ../bin/on_resize.py
   :language: python

Make note of these designs:

1. **Signal handlers only set a flag**: The ``on_resize()`` signal handler only calls
   ``_resize_pending.set()`` and does nothing else. Signal handlers should never
   perform I/O operations, terminal queries, or other complex work, because
   these callbacks can occur *at any time* in your code, even part-way through
   drawing, for example.

2. **Main loop processes events**: The main event loop checks ``_resize_pending``
   periodically using ``inkey(timeout=0.1)``. This 100ms delay naturally debounces
   rapid resize events from both signals and in-band notifications, displaying only
   one size update regardless of how many events arrive within that window.

Note the use of ``force=True`` when calling :meth:`~.Terminal.get_sixel_height_and_width`, the
return value is cached, so ``force=True`` ensures updated dimensions are retrieved after a resize
event. See :doc:`sixel` for more on caching behavior.

.. _SIGWINCH: https://en.wikipedia.org/wiki/SIGWINCH
