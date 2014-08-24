"This sub-module provides 'keyboard awareness'."

__author__ = 'Jeff Quast <contact@jeffquast.com>'
__license__ = 'MIT'

__all__ = ['Keystroke', 'get_keyboard_codes', 'get_keyboard_sequences']

import curses
import curses.has_key
import collections
if hasattr(collections, 'OrderedDict'):
    OrderedDict = collections.OrderedDict
else:
    # python 2.6 requires 3rd party library
    import ordereddict
    OrderedDict = ordereddict.OrderedDict

get_curses_keycodes = lambda: dict(
    ((keyname, getattr(curses, keyname))
     for keyname in dir(curses)
     if keyname.startswith('KEY_'))
)

# override a few curses constants with easier mnemonics,
# there may only be a 1:1 mapping, so for those who desire
# to use 'KEY_DC' from, perhaps, ported code, recommend
# that they simply compare with curses.KEY_DC.
CURSES_KEYCODE_OVERRIDE_MIXIN = (
    ('KEY_DELETE', curses.KEY_DC),
    ('KEY_INSERT', curses.KEY_IC),
    ('KEY_PGUP', curses.KEY_PPAGE),
    ('KEY_PGDOWN', curses.KEY_NPAGE),
    ('KEY_ESCAPE', curses.KEY_EXIT),
    ('KEY_SUP', curses.KEY_SR),
    ('KEY_SDOWN', curses.KEY_SF),
    ('KEY_UP_LEFT', curses.KEY_A1),
    ('KEY_UP_RIGHT', curses.KEY_A3),
    ('KEY_CENTER', curses.KEY_B2),
    ('KEY_BEGIN', curses.KEY_BEG),
)

# Inject KEY_{names} that we think would be useful, there are no curses
# definitions for the keypad keys.  We need keys that generate multibyte
# sequences, though it is useful to have some aliases for basic control
# characters such as TAB.
_lastval = max(get_curses_keycodes().values())
for key in ('TAB', 'KP_MULTIPLY', 'KP_ADD', 'KP_SEPARATOR', 'KP_SUBTRACT',
            'KP_DECIMAL', 'KP_DIVIDE', 'KP_EQUAL', 'KP_0', 'KP_1', 'KP_2',
            'KP_3', 'KP_4', 'KP_5', 'KP_6', 'KP_7', 'KP_8', 'KP_9'):
    _lastval += 1
    setattr(curses, 'KEY_{0}'.format(key), _lastval)


class Keystroke(unicode):
    """A unicode-derived class for describing keyboard input returned by
    the ``inkey()`` method of ``Terminal``, which may, at times, be a
    multibyte sequence, providing properties ``is_sequence`` as ``True``
    when the string is a known sequence, and ``code``, which returns an
    integer value that may be compared against the terminal class attributes
    such as ``KEY_LEFT``.
    """
    def __new__(cls, ucs='', code=None, name=None):
        new = unicode.__new__(cls, ucs)
        new._name = name
        new._code = code
        return new

    @property
    def is_sequence(self):
        "Whether the value represents a multibyte sequence (bool)."
        return self._code is not None

    def __repr__(self):
        return self._name is None and unicode.__repr__(self) or self._name
    __repr__.__doc__ = unicode.__doc__

    @property
    def name(self):
        "String-name of key sequence, such as ``'KEY_LEFT'`` (str)."
        return self._name

    @property
    def code(self):
        "Integer keycode value of multibyte sequence (int)."
        return self._code


def get_keyboard_codes():
    """get_keyboard_codes() -> dict

    Returns dictionary of (code, name) pairs for curses keyboard constant
    values and their mnemonic name. Such as key ``260``, with the value of
    its identity, ``KEY_LEFT``.  These are derived from the attributes by the
    same of the curses module, with the following exceptions:

    * ``KEY_DELETE`` in place of ``KEY_DC``
    * ``KEY_INSERT`` in place of ``KEY_IC``
    * ``KEY_PGUP`` in place of ``KEY_PPAGE``
    * ``KEY_PGDOWN`` in place of ``KEY_NPAGE``
    * ``KEY_ESCAPE`` in place of ``KEY_EXIT``
    * ``KEY_SUP`` in place of ``KEY_SR``
    * ``KEY_SDOWN`` in place of ``KEY_SF``
    """
    keycodes = OrderedDict(get_curses_keycodes())
    keycodes.update(CURSES_KEYCODE_OVERRIDE_MIXIN)

    # invert dictionary (key, values) => (values, key), preferring the
    # last-most inserted value ('KEY_DELETE' over 'KEY_DC').
    return dict(zip(keycodes.values(), keycodes.keys()))


