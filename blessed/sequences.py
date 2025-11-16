"""Module providing 'sequence awareness'."""
# std imports
import re
import sys
import math
import textwrap
from typing import TYPE_CHECKING

# 3rd party
from wcwidth import wcwidth

# local
from blessed._capabilities import CAPABILITIES_CAUSE_MOVEMENT, CAPABILITIES_HORIZONTAL_DISTANCE

if TYPE_CHECKING:  # pragma: no cover
    from blessed.terminal import Terminal

# std imports
from typing import List, Type, Tuple, Pattern, TypeVar, Iterator, Optional

# SupportsIndex was added in Python 3.8
if sys.version_info >= (3, 8):
    # std imports
    from typing import SupportsIndex
else:
    SupportsIndex = int

_T = TypeVar("_T")

__all__ = ('Sequence', 'SequenceTextWrapper', 'iter_parse', 'measure_length')


class Termcap():
    """Terminal capability of given variable name and pattern."""

    def __init__(self, name: str, pattern: str, attribute: str, nparams: int = 0) -> None:
        """
        Class initializer.

        :arg str name: name describing capability.
        :arg str pattern: regular expression string.
        :arg str attribute: :class:`~.Terminal` attribute used to build
            this terminal capability.
        :arg int nparams: number of positional arguments for callable.
        """
        self.name = name
        self.pattern = pattern
        self.attribute = attribute
        self.nparams = nparams
        self._re_compiled: Optional[Pattern[str]] = None

    def __repr__(self) -> str:
        return f'<Termcap {self.name}:{self.pattern!r}>'

    @property
    def named_pattern(self) -> str:
        """Regular expression pattern for capability with named group."""
        return f'(?P<{self.name}>{self.pattern})'

    @property
    def re_compiled(self) -> Pattern[str]:
        """Compiled regular expression pattern for capability."""
        if self._re_compiled is None:
            self._re_compiled = re.compile(self.pattern)
        return self._re_compiled

    @property
    def will_move(self) -> bool:
        """Whether capability causes cursor movement."""
        return self.name in CAPABILITIES_CAUSE_MOVEMENT

    def horizontal_distance(self, text: str) -> int:
        """
        Horizontal carriage adjusted by capability, may be negative.

        :rtype: int
        :arg str text: for capabilities *parm_left_cursor*, *parm_right_cursor*, provide the
            matching sequence text, its interpreted distance is returned.
        :returns: 0 except for matching '
        :raises ValueError: ``text`` does not match regex for capability
        """
        value = CAPABILITIES_HORIZONTAL_DISTANCE.get(self.name)
        if value is None:
            return 0

        if self.nparams:
            match = self.re_compiled.match(text)
            if match:
                return value * int(match.group(1))
            raise ValueError(f'Invalid parameters for termccap {self.name}: {text!r}')

        return value

    # pylint: disable=too-many-positional-arguments
    @classmethod
    def build(cls, name: str, capability: str, attribute: str, nparams: int = 0,
              numeric: int = 99, match_grouped: bool = False, match_any: bool = False,
              match_optional: bool = False) -> "Termcap":
        r"""
        Class factory builder for given capability definition.

        :arg str name: Variable name given for this pattern.
        :arg str capability: A unicode string representing a terminal
            capability to build for. When ``nparams`` is non-zero, it
            must be a callable unicode string (such as the result from
            ``getattr(term, 'bold')``.
        :arg str attribute: The terminfo(5) capability name by which this
            pattern is known.
        :arg int nparams: number of positional arguments for callable.
        :arg int numeric: Value to substitute into capability to when generating pattern
        :arg bool match_grouped: If the numeric pattern should be
            grouped, ``(\d+)`` when ``True``, ``\d+`` default.
        :arg bool match_any: When keyword argument ``nparams`` is given,
            *any* numeric found in output is suitable for building as
            pattern ``(\d+)``.  Otherwise, only the first matching value of
            range *(numeric - 1)* through *(numeric + 1)* will be replaced by
            pattern ``(\d+)`` in builder.
        :arg bool match_optional: When ``True``, building of numeric patterns
            containing ``(\d+)`` will be built as optional, ``(\d+)?``.
        :rtype: blessed.sequences.Termcap
        :returns: Terminal capability instance for given capability definition
        """
        _numeric_regex = r'\d+'
        if match_grouped:
            _numeric_regex = r'(\d+)'
        if match_optional:
            _numeric_regex = r'(\d+)?'
        numeric = 99 if numeric is None else numeric

        # basic capability attribute, not used as a callable
        if nparams == 0:
            return cls(name, re.escape(capability), attribute, nparams)

        # a callable capability accepting numeric argument
        _outp = re.escape(capability(*(numeric,) * nparams))
        if not match_any:
            for num in range(numeric - 1, numeric + 2):
                if str(num) in _outp:
                    pattern = _outp.replace(str(num), _numeric_regex)
                    return cls(name, pattern, attribute, nparams)

        pattern = r'(\d+)' if match_grouped else r'\d+'
        return cls(name, re.sub(pattern, lambda x: _numeric_regex, _outp), attribute, nparams)


