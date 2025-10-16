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
    MouseEvent,
    MouseSGREvent,
    MouseLegacyEvent,
    FocusEvent,
)
from blessed.dec_modes import DecModeResponse
from .accessories import TestTerminal


# Helper to create a dec_mode_cache with all DEC event modes enabled
def _make_enabled_cache():
    """Create a dec_mode_cache with all DEC event modes enabled."""
    return {
        2004: DecModeResponse.SET,  # BRACKETED_PASTE
        1000: DecModeResponse.SET,  # MOUSE_REPORT_CLICK
        1002: DecModeResponse.SET,  # MOUSE_REPORT_DRAG
        1003: DecModeResponse.SET,  # MOUSE_ALL_MOTION
        1001: DecModeResponse.SET,  # MOUSE_HILITE_TRACKING
        1004: DecModeResponse.SET,  # FOCUS_IN_OUT_EVENTS
        1006: DecModeResponse.SET,  # MOUSE_EXTENDED_SGR
        1016: DecModeResponse.SET,  # MOUSE_SGR_PIXELS
    }


class TestDECEventMatching:
    """Test DEC event pattern matching functionality."""

    @pytest.mark.parametrize("sequence", ['hello', 'abc123', '', '\x1b[9999z', '\x1b[unknown'])
    def test_match_dec_event_invalid(self, sequence):
        """Test that invalid sequences return None."""
        assert _match_dec_event(sequence) is None

    def test_bracketed_paste_detection(self):
        """Test bracketed paste sequence detection."""
        sequence = '\x1b[200~hello world\x1b[201~'
        ks = _match_dec_event(sequence, dec_mode_cache=_make_enabled_cache())

        assert ks is not None
        assert ks == sequence
        assert ks.mode == Terminal.DecPrivateMode.BRACKETED_PASTE
        assert ks._mode == 2004

        values = ks.mode_values
        assert isinstance(values, BracketedPasteEvent)
        assert values.text == 'hello world'

    def test_bracketed_paste_multiline(self):
        """Test bracketed paste with multiline content."""
        sequence = '\x1b[200~line1\nline2\tindented\x1b[201~'
        ks = _match_dec_event(sequence, dec_mode_cache=_make_enabled_cache())

        assert ks is not None
        values = ks.mode_values
        assert values.text == 'line1\nline2\tindented'

    @pytest.mark.parametrize("sequence,expected", [
        # (sequence, (button, x, y, released, shift, meta, ctrl, is_wheel))
        # Note: Protocol sends 1-indexed coordinates, converted to 0-indexed
        ('\x1b[0;10;20M', (0, 9, 19, False, False, False, False, False)),
        ('\x1b[0;15;25m', (0, 14, 24, True, False, False, False, False)),
        ('\x1b[28;5;5M', (0, 4, 4, False, True, True, True, False)),
        ('\x1b[64;10;10M', (64, 9, 9, False, False, False, False, True)),
        ('\x1b[65;10;10M', (65, 9, 9, False, False, False, False, True)),
        ('\x1b[<65;134;27M', (65, 133, 26, False, False, False, False, True)),
        ('\x1b[<64;134;27M', (64, 133, 26, False, False, False, False, True)),
    ])
    def test_mouse_sgr_events(self, sequence, expected):
        """Test SGR mouse events with various button, modifier, and wheel states."""
        button, x, y, released, shift, meta, ctrl, is_wheel = expected
        ks = _match_dec_event(sequence, dec_mode_cache=_make_enabled_cache())

        assert ks is not None
        # When both 1006 and 1016 are enabled, 1016 (SGR-Pixels) is preferred
        assert ks.mode in (Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR,
                           Terminal.DecPrivateMode.MOUSE_SGR_PIXELS)

        values = ks.mode_values
        assert isinstance(values, MouseSGREvent)
        assert values.button_value == button
        assert values.x == x
        assert values.y == y
        assert values.released == released
        assert values.shift == shift
        assert values.meta == meta
        assert values.ctrl == ctrl
        assert values.is_wheel == is_wheel

    @pytest.mark.parametrize("sequence,expected_release,expected_button", [
        ('\x1b[M   ', False, 0),  # Press event
        ('\x1b[M#@@', True, 0),   # Release event (button reset to 0)
    ])
    def test_mouse_legacy_events(self, sequence, expected_release, expected_button):
        """Test legacy mouse events for press and release."""
        ks = _match_dec_event(sequence, dec_mode_cache=_make_enabled_cache())
        assert ks.mode.value == 1000  # Default legacy mode

        values = ks.mode_values
        assert isinstance(values, MouseLegacyEvent)
        assert values.released == expected_release
        assert values.button_value == expected_button
        assert not values.is_motion
        assert not values.is_wheel

    @pytest.mark.parametrize("sequence,expected_gained", [
        ('\x1b[I', True),   # Focus gained
        ('\x1b[O', False),  # Focus lost
    ])
    def test_focus_events(self, sequence, expected_gained):
        """Test focus events for gained and lost."""
        ks = _match_dec_event(sequence, dec_mode_cache=_make_enabled_cache())
        assert ks.mode == Terminal.DecPrivateMode.FOCUS_IN_OUT_EVENTS

        values = ks.mode_values
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

    assert ks.mode_values is None


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


