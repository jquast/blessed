Measuring
=========

Any string containing sequences can be measured by blessed using the :meth:`~.Terminal.length`
method. This means that blessed can measure, right-align, center, truncate, or word-wrap its
own output!

The :attr:`~.Terminal.height` and :attr:`~.Terminal.width` properties always provide a current
readout of the size of the window:

    >>> term.height, term.width
    (34, 102)

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

To detect when the size of the window changes, you can author a callback for SIGWINCH_ signals:

.. code-block:: python

    import signal
    from blessed import Terminal

    term = Terminal()

    def on_resize(sig, action):
        print(f'height={term.height}, width={term.width}')

    signal.signal(signal.SIGWINCH, on_resize)

    # wait for keypress
    term.inkey()

.. image:: https://dxtz6bzwq9sxx.cloudfront.net/demo_resize_window.gif
    :alt: A visual animated example of the on_resize() function callback

.. note:: This is not compatible with Windows! We hope to make a cross-platform API for this in the
          future https://github.com/jquast/blessed/issues/131.

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
