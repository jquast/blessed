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
                          init_subproc_coverage,
                          pty_test)

got_sigwinch = False

pytestmark = pytest.mark.skipif(
    not TEST_KEYBOARD or IS_WINDOWS,
    reason="Timing-sensitive tests excluded, or, windows incompatible")


def assert_elapsed_range_ms(start_time, min_ms, max_ms):
    """Assert that elapsed time in milliseconds is within range."""
    elapsed_ms = (time.time() - start_time) * 100
    assert min_ms <= int(elapsed_ms) <= max_ms


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
    assert_elapsed_range_ms(stime, 15, 80)


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
        assert_elapsed_range_ms(stime, 25, 80)
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
            assert_elapsed_range_ms(stime, *expected_cs_range)
    child(use_stream, timeout, expected_cs_range)


def test_keystroke_0s_cbreak_with_input():
    """0-second keystroke with input; Keypress should be immediately returned."""
    def child(term):
        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=0)
            return inp.encode('utf-8')

    def parent(master_fd):
        os.write(master_fd, SEND_SEMAPHORE)
        os.write(master_fd, b'x')
        read_until_semaphore(master_fd)

    stime = time.time()
    output = pty_test(child, parent, 'test_keystroke_0s_cbreak_with_input')
    assert output == 'x'
    assert math.floor(time.time() - stime) == 0.0


def test_keystroke_cbreak_with_input_slowly():
    """0-second keystroke with input; Keypress should be immediately returned."""
    def child(term):
        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        result = []
        with term.cbreak():
            while True:
                inp = term.inkey(timeout=0.5)
                result.append(inp)
                if inp == 'X':
                    break
        return ''.join(result).encode('utf-8')

    def parent(master_fd):
        os.write(master_fd, SEND_SEMAPHORE)
        os.write(master_fd, b'a')
        time.sleep(0.1)
        os.write(master_fd, b'b')
        time.sleep(0.1)
        os.write(master_fd, b'cdefgh')
        time.sleep(0.1)
        os.write(master_fd, b'X')
        read_until_semaphore(master_fd)

    stime = time.time()
    output = pty_test(child, parent, 'test_keystroke_cbreak_with_input_slowly')
    assert output == 'abcdefghX'
    assert math.floor(time.time() - stime) == 0.0


def test_keystroke_0s_cbreak_multibyte_utf8():
    """0-second keystroke with multibyte utf-8 input; should decode immediately."""
    # utf-8 bytes represent "latin capital letter upsilon".
    def child(term):
        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=0)
            return inp.encode('utf-8')

    def parent(master_fd):
        os.write(master_fd, SEND_SEMAPHORE)
        os.write(master_fd, '\u01b1'.encode())
        read_until_semaphore(master_fd)

    stime = time.time()
    output = pty_test(child, parent, 'test_keystroke_0s_cbreak_multibyte_utf8')
    assert output == 'Ʊ'
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
        os.write(master_fd, b'\x03')
        stime = time.time()
        output = read_until_eof(master_fd)
    pid, status = os.waitpid(pid, 0)
    assert (output == '\x03' or
            output == '' and not os.isatty(0))
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


def test_keystroke_0s_cbreak_sequence():
    """0-second keystroke with multibyte sequence; should decode immediately."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=0)
            return inp.name.encode('ascii')

    def parent(master_fd):
        os.write(master_fd, '\x1b[D'.encode('ascii'))
        read_until_semaphore(master_fd)

    stime = time.time()
    output = pty_test(child, parent, 'test_keystroke_0s_cbreak_sequence')
    assert output == 'KEY_LEFT'
    assert math.floor(time.time() - stime) == 0.0


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_keystroke_20ms_cbreak_with_input():
    """1-second keystroke w/multibyte sequence; should return after ~1 second."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=5)
            return inp.name.encode('utf-8')

    def parent(master_fd):
        read_until_semaphore(master_fd)
        time.sleep(0.2)
        os.write(master_fd, '\x1b[C'.encode('ascii'))

    stime = time.time()
    output = pty_test(child, parent, 'test_keystroke_20ms_cbreak_with_input')
    assert output == 'KEY_RIGHT'
    assert_elapsed_range_ms(stime, 19, 40)


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_esc_delay_cbreak_15ms():
    """esc_delay=0.15 will cause a single ESC (\\x1b) to delay for 15ms"""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=1, esc_delay=0.15)
            measured_time = (time.time() - stime) * 100
            return f'{inp.name} {measured_time:.0f}'.encode('ascii')

    def parent(master_fd):
        read_until_semaphore(master_fd)
        os.write(master_fd, '\x1b'.encode('ascii'))

    output = pty_test(child, parent, 'test_esc_delay_cbreak_15ms')
    key_name, duration_ms = output.split()

    assert key_name == 'KEY_ESCAPE'
    assert 14 <= int(duration_ms) <= 20, int(duration_ms)


