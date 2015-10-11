#!/usr/bin/env python
"""
Problem: A screen drawing application wants to detect whether the connecting
terminal client is capable of rendering utf8 bytes.  Some transports, such
as a serial link, often cannot forward their ``LANG`` environment preference.

We can interactively determine whether the connecting terminal emulator is
rendering in utf8 by making an inquiry of their terminal cursor position:

    - request cursor position (p0)
    - display a long utf8 byte that renders as one cell
    - request cursor position (p1)

If the horizontal distance of (p0, p1) is 1 cell, we know the connecting
client is most certainly matching our intended encoding.

One could detect a great variety of encodings, see for example:
https://github.com/jquast/blessed/blob/master/docs/_static/soulburner-ru-family-encodings.jpg

  - Request cursor location using :meth:`~.get_location` and store response.
  - Emit a multibyte UTF-8 character, such as ⦰ (``\x29\xb0``).
  - Request cursor location using :meth:`~.get_location` and store response.
  - Determine the difference of the *(y, x)* location of the response.

    If the horizontal distance is *1*, then the client decoded the two UTF-8
    bytes as a single character, and can be considered capable.

    If it is *2*, the client is using a `code page`_ and is incapable of
    decoding a UTF-8 bytestream
"""
