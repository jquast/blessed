#!/usr/bin/env python
"""
This is an example application for the 'blessed' Terminal library for python.

It is also an experiment in functional programming.
"""

from __future__ import division, print_function
from collections import namedtuple
from functools import partial
from random import randrange

from blessed import Terminal


# python 2/3 compatibility, provide 'echo' function as an
# alias for "print without newline and flush"
try:
    # pylint: disable=invalid-name
    #         Invalid constant name "echo"
    echo = partial(print, end='', flush=True)
    echo(u'')
except TypeError:
    # TypeError: 'flush' is an invalid keyword argument for this function
    import sys

    def echo(text):
        """python 2 version of print(end='', flush=True)."""
        sys.stdout.write(u'{0}'.format(text))
        sys.stdout.flush()

# a worm is a list of (y, x) segments Locations
Location = namedtuple('Point', ('y', 'x',))

# a nibble is a (x,y) Location and value
Nibble = namedtuple('Nibble', ('location', 'value'))

# A direction is a bearing, fe.
# y=0, x=-1 = move right
# y=1, x=0 = move down
Direction = namedtuple('Direction', ('y', 'x',))

# these functions return a new Location instance, given
# the direction indicated by their name.
LEFT = (0, -1)
RIGHT = (0, 1)
UP = (-1, 0)
DOWN = (1, 0)

def left_of(segment, term):
    """Return Location left-of given segment."""
    # pylint: disable=unused-argument
    #         Unused argument 'term'
    return Location(y=segment.y,
                    x=max(0, segment.x - 1))

def right_of(segment, term):
    """Return Location right-of given segment."""
    return Location(y=segment.y,
                    x=min(term.width - 1, segment.x + 1))

def above(segment, term):
    """Return Location above given segment."""
    # pylint: disable=unused-argument
    #         Unused argument 'term'
    return Location(
        y=max(0, segment.y - 1),
        x=segment.x)

def below(segment, term):
    """Return Location below given segment."""
    return Location(
        y=min(term.height - 1, segment.y + 1),
        x=segment.x)

def next_bearing(term, inp_code, bearing):
    """
    Return direction function for new bearing by inp_code.

    If no inp_code matches a bearing direction, return
    a function for the current bearing.
    """
    return {
        term.KEY_LEFT: left_of,
        term.KEY_RIGHT: right_of,
        term.KEY_UP: above,
        term.KEY_DOWN: below,
    }.get(inp_code,
          # direction function given the current bearing
          {LEFT: left_of,
           RIGHT: right_of,
           UP: above,
           DOWN: below}[(bearing.y, bearing.x)])


def change_bearing(f_mov, segment, term):
    """Return new bearing given the movement f(x)."""
    return Direction(
        f_mov(segment, term).y - segment.y,
        f_mov(segment, term).x - segment.x)

def bearing_flipped(dir1, dir2):
    """
    direction-flipped check.

    Return true if dir2 travels in opposite direction of dir1.
    """
    return (0, 0) == (dir1.y + dir2.y, dir1.x + dir2.x)

def hit_any(loc, segments):
    """Return True if `loc' matches any (y, x) coordinates within segments."""
    # `segments' -- a list composing a worm.
    return loc in segments

def hit_vany(locations, segments):
    """Return True if any locations are found within any segments."""
    return any(hit_any(loc, segments)
               for loc in locations)

def hit(src, dst):
    """Return True if segments are same position (hit detection)."""
    return src.x == dst.x and src.y == dst.y

def next_wormlength(nibble, head, worm_length):
    """Return new worm_length if current nibble is hit."""
    if hit(head, nibble.location):
        return worm_length + nibble.value
    return worm_length

def next_speed(nibble, head, speed, modifier):
    """Return new speed if current nibble is hit."""
    if hit(head, nibble.location):
        return speed * modifier
    return speed

def head_glyph(direction):
    """Return character for worm head depending on horiz/vert orientation."""
    if direction in (left_of, right_of):
        return u':'
    return u'"'


