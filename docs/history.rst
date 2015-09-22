Version History
===============

1.7

    **new features**:

      - Context manager :meth:`~.cbreak`, which is equivalent to
        entering terminal state by :func:`tty.setcbreak` and returning
        on exit, as well as the lesser recommended :meth:`~.raw`,
        pairing from :func:`tty.setraw`.
      - :meth:`~.inkey` returns one or more characters received by
        the keyboard as a unicode sequence, with additional attributes
        :attr:`~.Keystroke.code` and :attr:`~.Keystroke.name`.  When
        the return value of :attr:`~.Keystroke.code` is not ``None``,
        a multi-byte sequence was received, allowing application keys
        (such as arrow keys) to be detected.
      - Context manager :meth:`~.keypad` emits sequences that enable
        "application keys" such as the diagonal keys on the numpad.
        This is equivalent to :meth:`curses.window.keypad`.
      - :meth:`~.Terminal.center`, :meth:`~.Terminal.rjust`, and
        :meth:`~.Terminal.ljust` aligns text containing sequences and CJK
        (double-width) characters to be aligned to terminal width, or by
        ``width`` argument specified.
      - :meth:`~.wrap`:  Allows text containing sequences to be
        word-wrapped without breaking mid-sequence, honoring their
        printable width.
      - :meth:`~.Terminal.strip`: strip all sequences *and* whitespace.
      - :meth:`~.Terminal.strip_seqs` strip only sequences.
      - :meth:`~.Terminal.rstrip` and :meth:`~.Terminal.lstrip` strips both
        sequences and trailing or leading whitespace, respectively.
      - Ignore :class:`curses.error` message ``'tparm() returned NULL'``:
        this occurs on win32 or other platforms using a limited curses
        implementation, such as PDCurses_, where :func:`curses.tparm` is
        not implemented, or no terminal capability database is available.
      - New public attribute: :attr:`~.kind`: the very same as given
        by the keyword argument of the same (or, determined by and
        equivalent to the ``TERM`` Environment variable).
      - Some attributes are now properties and raise exceptions when assigned,
        enforcing their immutable state representation: :attr:`~.kind`,
        :attr:`~.height`, :attr:`~.width`, :attr:`~.number_of_colors`.
      - Allow ``hpa``, ``vpa``, ``civis``, and ``cnorm`` termcap entries
        (of friendly names ``move_x``, ``move_y``, ``hide_cursor``,
        and ``normal_hide``) to work on tmux(1) or screen(1) by emulating
        support by proxy if they are not offered by the termcap database.
      - pypy is now a supported python platform implementation.
      - enhanced sphinx documentation.

    **testing improvements**:

      - The '2to3' tool is no longer used for python 3 support
      - Converted nose tests to pytest via tox. Added a TeamCity build farm to
        include OSX and FreeBSD testing. ``tox`` is now the primary entry point
        with which to execute tests, run static analysis, and build
        documentation.
      - py.test fixtures and ``@as_subprocess`` decorator for testing of many
        more terminal types than just 'xterm-256-color' as previously tested.
      - ``setup.py develop`` ensures a virtualenv and installs tox.
      - 100% (combined) coverage.


    **bug fixes**:

      - Cannot call :func:`curses.setupterm` more than once per process
        (from :meth:`Terminal.__init__`): emit a warning about what terminal
        kind subsequent calls will use.  Previously, blessed pretended
        to support a new terminal :attr:`~.kind`, but was actually using
        the :attr:`~.kind` specified by the first instantiation of
        :class:`~.Terminal`.
      - Allow unsupported terminal capabilities to be callable just as
        supported capabilities, so that the return value of
        :attr:`~.color`\(n) may be called on terminals without color
        capabilities.
      - :attr:`~.number_of_colors` failed when :attr:`~.does_styling` is
        ``False``.
      - Warn and set :attr:`~.does_styling` to ``False`` when the given
        :attr:`~.kind`` is not found in the terminal capability database.
      - For terminals without underline, such as vt220,
        ``term.underline('text')`` would emit ``u'text' + term.normal``.
        Now it only emits ``u'text'``.
      - Ensure :class:`~.FormattingString` and
        :class:`~.ParameterizingString` may be pickled.
      - Do not ignore :class:`curses.error` exceptions, unhandled curses
        errors are legitimate errors and should be reported as a bug.

    **depreciation**:
    python2.5 is no longer supported.  This is because
    it has become difficult to support through the testing frameworks,
    namely: tox, py.test, Travis CI and many other build and testing
    dependencies.


1.6
  * Add :attr:`~.does_styling`. This takes :attr:`~.force_styling`
    into account and should replace most uses of :attr:`~.is_a_tty`.
  * Make :attr:`~.is_a_tty` a read-only property like :attr:`~.does_styling`.
    Writing to it never would have done anything constructive.
  * Add :meth:`~.fullscreen`` and :meth:`hidden_cursor` to the
    auto-generated docs.

