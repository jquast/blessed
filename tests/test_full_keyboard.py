# -*- coding: utf-8 -*-
"""More advanced tests for capturing keyboard input, sometimes using pty"""

# std imports
import os
import sys
import math
import time
import signal
import platform
from io import StringIO
from unittest import mock

# 3rd party
import pytest

# local
from .conftest import TEST_RAW, IS_WINDOWS, TEST_QUICK, TEST_KEYBOARD
from .accessories import (SEMAPHORE,
                          RECV_SEMAPHORE,
                          SEND_SEMAPHORE,
                          TestTerminal,
                          echo_off,
                          as_subprocess,
                          read_until_eof,
                          read_until_semaphore,
                          init_subproc_coverage)

got_sigwinch = False

pytestmark = pytest.mark.skipif(
    not TEST_KEYBOARD or IS_WINDOWS,
    reason="Timing-sensitive tests please do not run on build farms.")


def assert_elapsed_range(start_time, min_ms, max_ms):
    """Assert that elapsed time in milliseconds is within range."""
    elapsed_ms = (time.time() - start_time) * 100
    assert min_ms <= int(elapsed_ms) <= max_ms, f"elapsed: {int(elapsed_ms)}ms"


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_kbhit_interrupted():
    """kbhit() survives signal handler."""
    # this is a test for a legacy version of python, doesn't hurt to keep around
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:
        cov = init_subproc_coverage('test_kbhit_interrupted')

        global got_sigwinch  # pylint: disable=global-statement
        got_sigwinch = False

        def on_resize(sig, action):
            global got_sigwinch  # pylint: disable=global-statement
            got_sigwinch = True

        term = TestTerminal()
        signal.signal(signal.SIGWINCH, on_resize)
        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.raw():
            assert term.inkey(timeout=0.2) == ''
        os.write(sys.__stdout__.fileno(), b'complete')
        assert got_sigwinch
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, SEND_SEMAPHORE)
        read_until_semaphore(master_fd)
        stime = time.time()
        time.sleep(0.05)
        os.kill(pid, signal.SIGWINCH)
        output = read_until_eof(master_fd)

    pid, status = os.waitpid(pid, 0)
    assert output == 'complete'
    assert os.WEXITSTATUS(status) == 0
    assert_elapsed_range(stime, 15, 80)


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_kbhit_interrupted_nonetype():
    """kbhit() should also allow interruption with timeout of None."""
    # pylint: disable=global-statement

    # std imports
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:
        cov = init_subproc_coverage('test_kbhit_interrupted_nonetype')

        # child pauses, writes semaphore and begins awaiting input
        global got_sigwinch
        got_sigwinch = False

        def on_resize(sig, action):
            global got_sigwinch
            got_sigwinch = True

        term = TestTerminal()
        signal.signal(signal.SIGWINCH, on_resize)
        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        try:
            with term.raw():
                term.inkey(timeout=None)
        except KeyboardInterrupt:
            os.write(sys.__stdout__.fileno(), b'complete')
            assert got_sigwinch

        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, SEND_SEMAPHORE)
        read_until_semaphore(master_fd)
        stime = time.time()
        time.sleep(0.05)
        os.kill(pid, signal.SIGWINCH)
        time.sleep(0.05)
        os.kill(pid, signal.SIGINT)
        output = read_until_eof(master_fd)

    pid, status = os.waitpid(pid, 0)
    assert output == 'complete'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0


