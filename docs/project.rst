Project
=======

**Bugs** or suggestions? Visit the `issue tracker`_ and file an issue.  We welcome your bug reports
and feature suggestions!

Are you stuck and need **support**?  Give `stackoverflow`_ a try.  If you're still having trouble,
we'd like to hear about it!  Open an issue in the `issue tracker`_ with a well-formed question.

Would you like to **contribute**?  That's awesome! Pull Requests are always welcome!

Fork
----

*Blessed* is a fork of `blessings <https://github.com/erikrose/blessings>`_. Apologies for the fork,
I just couldn't get the :doc:`keyboard`, and later :doc:`location` or :doc:`measuring` code accepted
upstream after two major initiatives, the effort was better spent in a fork, where the code is
accepted.

Furthermore, a project in the node.js language of the `same name, blessed
<https://github.com/chjj/blessed>`_, is **not** related, or a fork of each other in any way.

License
-------

*Blessed* is under the MIT License. See the `LICENSE
<https://github.com/jquast/blessed/blob/master/LICENSE>`_  file. Please enjoy!

Running Tests
-------------

Install and run tox::

    pip install --upgrade tox
    tox

Py.test is used as the test runner, and with the tox target supporting positional arguments, you may
for example use `looponfailing
<https://docs.pytest.org/en/3.0.1/xdist.html#running-tests-in-looponfailing-mode>`_ with python 3.7,
stopping at the first failing test case, and looping (retrying) after a filesystem save is
detected::

    tox -epy37 -- -fx

The test runner (``tox``) ensures all code and documentation complies with standard python style
guides, pep8 and pep257, as well as various static analysis tools.

.. warning::
   When you contribute a new feature, make sure it is covered by tests.

   Likewise, some bug fixes should include a test demonstrating the bug.

Further Reading
---------------

As a developer's API, blessed is often bundled with frameworks and toolsets that dive deeper into
Terminal I/O programming than :class:`~.Terminal` offers.  Here are some recommended readings to
help you along:

- The :linuxman:`terminfo(5)` manpage of your preferred posix-like operating system. The
  capabilities available as attributes of :class:`~.Terminal` are directly mapped to those listed in
  the column **Cap-name**.

- The :linuxman:`termios(3)` of your preferred posix-like operating system.

- `The TTY demystified <http://www.linusakesson.net/programming/tty/index.php>`_ by Linus Åkesson.

- `A Brief Introduction to Termios
  <https://blog.nelhage.com/2009/12/a-brief-introduction-to-termios/>`_ by Nelson Elhage.

- Richard Steven's `Advance Unix Programming
  <https://www.amazon.com/exec/obidos/ISBN=0201563177/wrichardstevensA/>`_ ("AUP") provides two very
  good chapters, "Terminal I/O" and "Pseudo Terminals".

- GNU's `The Termcap Manual
  <https://www.gnu.org/software/termutils/manual/termcap-1.3/html_mono/termcap.html>`_ by Richard M.
  Stallman.

- `Chapter 4
  <http://compsci.hunter.cuny.edu/~sweiss/course_materials/unix_lecture_notes/chapter_04.pdf>`_ of
  CUNY's course material for *Introduction to System Programming*, by `Stewart Weiss
  <http://compsci.hunter.cuny.edu/~sweiss/>`_

- `Chapter 11 <https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap11.html>`_ of the
  IEEE Open Group Base Specifications Issue 7, "General Terminal Interface"

- The GNU C Library documentation, section `Low-Level Terminal Interface
  <http://www.gnu.org/software/libc/manual/html_mono/libc.html#toc-Low_002dLevel-Terminal-Interface-1>`_

- The source code of many popular terminal emulators.  If there is ever any question of "the meaning
  of a terminal capability", or whether or not your preferred terminal emulator actually handles
  them, read the source! Many modern terminal emulators are now based on `libvte <https://github.com/GNOME/vte>`_.