1.5.1
  * Clean up fabfile, removing the redundant ``test`` command.
  * Add Travis support.
  * Make ``python setup.py test`` work without spurious errors on 2.6.
  * Work around a tox parsing bug in its config file.
  * Make context managers clean up after themselves even if there's an
    exception (Vitja Makarov :ghpull:`29`).
  * Parameterizing a capability no longer crashes when there is no tty
    (Vitja Makarov :ghpull:`31`)

1.5
  * Add syntactic sugar and documentation for ``enter_fullscreen``
    and ``exit_fullscreen``.
  * Add context managers :meth:`~.fullscreen` and :meth:`~.hidden_cursor`.
  * Now you can force a :class:`~.Terminal` to never to emit styles by
    passing keyword argument ``force_styling=None``.

1.4
  * Add syntactic sugar for cursor visibility control and single-space-movement
    capabilities.
  * Endorse the :meth:`~.location` context manager for restoring cursor
    position after a series of manual movements.
  * Fix a bug in which :meth:`~.location` that wouldn't do anything when
    passed zeros.
  * Allow tests to be run with ``python setup.py test``.

1.3
  * Added :attr:`~.number_of_colors`, which tells you how many colors the
    terminal supports.
  * Made :attr:`~.color`\(n) and :attr:`~.on_color`\(n) callable to wrap a
    string, like the named colors can. Also, make them both fall back to the
    ``setf`` and ``setb`` capabilities (like the named colors do) if the
    termcap entries for ``setaf`` and ``setab`` are not available.
  * Allowed :attr:`~.color` to act as an unparametrized string, not just a
    callable.
  * Made :attr:`~.height` and :attr:`~.width` examine any passed-in stream
    before falling back to stdout (This rarely if ever affects actual behavior;
    it's mostly philosophical).
  * Made caching simpler and slightly more efficient.
  * Got rid of a reference cycle between :class:`~.Terminal` and
    :class:`~.FormattingString`.
  * Updated docs to reflect that terminal addressing (as in :meth:`~location`)
    is 0-based.

1.2
  * Added support for Python 3! We need 3.2.3 or greater, because the curses
    library couldn't decide whether to accept strs or bytes before that
    (http://bugs.python.org/issue10570).
  * Everything that comes out of the library is now unicode. This lets us
    support Python 3 without making a mess of the code, and Python 2 should
    continue to work unless you were testing types (and badly). Please file a
    bug if this causes trouble for you.
  * Changed to the MIT License for better world domination.
  * Added Sphinx docs.

1.1
  * Added nicely named attributes for colors.
  * Introduced compound formatting.
  * Added wrapper behavior for styling and colors.
  * Let you force capabilities to be non-empty, even if the output stream is
    not a terminal.
  * Added :attr:`~.is_a_tty` to determine whether the output stream is a
    terminal.
  * Sugared the remaining interesting string capabilities.
  * Allow :meth:`~.location` to operate on just an x *or* y coordinate.

1.0
  * Extracted Blessed from `nose-progressive`_.


.. _`jquast/blessed`: https://github.com/jquast/blessed
.. _PDCurses: http://www.lfd.uci.edu/~gohlke/pythonlibs/#curses
.. _`nose-progressive`: https://pypi.python.org/pypi/nose-progressive/
