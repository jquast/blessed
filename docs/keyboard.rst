Keyboard Input
==============

Python's built-in :func:`input` function is great for simple prompts, but it has a big limitation: it waits for the Enter key. This makes it unsuitable for interactive applications that need to respond to individual keystrokes, arrow keys, or function keys.

Blessed provides a better solution through :meth:`~.Terminal.inkey`, which returns keystrokes immediately as :class:`~.Keystroke` objects. Combined with :meth:`~.Terminal.cbreak` mode, you can build responsive, interactive terminal applications.

Getting Started
---------------

Here's a simple example that reads a single keystroke:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        key = term.inkey()
        print(f"You pressed: {key!r}")

The :meth:`~.Terminal.cbreak` context manager enables immediate key detection. Inside this context, :meth:`~.Terminal.inkey` returns a :class:`~.Keystroke` object representing the key that was pressed.

Understanding Keystroke Objects
--------------------------------

The :class:`~.Keystroke` class makes it easy to work with keyboard input. It inherits from :class:`str`, so you can compare it directly to characters, but it also provides special properties for detecting modifier keys and special sequences.

is_sequence: Detecting Special Keys
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use :attr:`~.Keystroke.is_sequence` to check if the keystroke is a special key (like arrows or function keys) versus a regular character:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        key = term.inkey()
        
        if key.is_sequence:
            print(f"Special key: {key.name}")
        else:
            print(f"Regular character: {key}")

The :attr:`~.Keystroke.is_sequence` property returns ``True`` for arrow keys, function keys, and any key combination with modifiers (Ctrl, Alt, Shift).

name: Identifying Keys
~~~~~~~~~~~~~~~~~~~~~~

The :attr:`~.Keystroke.name` property provides a readable name for special keys, see this "paint by arrow key" example:

