"""Tests for sixel graphics queries."""
# std imports
import io
import os
import sys
import math
import time

# 3rd party
import pytest

# local
from .conftest import TEST_QUICK, IS_WINDOWS
from .accessories import (
    SEMAPHORE,
    TestTerminal,
    as_subprocess,
    read_until_semaphore,
    pty_test
)

pytestmark = pytest.mark.skipif(
    IS_WINDOWS, reason="ungetch and PTY testing not supported on Windows")


@pytest.mark.parametrize('da1_response,has_sixel,expected_output', [
    ('\x1b[?64;1;2;4c', True, 'SIXEL_YES'),  # VT420 with Sixel (4)
    ('\x1b[?64;1;2c', False, 'SIXEL_NO'),    # VT420 without Sixel
])
def test_does_sixel_with_and_without_support(da1_response, has_sixel, expected_output):
    """Test does_sixel() returns correct value based on DA1 response."""
    def child(term):
        term.ungetch(da1_response)
        result = term.does_sixel(timeout=0.01)
        assert result is has_sixel
        return expected_output.encode('utf-8')

    output = pty_test(child, parent_func=None,
                      test_name=f'test_does_sixel_{expected_output.lower()}')
    assert expected_output in output


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_does_sixel_returns_false_on_timeout():
    """Test does_sixel() returns False when timeout occurs."""
    def child(term):
        stime = time.time()
        result = term.does_sixel(timeout=0.1)
        elapsed = time.time() - stime
        assert result is False
        assert 0.08 <= elapsed <= 0.15
        return b'SIXEL_TIMEOUT'

    output = pty_test(child, parent_func=None, test_name='test_does_sixel_returns_false_on_timeout')
    assert output == '\x1b[cSIXEL_TIMEOUT'


def test_does_sixel_uses_cache():
    """Test does_sixel() uses cached device attributes."""
    def child(term):
        # DA1 response: VT420 (64) with 132-col (1), Printer (2), Sixel (4)
        term.ungetch('\x1b[?64;1;2;4c')
        result1 = term.does_sixel(timeout=0.01)

        # Second call uses cache, no new query sent
        result2 = term.does_sixel(timeout=0.01)

        assert result1 is True
        assert result2 is True
        return b'SIXEL_CACHE'

    output = pty_test(child, parent_func=None, test_name='test_does_sixel_uses_cache')
    assert output == '\x1b[cSIXEL_CACHE'