- The source code of the :linuxman:`tty(4)`, :linuxman:`pty(7)`, and the given "console driver" for
  any posix-like operating system.  If you search thoroughly enough, you will eventually discover a
  terminal sequence decoder, usually a ``case`` switch that translates ``\x1b[0m`` into a "reset
  color" action towards the video driver.  Though ``tty.c`` linked here is probably not the most
  interesting, it can get you started:

     - `FreeBSD <https://github.com/freebsd/freebsd/blob/master/sys/kern/tty.c>`_
     - `OpenBSD <http://cvsweb.openbsd.org/cgi-bin/cvsweb/~checkout~/src/sys/kern/tty.c?content-type=text/plain>`_
     - `Illumos (Solaris) <https://github.com/illumos/illumos-gate/blob/master/usr/src/uts/common/io/tty_common.c>`_
     - `Minix <https://github.com/Stichting-MINIX-Research-Foundation/minix/blob/master/minix/drivers/tty/tty/tty.c>`_
     - `Linux <https://github.com/torvalds/linux/blob/master/drivers/tty/n_tty.c>`_

- `Thomas E. Dickey <https://invisible-island.net/>`_ has been maintaining `xterm
  <https://invisible-island.net/xterm/xterm.html>`_, as well as a primary maintainer of many related
  packages such as `ncurses <https://invisible-island.net/ncurses/ncurses.html>`_ for quite a long
  while. His consistent, well-documented, long-term dedication to xterm, curses, and the many
  related projects is world-renown.

- `termcap & terminfo (O'Reilly Nutshell)
  <https://www.amazon.com/termcap-terminfo-OReilly-Nutshell-Linda/dp/0937175226>`_ by Linda Mui, Tim
  O'Reilly, and John Strang.

- Note that System-V systems, also known as `Unix98
  <https://en.wikipedia.org/wiki/Single_UNIX_Specification>`_ (SunOS, HP-UX, AIX and others) use a
  `Streams <https://en.wikipedia.org/wiki/STREAMS>`_ interface.  On these systems, the `ioctl(2)
  <https://pubs.opengroup.org/onlinepubs/009695399/functions/ioctl.html>`_ interface provides the
  ``PUSH`` and ``POP`` parameters to communicate with a Streams device driver, which differs
  significantly from Linux and BSD.

  Many of these systems provide compatible interfaces for Linux, but they may not always be as
  complete as the counterpart they emulate, most especially in regards to managing pseudo-terminals.

The misnomer of ANSI
--------------------

When people say 'ANSI', they are discussing:

- Standard `ECMA-48`_: Control Functions for Coded Character Sets

- `ANSI X3.64 <https://en.wikipedia.org/wiki/ANSI_escape_code#History>`_ from 1981, when the
  `American National Standards Institute <https://www.ansi.org/>`_ adopted the `ECMA-48`_ as
  standard, which was later withdrawn in 1997 (so in this sense it is *not* an ANSI standard).

- The `ANSI.SYS`_ driver provided in MS-DOS and clones.  The popularity of the IBM Personal Computer
  and MS-DOS of the era, and its ability to display colored text further populated the idea that
  such text "is ANSI".

- The various code pages used in MS-DOS Personal Computers, providing "block art" characters in the
  8th bit (int 127-255), paired with `ECMA-48`_ sequences supported by the MS-DOS `ANSI.SYS`_ driver
  to create artwork, known as `ANSI art <https://16colo.rs/>`_.

- The ANSI terminal database entry and its many descendants in the `terminfo database
  <https://invisible-island.net/ncurses/terminfo.src.html>`_.  This is mostly due to terminals
  compatible with SCO UNIX, which was the successor of Microsoft's Xenix, which brought some
  semblance of the Microsoft DOS `ANSI.SYS`_ driver capabilities.

- `Select Graphics Rendition (SGR) <https://vt100.net/docs/vt510-rm/SGR>`_
  on vt100 clones, which include many of the common sequences in `ECMA-48`_.

- Any sequence started by the `Control-Sequence-Inducer`_ is often mistakenly termed as an "ANSI
  Escape Sequence" though not appearing in `ECMA-48`_ or interpreted by the `ANSI.SYS`_ driver. The
  adjoining phrase "Escape Sequence" is so termed because it follows the ASCII character for the
  escape key (ESC, ``\x1b``).

.. _`issue tracker`: https://github.com/jquast/blessed/issues/
.. _`stackoverflow`: https://stackoverflow.com/
.. _code page: https://en.wikipedia.org/wiki/Code_page
.. _IBM CP437: https://en.wikipedia.org/wiki/Code_page_437
.. _Control-Sequence-Inducer: https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h2-Controls-beginning-with-ESC
.. _ANSI.SYS: http://www.kegel.com/nansi/
.. _ECMA-48: http://www.ecma-international.org/publications/standards/Ecma-048.htm
