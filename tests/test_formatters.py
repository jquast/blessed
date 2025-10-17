"""Tests string formatting functions."""
# std imports
import pickle
import platform
import multiprocessing

# 3rd party
import pytest

# local
from .accessories import TestTerminal, as_subprocess

try:
    # std imports
    from unittest import mock
except ImportError:
    # 3rd party
    import mock

if platform.system() != 'Windows':
    # std imports
    import curses
else:
    # 3rd party
    import jinxed as curses  # pylint: disable=import-error


def fn_tparm(*args):
    """Mock tparm function"""
    return '~'.join(
        str(arg) if num else arg.decode('latin1') for num, arg in enumerate(args)
    ).encode('latin1')


def test_parameterizing_string_args_unspecified(monkeypatch):
    """Test default args of formatters.ParameterizingString."""
    # local
    from blessed.formatters import FormattingString, ParameterizingString

    # first argument to tparm() is the sequence name, returned as-is;
    # subsequent arguments are usually Integers.
    monkeypatch.setattr(curses, 'tparm', fn_tparm)

    # given,
    pstr = ParameterizingString('')

    # exercise __new__
    assert str(pstr) == ''
    assert pstr._normal == ''
    assert pstr._name == '<not specified>'

    # exercise __call__
    zero = pstr(0)
    assert isinstance(zero, FormattingString)
    assert zero == '~0'
    assert zero('text') == '~0text'

    # exercise __call__ with multiple args
    onetwo = pstr(1, 2)
    assert isinstance(onetwo, FormattingString)
    assert onetwo == '~1~2'
    assert onetwo('text') == '~1~2text'


def test_parameterizing_string_args(monkeypatch):
    """Test basic formatters.ParameterizingString."""
    # local
    from blessed.formatters import FormattingString, ParameterizingString

    # first argument to tparm() is the sequence name, returned as-is;
    # subsequent arguments are usually Integers.
    monkeypatch.setattr(curses, 'tparm', fn_tparm)

    # given,
    pstr = ParameterizingString('cap', 'norm', 'seq-name')

    # exercise __new__
    assert str(pstr) == 'cap'
    assert pstr._normal == 'norm'
    assert pstr._name == 'seq-name'

    # exercise __call__
    zero = pstr(0)
    assert isinstance(zero, FormattingString)
    assert zero == 'cap~0'
    assert zero('text') == 'cap~0textnorm'

    # exercise __call__ with multiple args
    onetwo = pstr(1, 2)
    assert isinstance(onetwo, FormattingString)
    assert onetwo == 'cap~1~2'
    assert onetwo('text') == 'cap~1~2textnorm'


def test_parameterizing_string_type_error(monkeypatch):
    """Test formatters.ParameterizingString raising TypeError."""
    # local
    from blessed.formatters import ParameterizingString

    def tparm_raises_TypeError(*args):
        raise TypeError('custom_err')

    monkeypatch.setattr(curses, 'tparm', tparm_raises_TypeError)

    # given,
    pstr = ParameterizingString('cap', 'norm', 'cap-name')

    # ensure TypeError when given a string raises custom exception
    try:
        pstr('XYZ')
        assert False, "previous call should have raised TypeError"
    except TypeError as err:
        assert err.args[0] == (
            "Unknown terminal capability, 'cap-name', or, TypeError "
            "for arguments ('XYZ',): custom_err"
        )

    # ensure TypeError when given an integer raises its natural exception
    try:
        pstr(0)
        assert False, "previous call should have raised TypeError"
    except TypeError as err:
        assert err.args[0] == "custom_err"


def test_formattingstring(monkeypatch):
    """Test simple __call__ behavior of formatters.FormattingString."""
    # local
    from blessed.formatters import FormattingString

    # given, with arg
    pstr = FormattingString('attr', 'norm')

    # exercise __call__,
    assert pstr._normal == 'norm'
    assert str(pstr) == 'attr'
    assert pstr('text') == 'attrtextnorm'

    # given, with empty attribute
    pstr = FormattingString('', 'norm')
    assert pstr('text') == 'text'