def test_does_sixel_not_a_tty():
    """Test does_sixel() returns False when not a TTY."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = False

        result = term.does_sixel(timeout=0.01)
        assert result is False
    child()


def test_get_cell_height_and_width_success():
    """get_cell_height_and_width returns expected tuple with valid response."""
    def child(term):
        term.ungetch('\x1b[6;16;8t')
        result = term.get_cell_height_and_width(timeout=0.01)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result == (16, 8)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_cell_height_and_width_success')
    assert 'OK' in output


def test_get_cell_height_and_width_timeout():
    """get_cell_height_and_width returns (-1, -1) on timeout."""
    def child(term):
        result = term.get_cell_height_and_width(timeout=0.01)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result == (-1, -1)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_cell_height_and_width_timeout')
    assert 'OK' in output


def test_get_cell_height_and_width_caching():
    """get_cell_height_and_width caches results unless force=True."""
    def child(term):
        term.ungetch('\x1b[6;20;10t')
        result1 = term.get_cell_height_and_width(timeout=0.01)
        assert result1 == (20, 10)

        result2 = term.get_cell_height_and_width(timeout=0.01)
        assert result2 == (20, 10)

        result3 = term.get_cell_height_and_width(timeout=0.01, force=True)
        assert result3 == (-1, -1)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_cell_height_and_width_caching')
    assert 'OK' in output


def test_get_sixel_height_and_width_0s_ungetch():
    """0-second get_sixel_height_and_width call with mocked response via ungetch."""
    def child(term):
        stime = time.time()
        # XTWINOPS 16t first: cell is 16x8, with 24x80 terminal = 384x640
        term.ungetch('\x1b[6;16;8t')

        height, width = term.get_sixel_height_and_width(timeout=0.01)
        assert math.floor(time.time() - stime) == 0.0
        assert (height, width) == (384, 640)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_sixel_height_and_width_0s_ungetch')
    assert 'OK' in output


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
@pytest.mark.parametrize('method_name,expected_result,max_time', [
    ('get_sixel_height_and_width', (-1, -1), 0.15),
    ('get_sixel_colors', -1, 0.18),  # Longer: queries XTSMGRAPHICS + DA1
])
def test_sixel_methods_timeout(method_name, expected_result, max_time):
    """Sixel query methods return failure values on timeout."""
    def child(term):
        stime = time.time()

        result = getattr(term, method_name)(timeout=0.1)
        elapsed = time.time() - stime
        assert 0.08 <= elapsed <= max_time
        assert result == expected_result
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name=f'test_sixel_methods_timeout_{method_name}')
    assert 'OK' in output


def test_get_sixel_height_and_width_invalid_response():
    """get_sixel_height_and_width returns (-1, -1) on malformed response."""
    def child(term):
        term.ungetch('\x1b[?2;1;0S')  # Invalid - missing dimensions

        height, width = term.get_sixel_height_and_width(timeout=0.01)
        assert (height, width) == (-1, -1)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_sixel_height_and_width_invalid_response')
    assert 'OK' in output


def test_get_sixel_colors_success():
    """get_sixel_colors returns expected value with valid response."""
    def child(term):
        term.ungetch('\x1b[?1;0;256S')
        result = term.get_sixel_colors(timeout=0.01)
        assert result == 256
        return b'OK'

    output = pty_test(child, parent_func=None, test_name='test_get_sixel_colors_success')
    assert 'OK' in output


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_sixel_height_and_width_xtwinops_cell_success():
    """Test sixel height and width succeeds quickly with XTWINOPS 16t response."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            height, width = term.get_sixel_height_and_width(timeout=1.0)
            duration_s = time.time() - stime
            result = f'{height}x{width}|{duration_s:.2f}'
            return result.encode('utf-8')

    def parent(master_fd):
        read_until_semaphore(master_fd)
        # Read and discard the query sequence (XTWINOPS 16t)
        os.read(master_fd, 100)
        # Respond immediately with XTWINOPS 16t: cell is 16x8 pixels
        # Terminal is typically 24 rows x 80 cols, so 384x640 total pixels
        os.write(master_fd, b'\x1b[6;16;8t')

    stime = time.time()
    output = pty_test(child, parent, 'test_sixel_height_and_width_xtwinops_cell_success')
    dimensions, duration = output.split('|')

    # Assuming 24 rows x 80 cols: 16*24 = 384 height, 8*80 = 640 width
    assert dimensions == '384x640'
    # Should complete very quickly (not wait for fallback)
    assert float(duration) < 0.2
    assert math.floor(time.time() - stime) == 0.0


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_sixel_height_and_width_fallback_to_xtwinops():
    """Test sixel height and width falls back to XTWINOPS 14t after 16t timeout."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            height, width = term.get_sixel_height_and_width(timeout=1.0, force=True)
            duration_s = time.time() - stime
            result = f'{height}x{width}|{duration_s:.2f}'
            return result.encode('utf-8')

    def parent(master_fd):
        read_until_semaphore(master_fd)
        # Read and discard first query (XTWINOPS 16t - cell size)
        os.read(master_fd, 100)
        # Wait for XTWINOPS 16t timeout, then read XTWINOPS 14t query
        time.sleep(0.36)  # timeout/3, add a bit
        os.read(master_fd, 100)  # Read XTWINOPS 14t query
        # Respond to XTWINOPS 14t (window size)
        os.write(master_fd, b'\x1b[4;600;800t')

    stime = time.time()
    output = pty_test(child, parent, 'test_sixel_height_and_width_fallback_to_xtwinops')
    dimensions, duration = output.split('|')

    assert dimensions == '600x800'
    # Should take around timeout/3 + a bit
    assert 0.30 <= float(duration) <= 0.5
    assert math.floor(time.time() - stime) == 0.0


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_sixel_height_and_width_both_timeout():
    """Test sixel height and width returns (-1, -1) when all methods timeout."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            height, width = term.get_sixel_height_and_width(timeout=1.0, force=True)
            duration_s = time.time() - stime
            result = f'{height}x{width}|{duration_s:.2f}'
            return result.encode('utf-8')

    def parent(master_fd):
        read_until_semaphore(master_fd)
        # Read and discard first query (XTWINOPS 16t)
        os.read(master_fd, 100)
        # Wait for first timeout, then read XTWINOPS 14t query
        time.sleep(0.36)  # timeout/3, add a bit
        os.read(master_fd, 100)  # Read XTWINOPS 14t query
        # Wait for second timeout, read XTSMGRAPHICS query
        time.sleep(0.36)
        os.read(master_fd, 100)  # Read XTSMGRAPHICS query
        # Don't respond - let all timeout (TIOCSWINSZ doesn't send query)

    stime = time.time()
    output = pty_test(child, parent, 'test_sixel_height_and_width_both_timeout')
    dimensions, duration = output.split('|')

    assert dimensions == '-1x-1'
    # Should take around timeout/3 * 3 = 1.0s for the three queries
    assert 0.90 <= float(duration) <= 1.15
    assert math.floor(time.time() - stime) <= 1.0


