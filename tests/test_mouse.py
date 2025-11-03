"""Tests for mouse event handling."""
# std imports
import io
from unittest import mock

# 3rd party
import pytest

# local
from blessed import Terminal
from blessed.keyboard import Keystroke, _match_dec_event
from blessed.mouse import MouseEvent, MouseSGREvent, MouseLegacyEvent
from blessed.dec_modes import DecModeResponse
from .accessories import TestTerminal, as_subprocess, make_enabled_dec_cache


class TestMouseEventMatching:
    """Test mouse event pattern matching functionality."""

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
        ks = _match_dec_event(sequence, dec_mode_cache=make_enabled_dec_cache())

        assert ks is not None
        # When both 1006 and 1016 are enabled, 1016 (SGR-Pixels) is preferred
        assert ks.mode in (Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR,
                           Terminal.DecPrivateMode.MOUSE_SGR_PIXELS)

        values = ks._mode_values
        assert isinstance(values, MouseSGREvent)
        assert values.button_value == button
        assert values.x == x
        assert values.y == y
        assert values.released == released
        assert values.shift == shift
        assert values.meta == meta
        assert values.ctrl == ctrl
        assert values.is_wheel == is_wheel

    @pytest.mark.parametrize("mode,sequence,expected_release,expected_button", [
        (1000, '\x1b[M   ', False, 0),  # MOUSE_REPORT_CLICK - Press event
        (1000, '\x1b[M#@@', True, 0),   # MOUSE_REPORT_CLICK - Release
        (1002, '\x1b[M   ', False, 0),  # MOUSE_REPORT_DRAG - Press event
        (1002, '\x1b[M#@@', True, 0),   # MOUSE_REPORT_DRAG - Release
        (1003, '\x1b[M   ', False, 0),  # MOUSE_ALL_MOTION - Press event
        (1003, '\x1b[M#@@', True, 0),   # MOUSE_ALL_MOTION - Release
    ])
    def test_mouse_legacy_events(self, mode, sequence, expected_release, expected_button):
        """Test legacy mouse events work with all three legacy mouse modes."""
        # Test with only the specific mode enabled
        cache = {mode: DecModeResponse.SET}
        ks = _match_dec_event(sequence, dec_mode_cache=cache)
        assert ks.mode.value == mode

        values = ks._mode_values
        assert isinstance(values, MouseLegacyEvent)
        assert values.released == expected_release
        assert values.button_value == expected_button
        assert not values.is_motion
        assert not values.is_wheel


def test_mouse_sgr_csi_lt_events():
    """Test SGR mouse events with proper CSI < format."""
    cache = make_enabled_dec_cache()

    # Test press event with CSI < prefix
    ks_press = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    # When both 1006 and 1016 are enabled, 1016 (SGR-Pixels) is preferred
    assert ks_press.mode in (Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR,
                             Terminal.DecPrivateMode.MOUSE_SGR_PIXELS)

    values = ks_press._mode_values
    assert isinstance(values, MouseSGREvent)
    assert values.button_value == 0
    assert values.x == 9
    assert values.y == 19
    assert not values.released
    assert not values.shift and not values.meta and not values.ctrl

    # Test release event with CSI < prefix
    ks_release = _match_dec_event('\x1b[<0;15;25m', dec_mode_cache=cache)
    values = ks_release._mode_values
    assert values.x == 14
    assert values.y == 24
    assert values.released

    # Test modifiers with CSI < prefix (shift=4, meta=8, ctrl=16, combined=28)
    ks_mod = _match_dec_event('\x1b[<28;5;5M', dec_mode_cache=cache)
    values = ks_mod._mode_values
    assert values.shift and values.meta and values.ctrl
    assert values.button_value == 0

    # Test wheel events with CSI < prefix
    ks_wheel_up = _match_dec_event('\x1b[<64;10;10M', dec_mode_cache=cache)
    values_up = ks_wheel_up._mode_values
    assert values_up.button_value == 64 and values_up.is_wheel

    ks_wheel_down = _match_dec_event('\x1b[<65;10;10M', dec_mode_cache=cache)
    values_down = ks_wheel_down._mode_values
    assert values_down.button_value == 65 and values_down.is_wheel


