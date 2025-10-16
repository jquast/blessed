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

After confirming the :attr:`~.Keystroke.mode` value to
:attr:`~.Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR`, indicating it is a mouse
event, the :attr:`~.Keystroke.mode_values` object is a :class:`~.MouseEvent`
containing field values ``button``, ``y``, and ``x``.

.. note::

   Mouse coordinates are **0-indexed**, matching blessed's terminal movement
   functions like :meth:`~.Terminal.move_yx`. The top-left corner is ``(y=0, x=0)``,
   not ``(1, 1)``. This allows direct use of mouse coordinates with movement functions.

Understanding Buttons
---------------------

Mouse events come through :meth:`~.Terminal.inkey` just like keyboard events.

A :class:`~.Keystroke` object is a mouse event when :attr:`~.Keystroke.mode`
matches one of the enabled mouse modes
(:attr:`~Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR` or
:attr:`~Terminal.DecPrivateMode.MOUSE_SGR_PIXELS`).

Call :meth:`~.Keystroke.mode_values` to get a :class:`~.MouseEvent` instance
with the Human-readable :attr:`~.MouseEvent.button` name, including release
state. Button names follow the pattern ``[MODIFIERS_]BUTTON[_RELEASED]``,
such as:

- Basic events: "LEFT", "MIDDLE", "RIGHT", "SCROLL_UP", "SCROLL_DOWN"
- Release events: "LEFT_RELEASED", "MIDDLE_RELEASED", "RIGHT_RELEASED"
- With modifiers: "CTRL_LEFT", "SHIFT_SCROLL_UP", "META_RIGHT", "CTRL_META_LEFT_RELEASED"

Modifiers may be compounded, in order ``CTRL``, ``SHIFT``, and ``META``,
eg. ``CTRL_SHIFT_META_MIDDLE``

In this example, all possible combinations may be entered and recorded, see if
you have enough fingers for ``CTRL_SHIFT_META_MIDDLE``, imagine the
possibilities!

.. literalinclude:: ../bin/mouse_modifiers.py
   :language: python
   :linenos:

Checking Support
----------------

Not all terminals support mouse tracking or all kinds of mouse tracking.

Use :meth:`~blessed.Terminal.does_mouse` to check before enabling:

.. literalinclude:: ../bin/mouse_drag.py
   :language: python
   :linenos:

The :meth:`~.Terminal.does_mouse` method accepts the same parameters as
:meth:`~.Terminal.mouse_enabled` and returns ``True`` if all of given modes are
supported.

Using mouse_enabled()
---------------------

The :meth:`~blessed.Terminal.mouse_enabled` context manager enables the appropriate
`Dec Private Modes`_ depending on the simplified arguments given.

:meth:`~blessed.Terminal.mouse_enabled` accepts these keyword-only parameters:

* ``clicks=True`` - Enable basic click reporting (default)
* ``report_drag=False`` - Report motion while a button is held
* ``report_motion=False`` - Report all mouse movement
* ``report_pixels=False`` - Report position in pixels instead of cells
* ``timeout=1.0`` - Timeout for mode queries in seconds

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

report_motion
~~~~~~~~~~~~~

Reports all mouse movement, even without buttons pressed.  In this example,
report motion causes the terminal cursor to track with the mouse. Painting is
done while ``LEFT`` button is held down and colors changed by ``SCROLL_UP`` and
``SCROLL_DOWN``:

.. literalinclude:: ../bin/mouse_paint.py
   :language: python
   :linenos:

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

When using pixel mode, the :attr:`~.Keystroke.mode` value is
:attr:`~Terminal.DecPrivateMode.MOUSE_SGR_PIXELS` instead of the usual
:attr:`~.Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR`. The
:attr:`~.Keystroke.mode_values` object is still a :class:`~.MouseEvent`, only
the meaning of ``x`` and ``y`` values changes from cells to pixels.