@pytest.mark.parametrize('method_name,ungetch_response,expected_result,expected_failure', [
    ('get_sixel_height_and_width', '\x1b[6;20;8t', (480, 640), (-1, -1)),
    ('get_sixel_colors', '\x1b[?1;0;256S', 256, -1),
])
def test_sixel_methods_caching(method_name, ungetch_response, expected_result, expected_failure):
    """Sixel query methods cache results unless force=True."""
    def child(term):
        term.ungetch(ungetch_response)
        result1 = getattr(term, method_name)(timeout=0.01)
        assert result1 == expected_result

        result2 = getattr(term, method_name)(timeout=0.01)
        assert result2 == expected_result

        result3 = getattr(term, method_name)(timeout=0.01, force=True)
        assert result3 == expected_failure
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name=f'test_sixel_methods_caching_{method_name}')
    assert 'OK' in output


def test_timeout_reduction_subprocess():
    """Test timeout path when all methods fail (subprocess version)."""
    def child(term):
        # Call with a real timeout to trigger the timeout path
        # All methods will timeout (no ungetch)
        result = term.get_sixel_height_and_width(timeout=0.2, force=True)
        assert result == (-1, -1)
        # Should cache failure in all caches
        assert term._xtwinops_cell_cache == (-1, -1)
        assert term._xtwinops_cache == (-1, -1)
        assert term._xtsmgraphics_cache == (-1, -1)
        return b'OK'

    output = pty_test(child, parent_func=None, test_name='test_timeout_reduction_subprocess')
    assert 'OK' in output


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_timeout_allocation_across_methods():
    """Test timeout is allocated across detection methods."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            result = term.get_sixel_height_and_width(timeout=0.8, force=True)
            elapsed = time.time() - stime

            cell_cached = term._xtwinops_cell_cache
            window_cached = term._xtwinops_cache
            result_str = (f'{result[0]}x{result[1]}|{elapsed:.2f}|'
                          f'{cell_cached[0]}x{cell_cached[1]}|'
                          f'{window_cached[0]}x{window_cached[1]}')
            return result_str.encode('utf-8')

    def parent(master_fd):
        read_until_semaphore(master_fd)
        os.read(master_fd, 100)  # Read XTWINOPS 16t query
        time.sleep(0.29)  # Wait for first timeout (timeout/3 ≈ 0.267 seconds)
        os.read(master_fd, 100)  # Read XTWINOPS 14t query
        time.sleep(0.29)  # Wait for second timeout
        os.read(master_fd, 100)  # Read XTSMGRAPHICS query

    output = pty_test(child, parent, 'test_timeout_allocation_across_methods')
    result, elapsed, cell_cached, window_cached = output.split('|')

    assert result == '-1x-1'
    # Should take around 3 * timeout/3 = 0.8s (3 queries at third timeout each)
    assert 0.75 <= float(elapsed) <= 0.95
    # Should cache the failures
    assert cell_cached == '-1x-1'
    assert window_cached == '-1x-1'


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_cell_cache_sticky_failure():
    """Test that cell cache failure is cached but can be bypassed with force=True."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            # First call - cell will timeout, fallback to window
            stime1 = time.time()
            height1, width1 = term.get_sixel_height_and_width(timeout=1.0, force=True)
            duration1 = time.time() - stime1

            # Second call - should skip cell (sticky failure) and go directly to window
            stime2 = time.time()
            height2, width2 = term.get_sixel_height_and_width(timeout=1.0, force=True)
            duration2 = time.time() - stime2

            result = f'{height1}x{width1}|{duration1:.2f}|{height2}x{width2}|{duration2:.2f}'
            return result.encode('utf-8')

    def parent(master_fd):
        read_until_semaphore(master_fd)

        # First query - read cell, wait for timeout, read window, respond
        os.read(master_fd, 100)  # XTWINOPS 16t query
        time.sleep(0.36)  # timeout/3 ≈ 0.33s, add a bit
        os.read(master_fd, 100)  # XTWINOPS 14t query after fallback
        os.write(master_fd, b'\x1b[4;480;640t')

        # Second query with force=True - re-queries cell, then window
        os.read(master_fd, 100)  # XTWINOPS 16t query (force=True bypasses sticky failure)
        time.sleep(0.36)  # timeout/3 ≈ 0.33s, add a bit
        os.read(master_fd, 100)  # XTWINOPS 14t query after fallback
        os.write(master_fd, b'\x1b[4;480;640t')

    output = pty_test(child, parent, 'test_cell_cache_sticky_failure')
    dim1, dur1, dim2, dur2 = output.split('|')

    # First call should fallback (takes ~timeout/3)
    assert dim1 == '480x640'
    assert 0.30 <= float(dur1) <= 0.5

    # Second call with force=True also re-queries and fallbacks (takes ~timeout/3)
    assert dim2 == '480x640'
    assert 0.30 <= float(dur2) <= 0.5


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
@pytest.mark.parametrize('method_name,expected_failure,max_time', [
    ('get_sixel_height_and_width', (-1, -1), 0.15),
    ('get_sixel_colors', -1, 0.18),  # Longer: queries XTSMGRAPHICS + DA1
])
def test_cached_failure_returns_immediately(method_name, expected_failure, max_time):
    """Test that cached failure results return immediately on subsequent calls."""
    def child(term):
        # First call - will timeout and cache failure result
        stime1 = time.time()
        result1 = getattr(term, method_name)(timeout=0.1, force=True)
        elapsed1 = time.time() - stime1
        assert result1 == expected_failure
        assert 0.08 <= elapsed1 <= max_time

        # Second call - should return cached failure immediately (no timeout)
        stime2 = time.time()
        result2 = getattr(term, method_name)(timeout=0.1)
        elapsed2 = time.time() - stime2
        assert result2 == expected_failure
        assert elapsed2 < 0.01  # Should be instant from cache

        # Third call with force=True - bypasses cache and re-queries
        stime3 = time.time()
        result3 = getattr(term, method_name)(timeout=0.1, force=True)
        elapsed3 = time.time() - stime3
        assert result3 == expected_failure
        assert 0.08 <= elapsed3 <= max_time  # Should timeout again
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name=f'test_cached_failure_returns_immediately_{method_name}')
    assert 'OK' in output


