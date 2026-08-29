"""Configure test fixtures"""

# std imports
import itertools
import os
import platform

# 3rd party
import pytest

# local
from blessed.formatters import _tparm_cached


def pytest_configure(config: pytest.Config) -> None:
    """Normalize environment for consistent test results outside of tox."""
    os.environ.pop('TERM', None)
    os.environ.pop('COLORTERM', None)
    os.environ.pop('TERM_PROGRAM', None)
    os.environ.pop('TERM_PROGRAM_VERSION', None)


try:
    from pytest_codspeed import BenchmarkFixture  # noqa: F401  pylint: disable=unused-import
except ImportError:
    @pytest.fixture
    def benchmark():
        """No-op benchmark fixture for environments without pytest-codspeed."""
        def _passthrough(func, *args, **kwargs):
            return func(*args, **kwargs)
        return _passthrough

IS_WINDOWS = platform.system() == 'Windows'


@pytest.fixture(autouse=True)
def clear_tparm_cache():
    """Discard memoized tparm() results between tests."""
    _tparm_cached.cache_clear()
    yield
    _tparm_cached.cache_clear()


many_lines_params = [40, 80]
# we must test a '1' column for conditional in _handle_long_word
many_columns_params = [1, 10]


def envvar_enabled(envvar):
    """
    Return True if environment variable is set and enabled

    unset values, 'no', 0, and 'false' and treated as False regardless of case
    All other values are considered True
    """

    value = os.environ.get(envvar, False)

    if value is False:
        return value

    if value.lower() in {'no', 'false'}:
        return False

    try:
        return bool(int(value))
    except ValueError:
        return True


TEST_FULL = envvar_enabled('TEST_FULL')
TEST_KEYBOARD = envvar_enabled('TEST_KEYBOARD')
TEST_QUICK = envvar_enabled('TEST_QUICK')
TEST_RAW = envvar_enabled('TEST_RAW')
TEST_BENCHMARK = envvar_enabled('TEST_BENCHMARK')

# Skip benchmark tests unless TEST_BENCHMARK is set - they instantiate Terminal
# at module level which causes curses contamination in normal test runs
collect_ignore = []
if not TEST_BENCHMARK:
    collect_ignore.append('test_benchmarks.py')


if TEST_QUICK:
    many_lines_params = [80, ]
    many_columns_params = [25, ]


# Full list of terminal types available in jinxed's virtual database.
_JINXED_TERMINALS = [
    'xterm', 'xterm_256color', 'xterm_16color',
    'screen', 'screen_256color',
    'tmux', 'tmux_256color',
    'rxvt', 'rxvt_256color', 'rxvt_unicode', 'rxvt_unicode_256color',
    'putty', 'putty_256color',
    'st', 'st_256color',
    'ansi', 'ansi_bbs', 'ansicon',
    'linux', 'linux_16color',
    'vt220', 'vtwin10',
    'cons25', 'syncterm',
]

_term_cycle = itertools.cycle(_JINXED_TERMINALS)


@pytest.fixture
def any_term():
    """A single deterministically rotated terminal kind from jinxed's database."""
    return next(_term_cycle)


@pytest.fixture(params=many_lines_params)
def many_lines(request):
    """Various number of lines for screen height."""
    return request.param


@pytest.fixture(params=many_columns_params)
def many_columns(request):
    """Various number of columns for screen width."""
    return request.param