class SequenceTextWrapper(textwrap.TextWrapper):
    """Docstring overridden."""

    def __init__(self, width: int, term: 'Terminal', **kwargs: object) -> None:
        """
        Class initializer.

        This class supports the :meth:`~.Terminal.wrap` method.
        """
        self.term = term
        textwrap.TextWrapper.__init__(self, width, **kwargs)

    def _wrap_chunks(self, chunks):    # type: ignore[no-untyped-def]
        """
        Sequence-aware variant of :meth:`textwrap.TextWrapper._wrap_chunks`.

        :raises ValueError: ``self.width`` is not a positive integer
        :rtype: list
        :returns: text chunks adjusted for width

        This simply ensures that word boundaries are not broken mid-sequence, as standard python
        textwrap would incorrectly determine the length of a string containing sequences, and may
        also break consider sequences part of a "word" that may be broken by hyphen (``-``), where
        this implementation corrects both.
        """
        lines: List[str] = []
        if self.width <= 0 or not isinstance(self.width, int):
            raise ValueError(
                f"invalid width {self.width!r}({type(self.width)!r}) (must be integer > 0)"
            )

        term = self.term
        drop_whitespace = not hasattr(self, 'drop_whitespace'
                                      ) or self.drop_whitespace
        chunks.reverse()
        while chunks:
            cur_line: List[str] = []
            cur_len = 0
            indent = self.subsequent_indent if lines else self.initial_indent
            width = self.width - len(indent)
            if drop_whitespace and lines and not Sequence(chunks[-1], term).strip():
                del chunks[-1]
            while chunks:
                chunk_len = Sequence(chunks[-1], term).length()
                if cur_len + chunk_len > width:
                    if chunk_len > width:
                        self._handle_long_word(chunks, cur_line, cur_len, width)
                    break
                cur_line.append(chunks.pop())
                cur_len += chunk_len
            if drop_whitespace and (cur_line and not Sequence(cur_line[-1], term).strip()):
                del cur_line[-1]
            if cur_line:
                lines.append(f'{indent}{"".join(cur_line)}')
        return lines

    def _handle_long_word(self,  # type: ignore[no-untyped-def]
                          reversed_chunks, cur_line, cur_len, width):
        """
        Sequence-aware :meth:`textwrap.TextWrapper._handle_long_word`.

        This method ensures that word boundaries are not broken mid-sequence, as
        standard python textwrap would incorrectly determine the length of a
        string containing sequences and wide characters it would also break
        these "words" that would be broken by hyphen (``-``), this
        implementation corrects both.

        This is done by mutating the passed arguments, removing items from
        'reversed_chunks' and appending them to 'cur_line'.

        However, some characters (east-asian, emoji, etc.) cannot be split any
        less than 2 cells, so in the case of a width of 1, we have no choice
        but to allow those characters to flow outside of the given cell.
        """
        # Figure out when indent is larger than the specified width, and make
        # sure at least one character is stripped off on every pass
        space_left = 1 if width < 1 else width - cur_len
        # If we're allowed to break long words, then do so: put as much
        # of the next chunk onto the current line as will fit.

        if self.break_long_words:
            term = self.term
            chunk = reversed_chunks[-1]
            idx = nxt = seq_length = 0
            for text, _ in iter_parse(term, chunk):
                nxt += len(text)
                seq_length += Sequence(text, term).length()
                if seq_length > space_left:
                    if cur_len == 0 and width == 1 and nxt == 1 and seq_length == 2:
                        # Emoji etc. cannot be split under 2 cells, so in the
                        # case of a width of 1, we have no choice but to allow
                        # those characters to flow outside of the given cell.
                        pass
                    else:
                        break
                idx = nxt
            cur_line.append(chunk[:idx])
            reversed_chunks[-1] = chunk[idx:]

        # Otherwise, we have to preserve the long word intact.  Only add
        # it to the current line if there's nothing already there --
        # that minimizes how much we violate the width constraint.
        elif not cur_line:
            cur_line.append(reversed_chunks.pop())

        # If we're not allowed to break long words, and there's already
        # text on the current line, do nothing.  Next time through the
        # main loop of _wrap_chunks(), we'll wind up here again, but
        # cur_len will be zero, so the next line will be entirely
        # devoted to the long word that we can't handle right now.


