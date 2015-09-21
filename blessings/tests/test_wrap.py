import platform
import textwrap
import termios
import struct
import fcntl
import sys

from .accessories import (
    as_subprocess,
    TestTerminal,
    many_columns,
    all_terms,
)

import pytest


def test_SequenceWrapper_invalid_width():
    """Test exception thrown from invalid width"""
    WIDTH = -3

    @as_subprocess
    def child():
        term = TestTerminal()
        try:
            my_wrapped = term.wrap(u'------- -------------', WIDTH)
        except ValueError as err:
            assert err.args[0] == (
                "invalid width %r(%s) (must be integer > 0)" % (
                    WIDTH, type(WIDTH)))
        else:
            assert False, 'Previous stmt should have raised exception.'
            del my_wrapped  # assigned but never used

    child()


@pytest.mark.parametrize("kwargs", [
    dict(break_long_words=False,
         drop_whitespace=False,
         subsequent_indent=''),
    dict(break_long_words=False,
         drop_whitespace=True,
         subsequent_indent=''),
    dict(break_long_words=False,
         drop_whitespace=False,
         subsequent_indent=' '),
    dict(break_long_words=False,
         drop_whitespace=True,
         subsequent_indent=' '),
    dict(break_long_words=True,
         drop_whitespace=False,
         subsequent_indent=''),
    dict(break_long_words=True,
         drop_whitespace=True,
         subsequent_indent=''),
    dict(break_long_words=True,
         drop_whitespace=False,
         subsequent_indent=' '),
    dict(break_long_words=True,
         drop_whitespace=True,
         subsequent_indent=' '),
])
def test_SequenceWrapper(all_terms, many_columns, kwargs):
    """Test that text wrapping matches internal extra options."""
    @as_subprocess
    def child(term, width, kwargs):
        # build a test paragraph, along with a very colorful version
        term = TestTerminal()
        pgraph = u' Z! a bc defghij klmnopqrstuvw<<>>xyz012345678900  '
        attributes = ('bright_red', 'on_bright_blue', 'underline', 'reverse',
                      'red_reverse', 'red_on_white', 'superscript',
                      'subscript', 'on_bright_white')
        term.bright_red('x')
        term.on_bright_blue('x')
        term.underline('x')
        term.reverse('x')
        term.red_reverse('x')
        term.red_on_white('x')
        term.superscript('x')
        term.subscript('x')
        term.on_bright_white('x')

        pgraph_colored = u''.join([
            getattr(term, (attributes[idx % len(attributes)]))(char)
            if char != u' ' else u' '
            for idx, char in enumerate(pgraph)])

        internal_wrapped = textwrap.wrap(pgraph, width=width, **kwargs)
        my_wrapped = term.wrap(pgraph, width=width, **kwargs)
        my_wrapped_colored = term.wrap(pgraph_colored, width=width, **kwargs)

        # ensure we textwrap ascii the same as python
        assert internal_wrapped == my_wrapped

        # ensure content matches for each line, when the sequences are
        # stripped back off of each line
        for line_no, (left, right) in enumerate(
                zip(internal_wrapped, my_wrapped_colored)):
            assert left == term.strip_seqs(right)

        # ensure our colored textwrap is the same paragraph length
        assert (len(internal_wrapped) == len(my_wrapped_colored))

    child(all_terms, many_columns, kwargs)
