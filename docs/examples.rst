Examples
========

A few programs are provided with blessed to help interactively
test the various API features, but also serve as examples of using
blessed to develop applications.

These examples are not distributed with the package -- they are
only available in the github repository.  You can retrieve them
by cloning the repository, or simply downloading the "raw" file
link.

editor.py
---------
https://github.com/jquast/blessed/blob/master/bin/editor.py

This program demonstrates using the directional keys and noecho input
mode. It acts as a (very dumb) fullscreen editor, with support for
saving a file, which demonstrates how to provide a line-editor
rudimentary line-editor as well.

keymatrix.py
------------
https://github.com/jquast/blessed/blob/master/bin/keymatrix.py

This program displays a "gameboard" of all known special KEY_NAME
constants. When the key is depressed, it is highlighted, as well
as displaying the unicode sequence, integer code, and friendly-name
of any key pressed.

on_resize.py
------------
https://github.com/jquast/blessed/blob/master/bin/on_resize.py

This program installs a SIGWINCH signal handler, which detects
screen resizes while also polling for input, displaying keypresses.

This demonstrates how a program can react to screen resize events.

progress_bar.py
---------------
https://github.com/jquast/blessed/blob/master/bin/progress_bar.py

This program demonstrates a simple progress bar. All text is written
to stderr, to avoid the need to "flush" or emit newlines, and makes
use of the move_x (hpa) capability to "overstrike" the display a
scrolling progress bar.

tprint.py
---------
https://github.com/jquast/blessed/blob/master/bin/tprint.py

This program demonstrates how users may customize FormattingString
styles.  Accepting a string style, such as "bold" or "bright_red"
as the first argument, all subsequent arguments are displayed by
the given style.  This shows how a program could provide
user-customizable compound formatting names to configure a program's
styling.

worms.py
--------
https://github.com/jquast/blessed/blob/master/bin/worms.py

This program demonstrates how an interactive game could be made
with blessed.  It is designed after the class game of WORMS.BAS,
distributed with early Microsoft Q-BASIC for PC-DOS, and later
more popularly known as "snake" as it was named on early mobile
platforms.