def test_mouse_sgr_pixels_format():
    """Test SGR-Pixels format compatibility (mode 1016).

    SGR-Pixels (mode 1016) uses identical wire format to SGR (mode 1006).
    The difference is semantic - coordinates represent pixels vs character cells.
    Since wire format is identical, the decoder cannot distinguish between them;
    applications must interpret coordinates based on which mode was enabled.
    """
    # Test large coordinates typical of pixel-based reporting
    ks_pixels = _match_dec_event('\x1b[<0;1234;567M', dec_mode_cache=make_enabled_dec_cache())

    # Should parse as SGR-Pixels (mode 1016) if both modes are enabled since 1016 is preferred
    assert ks_pixels.mode == Terminal.DecPrivateMode.MOUSE_SGR_PIXELS

    values = ks_pixels._mode_values
    assert isinstance(values, MouseSGREvent)
    assert values.button_value == 0
    assert values.x == 1233
    assert values.y == 566
    assert not values.released
    assert not values.shift and not values.meta and not values.ctrl


def test_mouse_event_is_motion_field():
    """Test that is_motion field is present and correct for both SGR and legacy events."""
    cache = make_enabled_dec_cache()

    # Test SGR mouse event with motion (drag)
    ks_drag = _match_dec_event('\x1b[<32;10;20M', dec_mode_cache=cache)
    values = ks_drag._mode_values
    assert isinstance(values, MouseEvent)
    assert values.is_motion is True
    assert not values.released

    # Test SGR mouse press without motion
    ks_press = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    values = ks_press._mode_values
    assert values.is_motion is False

    # Test SGR mouse release with motion bit set
    ks_release = _match_dec_event('\x1b[<32;10;20m', dec_mode_cache=cache)
    values = ks_release._mode_values
    assert values.is_motion is True
    assert values.released is True

    # Test legacy mouse event with motion
    ks_legacy_motion = _match_dec_event('\x1b[M@  ', dec_mode_cache=cache)
    values = ks_legacy_motion._mode_values
    assert isinstance(values, MouseEvent)
    assert values.is_motion is True

    # Test legacy mouse event without motion
    ks_legacy_press = _match_dec_event('\x1b[M   ', dec_mode_cache=cache)
    values = ks_legacy_press._mode_values
    assert values.is_motion is False


def test_mouse_event_is_wheel_field():
    """Test that is_wheel field is present and correct for both SGR and legacy events."""
    cache = make_enabled_dec_cache()

    # Test wheel up event (button 64)
    ks_wheel_up = _match_dec_event('\x1b[<64;134;27M', dec_mode_cache=cache)
    values = ks_wheel_up._mode_values
    assert isinstance(values, MouseEvent)
    assert values.is_wheel is True
    assert values.button_value == 64
    assert values.x == 133
    assert values.y == 26

    # Test wheel down event (button 65)
    ks_wheel_down = _match_dec_event('\x1b[<65;134;27M', dec_mode_cache=cache)
    values = ks_wheel_down._mode_values
    assert values.is_wheel is True
    assert values.button_value == 65

    # Test regular mouse button presses (button 0-3) - should not be wheel
    for num in (0, 1, 2):
        ks_press_left = _match_dec_event(f'\x1b[<{num};10;20M', dec_mode_cache=cache)
        values = ks_press_left._mode_values
        assert values.is_wheel is False
        assert values.button_value == num

    # Test legacy mouse event - should not be wheel
    ks_legacy_press = _match_dec_event('\x1b[M   ', dec_mode_cache=cache)
    values = ks_legacy_press._mode_values
    assert values.is_wheel is False


def test_mouse_event_repr():
    """Test that MouseEvent __repr__ only shows active attributes."""
    cache = make_enabled_dec_cache()

    # Test simple press event - should only show button_value, x, y
    ks_press = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    values = ks_press._mode_values
    repr_str = repr(values)
    assert repr_str == "MouseEvent(button_value=0, x=9, y=19)"
    assert 'released' not in repr_str
    assert 'shift' not in repr_str

    # Test release event - should show released
    ks_release = _match_dec_event('\x1b[<0;10;20m', dec_mode_cache=cache)
    values = ks_release._mode_values
    repr_str = repr(values)
    assert 'released=True' in repr_str
    assert repr_str == "MouseEvent(button_value=0, x=9, y=19, released=True)"

    # Test with modifiers - should show shift, meta, ctrl
    ks_mod = _match_dec_event('\x1b[<28;5;5M', dec_mode_cache=cache)
    values = ks_mod._mode_values
    repr_str = repr(values)
    assert 'shift=True' in repr_str
    assert 'meta=True' in repr_str
    assert 'ctrl=True' in repr_str
    assert repr_str == "MouseEvent(button_value=0, x=4, y=4, shift=True, meta=True, ctrl=True)"

    # Test wheel event - should show is_wheel
    ks_wheel = _match_dec_event('\x1b[<64;10;10M', dec_mode_cache=cache)
    values = ks_wheel._mode_values
    repr_str = repr(values)
    assert 'is_wheel=True' in repr_str
    assert repr_str == "MouseEvent(button_value=64, x=9, y=9, is_wheel=True)"