def test_mouse_sgr_csi_lt_events():
    """Test SGR mouse events with proper CSI < format."""
    # Test standard SGR format: CSI < button ; x ; y M/m
    cache = _make_enabled_cache()

    # Test press event with CSI < prefix
    ks_press = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    # When both 1006 and 1016 are enabled, 1016 (SGR-Pixels) is preferred
    assert ks_press.mode in (Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR,
                             Terminal.DecPrivateMode.MOUSE_SGR_PIXELS)

    values = ks_press.mode_values
    assert isinstance(values, MouseSGREvent)
    assert values.button_value == 0  # Left button
    assert values.x == 9  # Protocol sends 10, converted to 0-indexed
    assert values.y == 19  # Protocol sends 20, converted to 0-indexed
    assert not values.released
    assert not values.shift and not values.meta and not values.ctrl

    # Test release event with CSI < prefix
    ks_release = _match_dec_event('\x1b[<0;15;25m', dec_mode_cache=cache)
    values = ks_release.mode_values
    assert values.x == 14  # Protocol sends 15, converted to 0-indexed
    assert values.y == 24  # Protocol sends 25, converted to 0-indexed
    assert values.released

    # Test modifiers with CSI < prefix (shift=4, meta=8, ctrl=16, combined=28)
    ks_mod = _match_dec_event('\x1b[<28;5;5M', dec_mode_cache=cache)
    values = ks_mod.mode_values
    assert values.shift and values.meta and values.ctrl
    assert values.button_value == 0  # Base button after masking

    # Test wheel events with CSI < prefix
    ks_wheel_up = _match_dec_event('\x1b[<64;10;10M', dec_mode_cache=cache)
    values_up = ks_wheel_up.mode_values
    assert values_up.button_value == 64 and values_up.is_wheel

    ks_wheel_down = _match_dec_event('\x1b[<65;10;10M', dec_mode_cache=cache)
    values_down = ks_wheel_down.mode_values
    assert values_down.button_value == 65 and values_down.is_wheel


def test_mouse_sgr_pixels_format():
    """Test SGR-Pixels format compatibility (mode 1016).

    SGR-Pixels (mode 1016) uses identical wire format to SGR (mode 1006).
    The difference is semantic - coordinates represent pixels vs character cells.
    Since wire format is identical, the decoder cannot distinguish between them;
    applications must interpret coordinates based on which mode was enabled.
    """
    # Test large coordinates typical of pixel-based reporting
    ks_pixels = _match_dec_event('\x1b[<0;1234;567M', dec_mode_cache=_make_enabled_cache())

    # Should parse as SGR-Pixels (mode 1016) if both modes are enabled since 1016 is preferred
    assert ks_pixels.mode == Terminal.DecPrivateMode.MOUSE_SGR_PIXELS

    values = ks_pixels.mode_values
    assert isinstance(values, MouseSGREvent)
    assert values.button_value == 0  # Left button
    assert values.x == 1233  # Large x coordinate (pixels), protocol sends 1234
    assert values.y == 566   # Large y coordinate (pixels), protocol sends 567
    assert not values.released
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

    # Regular sequence should resolve normally when DEC modes are not enabled
    ks = resolve_sequence('\x1b[A', keymap, codes, prefixes)
    assert ks.code == 100
    assert ks.name == 'KEY_UP'

    # DEC event sequence should match when modes are enabled
    dec_sequence = '\x1b[200~test\x1b[201~'
    ks_dec = resolve_sequence(dec_sequence, keymap, codes, prefixes,
                              dec_mode_cache=_make_enabled_cache())
    event_value = ks_dec.mode_values
    assert isinstance(event_value, BracketedPasteEvent)
    assert event_value.text == 'test'
    assert ks_dec.mode == Terminal.DecPrivateMode.BRACKETED_PASTE