def test_kbhit_no_kb():
    """kbhit() always immediately returns False without a keyboard."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=StringIO())
        stime = time.time()
        assert term._keyboard_fd is None
        assert not term.kbhit(timeout=0.3)
        assert_elapsed_range(stime, 25, 80)
    child()


def test_kbhit_no_tty():
    """kbhit() returns False immediately if HAS_TTY is False"""
    @as_subprocess
    def child():
        with mock.patch('blessed.terminal.HAS_TTY', False):
            term = TestTerminal(stream=StringIO())
            stime = time.time()
            assert term.kbhit(timeout=1.1) is False
            assert math.floor(time.time() - stime) == 0
    child()


@pytest.mark.parametrize(
    'use_stream,timeout,expected_cs_range', [
        (False, 0, (0, 5)),
        (True, 0, (0, 5)),
        pytest.param(False, 0.3, (25, 80), marks=pytest.mark.skipif(
            TEST_QUICK, reason="TEST_QUICK specified")),
        pytest.param(True, 0.3, (25, 80), marks=pytest.mark.skipif(
            TEST_QUICK, reason="TEST_QUICK specified")),
    ])
def test_keystroke_cbreak_noinput(use_stream, timeout, expected_cs_range):
    """Test keystroke without input with various timeout/stream combinations."""
    @as_subprocess
    def child(use_stream, timeout, expected_cs_range):
        stream = StringIO() if use_stream else None
        term = TestTerminal(stream=stream)
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=timeout)
            assert inp == ''
            assert_elapsed_range(stime, *expected_cs_range)
    child(use_stream, timeout, expected_cs_range)


def test_keystroke_0s_cbreak_with_input():
    """0-second keystroke with input; Keypress should be immediately returned."""
    # std imports
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:
        cov = init_subproc_coverage('test_keystroke_0s_cbreak_with_input')
        # child pauses, writes semaphore and begins awaiting input
        term = TestTerminal()
        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=0)
            os.write(sys.__stdout__.fileno(), inp.encode('utf-8'))
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, SEND_SEMAPHORE)
        os.write(master_fd, 'x'.encode('ascii'))
        read_until_semaphore(master_fd)
        stime = time.time()
        output = read_until_eof(master_fd)

    pid, status = os.waitpid(pid, 0)
    assert output == 'x'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


def test_keystroke_cbreak_with_input_slowly():
    """0-second keystroke with input; Keypress should be immediately returned."""
    # std imports
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:
        cov = init_subproc_coverage('test_keystroke_cbreak_with_input_slowly')
        # child pauses, writes semaphore and begins awaiting input
        term = TestTerminal()
        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            while True:
                inp = term.inkey(timeout=0.5)
                os.write(sys.__stdout__.fileno(), inp.encode('utf-8'))
                if inp == 'X':
                    break
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, SEND_SEMAPHORE)
        os.write(master_fd, 'a'.encode('ascii'))
        time.sleep(0.1)
        os.write(master_fd, 'b'.encode('ascii'))
        time.sleep(0.1)
        os.write(master_fd, 'cdefgh'.encode('ascii'))
        time.sleep(0.1)
        os.write(master_fd, 'X'.encode('ascii'))
        read_until_semaphore(master_fd)
        stime = time.time()
        output = read_until_eof(master_fd)

    pid, status = os.waitpid(pid, 0)
    assert output == 'abcdefghX'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


def test_keystroke_0s_cbreak_multibyte_utf8():
    """0-second keystroke with multibyte utf-8 input; should decode immediately."""
    # utf-8 bytes represent "latin capital letter upsilon".
    # std imports
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_keystroke_0s_cbreak_multibyte_utf8')
        term = TestTerminal()
        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=0)
            os.write(sys.__stdout__.fileno(), inp.encode('utf-8'))
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, SEND_SEMAPHORE)
        os.write(master_fd, '\u01b1'.encode('utf-8'))
        read_until_semaphore(master_fd)
        stime = time.time()
        output = read_until_eof(master_fd)
    pid, status = os.waitpid(pid, 0)
    assert output == 'Ʊ'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


# Avylove: Added delay which should account for race condition. Re-add skip if randomly fail
# @pytest.mark.skipif(os.environ.get('TRAVIS', None) is not None,
#                     reason="travis-ci does not handle ^C very well.")
@pytest.mark.skipif(platform.system() == 'Darwin',
                    reason='os.write() raises OSError: [Errno 5] Input/output error')
def test_keystroke_0s_raw_input_ctrl_c():
    """0-second keystroke with raw allows receiving ^C."""
    # std imports
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_keystroke_0s_raw_input_ctrl_c')
        term = TestTerminal()
        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
        with term.raw():
            os.write(sys.__stdout__.fileno(), RECV_SEMAPHORE)
            inp = term.inkey(timeout=0)
            os.write(sys.__stdout__.fileno(), inp.encode('latin1'))
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, SEND_SEMAPHORE)
        # ensure child is in raw mode before sending ^C,
        read_until_semaphore(master_fd)
        time.sleep(0.05)
        os.write(master_fd, '\x03'.encode('latin1'))
        stime = time.time()
        output = read_until_eof(master_fd)
    pid, status = os.waitpid(pid, 0)
    assert (output == '\x03' or
            output == '' and not os.isatty(0))
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


def test_keystroke_0s_cbreak_sequence():
    """0-second keystroke with multibyte sequence; should decode immediately."""
    # std imports
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_keystroke_0s_cbreak_sequence')
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=0)
            os.write(sys.__stdout__.fileno(), inp.name.encode('ascii'))
            sys.stdout.flush()
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, '\x1b[D'.encode('ascii'))
        read_until_semaphore(master_fd)
        stime = time.time()
        output = read_until_eof(master_fd)
    pid, status = os.waitpid(pid, 0)
    assert output == 'KEY_LEFT'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_keystroke_20ms_cbreak_with_input():
    """1-second keystroke w/multibyte sequence; should return after ~1 second."""
    # std imports
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_keystroke_20ms_cbreak_with_input')
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=5)
            os.write(sys.__stdout__.fileno(), inp.name.encode('utf-8'))
            sys.stdout.flush()
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        read_until_semaphore(master_fd)
        stime = time.time()
        time.sleep(0.2)
        os.write(master_fd, '\x1b[C'.encode('ascii'))
        output = read_until_eof(master_fd)

    pid, status = os.waitpid(pid, 0)
    assert output == 'KEY_RIGHT'
    assert os.WEXITSTATUS(status) == 0
    assert_elapsed_range(stime, 19, 40)


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_esc_delay_cbreak_15ms():
    """esc_delay=0.15 will cause a single ESC (\\x1b) to delay for 15ms"""
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_esc_delay_cbreak_15ms')
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=1, esc_delay=0.15)
            measured_time = (time.time() - stime) * 100
            os.write(sys.__stdout__.fileno(), f'{inp.name} {measured_time:.0f}'.encode('ascii'))
            sys.stdout.flush()
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        read_until_semaphore(master_fd)
        stime = time.time()
        os.write(master_fd, '\x1b'.encode('ascii'))
        key_name, duration_ms = read_until_eof(master_fd).split()

    pid, status = os.waitpid(pid, 0)
    assert key_name == 'KEY_ESCAPE'
    assert os.WEXITSTATUS(status) == 0
    assert 14 <= int(duration_ms) <= 20, int(duration_ms)


def test_esc_delay_cbreak_timout_0():
    """esc_delay still in effect with timeout of 0 ("nonblocking")."""
    # std imports
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_esc_delay_cbreak_timout_0')
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=0, esc_delay=0.15)
            measured_time = (time.time() - stime) * 100
            os.write(sys.__stdout__.fileno(), f'{inp.name} {measured_time:.0f}'.encode('ascii'))
            sys.stdout.flush()
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, '\x1b'.encode('ascii'))
        read_until_semaphore(master_fd)
        stime = time.time()
        key_name, duration_ms = read_until_eof(master_fd).split()

    pid, status = os.waitpid(pid, 0)
    assert key_name == 'KEY_ESCAPE'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0
    assert 14 <= int(duration_ms) <= 25, int(duration_ms)


def test_esc_delay_cbreak_nonprefix_sequence():
    """ESC a (\\x1ba) will return ALT_A immediately."""
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_esc_delay_cbreak_nonprefix_sequence')
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            keystroke = term.inkey(timeout=9)
            measured_time = (time.time() - stime) * 100
            os.write(
                sys.__stdout__.fileno(), f'{keystroke.name} {measured_time:.0f}'.encode('ascii')
            )
            sys.stdout.flush()
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        read_until_semaphore(master_fd)
        stime = time.time()
        os.write(master_fd, '\x1ba'.encode('ascii'))
        key_name, duration_ms = read_until_eof(master_fd).split()

    pid, status = os.waitpid(pid, 0)
    assert key_name == 'KEY_ALT_A'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0
    assert 0 <= int(duration_ms) <= 10, duration_ms


def test_get_location_0s():
    """0-second get_location call without response."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=StringIO())
        stime = time.time()
        y, x = term.get_location(timeout=0)
        assert math.floor(time.time() - stime) == 0.0
        assert (y, x) == (-1, -1)
    child()