def test_mouse_event_button_property():
    # pylint: disable=too-many-locals
    """Test that MouseEvent.button property returns correct button names."""
    cache = make_enabled_dec_cache()

    # Test basic buttons without modifiers
    ks_left = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    assert ks_left._mode_values.button == "LEFT"

    ks_middle = _match_dec_event('\x1b[<1;10;20M', dec_mode_cache=cache)
    assert ks_middle._mode_values.button == "MIDDLE"

    ks_right = _match_dec_event('\x1b[<2;10;20M', dec_mode_cache=cache)
    assert ks_right._mode_values.button == "RIGHT"

    # Test wheel events
    ks_scroll_up = _match_dec_event('\x1b[<64;10;10M', dec_mode_cache=cache)
    assert ks_scroll_up._mode_values.button == "SCROLL_UP"

    ks_scroll_down = _match_dec_event('\x1b[<65;10;10M', dec_mode_cache=cache)
    assert ks_scroll_down._mode_values.button == "SCROLL_DOWN"

    # Test buttons with single modifier
    ks_ctrl_left = _match_dec_event('\x1b[<16;10;20M', dec_mode_cache=cache)
    assert ks_ctrl_left._mode_values.button == "CTRL_LEFT"

    ks_shift_middle = _match_dec_event('\x1b[<5;10;20M', dec_mode_cache=cache)
    assert ks_shift_middle._mode_values.button == "SHIFT_MIDDLE"

    ks_meta_right = _match_dec_event('\x1b[<10;10;20M', dec_mode_cache=cache)
    assert ks_meta_right._mode_values.button == "META_RIGHT"

    # Test wheel with modifiers
    ks_shift_scroll_up = _match_dec_event('\x1b[<68;10;10M', dec_mode_cache=cache)
    assert ks_shift_scroll_up._mode_values.button == "SHIFT_SCROLL_UP"

    # Test multiple modifiers (ctrl=16, shift=4, meta=8, total=28)
    ks_multi_mod = _match_dec_event('\x1b[<28;5;5M', dec_mode_cache=cache)
    assert ks_multi_mod._mode_values.button == "CTRL_SHIFT_META_LEFT"

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
    ks_left_rel = _match_dec_event('\x1b[<0;10;20m', dec_mode_cache=cache)
    assert ks_left_rel._mode_values.button == "LEFT_RELEASED"

    ks_middle_rel = _match_dec_event('\x1b[<1;10;20m', dec_mode_cache=cache)
    assert ks_middle_rel._mode_values.button == "MIDDLE_RELEASED"

    ks_right_rel = _match_dec_event('\x1b[<2;10;20m', dec_mode_cache=cache)
    assert ks_right_rel._mode_values.button == "RIGHT_RELEASED"

    # Test release with modifiers
    ks_ctrl_left_rel = _match_dec_event('\x1b[<16;10;20m', dec_mode_cache=cache)
    assert ks_ctrl_left_rel._mode_values.button == "CTRL_LEFT_RELEASED"

    # Test extended button release
    mouse_ext_rel = MouseEvent(
        button_value=66, x=10, y=20, released=True,
        shift=False, meta=False, ctrl=False, is_motion=False, is_wheel=False
    )
    assert mouse_ext_rel.button == "BUTTON_6_RELEASED"


def test_mouse_event_backwards_compatibility():
    """Test that MouseSGREvent and MouseLegacyEvent still work as aliases."""
    cache = make_enabled_dec_cache()

    # Verify they are the same class
    assert MouseSGREvent is MouseEvent
    assert MouseLegacyEvent is MouseEvent

    # Verify isinstance checks work with old names
    ks_sgr = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    values = ks_sgr._mode_values
    assert isinstance(values, MouseSGREvent)
    assert isinstance(values, MouseLegacyEvent)
    assert isinstance(values, MouseEvent)

    ks_legacy = _match_dec_event('\x1b[M   ', dec_mode_cache=cache)
    values = ks_legacy._mode_values
    assert isinstance(values, MouseSGREvent)
    assert isinstance(values, MouseLegacyEvent)
    assert isinstance(values, MouseEvent)


