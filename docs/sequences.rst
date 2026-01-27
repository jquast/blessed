Sequences
=========

Sometimes it is necessary to make sense of terminal sequences, and to distinguish them from plain
text. Blessed provides methods to split, strip, and analyze strings containing escape sequences.

Splitting Sequences
-------------------

The :meth:`~.Terminal.split_seqs` method allows you to iterate over a terminal string by its
characters or sequences:

    >>> term.split_seqs(term.bold('bbq'))
    ['\x1b[1m', 'b', 'b', 'q', '\x1b(B', '\x1b[m']

This is useful for processing terminal output character-by-character while preserving the escape
sequences that control formatting.

Stripping Sequences
-------------------

The :meth:`~.Terminal.strip_seqs` method removes all escape sequences from a string, leaving only
the printable text:

    >>> phrase = term.bold_black('coffee')
    >>> phrase
    '\x1b[1m\x1b[30mcoffee\x1b(B\x1b[m'
    >>> term.strip_seqs(phrase)
    'coffee'

This is useful when you need the raw text content without any formatting codes, such as when
logging to a file or comparing string content.