# jquast: having trouble with these tests intermittently locking up on Mac OS X 10.15.1,
# that they *lock up* is troublesome, I tried to use "pytest-timeout" but this conflicts
# with our retry module, so, just skip them entirely.
@pytest.mark.skipif(not TEST_RAW, reason="TEST_RAW not specified")
def test_get_location_0s_under_raw():
    """0-second get_location call without response under raw mode."""
    # std imports
    import pty
    pid, _ = pty.fork()
    if pid == 0:
        cov = init_subproc_coverage('test_get_location_0s_under_raw')
        term = TestTerminal()
        with term.raw():
            stime = time.time()
            y, x = term.get_location(timeout=0)
            assert math.floor(time.time() - stime) == 0.0
            assert (y, x) == (-1, -1)

        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    stime = time.time()
    pid, status = os.waitpid(pid, 0)
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


@pytest.mark.skipif(not TEST_RAW, reason="TEST_RAW not specified")
def test_get_location_0s_reply_via_ungetch_under_raw():
    """0-second get_location call with response under raw mode."""
    # std imports
    import pty
    pid, _ = pty.fork()
    if pid == 0:
        cov = init_subproc_coverage('test_get_location_0s_reply_via_ungetch_under_raw')
        term = TestTerminal()
        with term.raw():
            stime = time.time()
            # monkey patch in an invalid response !
            term.ungetch('\x1b[10;10R')

            y, x = term.get_location(timeout=0.01)
            assert math.floor(time.time() - stime) == 0.0
            assert (y, x) == (9, 9)

        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    stime = time.time()
    pid, status = os.waitpid(pid, 0)
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


