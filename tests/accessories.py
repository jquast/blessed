"""Accessories for automated py.test runner."""

# std imports
import os
import sys
import codecs
import traceback
import contextlib
import time
import signal

# local
from blessed import Terminal
from blessed.dec_modes import DecModeResponse
# local
from .conftest import IS_WINDOWS

if IS_WINDOWS:
    # 3rd party
    import jinxed as curses  # pylint: disable=import-error
else:
    # std imports
    import pty
    import curses
    import termios

MAX_SUBPROC_TIME_SECONDS = 2  # no test should ever take over 2 seconds
test_kind = 'vtwin10' if IS_WINDOWS else 'xterm-256color'


def TestTerminal(is_a_tty=None, **kwargs):  # type: (...) -> Terminal
    """
    Create a Terminal instance with optional is_a_tty override.

    'is_a_tty' is useful to pass "is a tty" tests without pty_test
    """
    if 'kind' not in kwargs:
        kwargs['kind'] = test_kind
    term = Terminal(**kwargs)
    if is_a_tty is not None:
        term._is_a_tty = is_a_tty
    return term


SEND_SEMAPHORE = SEMAPHORE = b'SEMAPHORE\n'
RECV_SEMAPHORE = b'SEMAPHORE\r\n'


def make_enabled_dec_cache():
    """Create a dec_mode_cache with all DEC event modes enabled."""
    return {
        2004: DecModeResponse.SET,  # BRACKETED_PASTE
        1000: DecModeResponse.SET,  # MOUSE_REPORT_CLICK
        1002: DecModeResponse.SET,  # MOUSE_REPORT_DRAG
        1003: DecModeResponse.SET,  # MOUSE_ALL_MOTION
        1001: DecModeResponse.SET,  # MOUSE_HILITE_TRACKING
        1004: DecModeResponse.SET,  # FOCUS_IN_OUT_EVENTS
        1006: DecModeResponse.SET,  # MOUSE_EXTENDED_SGR
        1016: DecModeResponse.SET,  # MOUSE_SGR_PIXELS
        2048: DecModeResponse.SET,  # IN_BAND_WINDOW_RESIZE
    }


def init_subproc_coverage(run_note):
    """Run coverage on subprocess"""
    try:
        # 3rd party
        import coverage
    except ImportError:
        return None
    _coveragerc = os.path.join(
        os.path.dirname(__file__),
        os.pardir, 'tox.ini')
    cov = coverage.Coverage(config_file=_coveragerc)
    cov.start()
    return cov


class as_subprocess():  # pylint: disable=too-few-public-methods
    """This helper executes test cases in a child process, avoiding a python-internal bug of
    _curses: setupterm() may not be called more than once per process."""
    _CHILD_PID = 0
    encoding = 'utf8'

    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        # pylint: disable=too-many-locals,too-complex,too-many-branches,too-many-statements
        if IS_WINDOWS:
            self.func(*args, **kwargs)
            return

        pid_testrunner = os.getpid()
        pid, master_fd = pty.fork()  # pylint: disable=possibly-used-before-assignment
        if pid == self._CHILD_PID:
            # child process executes function, raises exception
            # if failed, causing a non-zero exit code, using the
            # protected _exit() function of ``os``; to prevent the
            # 'SystemExit' exception from being thrown.
            cov = init_subproc_coverage(
                f"@as_subprocess-{os.getpid()};{self.func}(*{args}, **{kwargs})"
            )
            try:
                self.func(*args, **kwargs)
            except Exception:  # pylint: disable=broad-except
                e_type, e_value, e_tb = sys.exc_info()
                o_err = [line.rstrip().encode('utf-8') for line in traceback.format_tb(e_tb)]
                o_err.append(('-=' * 20).encode('ascii'))
                o_err.extend([_exc.rstrip().encode('utf-8') for _exc in
                              traceback.format_exception_only(
                                  e_type, e_value)])
                os.write(sys.__stdout__.fileno(), b'\n'.join(o_err))
                os.close(sys.__stdout__.fileno())
                os.close(sys.__stderr__.fileno())
                os.close(sys.__stdin__.fileno())
                if cov is not None:
                    cov.stop()
                    cov.save()
                os._exit(1)
            else:
                if cov is not None:
                    cov.stop()
                    cov.save()
                os._exit(0)

        # detect rare fork in test runner, when bad bugs happen
        if pid_testrunner != os.getpid():
            print(f'TEST RUNNER HAS FORKED, {pid_testrunner}=>{os.getpid()}: EXIT', file=sys.stderr)
            os._exit(1)

        exc_output = ''
        decoder = codecs.getincrementaldecoder(self.encoding)()
        while True:
            try:
                _exc = os.read(master_fd, 65534)
            except OSError:
                # linux EOF
                break
            if not _exc:
                # bsd EOF
                break
            exc_output += decoder.decode(_exc)

        # parent process asserts exit code is 0, causing test
        # to fail if child process raised an exception/assertion
        # Use non-blocking wait with timeout to detect hung child processes
        timeout = MAX_SUBPROC_TIME_SECONDS
        start_time = time.time()
        status = None
        while True:
            pid_result, status = os.waitpid(pid, os.WNOHANG)
            if pid_result != 0:
                # Child has exited
                break
            if time.time() - start_time > timeout:
                # Child hasn't exited, it's hung - kill it and report what we know
                try:
                    os.kill(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)  # Clean up zombie
                except OSError:
                    pass
                os.close(master_fd)
                # Show the output we captured - this likely contains the root cause
                exc_output_msg = (
                    f'Child process hung and did not exit within {timeout}s.\n'
                    f'Output captured from child:\n{"=" * 40}\n{exc_output}\n{"=" * 40}'
                )
                raise AssertionError(exc_output_msg)
            time.sleep(0.05)  # Poll every 50ms

        os.close(master_fd)

        # Display any output written by child process
        # (esp. any AssertionError exceptions written to stderr).
        exc_output_msg = f'Output in child process:\n{"=" * 40}\n{exc_output}\n{"=" * 40}'
        assert exc_output == '', exc_output_msg

        # Also test exit status is non-zero
        assert os.WEXITSTATUS(status) == 0