def _alternative_left_right(term):
    """_alternative_left_right(T) -> dict

    Return dict of sequences ``term._cuf1``, and ``term._cub1``,
    valued as ``KEY_RIGHT``, ``KEY_LEFT`` when appropriate if available.

    some terminals report a different value for *kcuf1* than *cuf1*, but
    actually send the value of *cuf1* for right arrow key (which is
    non-destructive space).
    """
    keymap = dict()
    if term._cuf1 and term._cuf1 != u' ':
        keymap[term._cuf1] = curses.KEY_RIGHT
    if term._cub1 and term._cub1 != u'\b':
        keymap[term._cub1] = curses.KEY_LEFT
    return keymap


def get_keyboard_sequences(term):
    """get_keyboard_sequences(T) -> (OrderedDict)

    Initialize and return a keyboard map and sequence lookup table,
    (sequence, constant) from blessed Terminal instance ``term``,
    where ``sequence`` is a multibyte input sequence, such as u'\x1b[D',
    and ``constant`` is a constant, such as term.KEY_LEFT.  The return
    value is an OrderedDict instance, with their keys sorted longest-first.
    """
    # A small gem from curses.has_key that makes this all possible,
    # _capability_names: a lookup table of terminal capability names for
    # keyboard sequences (fe. kcub1, key_left), keyed by the values of
    # constants found beginning with KEY_ in the main curses module
    # (such as KEY_LEFT).
    #
    # latin1 encoding is used so that bytes in 8-bit range of 127-255
    # have equivalent chr() and unichr() values, so that the sequence
    # of a kermit or avatar terminal, for example, remains unchanged
    # in its byte sequence values even when represented by unicode.
    #
    capability_names = curses.has_key._capability_names
    sequence_map = dict((
        (seq.decode('latin1'), val)
        for (seq, val) in (
            (curses.tigetstr(cap), val)
            for (val, cap) in capability_names.iteritems()
        ) if seq
    ) if term.does_styling else ())

    sequence_map.update(_alternative_left_right(term))
    sequence_map.update(DEFAULT_SEQUENCE_MIXIN)

    # This is for fast lookup matching of sequences, preferring
    # full-length sequence such as ('\x1b[D', KEY_LEFT)
    # over simple sequences such as ('\x1b', KEY_EXIT).
    return OrderedDict((
        (seq, sequence_map[seq]) for seq in sorted(
            sequence_map, key=len, reverse=True)))


def resolve_sequence(text, mapper, codes):
    """resolve_sequence(text, mapper, codes) -> Keystroke()

    Returns first matching Keystroke() instance for sequences found in
    ``mapper`` beginning with input ``text``, where ``mapper`` is an
    OrderedDict of unicode multibyte sequences, such as u'\x1b[D' paired by
    their integer value (260), and ``codes`` is a dict of integer values (260)
    paired by their mnemonic name, 'KEY_LEFT'.
    """
    for sequence, code in mapper.iteritems():
        if text.startswith(sequence):
            return Keystroke(ucs=sequence, code=code, name=codes[code])
    return Keystroke(ucs=text and text[0] or u'')