@pytest.mark.parametrize('da1_response,expected_colors', [
    ('\x1b[?64;1;2;4c', 256),  # DA1 with sixel support (feature 4) -> defaults to 256
    ('\x1b[?64;1;2c', -1),     # DA1 without sixel -> returns -1
])
def test_get_sixel_colors_fallback_to_da1(da1_response, expected_colors):
    """get_sixel_colors falls back to DA1 when XTSMGRAPHICS fails."""
    def child(term):
        # ungetch DA1 response, no XTSMGRAPHICS color response (will timeout)
        term.ungetch(da1_response)
        colors = term.get_sixel_colors(timeout=0.1)

        assert colors == expected_colors
        assert term._xtsmgraphics_colors_cache == expected_colors
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name=f'test_get_sixel_colors_fallback_{expected_colors}')
    assert 'OK' in output


def test_sixel_height_width_with_xtwinops_14t():
    """Test that XTWINOPS 14t fallback works when cell size query fails."""
    def child(term):
        # XTWINOPS 16t fails (no response), XTWINOPS 14t succeeds
        term.ungetch('\x1b[4;1080;1920t')  # XTWINOPS 14t response: 1920x1080 window

        height, width = term.get_sixel_height_and_width(timeout=0.1)

        # Should use XTWINOPS 14t value
        assert (height, width) == (1080, 1920)
        # XTWINOPS 14t result should be cached
        assert term._xtwinops_cache == (1080, 1920)
        # XTWINOPS 16t should have cached failure
        assert term._xtwinops_cell_cache == (-1, -1)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_sixel_height_width_with_xtwinops_14t')
    assert 'OK' in output


