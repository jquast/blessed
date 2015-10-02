Further Reading
===============

As a developer's API, blessed is often bundled with frameworks and toolsets
that dive deeper into Terminal I/O programming than :class:`~.Terminal` offers.
Here are some recommended readings to help you along:

- `terminfo(5)
  <http://invisible-island.net/ncurses/man/terminfo.5.html>`_
  manpage of your preferred posix-like operating system. The capabilities
  available as attributes of :class:`~.Terminal` are directly mapped to those
  listed in the column **Cap-name**.

- `termios(4)
  <http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man4/termios.4>`_
  of your preferred posix-like operating system.

- `The TTY demystified
  <http://www.linusakesson.net/programming/tty/index.php>`_
  by Linus Åkesson.

- `A Brief Introduction to Termios
  <https://blog.nelhage.com/2009/12/a-brief-introduction-to-termios/>`_ by
  Nelson Elhage.

- Richard Steven's `Advance Unix Programming
  <http://www.amazon.com/exec/obidos/ISBN=0201563177/wrichardstevensA/>`_
  ("AUP") provides two very good chapters, "Terminal I/O" and
  "Pseudo Terminals".

- GNU's `The Termcap Manual
  <https://www.gnu.org/software/termutils/manual/termcap-1.3/html_mono/termcap.html>`_
  by Richard M. Stallman.

- `Chapter 4 <http://compsci.hunter.cuny.edu/~sweiss/course_materials/unix_lecture_notes/chapter_04.pdf>`_
  of CUNY's course material for *Introduction to System Programming*, by
  `Stewart Weiss <http://compsci.hunter.cuny.edu/~sweiss/>`_

- `Chapter 11
  <http://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap11.html>`_
  of the IEEE Open Group Base Specifications Issue 7, "General Terminal
  Interface"

- The GNU C Library documentation, section `Low-Level Terminal Interface
  <http://www.gnu.org/software/libc/manual/html_mono/libc.html#toc-Low_002dLevel-Terminal-Interface-1>`_

- The source code of many popular terminal emulators.  If there is ever any
  question of "the meaning of a terminal capability", or whether or not your
  preferred terminal emulator actually handles them, read the source!

  These are often written in the C language, and directly map the
  "Control Sequence Inducers" (CSI, literally ``\x1b[`` for most modern
  terminal types) emitted by most terminal capabilities to an action in a
  series of ``case`` switch statements.

  - Many modern libraries are now based on `libvte
    <https://github.com/GNOME/vte>`_ (or just 'vte'): Gnome Terminal,
    sakura, Terminator, Lilyterm, ROXTerm, evilvte, Termit, Termite, Tilda,
    tinyterm, lxterminal.
  - xterm, urxvt, SyncTerm, and EtherTerm.
  - There are far too many to name, Chose one you like!


- The source code of the tty(4), pty(4), and the given "console driver" for
  any posix-like operating system.  If you search thoroughly enough, you will
  eventually discover a terminal sequence decoder, usually a ``case`` switch
  that translates ``\x1b[0m`` into a "reset color" action towards the video
  driver.  Though ``tty.c`` is linked here (the only kernel file common among
  them), it is probably not the most interesting, but it can get you started:

     - `FreeBSD <https://github.com/freebsd/freebsd/blob/master/sys/kern/tty.c>`_
     - `OpenBSD <http://cvsweb.openbsd.org/cgi-bin/cvsweb/~checkout~/src/sys/kern/tty.c?content-type=text/plain>`_
     - `Illumos (Solaris) <https://github.com/illumos/illumos-gate/blob/master/usr/src/uts/common/io/tty_common.c>`_
     - `Minix <https://github.com/minix3/minix/blob/master/minix/drivers/tty/tty/tty.c>`_
     - `Linux <https://github.com/torvalds/linux/blob/master/drivers/tty/n_tty.c>`_

  The TTY driver is a great introduction to Kernel and Systems programming,
  because familiar components may be discovered and experimented with.  It is
  available on all operating systems (except windows), and because of its
  critical nature, examples of efficient file I/O, character buffers (often
  implemented as "ring buffers") and even fine-grained kernel locking can be
  found.

- `Thomas E. Dickey <http://invisible-island.net/>`_ has been maintaining
  `xterm <http://invisible-island.net/xterm/xterm.html>`_, as well as a
  primary maintainer of many related packages such as `ncurses
  <http://invisible-island.net/ncurses/ncurses.html>`_ for quite a long
  while.

- `termcap & terminfo (O'Reilly Nutshell)
  <http://www.amazon.com/termcap-terminfo-OReilly-Nutshell-Linda/dp/0937175226>`_
  by Linda Mui, Tim O'Reilly, and John Strang.

- Note that System-V systems, also known as `Unix98
  <https://en.wikipedia.org/wiki/Single_UNIX_Specification>`_ (SunOS, HP-UX,
  AIX and others) use a `Streams <https://en.wikipedia.org/wiki/STREAMS>`_
  interface.  On these systems, the `ioctl(2)
  <http://pubs.opengroup.org/onlinepubs/009695399/functions/ioctl.html>`_
  interface provides the ``PUSH`` and ``POP`` parameters to communicate with
  a Streams device driver, which differs significantly from Linux and BSD.

  Many of these systems provide compatible interfaces for Linux, but they may
  not always be as complete as the counterpart they emulate, most especially
  in regards to managing pseudo-terminals.
