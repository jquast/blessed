.. _`mouse input`:

Mouse Input
===========

Blessed supports mouse input in the terminal! Your applications can respond to
clicks, drags, scroll wheel, or track live mouse cursor movement, even at the
pixel-level, for creating interactive games and apps.

Overview:

* Check for support using :meth:`~blessed.Terminal.does_mouse`
* Enable mouse input with :meth:`~blessed.Terminal.mouse_enabled`
* Receive events through :meth:`~blessed.Terminal.inkey`

Mouse events work seamlessly with keyboard events - both come through the same
:meth:`~blessed.Terminal.inkey` method.

Getting Started
---------------

Here is a basic example:

.. literalinclude:: ../bin/mouse_simple.py
   :language: python
   :linenos:

The :meth:`~.Terminal.mouse_enabled` context manager enables mouse tracking
and automatically disables it when done. Mouse events arrive through
:meth:`~.Terminal.inkey` just like keyboard events.

Mouse events can be detected by checking if :attr:`~.Keystroke.name` starts
with ``'MOUSE_'``. The name includes the button and any modifiers, such as
``'MOUSE_LEFT'``, ``'MOUSE_CTRL_LEFT'``, or ``'MOUSE_SCROLL_UP'``. You can
also use magic method predicates like ``inp.is_mouse_left()``.

.. note::

   Mouse coordinates are **0-indexed**, matching blessed's terminal movement
   functions like :meth:`~.Terminal.move_yx`. The top-left corner is ``(y=0, x=0)``,
   not ``(1, 1)``. This allows direct use of mouse coordinates with movement functions.

Understanding Buttons
---------------------

Mouse events come through :meth:`~.Terminal.inkey` just like keyboard events.

You can detect mouse events using either the :attr:`~.Keystroke.name` property
or magic method predicates:

**Using the name property:**

The :attr:`~.Keystroke.name` returns button names with the ``MOUSE_`` prefix,
following the pattern ``MOUSE_[MODIFIERS_]BUTTON[_RELEASED]``:

.. code-block:: python

   inp = term.inkey()
   if inp.name == 'MOUSE_LEFT':
       print("Left button pressed")

**Using magic method predicates:**

.. code-block:: python

   inp = term.inkey()
   if inp.is_mouse_left():
       print("Left button pressed")
   elif inp.is_mouse_ctrl_left():
       print("Ctrl+Left button pressed")

**Button names include:**

- Basic events: ``MOUSE_LEFT``, ``MOUSE_MIDDLE``, ``MOUSE_RIGHT``, ``MOUSE_SCROLL_UP``,
  ``MOUSE_SCROLL_DOWN``
- Release events: ``MOUSE_LEFT_RELEASED``, ``MOUSE_MIDDLE_RELEASED``,
  ``MOUSE_RIGHT_RELEASED``
- With modifiers: ``MOUSE_CTRL_LEFT``, ``MOUSE_SHIFT_SCROLL_UP``, ``MOUSE_META_RIGHT``,
  ``MOUSE_CTRL_SHIFT_META_MIDDLE``

Modifiers are included in order ``CTRL``, ``SHIFT``, and ``META``

In this example, all possible combinations may be entered and recorded, see if
you have enough fingers for ``CTRL_SHIFT_META_MIDDLE``, imagine the
possibilities!

.. literalinclude:: ../bin/mouse_modifiers.py
   :language: python
   :linenos:

Understanding Mouse Coordinates
-------------------------------

Mouse coordinates are accessed by :attr:`~Keystroke.mouse_yx` attribute in as
tuple ``(int, int)`` of the corresponding row and column. This matches the
signature of :meth:`~Terminal.move_yx`. If :attr:`~Keystroke.mouse_yx` is used
on a keystroke that is not a mouse event, values ``(-1, -1)`` are returned.

There is also a :attr:`~Keystroke.mouse_xy` attribute that mirrors the signature
of :meth:`~Terminal.move_xy`.

- :attr:`~.Keystroke.mouse_yx` - position as a ``(y, x)`` tuple
- :attr:`~.Keystroke.mouse_xy` - position as an ``(x, y)`` tuple