def test_mouse_event_keystroke_name():  # pylint: disable=too-many-locals
    """Test that Keystroke.name returns correct MOUSE_* names for mouse events."""
    cache = make_enabled_dec_cache()

    # Test basic buttons without modifiers
    ks_left = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    assert ks_left.name == "MOUSE_LEFT"

    ks_middle = _match_dec_event('\x1b[<1;10;20M', dec_mode_cache=cache)
    assert ks_middle.name == "MOUSE_MIDDLE"

    ks_right = _match_dec_event('\x1b[<2;10;20M', dec_mode_cache=cache)
    assert ks_right.name == "MOUSE_RIGHT"

    # Test wheel events
    ks_scroll_up = _match_dec_event('\x1b[<64;10;10M', dec_mode_cache=cache)
    assert ks_scroll_up.name == "MOUSE_SCROLL_UP"

    ks_scroll_down = _match_dec_event('\x1b[<65;10;10M', dec_mode_cache=cache)
    assert ks_scroll_down.name == "MOUSE_SCROLL_DOWN"

    # Test buttons with single modifier
    ks_ctrl_left = _match_dec_event('\x1b[<16;10;20M', dec_mode_cache=cache)
    assert ks_ctrl_left.name == "MOUSE_CTRL_LEFT"

    ks_shift_middle = _match_dec_event('\x1b[<5;10;20M', dec_mode_cache=cache)
    assert ks_shift_middle.name == "MOUSE_SHIFT_MIDDLE"

    ks_meta_right = _match_dec_event('\x1b[<10;10;20M', dec_mode_cache=cache)
    assert ks_meta_right.name == "MOUSE_META_RIGHT"

    # Test wheel with modifiers
    ks_shift_scroll_up = _match_dec_event('\x1b[<68;10;10M', dec_mode_cache=cache)
    assert ks_shift_scroll_up.name == "MOUSE_SHIFT_SCROLL_UP"

    # Test multiple modifiers (ctrl=16, shift=4, meta=8, total=28)
    ks_multi_mod = _match_dec_event('\x1b[<28;5;5M', dec_mode_cache=cache)
    assert ks_multi_mod.name == "MOUSE_CTRL_SHIFT_META_LEFT"

    # Test release events with _RELEASED suffix
    ks_left_rel = _match_dec_event('\x1b[<0;10;20m', dec_mode_cache=cache)
    assert ks_left_rel.name == "MOUSE_LEFT_RELEASED"

    ks_middle_rel = _match_dec_event('\x1b[<1;10;20m', dec_mode_cache=cache)
    assert ks_middle_rel.name == "MOUSE_MIDDLE_RELEASED"

    ks_right_rel = _match_dec_event('\x1b[<2;10;20m', dec_mode_cache=cache)
    assert ks_right_rel.name == "MOUSE_RIGHT_RELEASED"

    # Test release with modifiers
    ks_ctrl_left_rel = _match_dec_event('\x1b[<16;10;20m', dec_mode_cache=cache)
    assert ks_ctrl_left_rel.name == "MOUSE_CTRL_LEFT_RELEASED"

    # Test with legacy mouse events
    ks_legacy_left = _match_dec_event('\x1b[M   ', dec_mode_cache=cache)
    assert ks_legacy_left.name == "MOUSE_LEFT"

    # Test that regular keystrokes don't have MOUSE_ names
    ks_regular = Keystroke('a')
    assert ks_regular.name is None or not ks_regular.name.startswith('MOUSE_')


def test_mouse_event_magic_methods():
    """Test that is_mouse_* magic methods work for mouse events."""
    cache = make_enabled_dec_cache()

    # Test basic button predicates
    ks_left = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    assert ks_left.is_mouse_left()
    assert not ks_left.is_mouse_right()
    assert not ks_left.is_mouse_middle()

    ks_middle = _match_dec_event('\x1b[<1;10;20M', dec_mode_cache=cache)
    assert ks_middle.is_mouse_middle()
    assert not ks_middle.is_mouse_left()

    ks_right = _match_dec_event('\x1b[<2;10;20M', dec_mode_cache=cache)
    assert ks_right.is_mouse_right()
    assert not ks_right.is_mouse_left()

    # Test wheel events
    ks_scroll_up = _match_dec_event('\x1b[<64;10;10M', dec_mode_cache=cache)
    assert ks_scroll_up.is_mouse_scroll_up()
    assert not ks_scroll_up.is_mouse_scroll_down()

    ks_scroll_down = _match_dec_event('\x1b[<65;10;10M', dec_mode_cache=cache)
    assert ks_scroll_down.is_mouse_scroll_down()
    assert not ks_scroll_down.is_mouse_scroll_up()

    # Test buttons with modifiers
    ks_ctrl_left = _match_dec_event('\x1b[<16;10;20M', dec_mode_cache=cache)
    assert ks_ctrl_left.is_mouse_ctrl_left()
    assert not ks_ctrl_left.is_mouse_left()

    ks_shift_middle = _match_dec_event('\x1b[<5;10;20M', dec_mode_cache=cache)
    assert ks_shift_middle.is_mouse_shift_middle()
    assert not ks_shift_middle.is_mouse_middle()

    ks_meta_right = _match_dec_event('\x1b[<10;10;20M', dec_mode_cache=cache)
    assert ks_meta_right.is_mouse_meta_right()
    assert not ks_meta_right.is_mouse_right()

    # Test multiple modifiers
    ks_multi_mod = _match_dec_event('\x1b[<28;5;5M', dec_mode_cache=cache)
    assert ks_multi_mod.is_mouse_ctrl_shift_meta_left()
    assert not ks_multi_mod.is_mouse_left()

    # Test release events
    ks_left_rel = _match_dec_event('\x1b[<0;10;20m', dec_mode_cache=cache)
    assert ks_left_rel.is_mouse_left_released()
    assert not ks_left_rel.is_mouse_left()

    ks_ctrl_left_rel = _match_dec_event('\x1b[<16;10;20m', dec_mode_cache=cache)
    assert ks_ctrl_left_rel.is_mouse_ctrl_left_released()
    assert not ks_ctrl_left_rel.is_mouse_ctrl_left()

    # Test that regular keystrokes don't match mouse predicates
    ks_regular = Keystroke('a')
    assert not ks_regular.is_mouse_left()
    assert not ks_regular.is_mouse_right()