def test_mouse_event_is_motion_field():
    """Test that is_motion field is present and correct for both SGR and legacy events."""
    cache = _make_enabled_cache()

    # Test SGR mouse event with motion (drag)
    ks_drag = _match_dec_event('\x1b[<32;10;20M', dec_mode_cache=cache)  # bit 32 set = motion
    values = ks_drag.mode_values
    assert isinstance(values, MouseEvent)
    assert values.is_motion is True
    assert not values.released

    # Test SGR mouse press without motion
    ks_press = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    values = ks_press.mode_values
    assert values.is_motion is False

    # Test SGR mouse release with motion bit set
    ks_release = _match_dec_event('\x1b[<32;10;20m',
                                  dec_mode_cache=cache)  # lowercase 'm' = release
    values = ks_release.mode_values
    assert values.is_motion is True
    assert values.released is True

    # Test legacy mouse event with motion
    # cb byte: 32 (motion bit) + offset 32 = 64 = '@'
    ks_legacy_motion = _match_dec_event('\x1b[M@  ', dec_mode_cache=cache)
    values = ks_legacy_motion.mode_values
    assert isinstance(values, MouseEvent)
    assert values.is_motion is True

    # Test legacy mouse event without motion
    ks_legacy_press = _match_dec_event('\x1b[M   ',
                                       dec_mode_cache=cache)  # cb=32, button=0, no motion
    values = ks_legacy_press.mode_values
    assert values.is_motion is False


def test_mouse_event_is_wheel_field():
    """Test that is_wheel field is present and correct for both SGR and legacy events."""
    cache = _make_enabled_cache()

    # Test wheel up event (button 64)
    ks_wheel_up = _match_dec_event('\x1b[<64;134;27M', dec_mode_cache=cache)
    values = ks_wheel_up.mode_values
    assert isinstance(values, MouseEvent)
    assert values.is_wheel is True
    assert values.button_value == 64
    assert values.x == 133  # Protocol sends 134, converted to 0-indexed
    assert values.y == 26   # Protocol sends 27, converted to 0-indexed

    # Test wheel down event (button 65)
    ks_wheel_down = _match_dec_event('\x1b[<65;134;27M', dec_mode_cache=cache)
    values = ks_wheel_down.mode_values
    assert values.is_wheel is True
    assert values.button_value == 65

    # Test regular mouse button presses (button 0-3) - should not be wheel
    for num in (0, 1, 2):
        ks_press_left = _match_dec_event(f'\x1b[<{num};10;20M', dec_mode_cache=cache)
        values = ks_press_left.mode_values
        assert values.is_wheel is False
        assert values.button_value == num

    # Test legacy mouse event - should not be wheel
    ks_legacy_press = _match_dec_event('\x1b[M   ', dec_mode_cache=cache)
    values = ks_legacy_press.mode_values
    assert values.is_wheel is False


def test_mouse_event_repr():
    """Test that MouseEvent __repr__ only shows active attributes."""
    cache = _make_enabled_cache()

    # Test simple press event - should only show button_value, x, y
    ks_press = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    values = ks_press.mode_values
    repr_str = repr(values)
    assert repr_str == "MouseEvent(button_value=0, x=9, y=19)"
    assert 'released' not in repr_str
    assert 'shift' not in repr_str

    # Test release event - should show released
    ks_release = _match_dec_event('\x1b[<0;10;20m', dec_mode_cache=cache)
    values = ks_release.mode_values
    repr_str = repr(values)
    assert 'released=True' in repr_str
    assert repr_str == "MouseEvent(button_value=0, x=9, y=19, released=True)"

    # Test with modifiers - should show shift, meta, ctrl
    # 28 = 4 (shift) + 8 (meta) + 16 (ctrl)
    ks_mod = _match_dec_event('\x1b[<28;5;5M', dec_mode_cache=cache)
    values = ks_mod.mode_values
    repr_str = repr(values)
    assert 'shift=True' in repr_str
    assert 'meta=True' in repr_str
    assert 'ctrl=True' in repr_str
    assert repr_str == "MouseEvent(button_value=0, x=4, y=4, shift=True, meta=True, ctrl=True)"

    # Test wheel event - should show is_wheel
    ks_wheel = _match_dec_event('\x1b[<64;10;10M', dec_mode_cache=cache)
    values = ks_wheel.mode_values
    repr_str = repr(values)
    assert 'is_wheel=True' in repr_str
    assert repr_str == "MouseEvent(button_value=64, x=9, y=9, is_wheel=True)"