.. code-block:: python

    from blessed import Terminal

    header_msg = "Press arrow keys (or 'q' to quit): "
    term = Terminal()
    position = [term.height // 2, term.width // 2]
    with term.cbreak(), term.fullscreen(), term.hidden_cursor():
        print(term.home + header_msg + term.clear_eos)

        while True:
            # show arrow-controlled block
            print(term.move_yx(*position) + '█', end='', flush=True)

            # get key,
            key = term.inkey()

            # take action,
            if key == 'q':
                break
            if key.name == 'KEY_UP':
                position[0] = max(0, position[0] - 1)
            elif key.name == 'KEY_LEFT':
                position[1] = max(0, position[1] - 1)
            elif key.name == 'KEY_DOWN':
                position[0] = max(term.height, position[0] + 1)
            elif key.name == 'KEY_RIGHT':
                position[1] = max(term.width, position[1] + 1)

Common key names include:

* ``KEY_UP``, ``KEY_DOWN``, ``KEY_LEFT``, ``KEY_RIGHT`` - Arrow keys
* ``KEY_ENTER`` - Enter/Return key
* ``KEY_BACKSPACE``, ``KEY_DELETE`` - Backspace and Delete keys
* ``KEY_TAB`` - Tab key
* ``KEY_ESCAPE`` - Escape key
* ``KEY_F1`` through ``KEY_F12`` - Function keys
* ``KEY_PGUP``, ``KEY_PGDOWN`` - Page Up and Page Down
* ``KEY_HOME``, ``KEY_END`` - Home and End keys

For regular characters without modifiers, :attr:`~.Keystroke.name` returns ``None``.

value: Getting Text Characters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :attr:`~.Keystroke.value` property returns the text character for keys that produce text, stripping away modifier information:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        text = ""
        print("Type something (Enter to finish):")
        
        while True:
            key = term.inkey()
            
            if key.name == 'KEY_ENTER':
                break
            elif key.name == 'KEY_BACKSPACE' and text:
                text = text[:-1]
                print(f"\r{term.clear_eol()}{text}", end='', flush=True)
            elif key.value:
                text += key.value
                print(key.value, end='', flush=True)
        
        print(f"\nYou typed: {text}")

For special keys like ``KEY_UP`` or ``KEY_F1``, :attr:`~.Keystroke.value` returns an empty string.

Working with Modifiers
----------------------

Blessed detects modifier keys (Ctrl, Alt, Shift) combined with regular keys or special keys. The :attr:`~.Keystroke.name` property represents these combinations:

Modifiers with Letters and Numbers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        print("Try Ctrl+Q or Alt+X:")
        while True:
            key = term.inkey()
            
            if key.name == 'KEY_CTRL_Q':
                print("Quitting with Ctrl+Q")
                break
            elif key.name == 'KEY_ALT_X':
                print("You pressed Alt+X")
            elif key.name == 'KEY_CTRL_ALT_S':
                print("Ctrl+Alt+S detected!")

Key names with modifiers follow the pattern:

* ``KEY_CTRL_<char>`` - Control + character (e.g., ``KEY_CTRL_C``)
* ``KEY_ALT_<char>`` - Alt + character (e.g., ``KEY_ALT_F``)
* ``KEY_SHIFT_<char>`` - Shift + letter (e.g., ``KEY_ALT_SHIFT_A``)
* ``KEY_CTRL_ALT_<char>`` - Ctrl + Alt + character

Modifiers with Special Keys
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also combine modifiers with arrow keys, function keys, and other special keys:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        print("Try Shift+arrows or Ctrl+Delete:")
        while True:
            key = term.inkey()
            
            if key == 'q':
                break
            elif key.name == 'KEY_SHIFT_LEFT':
                print("Shift+Left")
            elif key.name == 'KEY_CTRL_DELETE':
                print("Ctrl+Delete")
            elif key.name == 'KEY_CTRL_ALT_F1':
                print("Ctrl+Alt+F1")

Examples include:

* ``KEY_SHIFT_LEFT`` - Shift + Left Arrow
* ``KEY_CTRL_BACKSPACE`` - Ctrl + Backspace
* ``KEY_ALT_DELETE`` - Alt + Delete
* ``KEY_CTRL_SHIFT_F3`` - Ctrl + Shift + F3

Magic Methods
-------------

The :class:`~.Keystroke` class provides convenient "magic methods" for checking keys and modifiers. These methods all start with ``is_`` and can make your code more readable.

Basic Usage
~~~~~~~~~~~

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        key = term.inkey()
        
        # Check for specific character with modifier
        if key.is_ctrl('c'):
            print("Ctrl+C pressed")
        
        # Check for function key
        if key.is_f1():
            print("F1 pressed")
        
        # Check for arrow key with modifier
        if key.is_shift_left():
            print("Shift+Left pressed")

Method Patterns
~~~~~~~~~~~~~~~

The magic methods follow these patterns:

**Modifier + character:**

.. code-block:: python

    key.is_ctrl('x')           # Ctrl+X
    key.is_alt('q')            # Alt+Q
    key.is_ctrl_alt('s')       # Ctrl+Alt+S
    key.is_ctrl_shift_alt('a') # Ctrl+Shift+Alt+A

**Special keys:**

.. code-block:: python

    key.is_f1()          # F1 key
    key.is_up()          # Up arrow
    key.is_enter()       # Enter key
    key.is_backspace()   # Backspace

**Modifier + special key:**

.. code-block:: python

    key.is_ctrl_left()       # Ctrl+Left arrow
    key.is_alt_backspace()   # Alt+Backspace
    key.is_shift_f5()        # Shift+F5

Case Sensitivity
~~~~~~~~~~~~~~~~

By default, character matching is case-insensitive. You can change this with the ``ignore_case`` parameter:

.. code-block:: python

    key.is_ctrl('x')                     # Matches Ctrl+X and Ctrl+x
    key.is_ctrl('x', ignore_case=False)  # Only matches Ctrl+x

Timeouts and Non-Blocking Input
--------------------------------

The :meth:`~.Terminal.inkey` method accepts a ``timeout`` parameter (in seconds) for non-blocking input:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        print("Press any key (waiting 3 seconds)...")
        key = term.inkey(timeout=3)
        
        if key:
            print(f"You pressed: {key!r}")
        else:
            print("No key pressed (timeout)")

A timeout of ``0`` checks for input immediately without waiting:

.. code-block:: python

    from blessed import Terminal
    import time

    term = Terminal()
    with term.cbreak():
        print("Animation running... Press any key to stop")
        running = True
        
        while running:
            # Check for keypress without blocking
            key = term.inkey(timeout=0)
            if key:
                running = False
            else:
                # Do animation frame
                print(".", end='', flush=True)
                time.sleep(0.1)

Event Types
-----------

Some terminals can report when keys are pressed, held (repeated), or released. You can detect these events using the :attr:`~.Keystroke.pressed`, :attr:`~.Keystroke.repeated`, and :attr:`~.Keystroke.released` properties:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        print("Press and hold a key:")
        while True:
            key = term.inkey()
            
            if key == 'q':
                break
            
            if key.pressed:
                print(f"{key!r} pressed")
            elif key.repeated:
                print(f"{key!r} repeating")
            elif key.released:
                print(f"{key!r} released")

Note that not all terminals support key release events. Most terminals only report key press events.

Practical Examples
------------------

Menu Navigation
~~~~~~~~~~~~~~~

Here's a simple menu that responds to arrow keys:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    
    def show_menu(items, selected):
        print(term.home + term.clear)
        for i, item in enumerate(items):
            if i == selected:
                print(term.reverse(f"> {item}"))
            else:
                print(f"  {item}")
        print("\nUse arrows to navigate, Enter to select, Q to quit")
    
    items = ["Open File", "Save File", "Settings", "Exit"]
    selected = 0
    
    with term.cbreak():
        show_menu(items, selected)
        
        while True:
            key = term.inkey()
            
            if key == 'q':
                break
            elif key.name == 'KEY_UP' and selected > 0:
                selected -= 1
                show_menu(items, selected)
            elif key.name == 'KEY_DOWN' and selected < len(items) - 1:
                selected += 1
                show_menu(items, selected)
            elif key.name == 'KEY_ENTER':
                print(term.clear)
                print(f"Selected: {items[selected]}")
                break

Text Input with Editing
~~~~~~~~~~~~~~~~~~~~~~~~

A simple text input field with backspace support:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    
    def get_input(prompt):
        print(prompt, end='', flush=True)
        text = ""
        
        with term.cbreak():
            while True:
                key = term.inkey()
                
                if key.name == 'KEY_ENTER':
                    print()
                    return text
                elif key.name == 'KEY_ESCAPE':
                    print()
                    return None
                elif key.name in ('KEY_BACKSPACE', 'KEY_DELETE') and text:
                    text = text[:-1]
                    print('\b \b', end='', flush=True)
                elif key.value and len(text) < 40:
                    text += key.value
                    print(key.value, end='', flush=True)
    
    name = get_input("Enter your name: ")
    if name:
        print(f"Hello, {name}!")

Keyboard Shortcuts
~~~~~~~~~~~~~~~~~~

Implementing common keyboard shortcuts:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    
    with term.cbreak():
        print("Try these shortcuts:")
        print("  Ctrl+S - Save")
        print("  Ctrl+O - Open")
        print("  Ctrl+Q - Quit")
        
        while True:
            key = term.inkey()
            
            if key.is_ctrl('q'):
                print("\nQuitting...")
                break
            elif key.is_ctrl('s'):
                print("\nSaving...")
            elif key.is_ctrl('o'):
                print("\nOpening...")

Additional Features
-------------------

Flushing Input
~~~~~~~~~~~~~~

Sometimes you need to clear any pending keyboard input, such as when switching screens or after a delay. Use :meth:`~.Terminal.flushinp` to discard buffered input:

.. code-block:: python

    from blessed import Terminal
    import time

    term = Terminal()
    
    with term.cbreak():
        print("Processing... (please wait)")
        time.sleep(2)
        
        # Discard any keys pressed during the delay
        term.flushinp()
        
        print("Ready! Press any key:")
        key = term.inkey()

Backspace and Delete Keys
~~~~~~~~~~~~~~~~~~~~~~~~~~

Different terminals may send different codes for the Backspace and Delete keys. Blessed normalizes these as ``KEY_BACKSPACE`` and ``KEY_DELETE``, but to be safe, you can handle both:

.. code-block:: python

    if key.name in ('KEY_BACKSPACE', 'KEY_DELETE'):
        # Handle backspace/delete
        pass

For building text editors or input fields, treating both keys as backspace is often the most user-friendly approach.

Advanced: Accessing Key Codes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For advanced use cases, you can access the raw keycode with :attr:`~.Keystroke.code`:

.. code-block:: python

    from blessed import Terminal

    term = Terminal()
    with term.cbreak():
        key = term.inkey()
        
        if key.code:
            print(f"Keycode: {key.code}")
            print(f"Name: {key.name}")

The :attr:`~.Keystroke.code` property returns an integer matching curses key constants like ``term.KEY_LEFT`` (260). For regular characters without modifiers, it returns ``None``.

Summary
-------

The :class:`~.Keystroke` class provides a powerful yet simple interface for keyboard input:

* Use :attr:`~.Keystroke.is_sequence` to detect special keys
* Use :attr:`~.Keystroke.name` to identify keys by name (e.g., ``KEY_F1``, ``KEY_CTRL_Q``)
* Use :attr:`~.Keystroke.value` to get text characters for input
* Use magic methods like ``is_ctrl('x')`` for readable key checks
* Use :meth:`~.Terminal.inkey` with ``timeout`` for non-blocking input

With these tools, you can build responsive, interactive terminal applications that feel natural to use.
