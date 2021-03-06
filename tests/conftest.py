# std imports
import os

# 3rd party
import pytest

all_terms_params = 'xterm screen ansi vt220 rxvt cons25 linux'.split()
many_lines_params = [40, 80]
# we must test a '1' column for conditional in _handle_long_word
many_columns_params = [1, 10]

if os.environ.get('TEST_QUICK'):
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
