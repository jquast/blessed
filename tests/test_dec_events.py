# -*- coding: utf-8 -*-
"""Tests for DEC Private Mode event handling."""
# std imports
import re
import io

# 3rd party
import pytest

# local
from blessed.keyboard import (
    Keystroke,
    _match_dec_event,
    BracketedPasteEvent,
    MouseSGREvent,
    MouseLegacyEvent,
    FocusEvent,
)
from blessed.dec_modes import DecPrivateMode
from .accessories import TestTerminal, as_subprocess


@pytest.fixture
def bracketed_paste_sequence():
    """Bracketed paste test sequence."""
    return '\x1b[200~hello world\x1b[201~'


@pytest.fixture
def multiline_paste_sequence():
    """Multiline paste test sequence."""
    return '\x1b[200~line1\nline2\tindented\x1b[201~'


@pytest.fixture
def sgr_mouse_sequences():
    """SGR mouse test sequences."""
    return {
        'press': '\x1b[0;10;20M',
        'release': '\x1b[0;15;25m',
        'modifiers': '\x1b[28;5;5M',
        'wheel_up': '\x1b[64;10;10M',
        'wheel_down': '\x1b[65;10;10M'
    }


@pytest.fixture
def legacy_mouse_sequences():
    """Legacy mouse test sequences."""
    return {
        'press': '\x1b[M   ',
        'release': '\x1b[M#@@'
    }


@pytest.fixture
def focus_sequences():
    """Focus event test sequences."""
    return {
        'gained': '\x1b[I',
        'lost': '\x1b[O'
    }


class TestDECEventMatching:
    """Test DEC event pattern matching functionality."""

    @pytest.mark.parametrize("sequence", ['hello', 'abc123', '', '\x1b[9999z', '\x1b[unknown'])
    def test_match_dec_event_invalid(self, sequence):
        """Test that invalid sequences return None."""
        assert _match_dec_event(sequence) is None

    def test_bracketed_paste_detection(self, bracketed_paste_sequence):
        """Test bracketed paste sequence detection."""
        ks = _match_dec_event(bracketed_paste_sequence)

        assert ks is not None
        assert ks == bracketed_paste_sequence
        assert ks.event_mode == DecPrivateMode.BRACKETED_PASTE
        assert ks._mode == 2004

        values = ks.mode_values()
        assert isinstance(values, BracketedPasteEvent)
        assert values.text == 'hello world'

    def test_bracketed_paste_multiline(self, multiline_paste_sequence):
        """Test bracketed paste with multiline content."""
        ks = _match_dec_event(multiline_paste_sequence)

        assert ks is not None
        values = ks.mode_values()
        assert values.text == 'line1\nline2\tindented'

    def test_mouse_sgr_events(self, sgr_mouse_sequences):
        """Test SGR mouse events using fixtures."""
        # Test press event
        ks_press = _match_dec_event(sgr_mouse_sequences['press'])
        assert ks_press.event_mode == DecPrivateMode.MOUSE_EXTENDED_SGR

        values = ks_press.mode_values()
        assert isinstance(values, MouseSGREvent)
        assert values.button == 0  # Left button
        assert values.x == 10
        assert values.y == 20
        assert not values.is_release

        # Test release event
        ks_release = _match_dec_event(sgr_mouse_sequences['release'])
        values = ks_release.mode_values()
        assert values.x == 15
        assert values.y == 25
        assert values.is_release

        # Test modifiers
        ks_mod = _match_dec_event(sgr_mouse_sequences['modifiers'])
        values = ks_mod.mode_values()
        assert values.shift and values.meta and values.ctrl
        assert values.button == 0  # Base button after masking

        # Test wheel events
        ks_wheel_up = _match_dec_event(sgr_mouse_sequences['wheel_up'])
        values_up = ks_wheel_up.mode_values()
        assert values_up.button == 64 and values_up.is_wheel

        ks_wheel_down = _match_dec_event(sgr_mouse_sequences['wheel_down'])
        values_down = ks_wheel_down.mode_values()
        assert values_down.button == 65 and values_down.is_wheel

    def test_mouse_legacy_events(self, legacy_mouse_sequences):
        """Test legacy mouse events using fixtures."""
        # Test press event
        ks_press = _match_dec_event(legacy_mouse_sequences['press'])
        assert ks_press.event_mode.value == 1000  # Default legacy mode

        values = ks_press.mode_values()
        assert isinstance(values, MouseLegacyEvent)
        assert values.button == 0 and values.x == 0 and values.y == 0
        assert not values.is_release and not values.is_motion and not values.is_wheel

        # Test release event
        ks_release = _match_dec_event(legacy_mouse_sequences['release'])
        values = ks_release.mode_values()
        assert values.is_release and values.button == 0

    def test_focus_events(self, focus_sequences):
        """Test focus events using fixtures."""
        # Test focus gained
        ks_gained = _match_dec_event(focus_sequences['gained'])
        assert ks_gained.event_mode == DecPrivateMode.FOCUS_IN_OUT_EVENTS
        values = ks_gained.mode_values()
        assert isinstance(values, FocusEvent) and values.gained is True

        # Test focus lost
        ks_lost = _match_dec_event(focus_sequences['lost'])
        values = ks_lost.mode_values()
        assert isinstance(values, FocusEvent) and values.gained is False