def test_mouse_motion_event_naming():
    """Test that motion events are named correctly."""
    cache = make_enabled_dec_cache()

    # Pure motion without button (button=3 "no button", motion bit set = 35)
    ks_motion = _match_dec_event('\x1b[<35;10;20M', dec_mode_cache=cache)
    assert ks_motion.name == "MOUSE_MOTION"
    assert ks_motion.is_mouse_motion()

    # Drag with left button (button=0 "LEFT", motion bit set = 32)
    ks_left_motion = _match_dec_event('\x1b[<32;10;20M', dec_mode_cache=cache)
    values = ks_left_motion._mode_values
    assert values.button_value == 0
    assert values.is_motion
    assert ks_left_motion.name == "MOUSE_LEFT_MOTION"
    assert ks_left_motion.is_mouse_left_motion()

    # Drag with middle button (button=1, motion bit set = 33)
    ks_middle_motion = _match_dec_event('\x1b[<33;10;20M', dec_mode_cache=cache)
    assert ks_middle_motion.name == "MOUSE_MIDDLE_MOTION"
    assert ks_middle_motion.is_mouse_middle_motion()

    # Drag with right button (button=2, motion bit set = 34)
    ks_right_motion = _match_dec_event('\x1b[<34;10;20M', dec_mode_cache=cache)
    assert ks_right_motion.name == "MOUSE_RIGHT_MOTION"
    assert ks_right_motion.is_mouse_right_motion()

    # Pure motion with modifiers (button=3, ctrl=16, motion=32 = 51)
    ks_ctrl_motion = _match_dec_event('\x1b[<51;10;20M', dec_mode_cache=cache)
    assert ks_ctrl_motion.name == "MOUSE_CTRL_MOTION"

    # Left drag with modifiers (button=0, ctrl=16, motion=32 = 48)
    ks_ctrl_left_motion = _match_dec_event('\x1b[<48;10;20M', dec_mode_cache=cache)
    values = ks_ctrl_left_motion._mode_values
    assert values.button_value == 0
    assert values.ctrl
    assert values.is_motion
    assert ks_ctrl_left_motion.name == "MOUSE_CTRL_LEFT_MOTION"
    assert ks_ctrl_left_motion.is_mouse_ctrl_left_motion()

    # Motion events should NOT have _RELEASED suffix
    ks_motion_not_released = _match_dec_event('\x1b[<32;10;20m', dec_mode_cache=cache)
    assert not ks_motion_not_released.name.endswith('_RELEASED')


def test_mouse_coordinate_properties():
    """Test that mouse events have mouse_yx and mouse_xy properties."""
    cache = make_enabled_dec_cache()

    # Test with SGR mouse event
    ks_mouse = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)

    # Test tuple properties
    assert ks_mouse.mouse_yx == (19, 9)
    assert ks_mouse.mouse_xy == (9, 19)

    # Test with different coordinates
    ks_mouse2 = _match_dec_event('\x1b[<0;50;100M', dec_mode_cache=cache)
    assert ks_mouse2.mouse_yx == (99, 49)
    assert ks_mouse2.mouse_xy == (49, 99)

    # Test with pixel coordinates (large values)
    ks_pixels = _match_dec_event('\x1b[<0;1234;567M', dec_mode_cache=cache)
    assert ks_pixels.mouse_yx == (566, 1233)
    assert ks_pixels.mouse_xy == (1233, 566)

    # Regular keystrokes should return (-1, -1) for coordinate properties
    ks_regular = Keystroke('a')
    assert ks_regular.mouse_yx == (-1, -1)
    assert ks_regular.mouse_xy == (-1, -1)


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
        (0, 200, 190, False, False, False, False, False),
        (1, 210, 200, False, True, False, False, False),
        (2, 220, 210, False, False, True, False, False),
    ]

    def child(term):
        term._dec_mode_cache = make_enabled_dec_cache()
        results = []
        with term.cbreak():
            for _ in test_cases:
                ks = term.inkey(timeout=1.0)
                if ks and ks._mode_values:
                    evt = ks._mode_values
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


