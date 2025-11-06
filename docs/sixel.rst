Sixel Graphics
==============

Blessed provides support for querying sixel graphics capabilities in modern
terminal emulators.  Sixel is a bitmap graphics format that allows applications
to display inline images directly in the terminal.

Checking Sixel Support
----------------------

Before using sixel graphics, check if your terminal supports them using
:meth:`~Terminal.does_sixel`:

.. code-block:: python

    term = Terminal()

    if term.does_sixel():
        # Terminal supports sixel graphics
        display_sixel_image()
    else:
        # Fall back to text
        display_text_fallback()

Window Dimensions
-----------------

Get the maximum pixel dimensions available for sixel graphics using
:meth:`~.Terminal.get_sixel_height_and_width`:

.. code-block:: python

    term = Terminal()

    height, width = term.get_sixel_height_and_width()
    if (height, width) != (-1, -1):
        print(f"Sixel dimensions: {width}x{height} pixels")
        # Scale your sixel graphics to fit within these dimensions
    else:
        print("Could not determine sixel dimensions")

The returned dimensions represent the maximum height and width in pixels for
sixel graphics rendering. If the query times out or fails, ``(-1, -1)`` is
returned.

.. note::

   The sixel area dimensions may differ from window pixel dimensions reported
   by :attr:`~.Terminal.pixel_height` and :attr:`~.Terminal.pixel_width`.

   Window pixel dimensions from :attr:`~.Terminal.pixel_height` and
   :attr:`~.Terminal.pixel_width` may include margins and window decorations,
   reporting values too large to contain an image.

Cell Dimensions
---------------

Get the pixel dimensions of a single character cell using
:meth:`~Terminal.get_cell_pixel_height_and_width`:

.. code-block:: python

    term = Terminal()

    cell_height, cell_width = term.get_cell_pixel_height_and_width(timeout=1.0)
    if (cell_height, cell_width) != (-1, -1):
        print(f"Character cell size: {cell_width}x{cell_height} pixels")
        # Useful for pixel-perfect positioning of graphics
    else:
        print("Could not determine cell dimensions")

.. note:: Although not necessarily a sixel feature, this information is crucial
   for precise positioning and sizing of graphics relative to text. However,
   many modern terminals may not report these values accurately.

Colors
------

Determine how many colors are available for sixel graphics using
:meth:`~Terminal.get_sixel_colors`:

.. code-block:: python

    term = Terminal()

    colors = term.get_sixel_colors()
    if colors != -1:
        print(f"Sixel color registers: {colors}")
        # Use this to optimize your sixel color palette
    else:
        print("Could not determine sixel color support")

Returns the number of color registers available, defaults to ``256`` for
terminals that support sixel but fail to respond to ``XTSMGRAPHICS`` query.

Returns ``-1`` when sixel is not supported.

Caching
-------

Query results are always cached, successful or not. If any call fails to return
under timeout and returns ``-1`` values, all subsequent calls return that same
value until ``force=True`` is set.

Successful queries are *also* cached and always returned without direct re-inquiry
unless ``force=True``.

Any method used to determine window size changes can be used to "force" a new
lookup and bypassing the cache:

.. code-block:: python

    term = Terminal()

    # First call queries the terminal
    height1, width1 = term.get_sixel_height_and_width(timeout=1.0)

    # Second call returns cached result (instant)
    # and always returns same result
    height2, width2 = term.get_sixel_height_and_width()
    assert width2, height2 == width1, height2

    # Force a fresh inquiry,
    height, width = term.get_sixel_height_and_width(timeout=1.0, force=True)


Complete Workflow
-----------------

Here is a complete example of checking for Sixel support, Window, and Cell dimensions:

.. literalinclude:: ../bin/sixel_query.py