def test_get_location_0s_reply_via_ungetch():
    """0-second get_location call with response."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=StringIO())
        stime = time.time()
        # monkey patch in an invalid response !
        term.ungetch('\x1b[10;10R')

        y, x = term.get_location(timeout=0.01)
        assert math.floor(time.time() - stime) == 0.0
        assert (y, x) == (9, 9)
    child()


def test_get_location_0s_nonstandard_u6():
    """u6 without %i should not be decremented."""
    # local
    from blessed.formatters import ParameterizingString

    @as_subprocess
    def child():
        term = TestTerminal(stream=StringIO())

        stime = time.time()
        # monkey patch in an invalid response !
        term.ungetch('\x1b[10;10R')

        with mock.patch.object(term, 'u6') as mock_u6:
            mock_u6.return_value = ParameterizingString('\x1b[%d;%dR', term.normal, 'u6')
            y, x = term.get_location(timeout=0.01)
        assert math.floor(time.time() - stime) == 0.0
        assert (y, x) == (10, 10)
    child()


def test_get_location_styling_indifferent():
    """Ensure get_location() behavior is the same regardless of styling"""
    @as_subprocess
    def child():
        term = TestTerminal(stream=StringIO(), force_styling=True)
        term.ungetch('\x1b[10;10R')
        y, x = term.get_location(timeout=0.01)
        assert (y, x) == (9, 9)

        term = TestTerminal(stream=StringIO(), force_styling=False)
        term.ungetch('\x1b[10;10R')
        y, x = term.get_location(timeout=0.01)
        assert (y, x) == (9, 9)
    child()


def test_get_location_timeout():
    """0-second get_location call with response."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=StringIO())
        stime = time.time()
        # monkey patch in an invalid response !
        term.ungetch('\x1b[0n')

        y, x = term.get_location(timeout=0.2)
        assert math.floor(time.time() - stime) == 0.0
        assert (y, x) == (-1, -1)
    child()


