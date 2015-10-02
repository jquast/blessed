Growing Pains
=============

When making terminal applications, there are a surprisingly number of
portability issues and edge cases.  Although Blessed provides an abstraction
for the full curses capability database, it is not sufficient to secure
you from several considerations shared here.

8 and 16 colors
---------------

Where 8 and 16 colors are used, they should be assumed to be the
`CGA Color Palette`_.  Though there is no terminal standard that proclaims
that the CGA colors are used, their values are the best approximations
across all common hardware terminals and terminal emulators.

A recent phenomenon of users is to customize their base 16 colors to provide
(often, more "washed out") color schemes.  Furthermore, we are only recently
getting LCD displays of colorspaces that achieve close approximation to the
original video terminals.  Some find these values uncomfortably intense: in
their original CRT form, their contrast and brightness was lowered by hardware
dials, whereas today's LCD's typically display well only near full intensity.

Though we may not *detect* the colorspace of the remote terminal, **we can**:

- Trust that a close approximation of the `CGA Color Palette`_ for the base
  16 colors will be displayed for **most** users.

- Trust that users who have made the choice to adjust their palette have made
  the choice to do so, and are able to re-adjust such palettes as necessary
  to accommodate different programs (such as through the use of "Themes").

.. note::

   It has become popular to use dynamic system-wide color palette adjustments
   in software such as `f.lux`_, which adjust the system-wide "Color Profile"
   of the entire graphics display depending on the time of day.  One might
   assume that ``term.blue("text")`` may be **completely** invisible to such
   users during the night!


Where is brown, purple, or grey?
--------------------------------

There are **only 8 color names** on a 16-color terminal:  The second set of
eight colors are "high intensity" versions of the first in direct series.

The colors *brown*, *purple*, and *grey* are not named in the first series,
though they are available:

- **brown**: *yellow is brown*, only high-intensity yellow
  (``bright_yellow``) is yellow!

- **purple**: *magenta is purple*.  In earlier, 4-bit color spaces, there
  were only black, cyan, magenta, and white of low and high intensity, such
  as found on common home computers like the `ZX Spectrum`_.

  Additional "colors" were only possible through dithering.  The color names
  cyan and magenta on later graphics adapters are carried over from its
  predecessors.  Although the color cyan remained true in RGB value on
  16-color to its predecessor, magenta shifted farther towards blue from red
  becoming purple (as true red was introduced as one of the new base 8
  colors).

