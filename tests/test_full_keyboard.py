# -*- coding: utf-8 -*-
# std imports
import os
import sys
import math
import time
import signal
import platform

# 3rd party
import six
import mock
import pytest

# local
from .accessories import (SEMAPHORE,
                          RECV_SEMAPHORE,
                          SEND_SEMAPHORE,
                          TestTerminal,
                          echo_off,
                          as_subprocess,
                          read_until_eof,
                          read_until_semaphore,
                          init_subproc_coverage)

pytestmark = pytest.mark.skipif(
    os.environ.get('TEST_KEYBOARD', None) != 'yes' or platform.system() == 'Windows',
    reason="Timing-sensitive tests please do not run on build farms.")

@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
                    reason="TEST_QUICK specified")
def test_kbhit_interrupted():
    """kbhit() should not be interrupted with a signal handler."""
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:
        cov = init_subproc_coverage('test_kbhit_interrupted')

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
        with term.raw():
            assert term.inkey(timeout=1.05) == u''
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
    assert output == u'complete'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 1.0


@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
                    reason="TEST_QUICK specified")
def test_kbhit_interrupted_nonetype():
    """kbhit() should also allow interruption with timeout of None."""
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
    assert output == u'complete'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0


def test_kbhit_no_kb():
    """kbhit() always immediately returns False without a keyboard."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=six.StringIO())
        stime = time.time()
        assert term._keyboard_fd is None
        assert not term.kbhit(timeout=1.1)
        assert math.floor(time.time() - stime) == 1.0
    child()


def test_kbhit_no_tty():
    """kbhit() returns False immediately if HAS_TTY is False"""
    import blessed.terminal
    @as_subprocess
    def child():
        with mock.patch('blessed.terminal.HAS_TTY', False):
            term = TestTerminal(stream=six.StringIO())
            stime = time.time()
            assert term.kbhit(timeout=1.1) is False
            assert math.floor(time.time() - stime) == 0
    child()


def test_keystroke_0s_cbreak_noinput():
    """0-second keystroke without input; '' should be returned."""
    @as_subprocess
    def child():
        term = TestTerminal()
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=0)
            assert (inp == u'')
            assert (math.floor(time.time() - stime) == 0.0)
    child()


def test_keystroke_0s_cbreak_noinput_nokb():
    """0-second keystroke without data in input stream and no keyboard/tty."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=six.StringIO())
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=0)
            assert (inp == u'')
            assert (math.floor(time.time() - stime) == 0.0)
    child()


@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
                    reason="TEST_QUICK specified")
def test_keystroke_1s_cbreak_noinput():
    """1-second keystroke without input; '' should be returned after ~1 second."""
    @as_subprocess
    def child():
        term = TestTerminal()
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=1)
            assert (inp == u'')
            assert (math.floor(time.time() - stime) == 1.0)
    child()


@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
                    reason="TEST_QUICK specified")