@pytest.mark.parametrize("mode,expected_error", [
    (None, "Should only call mode_values.*when event_mode is non-None"),
    (9999, "Unknown DEC mode 9999")
])
def test_mode_values_errors(mode, expected_error):
    """Test mode_values() error cases."""
    match = None
    if mode:
        match = re.match(r'\x1b\[test', '\x1b[test')

    ks = Keystroke('xxxxxxxxx', mode=mode, match=match)

    with pytest.raises(TypeError, match=expected_error):
        ks.mode_values()


def test_keystroke_with_dec_mode():
    """Test keystroke with DEC mode - minimal test since Keystroke is covered in test_keyboard.py."""
    match = re.match(r'\x1b\[200~(?P<text>.*?)\x1b\[201~', '\x1b[200~test\x1b[201~')
    ks = Keystroke('\x1b[200~test\x1b[201~', mode=2004, match=match)
    assert ks.event_mode == DecPrivateMode.BRACKETED_PASTE
    assert ks.mode == DecPrivateMode.BRACKETED_PASTE
    assert ks.is_sequence


def test_terminal_dec_mode_context_no_styling():
    """Test DEC mode context managers with force_styling=False"""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)
    with term.dec_modes_enabled(DecPrivateMode.BRACKETED_PASTE):
        pass
    with term.dec_modes_enabled(DecPrivateMode.MOUSE_EXTENDED_SGR):
        pass
    output = stream.getvalue()
    assert output == ''


def test_mouse_sgr_csi_lt_events():
    """Test SGR mouse events with proper CSI < format."""
    # Test standard SGR format: CSI < button ; x ; y M/m

    # Test press event with CSI < prefix
    ks_press = _match_dec_event('\x1b[<0;10;20M')
    assert ks_press.event_mode == DecPrivateMode.MOUSE_EXTENDED_SGR

    values = ks_press.mode_values()
    assert isinstance(values, MouseSGREvent)
    assert values.button == 0  # Left button
    assert values.x == 10
    assert values.y == 20
    assert not values.is_release
    assert not values.shift and not values.meta and not values.ctrl

    # Test release event with CSI < prefix
    ks_release = _match_dec_event('\x1b[<0;15;25m')
    values = ks_release.mode_values()
    assert values.x == 15
    assert values.y == 25
    assert values.is_release

    # Test modifiers with CSI < prefix (shift=4, meta=8, ctrl=16, combined=28)
    ks_mod = _match_dec_event('\x1b[<28;5;5M')
    values = ks_mod.mode_values()
    assert values.shift and values.meta and values.ctrl
    assert values.button == 0  # Base button after masking

    # Test wheel events with CSI < prefix
    ks_wheel_up = _match_dec_event('\x1b[<64;10;10M')
    values_up = ks_wheel_up.mode_values()
    assert values_up.button == 64 and values_up.is_wheel

    ks_wheel_down = _match_dec_event('\x1b[<65;10;10M')
    values_down = ks_wheel_down.mode_values()
    assert values_down.button == 65 and values_down.is_wheel


def test_mouse_sgr_pixels_format():
    """Test SGR-Pixels format compatibility (mode 1016).

    SGR-Pixels (mode 1016) uses identical wire format to SGR (mode 1006).
    The difference is semantic - coordinates represent pixels vs character cells.
    Since wire format is identical, the decoder cannot distinguish between them;
    applications must interpret coordinates based on which mode was enabled.
    """
    # Test large coordinates typical of pixel-based reporting
    ks_pixels = _match_dec_event('\x1b[<0;1234;567M')

    # Should parse as regular SGR event (mode 1006) since wire format is identical
    assert ks_pixels.event_mode == DecPrivateMode.MOUSE_EXTENDED_SGR

    values = ks_pixels.mode_values()
    assert isinstance(values, MouseSGREvent)
    assert values.button == 0  # Left button
    assert values.x == 1234  # Large x coordinate (pixels)
    assert values.y == 567   # Large y coordinate (pixels)
    assert not values.is_release
    assert not values.shift and not values.meta and not values.ctrl

    # The interpretation of these coordinates as pixels (vs cells) depends on
    # whether the application enabled mode 1016, not on the sequence structure


def test_resolve_sequence():
    """Test that DEC events don't interfere with regular sequence resolution."""
    from blessed.keyboard import resolve_sequence, OrderedDict, get_leading_prefixes

    # Mock keymap and codes for basic resolver
    keymap = OrderedDict([('\x1b[A', 100)])  # Up arrow
    prefixes = get_leading_prefixes(keymap)
    codes = {100: 'KEY_UP'}

    # Regular sequence should resolve normally
    ks = resolve_sequence('\x1b[A', keymap, codes, prefixes)
    assert ks.code == 100
    assert ks.name == 'KEY_UP'

    # DEC event sequence should also match with same keymap
    dec_sequence = '\x1b[200~test\x1b[201~'
    ks_dec = resolve_sequence(dec_sequence, keymap, codes, prefixes)
    event_value = ks_dec.mode_values()
    assert isinstance(event_value, BracketedPasteEvent)
    assert event_value.text == 'test'
    assert ks_dec.mode == DecPrivateMode.BRACKETED_PASTE