def test_mouse_event_button_property():
    # pylint: disable=too-many-locals
    """Test that MouseEvent.button property returns correct button names."""
    cache = _make_enabled_cache()

    # Test basic buttons without modifiers
    ks_left = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    assert ks_left.mode_values.button == "LEFT"

    ks_middle = _match_dec_event('\x1b[<1;10;20M', dec_mode_cache=cache)
    assert ks_middle.mode_values.button == "MIDDLE"

    ks_right = _match_dec_event('\x1b[<2;10;20M', dec_mode_cache=cache)
    assert ks_right.mode_values.button == "RIGHT"

    # Test wheel events
    ks_scroll_up = _match_dec_event('\x1b[<64;10;10M', dec_mode_cache=cache)
    assert ks_scroll_up.mode_values.button == "SCROLL_UP"

    ks_scroll_down = _match_dec_event('\x1b[<65;10;10M', dec_mode_cache=cache)
    assert ks_scroll_down.mode_values.button == "SCROLL_DOWN"

    # Test buttons with single modifier
    ks_ctrl_left = _match_dec_event('\x1b[<16;10;20M', dec_mode_cache=cache)  # ctrl=16
    assert ks_ctrl_left.mode_values.button == "CTRL_LEFT"

    ks_shift_middle = _match_dec_event('\x1b[<5;10;20M', dec_mode_cache=cache)  # shift=4, button=1
    assert ks_shift_middle.mode_values.button == "SHIFT_MIDDLE"

    ks_meta_right = _match_dec_event('\x1b[<10;10;20M', dec_mode_cache=cache)  # meta=8, button=2
    assert ks_meta_right.mode_values.button == "META_RIGHT"

    # Test wheel with modifiers
    ks_shift_scroll_up = _match_dec_event(
        '\x1b[<68;10;10M',
        dec_mode_cache=cache)  # shift=4, button=64
    assert ks_shift_scroll_up.mode_values.button == "SHIFT_SCROLL_UP"

    # Test multiple modifiers (ctrl=16, shift=4, meta=8, total=28)
    ks_multi_mod = _match_dec_event('\x1b[<28;5;5M', dec_mode_cache=cache)
    assert ks_multi_mod.mode_values.button == "CTRL_SHIFT_META_LEFT"

    # Test extended buttons (button >= 66)
    mouse_extended = MouseEvent(
        button_value=66, x=10, y=20, released=False,
        shift=False, meta=False, ctrl=False, is_motion=False, is_wheel=False
    )
    assert mouse_extended.button == "BUTTON_6"

    mouse_extended_7 = MouseEvent(
        button_value=67, x=10, y=20, released=False,
        shift=False, meta=False, ctrl=False, is_motion=False, is_wheel=False
    )
    assert mouse_extended_7.button == "BUTTON_7"

    # Test extended button with modifiers
    mouse_ext_shift = MouseEvent(
        button_value=66, x=10, y=20, released=False,
        shift=True, meta=False, ctrl=False, is_motion=False, is_wheel=False
    )
    assert mouse_ext_shift.button == "SHIFT_BUTTON_6"

    # Test release events with _RELEASED suffix
    ks_left_rel = _match_dec_event('\x1b[<0;10;20m',
                                   dec_mode_cache=cache)  # lowercase 'm' = release
    assert ks_left_rel.mode_values.button == "LEFT_RELEASED"

    ks_middle_rel = _match_dec_event('\x1b[<1;10;20m', dec_mode_cache=cache)
    assert ks_middle_rel.mode_values.button == "MIDDLE_RELEASED"

    ks_right_rel = _match_dec_event('\x1b[<2;10;20m', dec_mode_cache=cache)
    assert ks_right_rel.mode_values.button == "RIGHT_RELEASED"

    # Test release with modifiers
    ks_ctrl_left_rel = _match_dec_event(
        '\x1b[<16;10;20m',
        dec_mode_cache=cache)  # ctrl=16, released
    assert ks_ctrl_left_rel.mode_values.button == "CTRL_LEFT_RELEASED"

    # Test extended button release
    mouse_ext_rel = MouseEvent(
        button_value=66, x=10, y=20, released=True,
        shift=False, meta=False, ctrl=False, is_motion=False, is_wheel=False
    )
    assert mouse_ext_rel.button == "BUTTON_6_RELEASED"


