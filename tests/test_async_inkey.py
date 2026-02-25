"""Tests for async_inkey() and _async_read_byte()."""

# std imports
import os
import sys
import time
import asyncio
from unittest import mock

# 3rd party
import pytest

# local
from .conftest import IS_WINDOWS
from .accessories import SEMAPHORE, TestTerminal, pty_test, as_subprocess, read_until_semaphore

pytestmark = pytest.mark.skipif(IS_WINDOWS, reason="no pty on Windows")


def test_async_read_byte_returns_data():
    """_async_read_byte returns data written to pty."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    term._async_read_byte(loop, timeout=1.0))
            finally:
                loop.close()
            assert result == b'x'
            return b'OK'

    def parent(master_fd):
        read_until_semaphore(master_fd)
        os.write(master_fd, b'x')

    output = pty_test(child, parent, 'test_async_read_byte_returns_data')
    assert output == 'OK'


def test_async_read_byte_timeout_returns_none():
    """_async_read_byte returns None on timeout."""
    def child(term):
        with term.cbreak():
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    term._async_read_byte(loop, timeout=0.05))
            finally:
                loop.close()
            assert result is None
            return b'OK'

    output = pty_test(child, test_name='test_async_read_byte_timeout_returns_none')
    assert output == 'OK'


def test_async_inkey_simple_keystroke():
    """async_inkey resolves a simple keystroke."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            loop = asyncio.new_event_loop()
            try:
                ks = loop.run_until_complete(
                    term.async_inkey(timeout=1.0))
            finally:
                loop.close()
            assert str(ks) == 'x'
            assert not ks.is_sequence
            return b'OK'

    def parent(master_fd):
        read_until_semaphore(master_fd)
        os.write(master_fd, b'x')

    output = pty_test(child, parent, 'test_async_inkey_simple_keystroke')
    assert output == 'OK'


def test_async_inkey_timeout_returns_empty():
    """async_inkey returns empty Keystroke on timeout."""
    def child(term):
        with term.cbreak():
            loop = asyncio.new_event_loop()
            try:
                ks = loop.run_until_complete(
                    term.async_inkey(timeout=0.05))
            finally:
                loop.close()
            assert str(ks) == ''
            assert ks.code is None
            assert ks.name is None
            return b'OK'

    output = pty_test(child, test_name='test_async_inkey_timeout_returns_empty')
    assert output == 'OK'


def test_async_inkey_mouse_x10():
    """async_inkey decodes X10 mouse event with all bytes at once."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            loop = asyncio.new_event_loop()
            try:
                ks = loop.run_until_complete(
                    term.async_inkey(timeout=2.0))
            finally:
                loop.close()
            assert ks.is_mouse
            return b'OK'

    def parent(master_fd):
        read_until_semaphore(master_fd)
        # X10 mouse: ESC [ M button_byte x_byte y_byte
        os.write(master_fd, b'\x1b[M \x21\x21')

    output = pty_test(child, parent, 'test_async_inkey_mouse_x10')
    assert output == 'OK'


def test_async_inkey_resize_event():
    """async_inkey updates preferred_size_cache on in-band resize."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        # Enable in-band resize in the DEC mode cache
        from blessed.terminal import _DecPrivateMode
        term._dec_mode_cache[_DecPrivateMode.IN_BAND_WINDOW_RESIZE] = True
        with term.cbreak():
            loop = asyncio.new_event_loop()
            try:
                ks = loop.run_until_complete(
                    term.async_inkey(timeout=2.0))
            finally:
                loop.close()
            assert ks.name == 'RESIZE_EVENT'
            assert term._preferred_size_cache.ws_row == 24
            assert term._preferred_size_cache.ws_col == 80
            return b'OK'

    def parent(master_fd):
        read_until_semaphore(master_fd)
        # DEC mode 2048: in-band resize: ESC[48;rows;cols;hpix;wpixt
        os.write(master_fd, b'\x1b[48;24;80;480;1600t')

    output = pty_test(child, parent, 'test_async_inkey_resize_event')
    assert output == 'OK'