def test_nested_formattingstring(monkeypatch):
    """Test nested __call__ behavior of formatters.FormattingString."""
    # local
    from blessed.formatters import FormattingString

    # given, with arg
    pstr = FormattingString('a1-', 'n-')
    zstr = FormattingString('a2-', 'n-')

    # exercise __call__
    assert pstr('x-', zstr('f-'), 'q-') == 'a1-x-a2-f-n-a1-q-n-'


def test_nested_formattingstring_type_error(monkeypatch):
    """Test formatters.FormattingString raising TypeError."""
    # local
    from blessed.formatters import FormattingString

    # given,
    pstr = FormattingString('a-', 'n-')

    # exercise,
    with pytest.raises(TypeError) as err:
        pstr('text', 0x123, '...')

    # verify,
    assert str(err.value) == (
        "TypeError for FormattingString argument, 291, at position 1: "
        "expected type str, got int"
    )


def test_nullcallablestring(monkeypatch):
    """Test formatters.NullCallableString."""
    # local
    from blessed.formatters import NullCallableString

    # given, with arg
    pstr = NullCallableString()

    # exercise __call__,
    assert str(pstr) == ''
    assert pstr('text') == 'text'
    assert pstr('text', 'moretext') == 'textmoretext'
    assert pstr(99, 1) == ''
    assert pstr() == ''
    assert pstr(0) == ''


def test_split_compound():
    """Test formatters.split_compound."""
    # local
    from blessed.formatters import split_compound

    assert split_compound('') == ['']
    assert split_compound('a_b_c') == ['a', 'b', 'c']
    assert split_compound('a_on_b_c') == ['a', 'on_b', 'c']
    assert split_compound('a_bright_b_c') == ['a', 'bright_b', 'c']
    assert split_compound('a_on_bright_b_c') == ['a', 'on_bright_b', 'c']


def test_resolve_capability(monkeypatch):
    """Test formatters.resolve_capability and term sugaring."""
    # local
    from blessed.formatters import resolve_capability

    # given, always returns a b'seq'
    def tigetstr(attr):
        return f'seq-{attr}'.encode('latin1')

    monkeypatch.setattr(curses, 'tigetstr', tigetstr)
    term = mock.Mock()
    term._sugar = {'mnemonic': 'xyz'}

    # exercise
    assert resolve_capability(term, 'mnemonic') == 'seq-xyz'
    assert resolve_capability(term, 'natural') == 'seq-natural'

    # given, where tigetstr returns None
    def tigetstr_none(attr):
        return None

    monkeypatch.setattr(curses, 'tigetstr', tigetstr_none)

    # exercise,
    assert resolve_capability(term, 'natural') == ''

    # given, where does_styling is False
    def raises_exception(*args):
        assert False, "Should not be called"

    term.does_styling = False
    monkeypatch.setattr(curses, 'tigetstr', raises_exception)

    # exercise,
    assert resolve_capability(term, 'natural') == ''


def test_resolve_color(monkeypatch):
    """Test formatters.resolve_color."""
    # local
    from blessed.formatters import FormattingString, NullCallableString, resolve_color

    def color_cap(digit):
        return f'seq-{digit}'

    monkeypatch.setattr(curses, 'COLOR_RED', 1984)

    # given, terminal with color capabilities
    term = mock.Mock()
    term._background_color = color_cap
    term._foreground_color = color_cap
    term.number_of_colors = -1
    term.normal = 'seq-normal'

    # exercise,
    red = resolve_color(term, 'red')
    assert isinstance(red, FormattingString)
    assert red == 'seq-1984'
    assert red('text') == 'seq-1984textseq-normal'

    # exercise bold, +8
    bright_red = resolve_color(term, 'bright_red')
    assert isinstance(bright_red, FormattingString)
    assert bright_red == 'seq-1992'
    assert bright_red('text') == 'seq-1992textseq-normal'

    # given, terminal without color
    term.number_of_colors = 0

    # exercise,
    red = resolve_color(term, 'red')
    assert isinstance(red, NullCallableString)
    assert red == ''
    assert red('text') == 'text'

    # exercise bold,
    bright_red = resolve_color(term, 'bright_red')
    assert isinstance(bright_red, NullCallableString)
    assert bright_red == ''
    assert bright_red('text') == 'text'