def test_get_fgcolor_0s():
    """0-second get_fgcolor call without response."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=StringIO())
        stime = time.time()
        rgb = term.get_fgcolor(timeout=0)
        assert math.floor(time.time() - stime) == 0.0
        assert rgb == (-1, -1, -1)
    child()


def test_get_fgcolor_0s_reply_via_ungetch():
    """0-second get_fgcolor call with response."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=StringIO())
        stime = time.time()
        term.ungetch('\x1b]10;rgb:a0/52/2d\x07')  # sienna

        rgb = term.get_fgcolor(timeout=0.01)
        assert math.floor(time.time() - stime) == 0.0
        assert rgb == (160, 82, 45)
    child()


def test_get_fgcolor_styling_indifferent():
    """Ensure get_fgcolor() behavior is the same regardless of styling"""
    @as_subprocess
    def child():
        term = TestTerminal(stream=StringIO(), force_styling=True)
        term.ungetch('\x1b]10;rgb:d2/b4/8c\x07')  # tan
        rgb = term.get_fgcolor(timeout=0.01)
        assert rgb == (210, 180, 140)

        term = TestTerminal(stream=StringIO(), force_styling=False)
        term.ungetch('\x1b]10;rgb:40/e0/d0\x07')  # turquoise
        rgb = term.get_fgcolor(timeout=0.01)
        assert rgb == (64, 224, 208)
    child()


def test_get_bgcolor_0s():
    """0-second get_bgcolor call without response."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=StringIO())
        stime = time.time()
        rgb = term.get_bgcolor(timeout=0)
        assert math.floor(time.time() - stime) == 0.0
        assert rgb == (-1, -1, -1)
    child()


def test_get_bgcolor_0s_reply_via_ungetch():
    """0-second get_bgcolor call with response."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=StringIO())
        stime = time.time()
        term.ungetch('\x1b]11;rgb:99/32/cc\x07')  # darkorchid

        rgb = term.get_bgcolor(timeout=0.01)
        assert math.floor(time.time() - stime) == 0.0
        assert rgb == (153, 50, 204)
    child()


def test_get_bgcolor_styling_indifferent():
    """Ensure get_bgcolor() behavior is the same regardless of styling"""
    @as_subprocess
    def child():
        term = TestTerminal(stream=StringIO(), force_styling=True)
        term.ungetch('\x1b]11;rgb:ff/e4/c4\x07')  # bisque
        rgb = term.get_bgcolor(timeout=0.01)
        assert rgb == (255, 228, 196)

        term = TestTerminal(stream=StringIO(), force_styling=False)
        term.ungetch('\x1b]11;rgb:de/b8/87\x07')  # burlywood
        rgb = term.get_bgcolor(timeout=0.01)
        assert rgb == (222, 184, 135)
    child()


def test_detached_stdout():
    """Ensure detached __stdout__ does not raise an exception"""
    # std imports
    import pty
    pid, _ = pty.fork()
    if pid == 0:
        cov = init_subproc_coverage('test_detached_stdout')
        sys.__stdout__.detach()
        term = TestTerminal()
        assert term._init_descriptor is None
        assert term.does_styling is False

        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    stime = time.time()
    pid, status = os.waitpid(pid, 0)
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0