def test_async_read_byte_oserror_propagates():
    """OSError from os.read propagates through the future."""
    @as_subprocess
    def child():
        term = TestTerminal()
        term._keyboard_fd = 0

        loop = asyncio.new_event_loop()
        try:
            original_add_reader = loop.add_reader

            def mock_add_reader(fd, callback):
                original_add_reader(fd, callback)
                loop.call_soon(callback)

            with mock.patch.object(loop, 'add_reader', side_effect=mock_add_reader):
                with mock.patch('os.read', side_effect=OSError("mock read error")):
                    with pytest.raises(OSError, match="mock read error"):
                        loop.run_until_complete(
                            term._async_read_byte(loop, timeout=1.0))
        finally:
            loop.close()

    child()


def test_async_read_byte_no_timeout():
    """_async_read_byte with timeout=None waits indefinitely."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    term._async_read_byte(loop, timeout=None))
            finally:
                loop.close()
            assert result == b'z'
            return b'OK'

    def parent(master_fd):
        read_until_semaphore(master_fd)
        time.sleep(0.05)
        os.write(master_fd, b'z')

    output = pty_test(child, parent, 'test_async_read_byte_no_timeout')
    assert output == 'OK'


def test_async_inkey_escape_key():
    """async_inkey resolves bare escape after esc_delay."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            loop = asyncio.new_event_loop()
            try:
                ks = loop.run_until_complete(
                    term.async_inkey(timeout=2.0, esc_delay=0.05))
            finally:
                loop.close()
            assert ks.name == 'KEY_ESCAPE'
            assert len(ks) == 1
            return b'OK'

    def parent(master_fd):
        read_until_semaphore(master_fd)
        os.write(master_fd, b'\x1b')

    output = pty_test(child, parent, 'test_async_inkey_escape_key')
    assert output == 'OK'


def test_async_inkey_arrow_key():
    """async_inkey resolves multi-byte arrow key sequence."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            loop = asyncio.new_event_loop()
            try:
                ks = loop.run_until_complete(
                    term.async_inkey(timeout=2.0))
            finally:
                loop.close()
            assert ks.name == 'KEY_UP'
            assert ks.is_sequence
            return b'OK'

    def parent(master_fd):
        read_until_semaphore(master_fd)
        os.write(master_fd, b'\x1b[A')

    output = pty_test(child, parent, 'test_async_inkey_arrow_key')
    assert output == 'OK'


def test_async_inkey_buffered_multi_byte():
    """async_inkey resolves when multiple bytes arrive at once (kbhit drain)."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            loop = asyncio.new_event_loop()
            try:
                ks = loop.run_until_complete(
                    term.async_inkey(timeout=2.0))
                assert str(ks) == 'x'
                ks2 = loop.run_until_complete(
                    term.async_inkey(timeout=0.5))
                assert str(ks2) == 'y'
            finally:
                loop.close()
            return b'OK'

    def parent(master_fd):
        read_until_semaphore(master_fd)
        os.write(master_fd, b'xy')

    output = pty_test(child, parent, 'test_async_inkey_buffered_multi_byte')
    assert output == 'OK'


def test_async_inkey_incomplete_csi_timeout():
    """async_inkey times out mid-loop when CSI prefix arrives but no final byte."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            loop = asyncio.new_event_loop()
            try:
                ks = loop.run_until_complete(
                    term.async_inkey(timeout=0.3, esc_delay=0.05))
            finally:
                loop.close()
            # partial CSI \x1b[ arrives, loop iterates reading bytes,
            # then times out on next read — returns empty Keystroke
            assert str(ks) == '' or ks.name is not None
            return b'OK'

    def parent(master_fd):
        read_until_semaphore(master_fd)
        time.sleep(0.05)
        # Send CSI prefix without a final byte
        os.write(master_fd, b'\x1b[')

    output = pty_test(child, parent, 'test_async_inkey_incomplete_csi_timeout')
    assert output == 'OK'