def read_until_semaphore(fd, semaphore=RECV_SEMAPHORE, encoding='utf8'):
    """
    Read file descriptor ``fd`` until ``semaphore`` is found.

    Used to ensure the child process is awake and ready. For timing tests; without a semaphore, the
    time to fork() would be (incorrectly) included in the duration of the test, which can be very
    length on continuous integration servers (such as Travis-CI).
    """
    # note that when a child process writes xyz\\n, the parent
    # process will read xyz\\r\\n -- this is how pseudo terminals
    # behave; a virtual terminal requires both carriage return and
    # line feed, it is only for convenience that \\n does both.
    outp = ''
    decoder = codecs.getincrementaldecoder(encoding)()
    semaphore = semaphore.decode('ascii')
    while not outp.startswith(semaphore):
        try:
            _exc = os.read(fd, 1)
        except OSError:  # Linux EOF
            break
        if not _exc:     # BSD EOF
            break
        outp += decoder.decode(_exc, final=False)
    assert outp.startswith(semaphore), (
        f'Semaphore not recv before EOF (expected: {semaphore!r}, got: {outp!r})'
    )
    return outp[len(semaphore):]


def read_until_eof(fd, encoding='utf8'):
    """
    Read file descriptor ``fd`` until EOF.

    Return decoded string.
    """
    decoder = codecs.getincrementaldecoder(encoding)()
    outp = ''
    while True:
        try:
            _exc = os.read(fd, 100)
        except OSError:  # linux EOF
            break
        if not _exc:  # bsd EOF
            break
        outp += decoder.decode(_exc, final=False)
    return outp


@contextlib.contextmanager
def echo_off(fd):
    """Ensure any bytes written to pty fd are not duplicated as output."""
    if not IS_WINDOWS:
        # pylint: disable=possibly-used-before-assignment
        try:
            attrs = termios.tcgetattr(fd)
            attrs[3] = attrs[3] & ~termios.ECHO
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
            yield
        finally:
            attrs[3] = attrs[3] | termios.ECHO
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
    else:
        yield


def unicode_cap(cap):
    """Return the result of ``tigetstr`` except as Unicode."""
    try:
        val = curses.tigetstr(cap)
    except curses.error:
        val = None

    return val.decode('latin1') if val else ''


def unicode_parm(cap, *parms):
    """Return the result of ``tparm(tigetstr())`` except as Unicode."""
    try:
        cap = curses.tigetstr(cap)
    except curses.error:
        cap = None
    if cap:
        try:
            val = curses.tparm(cap, *parms)
        except curses.error:
            val = None
        if val:
            return val.decode('latin1')
    return ''


def _setwinsize(fd, rows, cols):
    """Set PTY window size."""
    import struct  # pylint: disable=import-outside-toplevel
    import fcntl  # pylint: disable=import-outside-toplevel
    import termios as termios_mod  # pylint: disable=import-outside-toplevel
    TIOCSWINSZ = getattr(termios_mod, 'TIOCSWINSZ', -2146929561)
    # Note, assume ws_xpixel and ws_ypixel are zero.
    s = struct.pack('HHHH', rows, cols, 0, 0)
    fcntl.ioctl(fd, TIOCSWINSZ, s)