"""In a perfect world, terminal emulators would always send exactly what
the terminfo(5) capability database plans for them, accordingly by the
value of the ``TERM`` name they declare.

But this isn't a perfect world. Many vt220-derived terminals, such as
those declaring 'xterm', will continue to send vt220 codes instead of
their native-declared codes, for backwards-compatibility.

This goes for many: rxvt, putty, iTerm.

These "mixins" are used for *all* terminals, regardless of their type.

Furthermore, curses does not provide sequences sent by the keypad,
at least, it does not provide a way to distinguish between keypad 0
and numeric 0.
"""
DEFAULT_SEQUENCE_MIXIN = (
    # these common control characters (and 127, ctrl+'?') mapped to
    # an application key definition.
    (unichr(10), curses.KEY_ENTER),
    (unichr(13), curses.KEY_ENTER),
    (unichr(8), curses.KEY_BACKSPACE),
    (unichr(9), curses.KEY_TAB),
    (unichr(27), curses.KEY_EXIT),
    (unichr(127), curses.KEY_DC),

    (u"\x1b[A", curses.KEY_UP),
    (u"\x1b[B", curses.KEY_DOWN),
    (u"\x1b[C", curses.KEY_RIGHT),
    (u"\x1b[D", curses.KEY_LEFT),
    (u"\x1b[F", curses.KEY_END),
    (u"\x1b[H", curses.KEY_HOME),
    # not sure where these are from .. please report
    (u"\x1b[K", curses.KEY_END),
    (u"\x1b[U", curses.KEY_NPAGE),
    (u"\x1b[V", curses.KEY_PPAGE),

    # keys sent after term.smkx (keypad_xmit) is emitted, source:
    # http://www.xfree86.org/current/ctlseqs.html#PC-Style%20Function%20Keys
    # http://fossies.org/linux/rxvt/doc/rxvtRef.html#KeyCodes
    #
    # keypad, numlock on
    (u"\x1bOM", curses.KEY_ENTER),         # return
    (u"\x1bOj", curses.KEY_KP_MULTIPLY),   # *
    (u"\x1bOk", curses.KEY_KP_ADD),        # +
    (u"\x1bOl", curses.KEY_KP_SEPARATOR),  # ,
    (u"\x1bOm", curses.KEY_KP_SUBTRACT),   # -
    (u"\x1bOn", curses.KEY_KP_DECIMAL),    # .
    (u"\x1bOo", curses.KEY_KP_DIVIDE),     # /
    (u"\x1bOX", curses.KEY_KP_EQUAL),      # =
    (u"\x1bOp", curses.KEY_KP_0),          # 0
    (u"\x1bOq", curses.KEY_KP_1),          # 1
    (u"\x1bOr", curses.KEY_KP_2),          # 2
    (u"\x1bOs", curses.KEY_KP_3),          # 3
    (u"\x1bOt", curses.KEY_KP_4),          # 4
    (u"\x1bOu", curses.KEY_KP_5),          # 5
    (u"\x1bOv", curses.KEY_KP_6),          # 6
    (u"\x1bOw", curses.KEY_KP_7),          # 7
    (u"\x1bOx", curses.KEY_KP_8),          # 8
    (u"\x1bOy", curses.KEY_KP_9),          # 9

    #
    # keypad, numlock off
    (u"\x1b[1~", curses.KEY_FIND),         # find
    (u"\x1b[2~", curses.KEY_IC),           # insert (0)
    (u"\x1b[3~", curses.KEY_DC),           # delete (.), "Execute"
    (u"\x1b[4~", curses.KEY_SELECT),       # select
    (u"\x1b[5~", curses.KEY_PPAGE),        # pgup   (9)
    (u"\x1b[6~", curses.KEY_NPAGE),        # pgdown (3)
    (u"\x1b[7~", curses.KEY_HOME),         # home
    (u"\x1b[8~", curses.KEY_END),          # end
    (u"\x1b[OA", curses.KEY_UP),           # up     (8)
    (u"\x1b[OB", curses.KEY_DOWN),         # down   (2)
    (u"\x1b[OC", curses.KEY_RIGHT),        # right  (6)
    (u"\x1b[OD", curses.KEY_LEFT),         # left   (4)
    (u"\x1b[OF", curses.KEY_END),          # end    (1)
    (u"\x1b[OH", curses.KEY_HOME),         # home   (7)

    # The vt220 placed F1-F4 above the keypad, in place of actual
    # F1-F4 were local functions (hold screen, print screen,
    # set up, data/talk, break).
    (u"\x1bOP", curses.KEY_F1),
    (u"\x1bOQ", curses.KEY_F2),
    (u"\x1bOR", curses.KEY_F3),
    (u"\x1bOS", curses.KEY_F4),
)