SequenceTextWrapper.__doc__ = textwrap.TextWrapper.__doc__


class Sequence(str):
    """
    A "sequence-aware" version of the base :class:`str` class.

    This unicode-derived class understands the effect of escape sequences
    of printable length, allowing a properly implemented :meth:`rjust`,
    :meth:`ljust`, :meth:`center`, and :meth:`length`.
    """

    def __new__(cls: Type[_T], sequence_text: str, term: 'Terminal') -> _T:
        """
        Class constructor.

        :arg str sequence_text: A string that may contain sequences.
        :arg blessed.Terminal term: :class:`~.Terminal` instance.
        """
        new = str.__new__(cls, sequence_text)
        new._term = term
        return new

    def ljust(self, width: SupportsIndex, fillchar: str = ' ') -> str:
        """
        Return string containing sequences, left-adjusted.

        :arg int width: Total width given to left-adjust ``text``.  If
            unspecified, the width of the attached terminal is used (default).
        :arg str fillchar: String for padding right-of ``text``.
        :returns: String of ``text``, left-aligned by ``width``.
        :rtype: str
        """
        rightside = fillchar * int(
            (max(0.0, float(width.__index__() - self.length()))) / float(len(fillchar)))
        return ''.join((self, rightside))

    def rjust(self, width: SupportsIndex, fillchar: str = ' ') -> str:
        """
        Return string containing sequences, right-adjusted.

        :arg int width: Total width given to right-adjust ``text``.  If
            unspecified, the width of the attached terminal is used (default).
        :arg str fillchar: String for padding left-of ``text``.
        :returns: String of ``text``, right-aligned by ``width``.
        :rtype: str
        """
        leftside = fillchar * int(
            (max(0.0, float(width.__index__() - self.length()))) / float(len(fillchar)))
        return ''.join((leftside, self))

    def center(self, width: SupportsIndex, fillchar: str = ' ') -> str:
        """
        Return string containing sequences, centered.

        :arg int width: Total width given to center ``text``.  If
            unspecified, the width of the attached terminal is used (default).
        :arg str fillchar: String for padding left and right-of ``text``.
        :returns: String of ``text``, centered by ``width``.
        :rtype: str
        """
        split = max(0.0, float(width.__index__()) - self.length()) / 2
        leftside = fillchar * int(
            (max(0.0, math.floor(split))) / float(len(fillchar)))
        rightside = fillchar * int(
            (max(0.0, math.ceil(split))) / float(len(fillchar)))
        return ''.join((leftside, self, rightside))

    def truncate(self, width: SupportsIndex) -> str:
        """
        Truncate a string in a sequence-aware manner.

        Any printable characters beyond ``width`` are removed, while all
        sequences remain in place. Horizontal Sequences are first expanded
        by :meth:`padd`.

        :arg int width: The printable width to truncate the string to.
        :rtype: str
        :returns: String truncated to at most ``width`` printable characters.
        """
        output = ""
        current_width = 0
        target_width = width.__index__()
        parsed_seq = iter_parse(self._term, self.padd())

        # Retain all text until non-cap width reaches desired width
        for text, cap in parsed_seq:
            if not cap:
                # use wcwidth clipped to 0 because it can sometimes return -1
                current_width += max(wcwidth(text), 0)
                if current_width > target_width:
                    break
            output += text

        # Return with remaining caps appended
        return f'{output}{"".join(text for text, cap in parsed_seq if cap)}'

    def length(self) -> int:
        r"""
        Return the printable length of string containing sequences.

        Strings containing ``term.left`` or ``\b`` will cause "overstrike",
        but a length less than 0 is not ever returned. So ``_\b+`` is a
        length of 1 (displays as ``+``), but ``\b`` alone is simply a
        length of 0.

        Some characters may consume more than one cell, mainly those CJK
        Unified Ideographs (Chinese, Japanese, Korean) defined by Unicode
        as half or full-width characters.

        For example:

            >>> from blessed import Terminal
            >>> from blessed.sequences import Sequence
            >>> term = Terminal()
            >>> msg = term.clear + term.red('コンニチハ')
            >>> Sequence(msg, term).length()
            10

        .. note:: Although accounted for, strings containing sequences such
            as ``term.clear`` will not give accurate returns, it is not
            considered lengthy (a length of 0).
        """
        # because control characters may return -1, "clip" their length to 0.
        return sum(max(wcwidth(w_char), 0) for w_char in self.padd(strip=True))

    def strip(self, chars: Optional[str] = None) -> str:
        """
        Return string of sequences, leading and trailing whitespace removed.

        :arg str chars: Remove characters in chars instead of whitespace.
        :rtype: str
        :returns: string of sequences with leading and trailing whitespace removed.
        """
        return self.strip_seqs().strip(chars)

    def lstrip(self, chars: Optional[str] = None) -> str:
        """
        Return string of all sequences and leading whitespace removed.

        :arg str chars: Remove characters in chars instead of whitespace.
        :rtype: str
        :returns: string of sequences with leading removed.
        """
        return self.strip_seqs().lstrip(chars)

    def rstrip(self, chars: Optional[str] = None) -> str:
        """
        Return string of all sequences and trailing whitespace removed.

        :arg str chars: Remove characters in chars instead of whitespace.
        :rtype: str
        :returns: string of sequences with trailing removed.
        """
        return self.strip_seqs().rstrip(chars)

    def strip_seqs(self) -> str:
        """
        Return ``text`` stripped of only its terminal sequences.

        :rtype: str
        :returns: Text with terminal sequences removed
        """
        return self.padd(strip=True)

    def padd(self, strip: bool = False) -> str:
        """
        Return non-destructive horizontal movement as destructive spacing.

        :arg bool strip: Strip terminal sequences
        :rtype: str
        :returns: Text adjusted for horizontal movement
        """
        data = self
        if self._term.caps_compiled.search(data) is None:
            return str(data)
        if strip:  # strip all except CAPABILITIES_HORIZONTAL_DISTANCE
            # pylint: disable-next=protected-access
            data = self._term._caps_compiled_without_hdist.sub("", data)

            if self._term.caps_compiled.search(data) is None:
                return str(data)

            # pylint: disable-next=protected-access
            caps = self._term._hdist_caps_named_compiled
        else:
            # pylint: disable-next=protected-access
            caps = self._term._caps_named_compiled

        outp = ''
        last_end = 0

        for match in caps.finditer(data):

            # Capture unmatched text between matched capabilities
            if match.start() > last_end:
                outp += data[last_end:match.start()]

            last_end = match.end()
            text = match.group(match.lastgroup)
            value = self._term.caps[match.lastgroup].horizontal_distance(text)

            if value > 0:
                outp += ' ' * value
            elif value < 0:
                outp = outp[:value]
            else:
                outp += text

        # Capture any remaining unmatched text
        if last_end < len(data):
            outp += data[last_end:]

        return outp


def iter_parse(term: 'Terminal', text: str) -> Iterator[Tuple[str, Optional[Termcap]]]:
    """
    Generator yields (text, capability) for characters of ``text``.

    value for ``capability`` may be ``None``, where ``text`` is
    :class:`str` of length 1.  Otherwise, ``text`` is a full
    matching sequence of given capability.
    """
    for match in term._caps_compiled_any.finditer(text):  # pylint: disable=protected-access
        name = match.lastgroup
        value = match.group(name) if name else ''
        if name == 'MISMATCH':
            yield (value, None)
        else:
            yield value, term.caps.get(name, '')


def measure_length(text: str, term: 'Terminal') -> int:
    """
    .. deprecated:: 1.12.0.

    :rtype: int
    :returns: Length of the first sequence in the string
    """
    try:
        text, capability = next(iter_parse(term, text))
        if capability:
            return len(text)
    except StopIteration:
        return 0
    return 0