.. literalinclude:: ../bin/mouse_coords.py
   :language: python
   :linenos:

Checking Support
----------------

Not all terminals support mouse tracking or all kinds of mouse tracking.

Use :meth:`~blessed.Terminal.does_mouse` to check before enabling:

.. literalinclude:: ../bin/mouse_query.py
   :language: python
   :linenos:

The :meth:`~.Terminal.does_mouse` method accepts the same parameters as
:meth:`~.Terminal.mouse_enabled` and returns ``True`` if all of given modes are
supported.

Using mouse_enabled()
---------------------

The :meth:`~blessed.Terminal.mouse_enabled` context manager enables the appropriate
:ref:`dec private modes` depending on the simplified arguments given.

:meth:`~blessed.Terminal.mouse_enabled` accepts these keyword-only parameters:

* ``clicks=True`` - Enable basic click reporting (default).
* ``report_drag=False`` - Report motion while a button is held.
* ``report_motion=False`` - Report all mouse movement.
* ``report_pixels=False`` - Report position in pixels instead of cells.
* ``timeout=1.0`` - Timeout for mode queries, in seconds.

**Parameter Precedence**

The tracking modes have precedence: ``report_motion`` > ``report_drag`` > ``clicks``.
When you enable a higher-precedence mode, it automatically includes the functionality
of lower modes. For example, ``report_motion=True`` will also track drags and clicks.

report_drag
~~~~~~~~~~~

Reports motion only while a button is held down:

.. literalinclude:: ../bin/mouse_drag.py
   :language: python
   :linenos:

When using ``report_drag=True`` or ``report_motion=True``, you'll receive motion
events in the :attr:`~Keystroke.name` attribute with a ``_MOTION`` suffix:

- ``MOUSE_MOTION`` - Motion without any button pressed (``report_motion``)
- ``MOUSE_LEFT_MOTION``, ``MOUSE_MIDDLE_MOTION``, ``MOUSE_RIGHT_MOTION`` -
  Dragging with a button held, usually follows click, eg. ``MOUSE_LEFT``.

Motion events include modifiers just like click events, for example ``MOUSE_CTRL_LEFT_MOTION``.

.. _report_motion:

report_motion
~~~~~~~~~~~~~

Reports all mouse clicks movement, even without buttons pressed. The
:attr:`~Keystroke.name` attribute of ``MOUSE_MOTION`` is given when no button or
scroll wheel events have occurred, only an updated :attr:`~Keystroke.mouse_yx`
position.

In this example, the terminal cursor tracks with the mouse pointer because the
:meth:`~Terminal.move_yx` sequence is displayed following any mouse event,
especially ``MOUSE_MOTION``, tracking the :attr:`Keystroke.mouse_yx` coordinate.

.. literalinclude:: ../bin/mouse_paint.py
   :language: python
   :linenos:

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/mouse_paint.gif

Painting is done while the left mouse button is held down, tracking both
``MOUSE_LEFT`` and ``MOUSE_LEFT_MOTION``, erased with ``MOUSE_RIGHT``, and color
selection changed by ``MOUSE_SCROLL_UP`` and ``MOUSE_SCROLL_DOWN``.

.. note::

   When using ``report_motion=True``, process events quickly! Mouse movement
   generates many events that can fill the input buffer if not consumed promptly.

report_pixels
~~~~~~~~~~~~~

By default, mouse positions are reported in character cell coordinates - each
position corresponds to a single character in the terminal grid.

For higher precision, use ``report_pixels=True`` to get pixel coordinates instead.
This is especially useful when combined with graphics protocols like Sixel:

.. literalinclude:: ../bin/mouse_pixels.py
   :language: python
   :linenos:

When using pixel mode, mouse events still use the same :attr:`~.Keystroke.name`
pattern (e.g., ``'MOUSE_LEFT'``) and magic method predicates (e.g.,
``inp.is_mouse_left()``). The :attr:`~.Keystroke.x` and :attr:`~.Keystroke.y`
properties represent pixels instead of character cells.