@pytest.mark.parametrize("clicks,drag,motion,pixels,expected_modes", [
    (True, False, False, False, [1006, 1000]),
    (False, True, False, False, [1006, 1002]),
    (False, False, True, False, [1006, 1003]),
    (True, False, False, True, [1006, 1000, 1016]),
    (False, True, False, True, [1006, 1002, 1016]),
    (False, False, True, True, [1006, 1003, 1016]),
    (True, True, False, False, [1006, 1002]),
    (True, False, True, False, [1006, 1003]),
    (True, True, True, False, [1006, 1003]),
    (False, False, False, False, [1006]),
])
def test_mouse_enabled_mode_selection(clicks, drag, motion, pixels, expected_modes):
    """Test mouse_enabled selects correct modes based on parameters."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True
        mock_response.enabled = False

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response), \
                mock.patch.object(term, '_dec_mode_set_enabled') as mock_set_enabled, \
                mock.patch.object(term, '_dec_mode_set_disabled') as mock_set_disabled:

            with term.mouse_enabled(clicks=clicks, report_drag=drag,
                                    report_motion=motion, report_pixels=pixels):
                args = mock_set_enabled.call_args[0]
                mode_values = [m.value if hasattr(m, 'value') else m for m in args]
                assert mode_values == expected_modes

            mock_set_disabled.assert_called_once()
    child()


def test_mouse_enabled_no_styling():
    """Test mouse_enabled does nothing when does_styling is False."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)

    with term.mouse_enabled():
        pass

    assert stream.getvalue() == ""


@pytest.mark.parametrize("clicks,drag,motion,pixels,expected_modes", [
    (True, False, False, False, [1006, 1000]),
    (False, True, False, False, [1006, 1002]),
    (False, False, True, False, [1006, 1003]),
    (True, False, False, True, [1006, 1000, 1016]),
    (False, True, False, True, [1006, 1002, 1016]),
    (False, False, True, True, [1006, 1003, 1016]),
    (False, False, False, False, [1006]),
])
def test_does_mouse_supported(clicks, drag, motion, pixels, expected_modes):
    """Test does_mouse returns True when all required modes are supported."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response) as mock_get:
            result = term.does_mouse(clicks=clicks, report_drag=drag,
                                     report_motion=motion, report_pixels=pixels)

            assert result is True
            assert mock_get.call_count == len(expected_modes)
            for mode_value in expected_modes:
                assert any(call[0][0] == mode_value for call in mock_get.call_args_list)
        assert stream.getvalue() == ''
    child()


def test_does_mouse_unsupported():
    """Test does_mouse returns False when any mode is unsupported."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        def get_mode_response(mode, timeout=None):
            mock_response = mock.Mock()
            if mode == Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR:
                mock_response.supported = True
            else:
                mock_response.supported = False
            return mock_response

        with mock.patch.object(term, 'get_dec_mode', side_effect=get_mode_response):
            result = term.does_mouse()
            assert result is False
        assert stream.getvalue() == ''
    child()


def test_does_mouse_no_styling():
    """Test does_mouse returns False when does_styling is False."""
    stream = io.StringIO()
    term = TestTerminal(stream=stream, force_styling=False)

    result = term.does_mouse()
    assert result is False
    assert stream.getvalue() == ""


def test_does_mouse_default_parameters():
    """Test does_mouse with default parameters checks click tracking."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response) as mock_get:
            result = term.does_mouse()

            assert result is True
            assert mock_get.call_count == 2
        assert stream.getvalue() == ''
    child()


def test_does_mouse_custom_timeout():
    """Test does_mouse respects custom timeout parameter."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)

        mock_response = mock.Mock()
        mock_response.supported = True

        with mock.patch.object(term, 'get_dec_mode', return_value=mock_response) as mock_get:
            result = term.does_mouse(timeout=2.5)

            assert result is True
            for call in mock_get.call_args_list:
                assert call[1].get('timeout') == 2.5 or call[0][1] == 2.5
        assert stream.getvalue() == ''
    child()