def test_resolve_attribute_as_color(monkeypatch):
    """Test simple resolve_attribte() given color name."""
    # local
    import blessed
    from blessed.formatters import resolve_attribute

    def resolve_color(term, digit):
        return f'seq-{digit}'

    COLORS = {'COLORX', 'COLORY'}
    COMPOUNDABLES = {'JOINT', 'COMPOUND'}
    monkeypatch.setattr(blessed.formatters, 'resolve_color', resolve_color)
    monkeypatch.setattr(blessed.formatters, 'COLORS', COLORS)
    monkeypatch.setattr(blessed.formatters, 'COMPOUNDABLES', COMPOUNDABLES)
    term = mock.Mock()
    assert resolve_attribute(term, 'COLORX') == 'seq-COLORX'


def test_resolve_attribute_as_compoundable(monkeypatch):
    """Test simple resolve_attribte() given a compoundable."""
    # local
    import blessed
    from blessed.formatters import FormattingString, resolve_attribute

    def resolve_cap(term, digit):
        return f'seq-{digit}'

    COMPOUNDABLES = {'JOINT', 'COMPOUND'}
    monkeypatch.setattr(blessed.formatters,
                        'resolve_capability',
                        resolve_cap)
    monkeypatch.setattr(blessed.formatters, 'COMPOUNDABLES', COMPOUNDABLES)
    term = mock.Mock()
    term.normal = 'seq-normal'

    compound = resolve_attribute(term, 'JOINT')
    assert isinstance(compound, FormattingString)
    assert str(compound) == 'seq-JOINT'
    assert compound('text') == 'seq-JOINTtextseq-normal'


def test_resolve_attribute_non_compoundables(monkeypatch):
    """Test recursive compounding of resolve_attribute()."""
    # local
    import blessed
    from blessed.formatters import ParameterizingString, resolve_attribute

    def uncompoundables(attr):
        return ['split', 'compound']

    def resolve_cap(term, digit):
        return f'seq-{digit}'

    monkeypatch.setattr(blessed.formatters,
                        'split_compound',
                        uncompoundables)
    monkeypatch.setattr(blessed.formatters,
                        'resolve_capability',
                        resolve_cap)
    monkeypatch.setattr(curses, 'tparm', fn_tparm)

    term = mock.Mock()
    term.normal = 'seq-normal'

    # given
    pstr = resolve_attribute(term, 'not-a-compoundable')
    assert isinstance(pstr, ParameterizingString)
    assert str(pstr) == 'seq-not-a-compoundable'
    # this is like calling term.move_x(3)
    assert pstr(3) == 'seq-not-a-compoundable~3'
    # this is like calling term.move_x(3)('text')
    assert pstr(3)('text') == 'seq-not-a-compoundable~3textseq-normal'


def test_resolve_attribute_recursive_compoundables(monkeypatch):
    """Test recursive compounding of resolve_attribute()."""
    # local
    import blessed
    from blessed.formatters import FormattingString, resolve_attribute

    # patch,
    def resolve_cap(term, digit):
        return f'seq-{digit}'

    monkeypatch.setattr(blessed.formatters,
                        'resolve_capability',
                        resolve_cap)
    monkeypatch.setattr(curses, 'tparm', fn_tparm)
    monkeypatch.setattr(curses, 'COLOR_RED', 6502)
    monkeypatch.setattr(curses, 'COLOR_BLUE', 6800)

    def color_cap(digit):
        return f'seq-{digit}'

    term = mock.Mock()
    term._background_color = color_cap
    term._foreground_color = color_cap
    term.normal = 'seq-normal'

    # given,
    pstr = resolve_attribute(term, 'bright_blue_on_red')

    # exercise,
    assert isinstance(pstr, FormattingString)
    assert str(pstr) == 'seq-6808seq-6502'
    assert pstr('text') == 'seq-6808seq-6502textseq-normal'


def test_formattingstring_picklability():
    """Test pickle-ability of a FormattingString."""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        # basic pickle
        assert pickle.loads(pickle.dumps(t.red))('orange') == t.red('orange')
        assert pickle.loads(pickle.dumps(t.normal)) == t.normal

        # and, pickle through multiprocessing
        r, w = multiprocessing.Pipe()
        w.send(t.normal)
        assert r.recv() == t.normal

    child()