def test_mouse_event_backwards_compatibility():
    """Test that MouseSGREvent and MouseLegacyEvent still work as aliases."""
    cache = _make_enabled_cache()

    # Verify they are the same class
    assert MouseSGREvent is MouseEvent
    assert MouseLegacyEvent is MouseEvent

    # Verify isinstance checks work with old names
    ks_sgr = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    values = ks_sgr.mode_values
    assert isinstance(values, MouseSGREvent)
    assert isinstance(values, MouseLegacyEvent)
    assert isinstance(values, MouseEvent)

    ks_legacy = _match_dec_event('\x1b[M   ', dec_mode_cache=cache)
    values = ks_legacy.mode_values
    assert isinstance(values, MouseSGREvent)
    assert isinstance(values, MouseLegacyEvent)
    assert isinstance(values, MouseEvent)


@pytest.mark.skipif(
    __import__('os').environ.get('TEST_KEYBOARD') != '1' or
    __import__('platform').system() == 'Windows',
    reason="Requires TEST_KEYBOARD=1 and not Windows"
)
def test_mouse_legacy_encoding_systematic():
    # pylint: disable=too-complex,too-many-locals
    """Test legacy mouse encoding/decoding via PTY."""
    import os
    import time
    from .accessories import pty_test

    def encode_legacy_mouse(button, x, y, shift=False, meta=False, ctrl=False,
                            released=False, is_motion=False):
        # pylint: disable=too-many-positional-arguments
        # x, y are 0-indexed application coordinates
        # Protocol requires 1-indexed coordinates, so add 1 before encoding
        cb = button if not released else 3
        if shift:
            cb |= 4
        if meta:
            cb |= 8
        if ctrl:
            cb |= 16
        if is_motion:
            cb |= 32
        return b'\x1b[M' + bytes([cb + 32, x + 1 + 32, y + 1 + 32])

    test_cases = [
        # button, x, y, shift, meta, ctrl, released, is_motion
        (0, 10, 20, False, False, False, False, False),
        (1, 50, 75, False, False, False, False, False),
        (0, 10, 20, True, False, False, False, False),
        (0, 15, 25, False, False, False, True, False),
        (0, 20, 30, False, False, False, False, True),
        # these would fail due to happy-path decoding error, eg.
        # > UnicodeDecodeError: 'utf-8' codec can't decode
        # > byte 0xe8 in position 0: invalid continuation byte
        (0, 200, 190, False, False, False, False, False),
        (1, 210, 200, False, True, False, False, False),
        (2, 220, 210, False, False, True, False, False),
    ]

    def child(term):
        term._dec_mode_cache = _make_enabled_cache()
        results = []
        with term.cbreak():
            for _ in test_cases:
                ks = term.inkey(timeout=1.0)
                if ks and ks.mode_values:
                    evt = ks.mode_values
                    results.append(f'{evt.button_value},{evt.x},{evt.y},'
                                   f'{int(evt.shift)},{int(evt.meta)},{int(evt.ctrl)},'
                                   f'{int(evt.released)},{int(evt.is_motion)}')
                else:
                    results.append('NONE')
        return ';'.join(results)

    def parent(master_fd):
        for button, x, y, shift, meta, ctrl, released, is_motion in test_cases:
            os.write(
                master_fd,
                encode_legacy_mouse(
                    button,
                    x,
                    y,
                    shift,
                    meta,
                    ctrl,
                    released,
                    is_motion))
            time.sleep(0.05)

    output = pty_test(child, parent)
    results = output.split(';')

    for idx, result in enumerate(results):
        if result == 'NONE':
            continue
        button, x, y, shift, meta, ctrl, released, is_motion = test_cases[idx]
        parts = result.split(',')
        assert int(parts[0]) == button
        assert int(parts[1]) == x
        assert int(parts[2]) == y
        assert bool(int(parts[3])) == shift
        assert bool(int(parts[4])) == meta
        assert bool(int(parts[5])) == ctrl
        assert bool(int(parts[6])) == released
        assert bool(int(parts[7])) == is_motion