def test_mouse_extended_button_motion():
    """Test extended mouse button motion events (button >= 66)."""
    # Test SGR format with extended button in motion
    mouse_ext_motion = MouseEvent(
        button_value=66, x=10, y=20, released=False,
        shift=False, meta=False, ctrl=False, is_motion=True, is_wheel=False
    )
    assert mouse_ext_motion.button == "BUTTON_6_MOTION"
    assert mouse_ext_motion.is_motion

    # Test with button 67
    mouse_ext_motion_7 = MouseEvent(
        button_value=67, x=10, y=20, released=False,
        shift=False, meta=False, ctrl=False, is_motion=True, is_wheel=False
    )
    assert mouse_ext_motion_7.button == "BUTTON_7_MOTION"


def test_mouse_legacy_wheel_events():
    """Test legacy mouse wheel event parsing."""
    cache = make_enabled_dec_cache()

    # Wheel up: cb=64 → chr(64+32)='`'
    wheel_up_seq = '\x1b[M`@@'
    ks_wheel_up = _match_dec_event(wheel_up_seq, dec_mode_cache=cache)

    values = ks_wheel_up._mode_values
    assert values.is_wheel
    assert values.button_value == 0
    assert ks_wheel_up.name == 'MOUSE_SCROLL_UP'

    # Wheel down: cb=65 → chr(65+32)='a'
    wheel_down_seq = '\x1b[Ma@@'
    ks_wheel_down = _match_dec_event(wheel_down_seq, dec_mode_cache=cache)

    values_down = ks_wheel_down._mode_values
    assert values_down.is_wheel
    assert values_down.button_value == 1
    assert ks_wheel_down.name == 'MOUSE_SCROLL_DOWN'


def test_mouse_wheel_unknown_button_value():
    """Test wheel event with unexpected button_value for completeness."""
    mouse_unknown_wheel = MouseEvent(
        button_value=2, x=10, y=20, released=False,
        shift=False, meta=False, ctrl=False, is_motion=False, is_wheel=True
    )
    button_name = mouse_unknown_wheel.button
    assert button_name == ""


def test_mouse_sgr_without_pixels_mode():
    """Test SGR mouse mode (1006) when pixels mode (1016) is not enabled."""
    cache = {
        Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR: DecModeResponse.SET,
        Terminal.DecPrivateMode.MOUSE_REPORT_CLICK: DecModeResponse.SET,
    }
    ks = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)
    assert ks.mode == Terminal.DecPrivateMode.MOUSE_EXTENDED_SGR
    values = ks._mode_values
    assert isinstance(values, MouseEvent)
    assert values.button_value == 0
    assert values.x == 9
    assert values.y == 19


def test_mouse_sgr_pixels_precedence():
    """Test that mode 1016 (SGR-Pixels) takes precedence over mode 1006 (SGR) when both enabled.

    Both modes use the same wire format, but mode 1016 is listed first in DEC_EVENT_PATTERNS,
    so it matches first when both are enabled. This is the desired behavior.
    """
    cache = make_enabled_dec_cache()
    ks = _match_dec_event('\x1b[<0;10;20M', dec_mode_cache=cache)

    # Should return mode 1016 (SGR-Pixels) due to pattern ordering
    assert ks.mode == Terminal.DecPrivateMode.MOUSE_SGR_PIXELS

    values = ks._mode_values
    assert isinstance(values, MouseEvent)
    assert values.button_value == 0
    assert values.x == 9
    assert values.y == 19


