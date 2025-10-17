# -*- coding: utf-8 -*-
"""Tests for DEC Private Mode event handling."""
# std imports
import re
import io

# 3rd party
import pytest

# local
from blessed import Terminal
from blessed.keyboard import (
    Keystroke,
    _match_dec_event,
    BracketedPasteEvent,
    FocusEvent,
)
from .accessories import TestTerminal, make_enabled_dec_cache


class TestDECEventMatching:
    """Test DEC event pattern matching functionality."""

    @pytest.mark.parametrize("sequence", ['hello', 'abc123', '', '\x1b[9999z', '\x1b[unknown'])
    def test_match_dec_event_invalid(self, sequence):
        """Test that invalid sequences return None."""
        assert _match_dec_event(sequence) is None

    def test_bracketed_paste_detection(self):
        """Test bracketed paste sequence detection."""
        sequence = '\x1b[200~hello world\x1b[201~'
        ks = _match_dec_event(sequence, dec_mode_cache=make_enabled_dec_cache())

        assert ks is not None
        assert ks == sequence
        assert ks.mode == Terminal.DecPrivateMode.BRACKETED_PASTE
        assert ks._mode == 2004

        values = ks._mode_values
        assert isinstance(values, BracketedPasteEvent)
        assert values.text == 'hello world'

    def test_bracketed_paste_multiline(self):
        """Test bracketed paste with multiline content."""
        sequence = '\x1b[200~line1\nline2\tindented\x1b[201~'
        ks = _match_dec_event(sequence, dec_mode_cache=make_enabled_dec_cache())

        assert ks is not None
        values = ks._mode_values
        assert values.text == 'line1\nline2\tindented'

    @pytest.mark.parametrize("sequence,expected_gained", [
        ('\x1b[I', True),   # Focus gained
        ('\x1b[O', False),  # Focus lost
    ])
    def test_focus_events(self, sequence, expected_gained):
        """Test focus events for gained and lost."""
        ks = _match_dec_event(sequence, dec_mode_cache=make_enabled_dec_cache())
        assert ks.mode == Terminal.DecPrivateMode.FOCUS_IN_OUT_EVENTS

        values = ks._mode_values
        assert isinstance(values, FocusEvent)
        assert values.gained is expected_gained


@pytest.mark.parametrize("mode,match_obj", [
    (None, None),
    (9999, re.compile(r'\x1b\[test'))
])
def test_mode_values_returns_none(mode, match_obj):
    """Test mode_values returns None for unsupported modes."""
    match = None
    if match_obj:
        match = match_obj.match('\x1b[test')

    ks = Keystroke('xxxxxxxxx', mode=mode, match=match)

    assert ks._mode_values is None


def test_keystroke_with_dec_mode():
    """Test keystroke with DEC mode - minimal test."""
    match = re.match(r'\x1b\[200~(?P<text>.*?)\x1b\[201~', '\x1b[200~test\x1b[201~')
    ks = Keystroke('\x1b[200~test\x1b[201~', mode=2004, match=match)
    assert ks.mode == Terminal.DecPrivateMode.BRACKETED_PASTE
    assert ks.is_sequence


def test_terminal_dec_mode_context_no_styling():
    """Test DEC mode context managers with force_styling=False"""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)
    with term.dec_modes_enabled(Terminal.DecPrivateMode.BRACKETED_PASTE):
        pass
    with term.dec_modes_enabled(Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR):
        pass
    output = stream.getvalue()
    assert output == ''


def test_resolve_sequence():
    """Test that DEC events don't interfere with regular sequence resolution."""
    from blessed.keyboard import resolve_sequence, OrderedDict, get_leading_prefixes

    # Mock keymap and codes for basic resolver
    keymap = OrderedDict([('\x1b[A', 100)])  # Up arrow
    prefixes = get_leading_prefixes(keymap)
    codes = {100: 'KEY_UP'}

    # Regular sequence should resolve normally when DEC modes are not enabled
    ks = resolve_sequence('\x1b[A', keymap, codes, prefixes)
    assert ks.code == 100
    assert ks.name == 'KEY_UP'

    # DEC event sequence should match when modes are enabled
    dec_sequence = '\x1b[200~test\x1b[201~'
    ks_dec = resolve_sequence(dec_sequence, keymap, codes, prefixes,
                              dec_mode_cache=make_enabled_dec_cache())
    event_value = ks_dec._mode_values
    assert isinstance(event_value, BracketedPasteEvent)
    assert event_value.text == 'test'
    assert ks_dec.mode == Terminal.DecPrivateMode.BRACKETED_PASTE


def test_focus_event_names():
    """Test that focus events have correct names."""
    cache = make_enabled_dec_cache()

    # Focus gained
    ks_focus_in = _match_dec_event('\x1b[I', dec_mode_cache=cache)
    assert ks_focus_in.name == "FOCUS_IN"

    # Focus lost
    ks_focus_out = _match_dec_event('\x1b[O', dec_mode_cache=cache)
    assert ks_focus_out.name == "FOCUS_OUT"

    # Regular keystrokes shouldn't match focus names
    ks_regular = Keystroke('I')
    assert ks_regular.name != "FOCUS_IN"


def test_bracketed_paste_name_and_text():
    """Test that bracketed paste events have correct name and text property."""
    cache = make_enabled_dec_cache()

    # Simple paste
    ks_paste = _match_dec_event('\x1b[200~hello world\x1b[201~', dec_mode_cache=cache)
    assert ks_paste.name == "BRACKETED_PASTE"
    assert ks_paste.text == "hello world"

    # Multiline paste
    ks_multiline = _match_dec_event('\x1b[200~line1\nline2\x1b[201~', dec_mode_cache=cache)
    assert ks_multiline.name == "BRACKETED_PASTE"
    assert ks_multiline.text == "line1\nline2"

    # Empty paste
    ks_empty = _match_dec_event('\x1b[200~\x1b[201~', dec_mode_cache=cache)
    assert ks_empty.name == "BRACKETED_PASTE"
    assert ks_empty.text == ""

    # Regular keystrokes should not have text property
    ks_regular = Keystroke('a')
    assert ks_regular.text is None
