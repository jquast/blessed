# -*- coding: utf-8 -*-
"""Accessories for automated py.test runner."""
from __future__ import print_function, with_statement

# std imports
import os
import sys
import codecs
import functools
import traceback
import contextlib

# local
from blessed import Terminal
from blessed._compat import TextType
from .conftest import IS_WINDOWS

try:
    from typing import Callable
except ImportError:  # py2
    pass


if IS_WINDOWS:
    import jinxed as curses
else:
    import curses
    import pty
    import termios


test_kind = 'vtwin10' if IS_WINDOWS else 'xterm-256color'
TestTerminal = functools.partial(Terminal, kind=test_kind)  # type: Callable[..., Terminal]
SEND_SEMAPHORE = SEMAPHORE = b'SEMAPHORE\n'
RECV_SEMAPHORE = b'SEMAPHORE\r\n'


def init_subproc_coverage(run_note):
    """Run coverage on subprocess"""
    try:
        import coverage
    except ImportError:
        return None
    _coveragerc = os.path.join(
        os.path.dirname(__file__),
        os.pardir, 'tox.ini')
    cov = coverage.Coverage(config_file=_coveragerc)
    cov.start()
    return cov


class as_subprocess(object):  # pylint: disable=too-few-public-methods
    """This helper executes test cases in a child process, avoiding a python-internal bug of
    _curses: setupterm() may not be called more than once per process."""
    _CHILD_PID = 0
    encoding = 'utf8'

    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):  # pylint: disable=too-many-locals,too-complex
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
                "@as_subprocess-{pid};{func_name}(*{args}, **{kwargs})"
                .format(pid=os.getpid(), func_name=self.func,
                        args=args, kwargs=kwargs))
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
            print('TEST RUNNER HAS FORKED, {0}=>{1}: EXIT'
                  .format(pid_testrunner, os.getpid()), file=sys.stderr)
            os._exit(1)

        exc_output = TextType()
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
        pid, status = os.waitpid(pid, 0)
        os.close(master_fd)

        # Display any output written by child process
        # (esp. any AssertionError exceptions written to stderr).
        exc_output_msg = 'Output in child process:\n%s\n%s\n%s' % (
            u'=' * 40, exc_output, u'=' * 40,)
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
    outp = TextType()
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
        'Semaphore not recv before EOF '
        '(expected: %r, got: %r)' % (semaphore, outp,))
    return outp[len(semaphore):]


def read_until_eof(fd, encoding='utf8'):
    """
    Read file descriptor ``fd`` until EOF.

    Return decoded string.
    """
    decoder = codecs.getincrementaldecoder(encoding)()
    outp = TextType()
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

    return val.decode('latin1') if val else u''


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
    return u''


class MockTigetstr(object):  # pylint: disable=too-few-public-methods
    """
    Wraps curses.tigetstr() to override specific capnames

    Capnames and return values are provided as keyword arguments
    """

    def __init__(self, **kwargs):
        self.callable = curses.tigetstr
        self.kwargs = kwargs

    def __call__(self, capname):
        return self.kwargs.get(capname, self.callable(capname))