- **grey**: there are actually **three shades of grey** (or American spelling,
  'gray'), though the color attribute named 'grey' does not exist!

  In ascending order of intensity, the shades of grey are:

  - ``bold_black``: in lieu of the uselessness of an "intense black", this is
    color is instead mapped to "dark grey".
  - ``white``: white is actually mild compared to the true color 'white': this
    is more officially mapped to "common grey", and is often the default
    foreground color.
  - ``bright_white``: is pure white (``#ffffff``).


white-on-black
~~~~~~~~~~~~~~

The default foreground and background should be assumed as *white-on-black*.

For quite some time, the families of terminals produced by DEC, IBM, and
Tektronix dominated the computing world with the default color scheme of
*green-on-black* and less commonly *amber-on-black* monochrome displays:
The inverse was a non-default configuration.  The IBM 3270 clients exclusively
used *green-on-black* in both hardware and software emulators, and is likely
a driving factor of the default *white-on-black* appearance of the first IBM
Personal Computer.

The less common *black-on-white* "ink paper" style of emulators is a valid
concern for those designing terminal interfaces.  The color scheme of
*black-on-white* directly conflicts with the intention of `bold is bright`_,
where ``term.bright_red('ATTENTION!')`` may become difficult to read,
as it appears as *pink on white*!


History of ink-paper inspired black-on-white
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Early home computers with color video adapters, such as the Commodore 64
provided *white-on-blue* as their basic video terminal configuration.  One can
only assume such appearances were provided to demonstrate their color
capabilities over competitors (such as the Apple ][).

More common, X11's xterm and the software HyperTerm bundle with MS Windows
provided an "ink on paper" *black-on-white* appearance as their default
configuration.  Two popular emulators continue to supply *black-on-white* by
default to this day: Xorg's xterm and Apple's Terminal.app.

.. note:: Windows no longer supplies a terminal emulator: the "command prompt"
   as we know it now uses the MSVCRT API routines to interact and does not
   make use of terminal sequences, even ignoring those sequences that MS-DOS
   family of systems previously interpreted through the ANSI.SYS driver,
   though it continues to default to *white-on-black*.


Bold is bright
--------------

**Where Bold is used, it should be assumed to be *Bright***.

Due to the influence of early graphics adapters providing a set of 8
"low-intensity" and 8 "high intensity" versions of the first, the term
"bold" for terminals sequences is synonymous with "high intensity" in
almost all circumstances.


History of bold as "wide stroke"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In typography, the true translation of "bold" is that a font should be
displayed *with emphasis*.  In classical terms, this would be achieved by
pen be re-writing over the same letters.  On a teletype or printer, this was
similarly achieved by writing a character, backspacing, then repeating the
same character in a form called **overstriking**.

To bold a character, ``C``, one would emit the sequence ``C^HC`` where
``^H`` is backspace (0x08).  To underline ``C``, one would would emit
``C^H_``.

**Video terminals do not support overstriking**.  Though the mdoc format for
manual pages continue to emit overstriking sequences for bold and underline,
translators such as mandoc will instead emit an appropriate terminal sequence.

Many characters previously displayable by combining using overstriking of
ASCII characters on teletypes, such as: ±, ≠, or ⩝ were delegated to a
`code page`_ or lost entirely until the introduction of multibyte encodings.

Much like the "ink paper" introduction in windowing systems for terminal
emulators, "wide stroke" bold was introduced only much later when combined
with operating systems that provided font routines such as TrueType.


Enforcing white-on-black
~~~~~~~~~~~~~~~~~~~~~~~~

In conclusion, *white-on-black* should be considered the default.  If there is
a need to **enforce** *white-on-black* for terminal clients suspected to be
defaulted as *black-on-white*, one would want to trust that a combination of
``term.home + term.white_on_black + term.clear`` should repaint the entire
emulator's window with the desired effect.

However, this cannot be trusted to **all** terminal emulators to perform
correctly!  Depending on your audience, you may instead ensure that the
entire screen (including whitespace) is painted using the ``on_black``
mnemonic.

Beware of customized color schemes
----------------------------------

A recent phenomenon is for users to customize these first 16 colors of their
preferred emulator to colors of their own liking.  Though this has always been
possible with ``~/.XResources``, the introduction of PuTTy and iTerm2 to
interactively adjustment these colors have made this much more common.

This may cause your audience to see your intended interface in a wildly
different form.  Your intended presentation may appear mildly unreadable.

Users are certainly free to customize their colors however they like, but it
should be known that displaying ``term.black_on_red("DANGER!")`` may appear
as "grey on pastel red" to your audience, reducing the intended effect of
intensity.


256 colors can avoid customization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first instinct of a user who aliases ls(1) to ``ls -G`` or ``colorls``,
when faced with the particularly low intensity of the default ``blue``
attribute is **to adjust their terminal emulator's color scheme of the base
16 colors**.

This is not necessary: the environment variable ``LSCOLORS`` may be redefined
to map an alternative color for blue, or to use ``bright_blue`` in its place.

Furthermore, all common terminal text editors such as emacs or vim may be
configured with "colorschemes" to make use of the 256-color support found in
most modern emulators.  Many readable shades of blue are available, and many
programs that emit such colors can be configured to emit a higher or lower
intensity variant from the full 256 color space through program configuration.


Monochrome and reverse
----------------------

Note that ``reverse`` takes the current foreground and background colors and
reverses them.  In contrast, the compound formatter ``black_on_red`` would
fail to set the background *or* foreground color on a monochrome display,
resulting in the same stylization as ``normal`` -- it would not appear any
different!

If your userbase consists of monochrome terminals, you may wish to provide
"lightbars" and other such effects using the compound formatter
``red_reverse``.  In the literal sense of "set foreground color to red, then
swap foreground and background", this produces a similar effect on
**both** color and monochrome displays.

For text, very few ``{color}_on_{color}`` formatters are visible with the
base 16 colors, so you should generally wish for ``black_on_{color}``
anyway.  By using ``{color}_reverse`` you may be portable with monochrome
displays as well.


Multibyte Encodings and Code pages
----------------------------------

A terminal that supports both multibyte encodings (UTF-8) and legacy 8-bit
code pages (ISO 2022) may instruct the terminal to switch between both
modes using the following sequences:

  - ``\x1b%G`` activates UTF-8 with an unspecified implementation level
    from ISO 2022 in a way that allows to go back to ISO 2022 again.
  - ``\x1b%@`` goes back from UTF-8 to ISO 2022 in case UTF-8 had been
    entered via ``\x1b%G``.
  - ``\x1b%/G`` switches to UTF-8 Level 1 with no return.
  - ``\x1b%/H`` switches to UTF-8 Level 2 with no return.
  - ``\x1b%/I`` switches to UTF-8 Level 3 with no return.

When a terminal is in ISO 2022 mode, you may use a sequence
to request a terminal to change its `code page`_.  It begins by ``\x1b(``,
followed by an ASCII character representing a code page selection.  For
example ``\x1b(U`` on the legacy VGA Linux console switches to the `IBM CP437`_
`code page`_, allowing North American MS-DOS artwork to be displayed in its
natural 8-bit byte encoding.  A list of standard codes and the expected code
page may be found on Thomas E. Dickey's xterm control sequences section on
sequences following the `Control-Sequence-Inducer`_.

For more information, see `What are the issues related to UTF-8 terminal
emulators? <http://www.cl.cam.ac.uk/~mgk25/unicode.html#term>`_ by
`Markus Kuhn <http://www.cl.cam.ac.uk/~mgk25/>`_ of the University of
Cambridge.

Detecting multibyte
~~~~~~~~~~~~~~~~~~~

One can be assured that the connecting client is capable of representing
UTF-8 and other multibyte character encodings by the Environment variable
``LANG``.  If this is not possible, there is an alternative method:

  - Emit Report Cursor Position (CPR), ``\x1b[6n`` and store response.
  - Emit a multibyte UTF-8 character, such as ⦰ (``\x29\xb0``).
  - Emit Report Cursor Position (CPR), ``\x1b[6n`` and store response.
  - Determine the difference of the *(y, x)* location of the response.
    If it is *1*, then the client decoded the two UTF-8 bytes as a
    single character, and can be considered capable.  If it is *2*,
    the client is using a `code page`_ and is incapable of decoding
    a UTF-8 bytestream.

Note that both SSH and Telnet protocols provide means for forwarding
the ``LANG`` environment variable.  However, some transports such as
a link by serial cable is incapable of forwarding Environment variables.

Detecting screen size
~~~~~~~~~~~~~~~~~~~~~

While we're on the subject, there are times when :attr:`height` and
:attr:`width` are not accurate -- when a transport does not provide the means
to propagate the COLUMNS and ROWS Environment values, or propagate the
SIGWINCH signals, such as through a serial link.

The same means described above for multibyte encoding detection may be used to
detect the remote client's window size:

  - Move cursor to row 999, 999.
  - Emit Report Cursor Position (CPR), ``\x1b[6n`` and store response.
  - The return value is the window dimensions of the client.

This is the method used by the program ``resize`` provided in the Xorg
distribution, and its source may be viewed as file `resize.c`_.

Alt or meta sends Escape
------------------------

Programs using GNU readline such as bash continue to provide default mappings
such as *ALT+u* to uppercase the word after cursor.  This is achieved
by the configuration option altSendsEscape or `metaSendsEscape
<http://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h2-Alt-and-Meta-Keys>`_

The default for most terminals, however, is that the meta key is bound by
the operating system (such as *META + F* for find), and that *ALT* is used
for inserting international keys (where the combination *ALT+u, a* is used
to insert the character ``ä``).

It is therefore a recommendation to **avoid alt or meta keys entirely** in
applications, and instead prefer the ctrl-key combinations, so as to avoid
instructing your users to configure their terminal emulators to communicate
such sequences.

If you wish to allow them optionally (such as through readline), the ability
to detect alt or meta key combinations is achieved by prefacing the combining
character with escape, so that *ALT+z* becomes *Escape + z* (or, in raw form
``\x1bz``).  Blessings currently provides no further assistance in detecting
these key combinations.


Backspace sends delete
----------------------

Typically, backspace is ``^H`` (8, or 0x08) and delete is ^? (127, or 0x7f).

On some systems however, the key for backspace is actually labeled and
transmitted as "delete", though its function in the operating system behaves
just as backspace.

It is highly recommend to accept **both** ``KEY_DELETE`` and ``KEY_BACKSPACE``
as having the same meaning except when implementing full screen editors,
and provide a choice to enable the delete mode by configuration.

The misnomer of ANSI
--------------------

When people say 'ANSI Sequence', they are discussing:

- Standard `ECMA-48`_: Control Functions for Coded Character Sets

- `ANSI X3.64 <http://sydney.edu.au/engineering/it/~tapted/ansi.html>`_ from
  1981, when the `American National Standards Institute
  <http://www.ansi.org/>`_ adopted the `ECMA-48`_ as standard, which was later
  withdrawn in 1997 (so in this sense it is *not* an ANSI standard).

- The `ANSI.SYS`_ driver provided in MS-DOS and
  clones.  The popularity of the IBM Personal Computer and MS-DOS of the era,
  and its ability to display colored text further populated the idea that such
  text "is ANSI".

- The various code pages used in MS-DOS Personal Computers,
  providing "block art" characters in the 8th bit (int 127-255), paired
  with `ECMA-48`_ sequences supported by the MS-DOS `ANSI.SYS`_ driver
  to create artwork, known as `ANSI art <http://pc.textmod.es/>`_.

- The ANSI terminal database entry and its many descendants in the
  `terminfo database
  <http://invisible-island.net/ncurses/terminfo.src.html>`_.  This is mostly
  due to terminals compatible with SCO UNIX, which was the successor of
  Microsoft's Xenix, which brought some semblance of the Microsoft DOS
  `ANSI.SYS`_ driver capabilities.

- `Select Graphics Rendition (SGR) <http://vt100.net/docs/vt510-rm/SGR>`_
  on vt100 clones, which include many of the common sequences in `ECMA-48`_.

- Any sequence started by the `Control-Sequence-Inducer`_ is often
  mistakenly termed as an "ANSI Escape Sequence" though not appearing in
  `ECMA-48`_ or interpreted by the `ANSI.SYS`_ driver. The adjoining phrase
  "Escape Sequence" is so termed because it follows the ASCII character
  for the escape key (ESC, ``\x1b``).

.. _code page: https://en.wikipedia.org/wiki/Code_page
.. _IBM CP437: https://en.wikipedia.org/wiki/Code_page_437
.. _CGA Color Palette: https://en.wikipedia.org/wiki/Color_Graphics_Adapter#With_an_RGBI_monitor
.. _f.lux: https://justgetflux.com/
.. _ZX Spectrum: https://en.wikipedia.org/wiki/List_of_8-bit_computer_hardware_palettes#ZX_Spectrum
.. _Control-Sequence-Inducer: http://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h2-Controls-beginning-with-ESC
.. _resize.c: http://www.opensource.apple.com/source/X11apps/X11apps-13/xterm/xterm-207/resize.c
.. _ANSI.SYS: http://www.kegel.com/nansi/
.. _ECMA-48: http://www.ecma-international.org/publications/standards/Ecma-048.htm
