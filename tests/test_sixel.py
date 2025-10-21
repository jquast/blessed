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


def test_get_sixel_height_and_width_0s_ungetch():
    """0-second get_sixel_height_and_width call with mocked response via ungetch."""
    def child(term):
        stime = time.time()
        term.ungetch('\x1b[?2;0;800;600S')

        height, width = term.get_sixel_height_and_width(timeout=0.01)
        assert math.floor(time.time() - stime) == 0.0
        assert (height, width) == (600, 800)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_get_sixel_height_and_width_0s_ungetch')
    assert 'OK' in output


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
@pytest.mark.parametrize('method_name,expected_result,max_time', [
    ('get_sixel_height_and_width', (-1, -1), 0.15),
    ('get_sixel_colors', -1, 0.18),  # Longer: queries XTSMGRAPHICS + DA1
    ('get_cell_height_and_width', (-1, -1), 0.15),
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


@pytest.mark.parametrize('method_name,ungetch_response,expected_result', [
    ('get_sixel_colors', '\x1b[?1;0;256S', 256),
    ('get_cell_height_and_width', '\x1b[6;16;8t', (16, 8)),
])
def test_sixel_query_methods_success(method_name, ungetch_response, expected_result):
    """Sixel query methods return expected values with valid responses."""
    def child(term):
        term.ungetch(ungetch_response)
        result = getattr(term, method_name)(timeout=0.01)
        assert result == expected_result
        return b'OK'

    output = pty_test(child, parent_func=None, test_name=f'test_{method_name}_success')
    assert 'OK' in output


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_sixel_height_and_width_xtsmgraphics_success():
    """Test sixel height and width succeeds quickly with XTSMGRAPHICS response."""
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
        # Read and discard the query sequence
        os.read(master_fd, 100)
        # Respond immediately with XTSMGRAPHICS
        os.write(master_fd, b'\x1b[?2;0;1024;768S')

    stime = time.time()
    output = pty_test(child, parent, 'test_sixel_height_and_width_xtsmgraphics_success')
    dimensions, duration = output.split('|')

    assert dimensions == '768x1024'
    # Should complete very quickly (not wait for fallback)
    assert float(duration) < 0.2
    assert math.floor(time.time() - stime) == 0.0


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_sixel_height_and_width_fallback_to_xtwinops():
    """Test sixel height and width falls back to XTWINOPS after XTSMGRAPHICS timeout."""
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
        # Read and discard first query (XTSMGRAPHICS)
        os.read(master_fd, 100)
        # Wait for XTSMGRAPHICS timeout, then read XTWINOPS query
        time.sleep(0.55)  # timeout/2 = 0.5, add a bit
        os.read(master_fd, 100)  # Read XTWINOPS query
        # Respond to XTWINOPS 14t (window size)
        os.write(master_fd, b'\x1b[4;600;800t')

    stime = time.time()
    output = pty_test(child, parent, 'test_sixel_height_and_width_fallback_to_xtwinops')
    dimensions, duration = output.split('|')

    assert dimensions == '600x800'
    # Should take around timeout/2 (0.5s) + response time
    assert 0.5 <= float(duration) <= 0.7
    assert math.floor(time.time() - stime) == 0.0


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_sixel_height_and_width_both_timeout():
    """Test sixel height and width returns (-1, -1) when both methods timeout."""
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
        # Read and discard first query (XTSMGRAPHICS)
        os.read(master_fd, 100)
        # Wait for XTSMGRAPHICS timeout, then read XTWINOPS query
        time.sleep(0.55)  # timeout/2 = 0.5, add a bit
        os.read(master_fd, 100)  # Read XTWINOPS query
        # Don't respond - let XTWINOPS timeout too

    stime = time.time()
    output = pty_test(child, parent, 'test_sixel_height_and_width_both_timeout')
    dimensions, duration = output.split('|')

    assert dimensions == '-1x-1'
    # Should take close to full timeout (1.0s)
    assert 0.9 <= float(duration) <= 1.2
    assert math.floor(time.time() - stime) == 1.0


@pytest.mark.parametrize('method_name,ungetch_response,expected_result', [
    ('get_sixel_height_and_width', '\x1b[?2;0;640;480S', (480, 640)),
    ('get_cell_height_and_width', '\x1b[6;20;10t', (20, 10)),
])
def test_sixel_methods_caching(method_name, ungetch_response, expected_result):
    """Sixel query methods cache results unless force=True."""
    def child(term):
        term.ungetch(ungetch_response)
        result1 = getattr(term, method_name)(timeout=0.01)
        assert result1 == expected_result

        result2 = getattr(term, method_name)(timeout=0.01)
        assert result2 == expected_result

        result3 = getattr(term, method_name)(timeout=0.01, force=True)
        assert result3 == (-1, -1)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name=f'test_sixel_methods_caching_{method_name}')
    assert 'OK' in output


def test_get_sixel_colors_caching():
    """Test that sixel colors are cached unless force=True."""
    def child(term):
        term.ungetch('\x1b[?1;0;256S')
        colors1 = term.get_sixel_colors(timeout=0.01)
        assert colors1 == 256

        colors2 = term.get_sixel_colors(timeout=0.01)
        assert colors2 == 256

        colors3 = term.get_sixel_colors(timeout=0.01, force=True)
        assert colors3 == -1
        return b'OK'

    output = pty_test(child, parent_func=None, test_name='test_get_sixel_colors_caching')
    assert 'OK' in output


def test_timeout_reduction_subprocess():
    """Test timeout reduction path when XTSMGRAPHICS fails (subprocess version)."""
    def child(term):
        # Call with a real timeout to trigger the timeout reduction path
        # Both XTSMGRAPHICS and XTWINOPS will timeout (no ungetch)
        result = term.get_sixel_height_and_width(timeout=0.2, force=True)
        assert result == (-1, -1)
        # Should cache failure in both caches
        assert term._xtsmgraphics_cache == (-1, -1)
        assert term._xtwinops_cache == (-1, -1)
        return b'OK'

    output = pty_test(child, parent_func=None, test_name='test_timeout_reduction_subprocess')
    assert 'OK' in output


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_timeout_reduction_after_xtsmgraphics_fails():
    """Test timeout is reduced after XTSMGRAPHICS times out and fallback uses reduced timeout."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            result = term.get_sixel_height_and_width(timeout=0.6, force=True)
            elapsed = time.time() - stime

            cached_value = term._xtsmgraphics_cache
            result_str = (f'{result[0]}x{result[1]}|{elapsed:.2f}|'
                          f'{cached_value[0]}x{cached_value[1]}')
            return result_str.encode('utf-8')

    def parent(master_fd):
        read_until_semaphore(master_fd)
        os.read(master_fd, 100)  # Read XTSMGRAPHICS query
        time.sleep(0.33)  # Wait for first timeout (timeout/2 = 0.3 seconds)
        os.read(master_fd, 100)  # Read XTWINOPS query

    output = pty_test(child, parent, 'test_timeout_reduction_after_xtsmgraphics_fails')
    result, elapsed, cached = output.split('|')

    assert result == '-1x-1'
    # Should take close to full timeout (0.6s) - XTSMGRAPHICS gets 0.3s, XTWINOPS gets ~0.3s
    assert 0.55 <= float(elapsed) <= 0.7
    # Should cache the failure
    assert cached == '-1x-1'


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_xtsmgraphics_sticky_failure():
    """Test that XTSMGRAPHICS failure sets sticky flag and skips to XTWINOPS."""
    def child(term):
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            # First call - XTSMGRAPHICS will timeout, fallback to XTWINOPS
            stime1 = time.time()
            height1, width1 = term.get_sixel_height_and_width(timeout=1.0, force=True)
            duration1 = time.time() - stime1

            # Second call - should skip XTSMGRAPHICS (sticky failure) and go directly to XTWINOPS
            stime2 = time.time()
            height2, width2 = term.get_sixel_height_and_width(timeout=1.0, force=True)
            duration2 = time.time() - stime2

            result = f'{height1}x{width1}|{duration1:.2f}|{height2}x{width2}|{duration2:.2f}'
            return result.encode('utf-8')

    def parent(master_fd):
        read_until_semaphore(master_fd)

        # First query - read XTSMGRAPHICS, wait for timeout, read XTWINOPS, respond
        os.read(master_fd, 100)  # XTSMGRAPHICS query
        time.sleep(0.55)  # timeout/2 = 0.5, add a bit
        os.read(master_fd, 100)  # XTWINOPS query after fallback
        os.write(master_fd, b'\x1b[4;480;640t')

        # Second query - should only be XTWINOPS (sticky failure skips XTSMGRAPHICS)
        os.read(master_fd, 100)  # XTWINOPS query
        time.sleep(0.05)
        os.write(master_fd, b'\x1b[4;480;640t')

    output = pty_test(child, parent, 'test_xtsmgraphics_sticky_failure')
    dim1, dur1, dim2, dur2 = output.split('|')

    # First call should fallback (takes ~timeout/2)
    assert dim1 == '480x640'
    assert 0.5 <= float(dur1) <= 0.7

    # Second call should skip XTSMGRAPHICS and go directly to XTWINOPS (fast)
    assert dim2 == '480x640'
    assert float(dur2) < 0.2  # Much faster than first call


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
@pytest.mark.parametrize('method_name,expected_failure,max_time', [
    ('get_sixel_height_and_width', (-1, -1), 0.15),
    ('get_sixel_colors', -1, 0.18),  # Longer: queries XTSMGRAPHICS + DA1
    ('get_cell_height_and_width', (-1, -1), 0.15),
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

        # Third call with force=True - should bypass cache and timeout again
        stime3 = time.time()
        result3 = getattr(term, method_name)(timeout=0.1, force=True)
        elapsed3 = time.time() - stime3
        assert result3 == expected_failure
        assert 0.08 <= elapsed3 <= max_time
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


def test_konsole_bogus_xtsmgraphics_validates_with_xtwinops():
    """Test that bogus XTSMGRAPHICS values (like Konsole's 16384x16384) validate with XTWINOPS."""
    def child(term):
        # Simulate Konsole: XTSMGRAPHICS returns 16384x16384 (bogus),
        # then XTWINOPS returns real size
        # ungetch in reverse order - XTWINOPS response first, then XTSMGRAPHICS
        term.ungetch('\x1b[4;1080;1920t')  # XTWINOPS 14t response: 1920x1080 window
        term.ungetch('\x1b[?2;0;16384;16384S')  # XTSMGRAPHICS response: bogus 16384x16384

        height, width = term.get_sixel_height_and_width(timeout=0.1)

        # Should use XTWINOPS value, not the bogus XTSMGRAPHICS value
        assert (height, width) == (1080, 1920)
        # XTWINOPS result should be cached
        assert term._xtwinops_cache == (1080, 1920)
        # XTSMGRAPHICS detected Konsole's bogus 16384x16384 and cached failure
        assert term._xtsmgraphics_cache == (-1, -1)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_konsole_bogus_xtsmgraphics_validates_with_xtwinops')
    assert 'OK' in output


@pytest.mark.skipif(TEST_QUICK, reason="TEST_QUICK specified")
def test_konsole_bogus_xtsmgraphics_real_terminal():
    """Test Konsole-like behavior with real PTY to verify both queries are made."""
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
        # Read XTSMGRAPHICS query
        os.read(master_fd, 100)
        # Respond with bogus Konsole-like value
        os.write(master_fd, b'\x1b[?2;0;16384;16384S')
        # Give child time to process, then read XTWINOPS validation query
        time.sleep(0.02)
        os.read(master_fd, 100)
        # Respond with realistic window size
        os.write(master_fd, b'\x1b[4;1080;1920t')

    output = pty_test(child, parent, 'test_konsole_bogus_xtsmgraphics_real_terminal')
    dimensions, duration = output.split('|')

    # Should use XTWINOPS value, not bogus XTSMGRAPHICS
    assert dimensions == '1080x1920'
    # Should complete quickly (both queries succeed)
    assert float(duration) < 0.3


@pytest.mark.parametrize('xtsmgraphics_cache,xtwinops_cache,expected_result', [
    ((768, 1024), (1080, 1920), (768, 1024)),  # XTSMGRAPHICS succeeded
    ((-1, -1), (1080, 1920), (1080, 1920)),    # XTSMGRAPHICS failed, XTWINOPS succeeded
])
def test_fast_path_with_both_caches_populated(xtsmgraphics_cache,
                                              xtwinops_cache,
                                              expected_result):
    """Test fast path returns cached value instantly when both caches populated."""
    def child(term):
        term._xtsmgraphics_cache = xtsmgraphics_cache
        term._xtwinops_cache = xtwinops_cache

        stime = time.time()
        height, width = term.get_sixel_height_and_width(timeout=0.1)
        elapsed = time.time() - stime

        assert (height, width) == expected_result
        assert elapsed < 0.01  # Instant from cache
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_fast_path_cache')
    assert 'OK' in output


def test_xtwinops_cache_return_after_xtsmgraphics_fails():
    """Test returning cached XTWINOPS value when XTSMGRAPHICS fails."""
    def child(term):
        # First call: XTSMGRAPHICS will fail, XTWINOPS will succeed
        term.ungetch('\x1b[4;1080;1920t')  # XTWINOPS response
        result1 = term.get_sixel_height_and_width(timeout=0.1)
        assert result1 == (1080, 1920)
        assert term._xtsmgraphics_cache == (-1, -1)
        assert term._xtwinops_cache == (1080, 1920)

        # Second call: Should return cached XTWINOPS without re-querying
        stime = time.time()
        result2 = term.get_sixel_height_and_width(timeout=0.1)
        elapsed = time.time() - stime
        assert result2 == (1080, 1920)
        # Should be instant from cache
        assert elapsed < 0.01
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_xtwinops_cache_return_after_xtsmgraphics_fails')
    assert 'OK' in output


def test_xtsmgraphics_cache_hit_without_xtwinops_cache():
    """XTSMGRAPHICS cache hit when XTWINOPS cache is None."""
    def child(term):
        # Prepopulate only XTSMGRAPHICS cache with successful value
        term._xtsmgraphics_cache = (768, 1024)
        term._xtwinops_cache = None

        stime = time.time()
        height, width = term.get_sixel_height_and_width(timeout=0.1)
        elapsed = time.time() - stime

        assert (height, width) == (768, 1024)
        assert elapsed < 0.01
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_xtsmgraphics_cache_hit_without_xtwinops_cache')
    assert 'OK' in output


def test_force_xtwinops_query_with_existing_cache():
    """Force XTWINOPS query even with existing cache."""
    def child(term):
        # Prepopulate both caches with XTSMGRAPHICS failed
        term._xtsmgraphics_cache = (-1, -1)
        term._xtwinops_cache = (1080, 1920)

        # Call with force=True - should re-query XTWINOPS, no ungetch so query will timeout
        result = term.get_sixel_height_and_width(timeout=0.1, force=True)

        # Should get timeout result, not cached value
        assert result == (-1, -1)
        assert term._xtwinops_cache == (-1, -1)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_force_xtwinops_query_with_existing_cache')
    assert 'OK' in output


def test_xtwinops_cache_return_on_xtsmgraphics_query_fails():
    """Return cached XTWINOPS when XTSMGRAPHICS query fails."""
    def child(term):
        # Prepopulate only XTWINOPS cache, XTSMGRAPHICS cache is None
        term._xtsmgraphics_cache = None
        term._xtwinops_cache = (1080, 1920)

        # Call without force - XTSMGRAPHICS will be queried, fail (no ungetch),
        # then return cached XTWINOPS
        height, width = term.get_sixel_height_and_width(timeout=0.1)

        assert (height, width) == (1080, 1920)
        assert term._xtsmgraphics_cache == (-1, -1)
        return b'OK'

    output = pty_test(child, parent_func=None,
                      test_name='test_xtwinops_cache_return_on_xtsmgraphics_query_fails')
    assert 'OK' in output
