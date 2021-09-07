"""Configure test fixtures"""

# std imports
import os
import platform
import subprocess

# 3rd party
import pytest

IS_WINDOWS = platform.system() == 'Windows'

all_terms_params = 'xterm screen ansi vt220 rxvt cons25 linux'.split()
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

    if value.lower() in ('no', 'false'):
        return False

    try:
        return bool(int(value))
    except ValueError:
        return True


TEST_FULL = envvar_enabled('TEST_FULL')
TEST_KEYBOARD = envvar_enabled('TEST_KEYBOARD')
TEST_QUICK = envvar_enabled('TEST_QUICK')
TEST_RAW = envvar_enabled('TEST_RAW')


if TEST_FULL:
    try:
        all_terms_params = [
            # use all values of the first column of data in output of 'toe -a'
            _term.split(None, 1)[0] for _term in
            subprocess.Popen(('toe', '-a'),  # pylint: disable=consider-using-with
                             stdout=subprocess.PIPE,
                             close_fds=True)
            .communicate()[0].splitlines()]
    except OSError:
        pass
elif IS_WINDOWS:
    all_terms_params = ['vtwin10', ]
elif TEST_QUICK:
    all_terms_params = 'xterm screen ansi linux'.split()


if TEST_QUICK:
    many_lines_params = [80, ]
    many_columns_params = [25, ]


@pytest.fixture(params=all_terms_params)
def all_terms(request):
    """Common kind values for all kinds of terminals."""
    return request.param


@pytest.fixture(params=many_lines_params)
def many_lines(request):
    """Various number of lines for screen height."""
    return request.param


@pytest.fixture(params=many_columns_params)
def many_columns(request):
    """Various number of columns for screen width."""
    return request.param