def test_formattingotherstring_picklability():
    """Test pickle-ability of a FormattingOtherString."""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=True)
        # basic pickle
        assert pickle.loads(pickle.dumps(t.move_left)) == t.move_left
        assert pickle.loads(pickle.dumps(t.move_left(3))) == t.move_left(3)
        assert pickle.loads(pickle.dumps(t.move_left))(3) == t.move_left(3)

        # and, pickle through multiprocessing
        r, w = multiprocessing.Pipe()
        w.send(t.move_left)
        assert r.recv()(3) == t.move_left(3)
        w.send(t.move_left(3))
        assert r.recv() == t.move_left(3)

    child()


def test_paramterizingstring_picklability():
    """Test pickle-ability of ParameterizingString."""
    @as_subprocess
    def child():
        # local
        from blessed.formatters import ParameterizingString
        t = TestTerminal(force_styling=True)

        color = ParameterizingString(t.color, t.normal, 'color')
        assert pickle.loads(pickle.dumps(color)) == color
        assert pickle.loads(pickle.dumps(color(3))) == color(3)
        assert pickle.loads(pickle.dumps(color))(3) == color(3)

        # and, pickle through multiprocessing
        r, w = multiprocessing.Pipe()
        w.send(color)
        assert r.recv() == color
        w.send(color(3))
        assert r.recv() == color(3)
        w.send(t.color)
        assert r.recv()(3) == t.color(3)

    child()


def test_pickled_parameterizing_string(monkeypatch):
    """Test pickle-ability of a formatters.ParameterizingString."""
    # local
    from blessed.formatters import ParameterizingString

    # simply send()/recv() over multiprocessing Pipe, a simple
    # pickle.loads(dumps(...)) did not reproduce this issue,
    # first argument to tparm() is the sequence name, returned as-is;
    # subsequent arguments are usually Integers.
    monkeypatch.setattr(curses, 'tparm', fn_tparm)

    # given,
    pstr = ParameterizingString('seqname', 'norm', 'cap-name')

    # multiprocessing Pipe implicitly pickles.
    r, w = multiprocessing.Pipe()

    # exercise picklability of ParameterizingString
    for proto_num in range(pickle.HIGHEST_PROTOCOL):
        assert pstr == pickle.loads(pickle.dumps(pstr, protocol=proto_num))
    w.send(pstr)
    assert r.recv() == pstr

    # exercise picklability of FormattingString
    # -- the return value of calling ParameterizingString
    zero = pstr(0)
    for proto_num in range(pickle.HIGHEST_PROTOCOL):
        assert zero == pickle.loads(pickle.dumps(zero, protocol=proto_num))
    w.send(zero)
    assert r.recv() == zero


def test_tparm_returns_null(monkeypatch):
    """Test 'tparm() returned NULL' is caught (win32 PDCurses systems)."""
    # on win32, any calls to tparm raises curses.error with message,
    # "tparm() returned NULL", function PyCurses_tparm of _cursesmodule.c
    # local
    from blessed.formatters import NullCallableString, ParameterizingString

    def tparm(*args):
        raise curses.error("tparm() returned NULL")

    monkeypatch.setattr(curses, 'tparm', tparm)

    term = mock.Mock()
    term.normal = 'seq-normal'

    pstr = ParameterizingString('cap', 'norm', 'seq-name')

    value = pstr(0)
    assert isinstance(value, NullCallableString)


def test_tparm_other_exception(monkeypatch):
    """Test 'tparm() returned NULL' is caught (win32 PDCurses systems)."""
    # on win32, any calls to tparm raises curses.error with message,
    # "tparm() returned NULL", function PyCurses_tparm of _cursesmodule.c
    # local
    from blessed.formatters import ParameterizingString

    def tparm(*args):
        raise curses.error("unexpected error in tparm()")

    monkeypatch.setattr(curses, 'tparm', tparm)

    term = mock.Mock()
    term.normal = 'seq-normal'

    pstr = ParameterizingString('cap', 'norm', 'seq-name')

    try:
        pstr('x')
        assert False, "previous call should have raised curses.error"
    except curses.error:
        pass