def next_nibble(term, nibble, head, worm):
    """
    Provide the next nibble.

    continuously generate a random new nibble so long as the current nibble
    hits any location of the worm.  Otherwise, return a nibble of the same
    location and value as provided.
    """
    loc, val = nibble.location, nibble.value
    while hit_vany([head] + worm, nibble_locations(loc, val)):
        loc = Location(x=randrange(1, term.width - 1),
                     y=randrange(1, term.height - 1))
        val = nibble.value + 1
    return Nibble(loc, val)


def nibble_locations(nibble_location, nibble_value):
    """Return array of locations for the current "nibble"."""
    # generate an array of locations for the current nibble's location
    # -- a digit such as '123' may be hit at 3 different (y, x) coordinates.
    return [Location(x=nibble_location.x + offset,
                     y=nibble_location.y)
            for offset in range(0, 1 + len('{}'.format(nibble_value)) - 1)]


def main():
    """Program entry point."""
    # pylint: disable=too-many-locals
    #         Too many local variables (20/15)
    term = Terminal()
    worm = [Location(x=term.width // 2, y=term.height // 2)]
    worm_length = 2
    bearing = Direction(*LEFT)
    direction = left_of
    nibble = Nibble(location=worm[0], value=0)
    color_nibble = term.black_on_green
    color_worm = term.yellow_reverse
    color_head = term.red_reverse
    color_bg = term.on_blue
    echo(term.move(1, 1))
    echo(color_bg(term.clear))

    # speed is actually a measure of time; the shorter, the faster.
    speed = 0.1
    modifier = 0.93
    inp = None

    echo(term.move(term.height, 0))
    with term.hidden_cursor(), term.cbreak(), term.location():
        while inp not in (u'q', u'Q'):

            # delete the tail of the worm at worm_length
            if len(worm) > worm_length:
                echo(term.move(*worm.pop(0)))
                echo(color_bg(u' '))

            # compute head location
            head = worm.pop()

            # check for hit against self; hitting a wall results in the (y, x)
            # location being clipped, -- and death by hitting self (not wall).
            if hit_any(head, worm):
                break

            # get the next nibble, which may be equal to ours unless this
            # nibble has been struck by any portion of our worm body.
            n_nibble = next_nibble(term, nibble, head, worm)

            # get the next worm_length and speed, unless unchanged.
            worm_length = next_wormlength(nibble, head, worm_length)
            speed = next_speed(nibble, head, speed, modifier)

            if n_nibble != nibble:
                # erase the old one, careful to redraw the nibble contents
                # with a worm color for those portions that overlay.
                for (yloc, xloc) in nibble_locations(*nibble):
                    echo(u''.join((
                        term.move(yloc, xloc),
                        (color_worm if (yloc, xloc) == head
                         else color_bg)(u' '),
                        term.normal)))
                # and draw the new,
                echo(term.move(*n_nibble.location) + (
                    color_nibble('{}'.format(n_nibble.value))))

            # display new worm head
            echo(term.move(*head) + color_head(head_glyph(direction)))

            # and its old head (now, a body piece)
            if worm:
                echo(term.move(*(worm[-1])))
                echo(color_worm(u' '))
            echo(term.move(*head))

            # wait for keyboard input, which may indicate
            # a new direction (up/down/left/right)
            inp = term.inkey(timeout=speed)

            # discover new direction, given keyboard input and/or bearing.
            nxt_direction = next_bearing(term, inp.code, bearing)

            # discover new bearing, given new direction compared to prev
            nxt_bearing = change_bearing(nxt_direction, head, term)

            # disallow new bearing/direction when flipped: running into
            # oneself, for example traveling left while traveling right.
            if not bearing_flipped(bearing, nxt_bearing):
                direction = nxt_direction
                bearing = nxt_bearing

            # append the prior `head' onto the worm, then
            # a new `head' for the given direction.
            worm.extend([head, direction(head, term)])

            # re-assign new nibble,
            nibble = n_nibble

    echo(term.normal)
    score = (worm_length - 1) * 100
    echo(u''.join((term.move(term.height - 1, 1), term.normal)))
    echo(u''.join((u'\r\n', u'score: {}'.format(score), u'\r\n')))

if __name__ == '__main__':
    main()