def test_konsole_bogus_xtsmgraphics_16384():
    """Test that bogus XTSMGRAPHICS values (like Konsole's 16384x16384) are rejected."""
    def child(term):
        # Note that real Konsole returns the correct values, answering to
        # XTWINOPS, this is just a "theoretical" terminal -- for code coverage.
        term.ungetch('\x1b[?2;0;16384;16384S')  # XTSMGRAPHICS response: bogus 16384x16384
        # Pre-cache failures to skip directly to XTSMGRAPHICS
        term._xtwinops_cell_cache = (-1, -1)
        term._xtwinops_cache = (-1, -1)

        height, width = term.get_sixel_height_and_width(timeout=0.1)

        # Should reject the bogus 16384x16384 value and return failure
        # XTSMGRAPHICS detected Konsole's bogus 16384x16384 and cached failure
        assert (height, width) == (-1, -1)
        assert term._xtsmgraphics_cache == (-1, -1)

    pty_test(child, parent_func=None, test_name='test_konsole_bogus_xtsmgraphics_16384')


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_konsole_bogus_xtsmgraphics_real_terminal():
    """Test _get_xtsmgraphics rejects Konsole's bogus 16384x16384 value."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            result = term._get_xtsmgraphics(timeout=0.5)
            return f'{result[0]}x{result[1]}'.encode('utf-8')

    def parent(master_fd):
        read_until_semaphore(master_fd)
        # Read XTSMGRAPHICS query
        os.read(master_fd, 100)
        # Respond with bogus Konsole-like value
        os.write(master_fd, b'\x1b[?2;0;16384;16384S')

    output = pty_test(child, parent, 'test_konsole_bogus_xtsmgraphics_real_terminal')

    # Should reject the bogus 16384x16384 value and return failure
    assert output == '-1x-1'


@pytest.mark.parametrize('cell_cache,window_cache,expected_result', [
    ((16, 8), None, (384, 640)),      # Cell size: 16*24=384, 8*80=640
    ((-1, -1), (1080, 1920), (1080, 1920)),  # Cell failed, window succeeded
])
def test_fast_path_with_caches_populated(cell_cache, window_cache, expected_result):
    """Test returns cached value instantly when caches populated."""
    def child(term):
        term._xtwinops_cell_cache = cell_cache
        term._xtwinops_cache = window_cache
        term._xtsmgraphics_cache = None

        stime = time.time()
        height, width = term.get_sixel_height_and_width(timeout=0.1)
        elapsed = time.time() - stime

        assert (height, width) == expected_result
        assert elapsed < 0.01  # Instant from cache
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_fast_path_cache')
    assert 'OK' in output


def test_xtwinops_window_cache_after_cell_fails():
    """Test returning cached XTWINOPS 14t value when 16t fails."""
    def child(term):
        # First call: XTWINOPS 16t will fail, XTWINOPS 14t will succeed
        term.ungetch('\x1b[4;1080;1920t')  # XTWINOPS 14t response
        result1 = term.get_sixel_height_and_width(timeout=0.1)
        assert result1 == (1080, 1920)
        assert term._xtwinops_cell_cache == (-1, -1)
        assert term._xtwinops_cache == (1080, 1920)

        # Second call: Should return cached XTWINOPS 14t without re-querying
        stime = time.time()
        result2 = term.get_sixel_height_and_width(timeout=0.1)
        elapsed = time.time() - stime
        assert result2 == (1080, 1920)
        # Should be instant from cache
        assert elapsed < 0.01
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_xtwinops_window_cache_after_cell_fails')
    assert 'OK' in output


def test_force_query_with_existing_cache():
    """Force query even with existing cache."""
    def child(term):
        # Prepopulate all caches
        term._xtwinops_cell_cache = (16, 8)
        term._xtwinops_cache = (1080, 1920)
        term._xtsmgraphics_cache = (-1, -1)

        # Call with force=True - should re-query, no ungetch so query will timeout
        result = term.get_sixel_height_and_width(timeout=0.1, force=True)

        # Should get timeout result, not cached value
        assert result == (-1, -1)
        assert term._xtwinops_cell_cache == (-1, -1)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_force_query_with_existing_cache')
    assert 'OK' in output


def test_window_cache_return_when_cell_query_fails():
    """Return cached XTWINOPS 14t when cell query fails, caching the failure."""
    def child(term):
        # Prepopulate only window cache, cell cache is None
        term._xtwinops_cell_cache = None
        term._xtwinops_cache = (1080, 1920)
        term._xtsmgraphics_cache = None

        # Call without force - cell query fails and caches failure, then returns window cache
        height, width = term.get_sixel_height_and_width(timeout=0.1)

        assert (height, width) == (1080, 1920)
        # Cell cache now has cached failure from the query attempt
        assert term._xtwinops_cell_cache == (-1, -1)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_window_cache_return_when_cell_query_fails')
    assert 'OK' in output


def test_preferred_size_cache_path():
    """Test get_sixel_height_and_width falls back to preferred_size_cache as last resort."""
    @as_subprocess
    def child():
        from blessed.terminal import WINSZ
        term = TestTerminal()

        # Pre-cache failures for methods 1-3 so it falls through to method 4
        term._xtwinops_cell_cache = (-1, -1)
        term._xtwinops_cache = (-1, -1)
        term._xtsmgraphics_cache = (-1, -1)
        term._preferred_size_cache = WINSZ(ws_row=24, ws_col=80, ws_xpixel=1920, ws_ypixel=1080)

        result = term.get_sixel_height_and_width(timeout=0.1)
        assert result == (1080, 1920)
    child()


def test_preferred_size_cache_with_zero_pixels():
    """Test that zero pixel dimensions in preferred_size_cache are skipped."""
    def child(term):
        from blessed.terminal import WINSZ

        term._preferred_size_cache = WINSZ(ws_row=24, ws_col=80, ws_xpixel=0, ws_ypixel=0)
        term.ungetch('\x1b[6;16;8t')  # Cell size response

        result = term.get_sixel_height_and_width(timeout=0.1)
        assert result == (384, 640)  # Falls through to cell query
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_preferred_size_cache_with_zero_pixels')
    assert 'OK' in output


@pytest.mark.parametrize('ws_ypixel,ws_xpixel', [
    (1920, 0),
    (0, 1080),
])
def test_preferred_size_cache_with_partial_zero_pixels(ws_ypixel, ws_xpixel):
    """Test that partial zero dimensions in preferred_size_cache are skipped."""
    # this is something of a fictional terminal, though maybe for some it may
    # someday be possible, very far down the logical fall-back ladder: that if
    # any of either width or height is 0 through in-band resize protocol, that
    # TIOCSWINSZ is used.
    def child(term):
        from blessed.terminal import WINSZ

        # Pre-cache failures for methods 1-3 so it falls through to method 4
        term._xtwinops_cell_cache = (-1, -1)
        term._xtwinops_cache = (-1, -1)
        term._xtsmgraphics_cache = (-1, -1)
        term._preferred_size_cache = WINSZ(ws_row=24, ws_col=80,
                                           ws_xpixel=ws_xpixel, ws_ypixel=ws_ypixel)

        # Since preferred_size_cache has partial zero, should fall through to TIOCSWINSZ
        # Mock TIOCSWINSZ to return valid dimensions
        original_height_and_width = term._height_and_width

        def mock_height_and_width():
            orig = original_height_and_width()
            return WINSZ(ws_row=orig.ws_row, ws_col=orig.ws_col,
                         ws_xpixel=1600, ws_ypixel=900)

        term._height_and_width = mock_height_and_width

        result = term.get_sixel_height_and_width(timeout=0.1)
        assert result == (900, 1600)  # Falls through to TIOCSWINSZ
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name=f'test_preferred_size_cache_partial_zero_{ws_ypixel}_{ws_xpixel}')
    assert 'OK' in output


def test_xtsmgraphics_cache_hit():
    """Test XTSMGRAPHICS cache is returned when cell and window caches fail."""
    def child(term):
        # Pre-cache failures for cell and window, but success for XTSMGRAPHICS
        term._xtwinops_cell_cache = (-1, -1)
        term._xtwinops_cache = (-1, -1)
        term._xtsmgraphics_cache = (600, 800)

        # Should return cached XTSMGRAPHICS value instantly
        stime = time.time()
        result = term.get_sixel_height_and_width(timeout=0.1)
        elapsed = time.time() - stime

        assert result == (600, 800)
        assert elapsed < 0.01  # Instant from cache
        return b'OK'

    output = pty_test(child, parent_func=None, test_name='test_xtsmgraphics_cache_hit')
    assert 'OK' in output


def test_tiocswinsz_path():
    """Test TIOCSWINSZ path when all queries fail but ioctl returns pixel dimensions."""
    def child(term):
        from blessed.terminal import WINSZ
        original_height_and_width = term._height_and_width

        def mock_height_and_width():
            orig = original_height_and_width()
            return WINSZ(ws_row=orig.ws_row, ws_col=orig.ws_col,
                         ws_xpixel=1600, ws_ypixel=900)

        term._height_and_width = mock_height_and_width

        result = term.get_sixel_height_and_width(timeout=0.1, force=True)
        assert result == (900, 1600)
        return b'OK'

    output = pty_test(child, parent_func=None, test_name='test_tiocswinsz_path')
    assert 'OK' in output


def test_tiocswinsz_invalid_dimensions():
    """Test TIOCSWINSZ path rejects invalid (zero or too large) pixel dimensions."""
    def child(term):
        from blessed.terminal import WINSZ
        original_height_and_width = term._height_and_width

        def mock_height_and_width():
            orig = original_height_and_width()
            return WINSZ(ws_row=orig.ws_row, ws_col=orig.ws_col,
                         ws_xpixel=50000, ws_ypixel=0)  # Too large, zero

        term._height_and_width = mock_height_and_width

        # Should skip invalid TIOCSWINSZ and fall through to XTSMGRAPHICS
        term.ungetch('\x1b[?2;0;800;600S')  # XTSMGRAPHICS response
        result = term.get_sixel_height_and_width(timeout=0.1, force=True)
        assert result == (600, 800)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_tiocswinsz_invalid_dimensions')
    assert 'OK' in output


def test_get_sixel_height_and_width_not_a_tty():
    """Test get_sixel_height_and_width returns (-1, -1) when not a TTY."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO(), force_styling=True)
        term._is_a_tty = False

        result = term.get_sixel_height_and_width(timeout=0.1)
        assert result == (-1, -1)
    child()
