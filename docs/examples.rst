Examples
========

A few programs are provided with blessed to help interactively test the various API features, but
also serve as examples of using blessed to develop applications.

These examples are not distributed with the package -- they are only available in the github
repository.  You can retrieve them by cloning the repository, or simply downloading the "raw" file
link.

.. note: animations are made using the following CLI example:

   ffmpeg -i blessed_demo_6.mov -pix_fmt rgb8 -r 24 -f gif - \
      | gifsicle --optimize=3 --delay=3 --resize-width 800 > blessed_demo_6.gif

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/blessed_demo_intro.gif
   :alt: Animations of x11-colorpicker.py, bounce.py, worms.py, and plasma.py

   :ref:`x11-colorpicker.py`, :ref:`bounce.py`, :ref:`worms.py`, and :ref:`plasma.py`.

.. _bounce.py:

bounce.py
---------

https://github.com/jquast/blessed/blob/master/bin/bounce.py

This is a very brief, basic primitive non-interactive version of a "classic tennis" video game. It
demonstrates basic timed refresh of a bouncing terminal cell.

.. _cnn.py:

cnn.py
-------------------
https://github.com/jquast/blessed/blob/master/bin/cnn.py

This program uses 3rd-party BeautifulSoup and requests library to fetch the cnn website and display
news article titles using the :meth:`~.Terminal.link` method, so that they may be clicked.

.. _detect-multibyte.py:

detect-multibyte.py
-------------------
https://github.com/jquast/blessed/blob/master/bin/detect-multibyte.py

This program also demonstrates how the :meth:`~.get_location` method
can be used to reliably test whether the terminal emulator supports
utf-8 or other multibyte encoding, by rendering multibyte characters
and measuring the change in cursor location.

.. _editor.py:

editor.py
---------
https://github.com/jquast/blessed/blob/master/bin/editor.py

This program demonstrates using the directional keys and noecho input
mode. It acts as a (very dumb) fullscreen editor, with support for
saving a file, as well as including a rudimentary line-editor.

.. _keymatrix.py:

keymatrix.py
------------
https://github.com/jquast/blessed/blob/master/bin/keymatrix.py

This program displays a special REPL for using :meth:`~.inkey` and displaying
the returned :class:`~.Keystroke` events, their names, events, and values.

This also provides an interface for toggling special modes, such as any of the
supported :ref:`kitty` Keyboard Protocols.

.. _on_resize.py:

on_resize.py
------------
https://github.com/jquast/blessed/blob/master/bin/on_resize.py

This program installs a SIGWINCH signal handler, which detects
screen resizes while also polling for input, displaying keypresses.

This demonstrates how a program can react to screen resize events.

.. _plasma.py:

plasma.py
---------
https://github.com/jquast/blessed/blob/master/bin/plasma.py

This demonstrates using only :meth:`~.Terminal.on_color_rgb` and the built-in :mod:`colorsys`
module to quickly display all of the colors of a rainbow in a classic demoscene `plasma effect
<https://lodev.org/cgtutor/plasma.html>`_

.. _progress_bar.py:

progress_bar.py
---------------
https://github.com/jquast/blessed/blob/master/bin/progress_bar.py

This program demonstrates a simple progress bar. All text is written
to stderr, to avoid the need to "flush" or emit newlines, and makes
use of the move_x (hpa) capability to "overstrike" the display a
scrolling progress bar.

.. _resize.py:

resize.py
---------
https://github.com/jquast/blessed/blob/master/bin/resize.py

This program demonstrates the :meth:`~.get_location` method,
behaving similar to `resize(1)
<https://github.com/joejulian/xterm/blob/master/resize.c>`_
: set environment and terminal settings to current window size.
The window size is determined by eliciting an answerback
sequence from the connecting terminal emulator.

.. _tprint.py:

tprint.py
---------
https://github.com/jquast/blessed/blob/master/bin/tprint.py

This program demonstrates how users may customize FormattingString
styles.  Accepting a string style, such as "bold" or "bright_red"
as the first argument, all subsequent arguments are displayed by
the given style.  This shows how a program could provide
user-customizable compound formatting names to configure a program's
styling.

.. _worms.py:

worms.py
--------
https://github.com/jquast/blessed/blob/master/bin/worms.py

This program demonstrates how an interactive game could be made
with blessed.  It is similar to `NIBBLES.BAS
<https://github.com/tangentstorm/tangentlabs/blob/master/qbasic/NIBBLES.BAS>`_
or "snake" of early mobile platforms.

.. _x11-colorpicker.py:

x11_colorpicker.py
------------------
https://github.com/jquast/blessed/blob/master/bin/x11_colorpicker.py

This program shows all of the X11 colors, demonstrates a basic keyboard-interactive program and
color selection, but is also a useful utility to pick colors!

.. _display_modes.py:

display_modes.py
----------------
https://github.com/jquast/blessed/blob/master/bin/display_modes.py

Detect and report all known DEC Private Modes supported by the Terminal and
display a report.

.. _strip.py:

strip.py
-------------
https://github.com/jquast/blessed/blob/master/bin/strip.py

This wrapper of the :meth:`~Terminal.strip_seqs` method reads text from standard
input, "strips" away all known output sequences and writes the result to stdout.


.. _bin/mouse_paint.py:

mouse_paint.py
--------------
https://github.com/jquast/blessed/blob/master/bin/mouse_paint.py

.. figure:: https://dxtz6bzwq9sxx.cloudfront.net/mouse_paint.gif

This is a basic "paint" program using :ref:`mouse input` with the :ref:`report_motion` feature.