def test_esc_delay_cbreak_timout_0():
    """esc_delay still in effect with timeout of 0 ("nonblocking")."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=0, esc_delay=0.15)
            measured_time = (time.time() - stime) * 100
            return f'{inp.name} {measured_time:.0f}'.encode('ascii')

    def parent(master_fd):
        os.write(master_fd, '\x1b'.encode('ascii'))
        read_until_semaphore(master_fd)

    stime = time.time()
    output = pty_test(child, parent, 'test_esc_delay_cbreak_timout_0')
    key_name, duration_ms = output.split()

    assert key_name == 'KEY_ESCAPE'
    assert math.floor(time.time() - stime) == 0.0
    assert 14 <= int(duration_ms) <= 25, int(duration_ms)


def test_esc_delay_cbreak_nonprefix_sequence():
    """ESC a (\\x1ba) will return ALT_A immediately."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            keystroke = term.inkey(timeout=9)
            measured_time = (time.time() - stime) * 100
            return f'{keystroke.name} {measured_time:.0f}'.encode('ascii')

    def parent(master_fd):
        read_until_semaphore(master_fd)
        os.write(master_fd, b'\x1ba')

    stime = time.time()
    output = pty_test(child, parent, 'test_esc_delay_cbreak_nonprefix_sequence')
    key_name, duration_ms = output.split()

    assert key_name == 'KEY_ALT_A'
    assert math.floor(time.time() - stime) == 0.0
    assert 0 <= int(duration_ms) <= 10, duration_ms


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_flushinp_timeout_with_continuous_input():
    """flushinp() respects timeout even when keystrokes arrive continuously."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            flushed = term.flushinp(timeout=0.1)
            measured_time = (time.time() - stime) * 100
            return f'{len(flushed)} {measured_time:.0f}'.encode('ascii')

    def parent(master_fd):
        read_until_semaphore(master_fd)
        for _ in range(5):
            os.write(master_fd, b'x')
            time.sleep(0.03)

    stime = time.time()
    output = pty_test(child, parent, 'test_flushinp_timeout_with_continuous_input')
    count, duration_ms = output.split()

    assert int(count) >= 3
    assert 8 <= int(duration_ms) <= 20
    assert_elapsed_range_ms(stime, 8, 25)


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
        term = TestTerminal(stream=StringIO(), force_styling=True, is_a_tty=True)
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
        term = TestTerminal(stream=StringIO(), force_styling=True, is_a_tty=True)
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
        term = TestTerminal(stream=StringIO(), force_styling=True, is_a_tty=True)
        term.ungetch('\x1b[10;10R')
        y, x = term.get_location(timeout=0.01)
        assert (y, x) == (9, 9)

        term = TestTerminal(stream=StringIO(), force_styling=False, is_a_tty=True)
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
        term = TestTerminal(stream=StringIO(), force_styling=True, is_a_tty=True)
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
        term = TestTerminal(stream=StringIO(), force_styling=True, is_a_tty=True)
        term.ungetch('\x1b]10;rgb:d2/b4/8c\x07')  # tan
        rgb = term.get_fgcolor(timeout=0.01)
        assert rgb == (210, 180, 140)

        term = TestTerminal(stream=StringIO(), force_styling=False, is_a_tty=True)
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
        term = TestTerminal(stream=StringIO(), force_styling=True, is_a_tty=True)
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
        term = TestTerminal(stream=StringIO(), force_styling=True, is_a_tty=True)
        term.ungetch('\x1b]11;rgb:ff/e4/c4\x07')  # bisque
        rgb = term.get_bgcolor(timeout=0.01)
        assert rgb == (255, 228, 196)

        term = TestTerminal(stream=StringIO(), force_styling=False, is_a_tty=True)
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


@pytest.mark.skipif(not TEST_KEYBOARD or IS_WINDOWS, reason="Requires TTY")
def test_cbreak_with_has_tty():
    """Test cbreak() context manager with HAS_TTY=True"""
    def child(term):
        # This test exercises the HAS_TTY path in cbreak()
        # Lines 2128-2140 in terminal.py
        with term.cbreak():
            # Verify we're in cbreak mode
            assert term._line_buffered is False
            # Write something to indicate success
            return b'CBREAK_OK'
        # After exiting context, line_buffered should be restored
        return b'RESTORED'

    output = pty_test(child, parent_func=None, test_name='test_cbreak_with_has_tty')
    assert 'CBREAK_OK' in output or 'RESTORED' in output


def test_inkey_with_csi_sequence_triggers_latin1_decoding():
    """Test that CSI sequences trigger Latin1 decoding path in inkey()"""
    def child(term):
        # Send a CSI sequence to trigger Latin1 decoding
        # This tests lines 2286-2296, 2315-2319, 2324->2330
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            # The CSI sequence should trigger _use_latin1_decoding
            ks = term.inkey(timeout=0.5)
            return ks.name.encode('ascii') if ks.name else b'EMPTY'

    def parent(master_fd):
        read_until_semaphore(master_fd)
        # Send a CSI sequence (arrow key)
        os.write(master_fd, b'\x1b[A')
        time.sleep(0.05)

    output = pty_test(child, parent, 'test_inkey_with_csi_sequence_triggers_latin1_decoding')
    assert output == 'KEY_UP'


def test_read_until_pattern_found():
    """Test _read_until when pattern is found in input stream."""
    def child(term):
        from blessed.keyboard import _read_until
        with term.cbreak():
            # This will test the match found branch (959->961)
            match, _ = _read_until(term, r'\d+;\d+R', timeout=1.0)
            # Verify we got a match
            assert match is not None
            return b'MATCH_FOUND'

    def parent(master_fd):
        # Write a pattern that will match
        time.sleep(0.05)
        os.write(master_fd, b'\x1b[10;20R')

    output = pty_test(child, parent, 'test_read_until_pattern_found')
    assert output == 'MATCH_FOUND'


def test_read_until_timeout_no_match():
    """Test _read_until when timeout occurs without pattern match."""
    def child(term):
        from blessed.keyboard import _read_until
        with term.cbreak():
            # This will test the timeout branch (963->965)
            stime = time.time()
            match, _ = _read_until(term, r'\d+;\d+R', timeout=0.1)
            elapsed = time.time() - stime
            # Verify timeout occurred
            assert match is None
            assert 0.08 <= elapsed <= 0.15
            return b'TIMEOUT'

    # Parent doesn't write any matching pattern - let it timeout
    output = pty_test(child, parent_func=None, test_name='test_read_until_timeout_no_match')
    assert output == 'TIMEOUT'


def test_read_until_buffer_aggregation():
    """Test _read_until buffer aggregation with hot keyboard input."""
    def child(term):
        from blessed.keyboard import _read_until
        with term.cbreak():
            # This will test the buffer aggregation loop (954->958)
            match, buf = _read_until(term, r'END', timeout=1.0)
            # Verify we got the full buffered content
            assert match is not None
            assert 'END' in buf
            return b'AGGREGATED'

    def parent(master_fd):
        # Write data in rapid succession to trigger buffer aggregation
        os.write(master_fd, b'abc')
        os.write(master_fd, b'def')
        os.write(master_fd, b'ghi')
        os.write(master_fd, b'END')
        time.sleep(0.05)

    output = pty_test(child, parent, 'test_read_until_buffer_aggregation')
    assert output == 'AGGREGATED'


def test_read_until_with_none_timeout():
    """Test _read_until with None timeout (blocks indefinitely until match)."""
    def child(term):
        from blessed.keyboard import _read_until
        with term.cbreak():
            # This tests the timeout=None path
            match, _ = _read_until(term, r'DONE', timeout=None)
            assert match is not None
            return b'NONE_TIMEOUT'

    def parent(master_fd):
        # Write matching pattern after short delay
        time.sleep(0.05)
        os.write(master_fd, b'DONE')
        time.sleep(0.05)

    output = pty_test(child, parent, 'test_read_until_with_none_timeout')
    assert output == 'NONE_TIMEOUT'


def test_read_until_loop_continuation():
    """Test _read_until loop continuation when pattern not yet matched."""
    def child(term):
        from blessed.keyboard import _read_until
        with term.cbreak():
            # Send partial data first, then complete pattern
            # This tests the loop continuation (963->946)
            match, _ = _read_until(term, r'COMPLETE', timeout=1.0)
            assert match is not None
            return b'LOOP_CONTINUED'

    def parent(master_fd):
        # Write partial data, then rest after delay
        os.write(master_fd, b'COM')
        time.sleep(0.05)
        os.write(master_fd, b'PLETE')
        time.sleep(0.05)

    output = pty_test(child, parent, 'test_read_until_loop_continuation')
    assert output == 'LOOP_CONTINUED'


def test_esc_delay_while_loop_with_continued_input():
    """Test ESC key delay while loop when receiving a complete escape sequence incrementally."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            ks = term.inkey(timeout=1.0, esc_delay=0.2)
            return ks.name.encode('ascii')

    def parent(master_fd):
        read_until_semaphore(master_fd)
        # Send ESC first
        os.write(master_fd, b'\x1b')
        # Then send '[' after a tiny delay but before esc_delay expires
        # This should cause the while loop body (lines 1545-1548) to execute
        time.sleep(0.05)
        os.write(master_fd, b'[')
        # Then complete with 'D' to form KEY_LEFT
        time.sleep(0.05)
        os.write(master_fd, b'D')

    output = pty_test(child, parent, 'test_esc_delay_while_loop_with_continued_input')
    assert output == 'KEY_LEFT'


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_esc_delay_long_sequence_prefix_slow_complete():
    """Long sequence sent slowly byte-by-byte should complete before esc_delay.

    Tests that when a multi-byte sequence like F5 (\x1b[15~) is sent byte-by-byte
    with delays, the prefix matching logic correctly waits for the complete sequence
    rather than timing out early. The sequence has multiple prefix points:
    \x1b -> \x1b[ -> \x1b[1 -> \x1b[15 -> \x1b[15~ (complete)
    """
    interval = 0.02
    sequence = b'\x1b[15~'  # F5 key

    # wait roughly 200ms more than expected
    esc_delay = (interval * len(sequence)) + 0.2

    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            keystroke = term.inkey(timeout=6.0, esc_delay=esc_delay)
            duration_ms = (time.time() - stime) * 100
            remaining = term.flushinp(timeout=0.15)
            result = f'{keystroke.name}|{keystroke.code}|{remaining!r}|{duration_ms:.0f}'
            return result.encode('ascii')

    def parent(master_fd):
        read_until_semaphore(master_fd)

        # Send the sequence byte-by-byte with delays
        for byte in sequence:
            time.sleep(interval)
            os.write(master_fd, bytes([byte]))

    output = pty_test(child, parent, 'test_esc_delay_long_sequence_prefix_slow_complete')
    key_name, key_code, remaining, duration_ms = output.split('|')

    # Even though sent 1 byte at-a-time, our resolver should notice the
    # prefix chain (\x1b -> \x1b[ -> \x1b[1 -> \x1b[15) and wait for completion
    # so long as each byte arrives before esc_delay has elapsed
    assert key_name == 'KEY_F5', (key_name, key_code, remaining, duration_ms)
    assert remaining == "''"
    # Duration should be at least the time to receive all bytes, but faster than full esc_delay
    # (since we recognize the complete pattern before the delay expires)
    assert (int(100 * interval * len(sequence) * 0.95) <= int(duration_ms) <=
            int(100 * esc_delay * 1.1))


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_esc_delay_incomplete_known_sequence():
    """Incomplete known sequence should timeout and be flushed.

    Tests that when a known sequence prefix (like \x1b[15 which is a prefix for
    F5 key) arrives but never completes, it properly times out after esc_delay
    and resolves to the base sequence (CSI in this case) with remaining data flushed.
    """
    esc_delay = 0.1

    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            keystroke = term.inkey(timeout=5.0, esc_delay=esc_delay)
            duration_ms = (time.time() - stime) * 100
            remaining = term.flushinp(0.15)
            result = f'{keystroke.name}|{remaining!r}|{duration_ms:.0f}'
            return result.encode('ascii')

    def parent(master_fd):
        read_until_semaphore(master_fd)

        # Send incomplete known sequence that never completes
        # \x1b[15 is a prefix for \x1b[15~ (F5), but we never send the ~
        os.write(master_fd, b'\x1b[15 ... never completes!')

    output = pty_test(child, parent, 'test_esc_delay_incomplete_known_sequence')
    keystroke, remaining, duration_ms = output.split('|')

    # Verify that the incomplete known sequence times out and resolves to CSI
    # (the \x1b[ part) after esc_delay, with the rest in remaining
    assert keystroke == 'CSI'
    assert remaining == repr('15 ... never completes!')
    assert int(100 * esc_delay * 0.95) <= int(duration_ms) <= int(100 * esc_delay * 1.1)