def test_keystroke_1s_cbreak_noinput_nokb():
    """1-second keystroke without input or keyboard."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=six.StringIO())
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=1)
            assert (inp == u'')
            assert (math.floor(time.time() - stime) == 1.0)
    child()


def test_keystroke_0s_cbreak_with_input():
    """0-second keystroke with input; Keypress should be immediately returned."""
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
        os.write(master_fd, u'x'.encode('ascii'))
        read_until_semaphore(master_fd)
        stime = time.time()
        output = read_until_eof(master_fd)

    pid, status = os.waitpid(pid, 0)
    assert output == u'x'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


def test_keystroke_cbreak_with_input_slowly():
    """0-second keystroke with input; Keypress should be immediately returned."""
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
        os.write(master_fd, u'a'.encode('ascii'))
        time.sleep(0.1)
        os.write(master_fd, u'b'.encode('ascii'))
        time.sleep(0.1)
        os.write(master_fd, u'cdefgh'.encode('ascii'))
        time.sleep(0.1)
        os.write(master_fd, u'X'.encode('ascii'))
        read_until_semaphore(master_fd)
        stime = time.time()
        output = read_until_eof(master_fd)

    pid, status = os.waitpid(pid, 0)
    assert output == u'abcdefghX'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


def test_keystroke_0s_cbreak_multibyte_utf8():
    """0-second keystroke with multibyte utf-8 input; should decode immediately."""
    # utf-8 bytes represent "latin capital letter upsilon".
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
        os.write(master_fd, u'\u01b1'.encode('utf-8'))
        read_until_semaphore(master_fd)
        stime = time.time()
        output = read_until_eof(master_fd)
    pid, status = os.waitpid(pid, 0)
    assert output == u'Ʊ'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


# Avylove: Added delay which should account for race contition. Re-add skip if randomly fail
# @pytest.mark.skipif(os.environ.get('TRAVIS', None) is not None,
#                     reason="travis-ci does not handle ^C very well.")
@pytest.mark.skipif(platform.system() == 'Darwin',
                    reason='os.write() raises OSError: [Errno 5] Input/output error')
def test_keystroke_0s_raw_input_ctrl_c():
    """0-second keystroke with raw allows receiving ^C."""
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
        os.write(master_fd, u'\x03'.encode('latin1'))
        stime = time.time()
        output = read_until_eof(master_fd)
    pid, status = os.waitpid(pid, 0)
    assert (output == u'\x03' or
            output == u'' and not os.isatty(0))
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


def test_keystroke_0s_cbreak_sequence():
    """0-second keystroke with multibyte sequence; should decode immediately."""
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
        os.write(master_fd, u'\x1b[D'.encode('ascii'))
        read_until_semaphore(master_fd)
        stime = time.time()
        output = read_until_eof(master_fd)
    pid, status = os.waitpid(pid, 0)
    assert output == u'KEY_LEFT'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
                    reason="TEST_QUICK specified")
def test_keystroke_1s_cbreak_with_input():
    """1-second keystroke w/multibyte sequence; should return after ~1 second."""
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_keystroke_1s_cbreak_with_input')
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=3)
            os.write(sys.__stdout__.fileno(), inp.name.encode('utf-8'))
            sys.stdout.flush()
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        read_until_semaphore(master_fd)
        stime = time.time()
        time.sleep(1)
        os.write(master_fd, u'\x1b[C'.encode('ascii'))
        output = read_until_eof(master_fd)

    pid, status = os.waitpid(pid, 0)
    assert output == u'KEY_RIGHT'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 1.0


@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
                    reason="TEST_QUICK specified")
def test_esc_delay_cbreak_035():
    """esc_delay will cause a single ESC (\\x1b) to delay for 0.35."""
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_esc_delay_cbreak_035')
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=5)
            measured_time = (time.time() - stime) * 100
            os.write(sys.__stdout__.fileno(), (
                '%s %i' % (inp.name, measured_time,)).encode('ascii'))
            sys.stdout.flush()
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        read_until_semaphore(master_fd)
        stime = time.time()
        os.write(master_fd, u'\x1b'.encode('ascii'))
        key_name, duration_ms = read_until_eof(master_fd).split()

    pid, status = os.waitpid(pid, 0)
    assert key_name == u'KEY_ESCAPE'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0
    assert 34 <= int(duration_ms) <= 45, duration_ms


@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
                    reason="TEST_QUICK specified")
def test_esc_delay_cbreak_135():
    """esc_delay=1.35 will cause a single ESC (\\x1b) to delay for 1.35."""
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_esc_delay_cbreak_135')
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=5, esc_delay=1.35)
            measured_time = (time.time() - stime) * 100
            os.write(sys.__stdout__.fileno(), (
                '%s %i' % (inp.name, measured_time,)).encode('ascii'))
            sys.stdout.flush()
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        read_until_semaphore(master_fd)
        stime = time.time()
        os.write(master_fd, u'\x1b'.encode('ascii'))
        key_name, duration_ms = read_until_eof(master_fd).split()

    pid, status = os.waitpid(pid, 0)
    assert key_name == u'KEY_ESCAPE'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 1.0
    assert 134 <= int(duration_ms) <= 145, int(duration_ms)


def test_esc_delay_cbreak_timout_0():
    """esc_delay still in effect with timeout of 0 ("nonblocking")."""
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_esc_delay_cbreak_timout_0')
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=0)
            measured_time = (time.time() - stime) * 100
            os.write(sys.__stdout__.fileno(), (
                '%s %i' % (inp.name, measured_time,)).encode('ascii'))
            sys.stdout.flush()
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, u'\x1b'.encode('ascii'))
        read_until_semaphore(master_fd)
        stime = time.time()
        key_name, duration_ms = read_until_eof(master_fd).split()

    pid, status = os.waitpid(pid, 0)
    assert key_name == u'KEY_ESCAPE'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0
    assert 34 <= int(duration_ms) <= 45, int(duration_ms)


def test_esc_delay_cbreak_nonprefix_sequence():
    """ESC a (\\x1ba) will return an ESC immediately."""
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_esc_delay_cbreak_nonprefix_sequence')
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            esc = term.inkey(timeout=5)
            inp = term.inkey(timeout=5)
            measured_time = (time.time() - stime) * 100
            os.write(sys.__stdout__.fileno(), (
                '%s %s %i' % (esc.name, inp, measured_time,)).encode('ascii'))
            sys.stdout.flush()
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        read_until_semaphore(master_fd)
        stime = time.time()
        os.write(master_fd, u'\x1ba'.encode('ascii'))
        key1_name, key2, duration_ms = read_until_eof(master_fd).split()

    pid, status = os.waitpid(pid, 0)
    assert key1_name == u'KEY_ESCAPE'
    assert key2 == u'a'
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0
    assert -1 <= int(duration_ms) <= 15, duration_ms


def test_esc_delay_cbreak_prefix_sequence():
    """An unfinished multibyte sequence (\\x1b[) will delay an ESC by .35."""
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        cov = init_subproc_coverage('test_esc_delay_cbreak_prefix_sequence')
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            esc = term.inkey(timeout=5)
            inp = term.inkey(timeout=5)
            measured_time = (time.time() - stime) * 100
            os.write(sys.__stdout__.fileno(), (
                '%s %s %i' % (esc.name, inp, measured_time,)).encode('ascii'))
            sys.stdout.flush()
        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    with echo_off(master_fd):
        read_until_semaphore(master_fd)
        stime = time.time()
        os.write(master_fd, u'\x1b['.encode('ascii'))
        key1_name, key2, duration_ms = read_until_eof(master_fd).split()

    pid, status = os.waitpid(pid, 0)
    assert key1_name == u'KEY_ESCAPE'
    assert key2 == u'['
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0
    assert 34 <= int(duration_ms) <= 45, duration_ms


def test_get_location_0s():
    """0-second get_location call without response."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=six.StringIO())
        stime = time.time()
        y, x = term.get_location(timeout=0)
        assert (math.floor(time.time() - stime) == 0.0)
        assert (y, x) == (-1, -1)
    child()


# jquast: having trouble with these tests intermittently locking up on Mac OS X 10.15.1,
# that they *lock up* is troublesome, I tried to use "pytest-timeout" but this conflicts
# with our retry module, so, just skip them entirely.
@pytest.mark.skipif(not os.environ.get('TEST_RAW'), reason="TEST_RAW not specified")
def test_get_location_0s_under_raw():
    """0-second get_location call without response under raw mode."""
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:
        cov = init_subproc_coverage('test_get_location_0s_under_raw')
        term = TestTerminal()
        with term.raw():
            stime = time.time()
            y, x = term.get_location(timeout=0)
            assert (math.floor(time.time() - stime) == 0.0)
            assert (y, x) == (-1, -1)

        if cov is not None:
            cov.stop()
            cov.save()
        os._exit(0)

    stime = time.time()
    pid, status = os.waitpid(pid, 0)
    assert os.WEXITSTATUS(status) == 0
    assert math.floor(time.time() - stime) == 0.0


@pytest.mark.skipif(not os.environ.get('TEST_RAW'), reason="TEST_RAW not specified")
def test_get_location_0s_reply_via_ungetch_under_raw():
    """0-second get_location call with response under raw mode."""
    import pty
    pid, master_fd = pty.fork()
    if pid == 0:
        cov = init_subproc_coverage('test_get_location_0s_reply_via_ungetch_under_raw')
        term = TestTerminal()
        with term.raw():
            stime = time.time()
            # monkey patch in an invalid response !
            term.ungetch(u'\x1b[10;10R')

            y, x = term.get_location(timeout=0.01)
            assert (math.floor(time.time() - stime) == 0.0)
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
        term = TestTerminal(stream=six.StringIO())
        stime = time.time()
        # monkey patch in an invalid response !
        term.ungetch(u'\x1b[10;10R')

        y, x = term.get_location(timeout=0.01)
        assert (math.floor(time.time() - stime) == 0.0)
        assert (y, x) == (9, 9)
    child()


def test_get_location_0s_nonstandard_u6():
    """u6 without %i should not be decremented."""
    from blessed.formatters import ParameterizingString
    @as_subprocess
    def child():
        term = TestTerminal(stream=six.StringIO())

        stime = time.time()
        # monkey patch in an invalid response !
        term.ungetch(u'\x1b[10;10R')

        with mock.patch.object(term, 'u6') as mock_u6:
            mock_u6.return_value = ParameterizingString(u'\x1b[%d;%dR', term.normal, 'u6')
            y, x = term.get_location(timeout=0.01)
        assert (math.floor(time.time() - stime) == 0.0)
        assert (y, x) == (10, 10)
    child()


def test_get_location_styling_indifferent():
    """Ensure get_location() behavior is the same regardless of styling"""
    @as_subprocess
    def child():
        term = TestTerminal(stream=six.StringIO(), force_styling=True)
        term.ungetch(u'\x1b[10;10R')
        y, x = term.get_location(timeout=0.01)
        assert (y, x) == (9, 9)

        term = TestTerminal(stream=six.StringIO(), force_styling=False)
        term.ungetch(u'\x1b[10;10R')
        y, x = term.get_location(timeout=0.01)
        assert (y, x) == (9, 9)
    child()


def test_get_location_timeout():
    """0-second get_location call with response."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=six.StringIO())
        stime = time.time()
        # monkey patch in an invalid response !
        term.ungetch(u'\x1b[0n')

        y, x = term.get_location(timeout=0.2)
        assert (math.floor(time.time() - stime) == 0.0)
        assert (y, x) == (-1, -1)
    child()


def test_kbhit_no_kb():
    """kbhit() always immediately returns False without a keyboard."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=six.StringIO())
        stime = time.time()
        assert term._keyboard_fd is None
        assert not term.kbhit(timeout=1.1)
        assert math.floor(time.time() - stime) == 1.0
    child()


def test_keystroke_0s_cbreak_noinput():
    """0-second keystroke without input; '' should be returned."""
    @as_subprocess
    def child():
        term = TestTerminal()
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=0)
            assert (inp == u'')
            assert (math.floor(time.time() - stime) == 0.0)
    child()


def test_keystroke_0s_cbreak_noinput_nokb():
    """0-second keystroke without data in input stream and no keyboard/tty."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=six.StringIO())
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=0)
            assert (inp == u'')
            assert (math.floor(time.time() - stime) == 0.0)
    child()


@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
                    reason="TEST_QUICK specified")
def test_keystroke_1s_cbreak_noinput():
    """1-second keystroke without input; '' should be returned after ~1 second."""
    @as_subprocess
    def child():
        term = TestTerminal()
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=1)
            assert (inp == u'')
            assert (math.floor(time.time() - stime) == 1.0)
    child()


@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
                    reason="TEST_QUICK specified")
def test_keystroke_1s_cbreak_noinput_nokb():
    """1-second keystroke without input or keyboard."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=six.StringIO())
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=1)
            assert (inp == u'')
            assert (math.floor(time.time() - stime) == 1.0)
    child()


@pytest.mark.skipif(six.PY2, reason="Python 3 only")
def test_detached_stdout():
    """Ensure detached __stdout__ does not raise an exception"""
    import pty
    pid, master_fd = pty.fork()
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