@pytest.mark.parametrize("kwargs,expected_modes", [
    # Default: clicks=True → SGR encoding (1006) + click tracking (1000)
    ({}, ['1006', '1000']),

    # All tracking disabled → only SGR encoding (1006), although this is
    # possible, there isn't any reason to do this -- no mouse events can
    # be captured.
    ({'clicks': False, 'report_drag': False, 'report_motion': False}, ['1006']),

    # report_drag=True → SGR encoding (1006) + drag tracking (1002)
    ({'report_drag': True}, ['1006', '1002']),
    # report_motion=True → SGR encoding (1006) + motion tracking (1003)
    ({'report_motion': True}, ['1006', '1003']),

    # Precedence test: clicks=True + report_drag=True → drag wins (1002)
    ({'clicks': True, 'report_drag': True}, ['1006', '1002']),
    # Precedence test: clicks=True + report_motion=True → motion wins (1003)
    ({'clicks': True, 'report_motion': True}, ['1006', '1003']),
    # Precedence test: report_drag=True + report_motion=True → motion wins (1003)
    ({'report_drag': True, 'report_motion': True}, ['1006', '1003']),
    # Precedence test: all tracking modes True → motion wins (1003)
    ({'clicks': True, 'report_drag': True, 'report_motion': True}, ['1006', '1003']),

    # With report_pixels: default + pixels → SGR (1006) + clicks (1000) + pixels (1016)
    ({'report_pixels': True}, ['1006', '1000', '1016']),
    # With report_pixels: drag + pixels → SGR (1006) + drag (1002) + pixels (1016)
    ({'report_drag': True, 'report_pixels': True}, ['1006', '1002', '1016']),
    # With report_pixels: motion + pixels → SGR (1006) + motion (1003) + pixels (1016)
    ({'report_motion': True, 'report_pixels': True}, ['1006', '1003', '1016']),
    # With report_pixels: precedence (all True) + pixels
    # → SGR (1006) + motion (1003) + pixels (1016)
    (
        {'clicks': True, 'report_drag': True, 'report_motion': True, 'report_pixels': True},
        ['1006', '1003', '1016']
    ),

    # With report_pixels: no tracking + pixels → SGR (1006) + pixels (1016),
    # again, this is possible, but there isn't any reason to do this -- no mouse
    # events can be captured.
    (
        {'clicks': False, 'report_drag': False, 'report_motion': False, 'report_pixels': True},
        ['1006', '1016']
    ),

])
def test_mouse_enabled_variations(kwargs, expected_modes):
    """Test mouse_enabled with various parameter combinations and precedence."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True
        modes_str = ';'.join(expected_modes)
        # Expected: DECSET (h=enable) on enter, DECRST (l=disable) on exit
        expected_output = f'\x1b[?{modes_str}h\x1b[?{modes_str}l'

        term.get_dec_mode = (
            lambda mode_num, timeout: DecModeResponse(mode_num, DecModeResponse.RESET)
        )

        with term.mouse_enabled(**kwargs):
            pass

        assert stream.getvalue() == expected_output
    child()


def test_does_mouse_default():
    """Test does_mouse with default parameters."""
    @as_subprocess
    def child():
        stream = io.StringIO()
        term = TestTerminal(stream=stream, force_styling=True)
        term._is_a_tty = True

        term.get_dec_mode = lambda mode_num, timeout: DecModeResponse(mode_num, DecModeResponse.SET)

        result = term.does_mouse()
        assert result is True
        assert stream.getvalue() == ''
    child()


def test_flushinp_with_unicode_followed_by_legacy_mouse():
    """Test flushinp() decodes legacy mouse sequences with high bytes after unicode text."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO())
        term._dec_mode_cache = make_enabled_dec_cache()

        # Emoji followed by legacy mouse at coordinates (200, 190)
        # cb=0 (button 0), x=200+1+32=233, y=190+1+32=223 (both >127, need latin1)
        emoji_and_mouse = '😀\x1b[M' + chr(32) + chr(233) + chr(223)
        term.ungetch(emoji_and_mouse)

        with term.cbreak():
            flushed = term.flushinp(timeout=0)
            # Should get emoji + mouse sequence as one string
            assert '😀' in flushed
            assert '\x1b[M' in flushed

            # Now decode and check the mouse event was properly parsed
            term.ungetch(emoji_and_mouse)
            # Read the emoji first
            emoji_ks = term.inkey(timeout=0.1)
            assert emoji_ks == '😀'

            # Then read the mouse event
            mouse_ks = term.inkey(timeout=0.1)
            assert mouse_ks._mode_values is not None
            evt = mouse_ks._mode_values
            assert evt.button_value == 0
            assert evt.x == 200
            assert evt.y == 190
    child()


def test_inkey_with_cjk_followed_by_legacy_mouse():
    """Test inkey() decodes legacy mouse sequences with high bytes after CJK characters."""
    @as_subprocess
    def child():
        term = TestTerminal(stream=io.StringIO())
        term._dec_mode_cache = make_enabled_dec_cache()

        # CJK character '你' followed by legacy mouse at coordinates (150, 145)
        # cb=0 (button 0), x=150+1+32=183, y=145+1+32=178 (both >127, need latin1)
        cjk_and_mouse = '你\x1b[M' + chr(32) + chr(183) + chr(178)
        term.ungetch(cjk_and_mouse)

        with term.cbreak():
            # Read the CJK character first
            cjk_ks = term.inkey(timeout=0.1)
            assert cjk_ks == '你'

            # Then read the mouse event - this is where the bug manifests
            # Without the fix, the high bytes won't be decoded as latin1
            mouse_ks = term.inkey(timeout=0.1)
            assert mouse_ks._mode_values is not None
            evt = mouse_ks._mode_values
            assert evt.button_value == 0
            assert evt.x == 150
            assert evt.y == 145
    child()