def pty_test(child_func, parent_func=None, test_name=None, rows=24, cols=80):
    """
    Wrapper for PTY-based tests to reduce boilerplate.

    Handles the common pattern of forking a PTY, running test code in the child
    process with coverage tracking, and optionally running parent-side code.

    Args:
        child_func: Function to run in child process. Receives a TestTerminal instance.
                   Should return bytes/str to write to stdout, or None.
        parent_func: Optional function to run in parent. Receives master_fd.
        test_name: Optional name for coverage tracking. Auto-derived from child_func if None.
        rows: Terminal height in rows (default 24)
        cols: Terminal width in columns (default 80)

    Returns:
        str: Output from child process (everything written to stdout)

    Example:
        def test_something():
            def child(term):
                with term.cbreak():
                    inp = term.inkey(timeout=0)
                    return inp.encode('utf-8')

            def parent(master_fd):
                os.write(master_fd, b'x')

            output = pty_test(child, parent)
            assert output == 'x'
    """
    # pylint: disable=too-complex,too-many-branches,too-many-locals
    # pylint: disable=missing-raises-doc,missing-type-doc,too-many-statements
    if IS_WINDOWS:
        # On Windows, just run child_func directly without PTY
        term = TestTerminal()
        result = child_func(term)
        return result.decode('utf-8') if isinstance(result, bytes) else (result or '')

    import pty as pty_module  # pylint: disable=import-outside-toplevel

    if test_name is None:
        test_name = getattr(child_func, '__name__', 'pty_test')

    pid, master_fd = pty_module.fork()

    # Set PTY window size in parent before child starts reading
    if pid != 0:
        _setwinsize(master_fd, rows, cols)

    if pid == 0:  # Child process
        cov = init_subproc_coverage(test_name)
        try:
            term = TestTerminal()
            result = child_func(term)

            # Write result to stdout if provided
            if result is not None:
                if isinstance(result, str):
                    result = result.encode('utf-8')
                os.write(sys.__stdout__.fileno(), result)
        except Exception:  # pylint: disable=broad-except
            # Write exception to stdout for debugging
            e_type, e_value, e_tb = sys.exc_info()
            o_err = [line.rstrip().encode('utf-8') for line in traceback.format_tb(e_tb)]
            o_err.append(('-=' * 20).encode('ascii'))
            o_err.extend([_exc.rstrip().encode('utf-8') for _exc in
                          traceback.format_exception_only(e_type, e_value)])
            os.write(sys.__stdout__.fileno(), b'\n'.join(o_err))
            if cov is not None:
                cov.stop()
                cov.save()
            os._exit(1)

        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    # Parent process
    with echo_off(master_fd):
        if parent_func is not None:
            parent_func(master_fd)
        output = read_until_eof(master_fd)

    # Use non-blocking wait with timeout to detect hung child processes
    timeout = 5.0  # 5 second timeout
    start_time = time.time()
    status = None
    while True:
        pid_result, status = os.waitpid(pid, os.WNOHANG)
        if pid_result != 0:
            # Child has exited
            break
        if time.time() - start_time > timeout:
            # Child hasn't exited, it's hung - kill it and report what we know
            try:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)  # Clean up zombie
            except OSError:
                pass
            # Show the output we captured - this likely contains the root cause
            raise AssertionError(
                f'Child process hung and did not exit within {timeout}s.\n'
                f'Output captured from child:\n{"=" * 40}\n{output}\n{"=" * 40}'
            )
        time.sleep(0.05)  # Poll every 50ms

    assert os.WEXITSTATUS(status) == 0, (
        f"Child process exited with status {os.WEXITSTATUS(status)}",
        f"Output from child: {output}")

    return output


class MockTigetstr():  # pylint: disable=too-few-public-methods
    """
    Wraps curses.tigetstr() to override specific capnames

    Capnames and return values are provided as keyword arguments
    """

    def __init__(self, **kwargs):
        self.callable = curses.tigetstr
        self.kwargs = kwargs

    def __call__(self, capname):
        return self.kwargs.get(capname, self.callable(capname))


def assert_modifiers(ks, ctrl=False, alt=False, shift=False, _super=False):
    """Assert keystroke modifier flags match expected values."""
    assert ks._ctrl is ctrl
    assert ks._alt is alt
    assert ks._shift is shift
    if _super is not None:
        assert ks._super is _super


def assert_modifiers_value(ks, modifiers):
    """Assert keystroke modifier integer values (modifiers_bits is auto-calculated)."""
    assert ks.modifiers == modifiers
    expected_bits = max(0, modifiers - 1)
    assert ks.modifiers_bits == expected_bits


def assert_only_modifiers(ks, *modifiers):
    """Assert keystroke has only the specified modifiers.

    Args:
        ks: The keystroke to check
        *modifiers: Variable number of modifier names ('ctrl', 'alt', 'shift')

    Examples:
        assert_only_modifiers(ks, 'alt')           # Alt only
        assert_only_modifiers(ks, 'ctrl')          # Ctrl only
        assert_only_modifiers(ks, 'shift')         # Shift only
        assert_only_modifiers(ks, 'ctrl', 'alt')   # Ctrl+Alt
    """
    # pylint: disable=missing-type-doc
    # Import KittyModifierBits to avoid magic numbers
    from blessed.keyboard import KittyModifierBits

    # Convert modifiers to a set for easy lookup
    modifier_set = {mod.lower() for mod in modifiers}

    # Calculate expected bits using getattr - naturally validates modifier names
    expected_bits = 0
    for modifier in modifier_set:
        expected_bits |= getattr(KittyModifierBits, modifier)

    expected_modifiers = expected_bits + 1

    # Build modifier flags for assert_modifiers using getattr
    modifier_flags = {mod: mod in modifier_set for mod in ('ctrl', 'alt', 'shift')}

    # Assert using existing helper functions
    assert_modifiers_value(ks, modifiers=expected_modifiers)
    assert_modifiers(ks, **modifier_flags)
