.. _line_editor:

Line Editor
===========

The :mod:`blessed.line_editor` module provides :class:`~blessed.line_editor.LineEditor`,
a headless single-line editor with readline-style keybindings, grapheme-aware cursor
movement, auto-suggest from history, password masking, and horizontal scrolling.

.. note::

   The editor never writes to the terminal directly — your application
   controls when and where output appears.

   Use the built-in :ref:`render methods <line_editor_render>` to produce
   ready-to-print escape sequences, or read
   :attr:`~blessed.line_editor.LineEditor.display` for raw display state
   if you need fully custom rendering.

Overview
--------

Feed keystrokes (from :meth:`~.Terminal.inkey` or :meth:`~.Terminal.async_inkey`) into
:meth:`~blessed.line_editor.LineEditor.feed_key`.  It returns a
:class:`~blessed.line_editor.LineEditResult` with these fields:

- ``line`` — the accepted string when Enter is pressed, otherwise ``None``
- ``interrupt`` / ``eof`` — ``True`` on Ctrl+C / Ctrl+D respectively
- ``changed`` — ``True`` when the display needs redrawing
- ``bell`` — a bell string to emit (empty when silent)

For bracketed paste, feed the pasted text through
:meth:`~blessed.line_editor.LineEditor.insert_text` instead of
:meth:`~blessed.line_editor.LineEditor.feed_key`.

For async usage, simply replace ``term.inkey()`` with ``await term.async_inkey()``.
See :ref:`async_input` in the keyboard documentation for more on ``async_inkey``.

Example
-------

A line editor with history, auto-suggest, password mode, and styled rendering:

.. literalinclude:: ../bin/line_editor_form.py
   :language: python
   :linenos:

.. _line_editor_history:

History
-------

:class:`~blessed.line_editor.LineHistory` stores command history in memory.
History navigation (Up/Down) and auto-suggest (type a prefix, press Right to accept)
are enabled automatically when a history instance is attached to the editor.

For on-disk persistence, read/write the ``entries`` list directly (most recent
entry last).

.. _line_editor_display:

Display State & Styling
-----------------------

Each call to :attr:`~blessed.line_editor.LineEditor.display` returns a
:class:`~blessed.line_editor.DisplayState` with the visible text, cursor position,
suggestion suffix, and clipping indicators.

The editor ships with default SGR styling (light cream text, dark suggestion).
Override with ``text_sgr``, ``suggestion_sgr``, ``bg_sgr``, or ``ellipsis_sgr``::

    editor = LineEditor(bg_sgr=term.on_brown, max_width=term.width)

When ``max_width`` is set and text overflows, ``overflow_left`` and
``overflow_right`` indicate which edges are truncated.  Use
``ellipsis_sgr`` to style the overflow indicator.

.. _line_editor_render:

Rendering Helpers
-----------------

:class:`~blessed.line_editor.LineEditor` provides three render methods that
build complete escape-sequence strings from the current display state:

:meth:`~blessed.line_editor.LineEditor.render`
   Full redraw — always produces correct output.

:meth:`~blessed.line_editor.LineEditor.render_insert`
   Fast-path after a character insert at end of buffer.  Returns ``None``
   when a full redraw is needed instead.

:meth:`~blessed.line_editor.LineEditor.render_backspace`
   Fast-path after a backspace at end of buffer.  Returns ``None``
   when a full redraw is needed instead.

Try the fast-path first and fall back to ``render()`` when it returns
``None``.  See the :ref:`example above <line_editor>` for the complete
pattern.

.. _line_editor_other:

Other Methods
-------------

:meth:`~blessed.line_editor.LineEditor.clear`
   Reset the buffer, cursor, and undo history.

:meth:`~blessed.line_editor.LineEditor.set_password_mode`
   Toggle password masking on or off mid-session.

.. _line_editor_constructor:

Constructor Options
-------------------

Beyond the styling and keybinding options shown above, :class:`~blessed.line_editor.LineEditor`
accepts:

``password``
   If ``True``, start in password mode (characters are masked).  Toggle at
   runtime with :meth:`~blessed.line_editor.LineEditor.set_password_mode`.

``password_char``
   Replacement character shown in password mode (default ``"⚻"``).

``limit``
   Maximum buffer length in characters (default 65536).

``limit_bell``
   Bell string emitted when the limit is reached (default ``"\\a"``).

``scroll_jump``
   Fraction of ``max_width`` to scroll when the cursor overflows (default 0.5).

.. _line_editor_keybindings:

Custom Keybindings
------------------

Pass a ``keymap`` dict to override or extend the default emacs/readline bindings.
Keys are :class:`~.Keystroke` ``.name`` strings (e.g. ``"KEY_CTRL_K"``), values are
callables accepting a :class:`~blessed.line_editor.LineEditor` and returning a
:class:`~blessed.line_editor.LineEditResult`.

Override an existing binding::

    def my_enter(editor):
        # custom accept logic
        return LineEditResult(line=editor.line, changed=True)

    editor = LineEditor(keymap={"KEY_ENTER": my_enter})

Add a new binding::

    def handle_f1(editor):
        editor.insert_text("help!")
        return LineEditResult(changed=True)

    editor = LineEditor(keymap={"KEY_F1": handle_f1})

Disable a binding by setting it to ``None``::

    # Ctrl+C becomes a silent no-op instead of raising interrupt
    editor = LineEditor(keymap={"KEY_CTRL_C": None})

Default Keybindings
-------------------

These are the default emacs/readline bindings.  All can be overridden via ``keymap``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Action
   * - Enter
     - Accept line
   * - Ctrl+C
     - Cancel (interrupt)
   * - Ctrl+D
     - EOF on empty line, delete at cursor otherwise
   * - Left, Ctrl+B
     - Move cursor left
   * - Right
     - Accept auto-suggest at end, otherwise move right
   * - Ctrl+F
     - Move cursor right
   * - Home, Ctrl+A
     - Move to start of line
   * - End, Ctrl+E
     - Move to end of line
   * - Shift+Left, Ctrl+Left
     - Move word left
   * - Shift+Right, Ctrl+Right
     - Move word right
   * - Backspace
     - Delete character before cursor
   * - Delete
     - Delete character at cursor
   * - Ctrl+K
     - Kill to end of line
   * - Ctrl+U
     - Kill to start of line
   * - Ctrl+W
     - Kill word backward
   * - Ctrl+Y
     - Yank (paste from kill ring)
   * - Up, Ctrl+P
     - Previous history entry
   * - Down, Ctrl+N
     - Next history entry
   * - Ctrl+Z
     - Undo
