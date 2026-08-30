"""Sub-module providing mouse event handling."""
# std imports
import re
from typing import Match

BUTTON_LEGACY_UNKNOWN = 3

# shift (4), meta (8), ctrl (16) and motion (32) share the button byte
BUTTON_MODIFIER_MASK = 4 | 8 | 16 | 32


class MouseEvent:  # pylint: disable=too-many-instance-attributes
    """
    Mouse event with button, coordinates, and modifier information.

    A unified mouse event structure that supports both legacy and SGR mouse protocols. Provides a
    dynamic button property that returns human-readable button names like "LEFT", "SCROLL_UP",
    "CTRL_LEFT", etc.

    :ivar int button_value: Raw button number with modifiers stripped (0=left, 1=middle, 2=right,
        3=none, 64=scroll up, 65=scroll down, 66-67 for buttons 6-7, and 128-131 for buttons 8-11).
    :ivar int x: Horizontal position (0-indexed, in cells or pixels depending on mode).
    :ivar int y: Vertical position (0-indexed, in cells or pixels depending on mode).
    :ivar bool released: True if this is a button release event.
    :ivar bool shift: True if Shift modifier is pressed.
    :ivar bool meta: True if Meta/Alt modifier is pressed.
    :ivar bool ctrl: True if Ctrl modifier is pressed.
    :ivar bool is_motion: True if motion is being reported (drag or all- motion mode).
    :ivar bool is_wheel: True if this is a scroll wheel event.
    """

    def __init__(self, button_value: int, x: int, y: int, released: bool,
                 shift: bool, meta: bool, ctrl: bool, is_motion: bool, is_wheel: bool):
        # pylint: disable=too-many-positional-arguments
        """
        Initialize a MouseEvent.

        :param int button_value: Raw button number.
        :param int x: Horizontal position.
        :param int y: Vertical position.
        :param bool released: Whether this is a button release event.
        :param bool shift: Whether Shift modifier is pressed.
        :param bool meta: Whether Meta/Alt modifier is pressed.
        :param bool ctrl: Whether Ctrl modifier is pressed.
        :param bool is_motion: Whether motion is being reported.
        :param bool is_wheel: Whether this is a scroll wheel event.
        """
        self.button_value = button_value
        self.x = x
        self.y = y
        self.released = released
        self.shift = shift
        self.meta = meta
        self.ctrl = ctrl
        self.is_motion = is_motion
        self.is_wheel = is_wheel

    def _get_base_button_name(self) -> str:
        """
        Get base button name without modifiers or state.

        :rtype: str
        :returns: Base button name like "LEFT", "MIDDLE", "RIGHT", or "BUTTON_6".
        """
        if self.button_value < 64:
            return {
                0: "LEFT",
                1: "MIDDLE",
                2: "RIGHT",
            }.get(self.button_value, '')
        # Extended buttons, bit 6 (64) selects buttons 4-7, bit 7 (128) selects buttons 8-11
        first_of_bank = 8 if self.button_value & 128 else 4
        return f"BUTTON_{first_of_bank + (self.button_value & 3)}"

    @property
    def button(self) -> str:
        """
        Return human-readable button name.

        Generates button names that include modifiers, button type, motion/release state:

        - "LEFT", "MIDDLE", "RIGHT" for standard mouse buttons
        - "LEFT_RELEASED", "MIDDLE_RELEASED", "RIGHT_RELEASED" for button releases
        - "RELEASED" for a legacy release, which does not report which button was released
        - "SCROLL_UP", "SCROLL_DOWN" for wheel events
        - "MOTION" for mouse movement with no button pressed
        - "LEFT_MOTION", "MIDDLE_MOTION", "RIGHT_MOTION" for drag events
        - "CTRL_LEFT", "SHIFT_SCROLL_UP", "CTRL_SHIFT_META_MOTION" with modifiers
        - "BUTTON_6" through "BUTTON_11" for extended mouse buttons

        :rtype: str
        :returns: Button name with modifiers, button type, and motion/release state.
        """
        button_name = ''

        # Add modifiers in order: ctrl, shift, meta
        for modifier in ('ctrl', 'shift', 'meta'):
            if getattr(self, modifier):
                button_name += f'{modifier.upper()}_'

        # Handle wheel events first, buttons 4 (64) and 5 (65)
        if self.is_wheel:
            if self.button_value == 64:
                button_name += "SCROLL_UP"
            elif self.button_value == 65:
                button_name += "SCROLL_DOWN"
            # Wheel events don't have motion or release variants in typical usage
            return button_name

        # Handle motion events specially
        if self.is_motion:
            # Motion with no button pressed
            if self.button_value == BUTTON_LEGACY_UNKNOWN:
                button_name += "MOTION"
            else:
                # Dragging with a specific button
                button_name += f"{self._get_base_button_name()}_MOTION"
        elif self.released and self.button_value == BUTTON_LEGACY_UNKNOWN:
            # Legacy protocols (modes 1000, 1002, 1003) do not report which
            # button was released, so it is named without one.
            button_name += "RELEASED"
        else:
            # Regular click or release events
            button_name += self._get_base_button_name()

            # Add release state (only for non-motion events)
            if self.released:
                button_name += "_RELEASED"

        return button_name

    def __repr__(self) -> str:
        """Return succinct representation showing only active attributes."""
        # Always show button_value, x, y
        parts = [f'button_value={self.button_value}', f'x={self.x}', f'y={self.y}']

        # Only show boolean flags when True
        for bool_name in ('released', 'shift', 'meta', 'ctrl', 'is_motion', 'is_wheel'):
            if getattr(self, bool_name):
                parts.append(f'{bool_name}=True')
        return f"MouseEvent({', '.join(parts)})"

    @classmethod
    def from_sgr_match(cls, match: Match[str]) -> 'MouseEvent':
        """
        Parse SGR mouse event from regex match.

        Handles both SGR (mode 1006) and SGR-Pixels (mode 1016) since they
        use identical wire formats: CSI < b;x;y m/M. The difference is semantic:

        - Mode 1006: coordinates represent character cell positions
        - Mode 1016: coordinates represent pixel positions

        Applications must interpret x,y coordinates based on which mode was enabled.

        The protocol sends 1-indexed coordinates (top-left is 1,1), but we convert
        to 0-indexed (top-left is 0,0) to match blessed's terminal movement functions.

        :param Match match: Regex match object with groups 'b', 'x', 'y', 'type'.
        :rtype: MouseEvent
        :returns: Parsed MouseEvent instance.
        """
        b = int(match.group('b'))
        x = int(match.group('x')) - 1  # Convert from 1-indexed to 0-indexed
        y = int(match.group('y')) - 1  # Convert from 1-indexed to 0-indexed
        event_type = match.group('type')

        released = event_type == 'm'

        # Extract modifiers from button code
        shift = bool(b & 4)
        meta = bool(b & 8)
        ctrl = bool(b & 16)

        # Extract motion/drag flags
        is_motion = bool(b & 32)

        # Strip modifiers to get the button, 0-2 for left/middle/right, 3 for none, and
        # 64-67 or 128-131 for the extended buttons 4-7 and 8-11
        button = b & ~BUTTON_MODIFIER_MASK
        is_wheel = button in {64, 65}  # buttons 4 and 5 are wheel up/down

        return cls(
            button_value=button,
            x=x,
            y=y,
            released=released,
            shift=shift,
            meta=meta,
            ctrl=ctrl,
            is_motion=is_motion,
            is_wheel=is_wheel
        )

    @classmethod
    def from_legacy_match(cls, match: Match[str]) -> 'MouseEvent':
        """
        Parse legacy mouse event (X10/1000/1002/1003) from regex match.

        The protocol sends 1-indexed coordinates (top-left is 1,1), but we convert to 0-indexed
        (top-left is 0,0) to match blessed's terminal movement functions.

        Each coordinate is transmitted as a single byte of ``value + 32``, so no position beyond
        223 can be expressed.  Windows Terminal and the console host (``conhost.exe``) share a VT
        input layer that *discards* any legacy mouse event where either coordinate exceeds 95,
        rather than transmit a byte above 127.  Both are limitations of the terminal without
        workaround, the SGR protocol is the only remedy.

        :param Match match: Regex match object with groups 'cb', 'cx', 'cy'.
        :rtype: MouseEvent
        :returns: Parsed MouseEvent instance.
        """
        cb = ord(match.group('cb')) - 32
        cx = ord(match.group('cx')) - 32 - 1  # Convert from 1-indexed to 0-indexed
        cy = ord(match.group('cy')) - 32 - 1  # Convert from 1-indexed to 0-indexed

        # Extract motion/drag flags
        is_motion = bool(cb & 32)

        # Strip modifiers to get the button, matching the SGR decoder
        button = cb & ~BUTTON_MODIFIER_MASK
        is_wheel = button in {64, 65}  # buttons 4 and 5 are wheel up/down
        # A low-bits value of 3 means "no button". When stationary this is a
        # button release; with the motion bit set (mode 1003 all-motion
        # tracking) it is a no-button motion event, which must keep button_value
        # 3 so it reports as "MOTION" rather than "LEFT_MOTION", matching the
        # SGR decoder.
        released = button == BUTTON_LEGACY_UNKNOWN and not is_motion

        # Extract modifier flags
        shift = bool(cb & 4)
        meta = bool(cb & 8)
        ctrl = bool(cb & 16)

        return cls(
            button_value=button,
            x=cx,
            y=cy,
            released=released,
            shift=shift,
            meta=meta,
            ctrl=ctrl,
            is_motion=is_motion,
            is_wheel=is_wheel
        )


# Backwards compatibility aliases
MouseSGREvent = MouseEvent
MouseLegacyEvent = MouseEvent


# Mouse event patterns (shared across multiple DEC modes)
# SGR mouse format (modes 1006 and 1016): ESC [ < b ; x ; y M/m
# The optional '<' allows backward compatibility with non-standard implementations
RE_PATTERN_MOUSE_SGR = re.compile(r'\x1b\[<?(?P<b>\d+);(?P<x>\d+);(?P<y>\d+)(?P<type>[mM])')
# Legacy mouse format (modes 1000, 1002, 1003): ESC [ M cb cx cy
RE_PATTERN_MOUSE_LEGACY = re.compile(r'\x1b\[M(?P<cb>.)(?P<cx>.)(?P<cy>.)')


__all__ = ('MouseEvent', 'MouseSGREvent', 'MouseLegacyEvent',
           'RE_PATTERN_MOUSE_SGR', 'RE_PATTERN_MOUSE_LEGACY',
           'BUTTON_LEGACY_UNKNOWN', 'BUTTON_MODIFIER_MASK')
