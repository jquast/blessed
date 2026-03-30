#!/usr/bin/env python3
"""Line editor demo with clipboard, bracketed paste, history, and scrolling."""
from functools import partial

from blessed import Terminal
from blessed.line_editor import LineEditor, LineHistory, LineEditResult

term = Terminal()
history = LineHistory()
echo = partial(print, end='\r\n', flush=True)

has_clipboard = term.does_osc52_clipboard()


def copy_line(ed):
    term.clipboard_copy(ed.line)
    return LineEditResult()


def paste_line(ed):
    text = term.clipboard_paste()
    return ed.insert_text(text) if text else LineEditResult()


with term.raw(), term.cursor_shape(term.CursorShape.BLINKING_BLOCK), term.bracketed_paste():
    if has_clipboard:
        echo("press ^C and ^V for OS clipboard, type 'quit' to exit")
    else:
        echo("type 'quit' to exit")
    echo()
    while True:
        margin = max(1, term.width // 5)
        width = term.width - margin * 2
        prompt = "Prompt> "
        col = margin
        ed_width = width - len(prompt)
        keymap = {}
        if has_clipboard:
            keymap['KEY_CTRL_C'] = copy_line
            keymap['KEY_CTRL_V'] = paste_line
        ed = LineEditor(history=history, max_width=ed_width, limit=200,
                        bg_sgr=term.on_brown,
                        keymap=keymap or None)
        echo(term.move_x(col) + prompt, end='')
        row = term.get_location()[0]
        ed_col = col + len(prompt)
        echo(ed.render(term, row, ed_width, col=ed_col), end='')
        while True:
            key = term.inkey()
            if key.name == 'BRACKETED_PASTE':
                result = ed.insert_text(key.text)
            else:
                result = ed.feed_key(key)
            if result.bell:
                echo(result.bell, end='')
            if result.changed:
                key_str = str(key)
                out = None
                if key_str and key_str.isprintable() and len(key_str) == 1:
                    out = ed.render_insert(term, row, key_str)
                elif getattr(key, "name", None) == "KEY_BACKSPACE":
                    out = ed.render_backspace(term, row)
                if out is None:
                    out = ed.render(term, row, ed_width, col=ed_col)
                echo(out, end='')
            if result.line is not None:
                echo()
                if result.line:
                    echo(term.move_x(col) + f"  => {result.line!r}")
                break
        if (result.line or '').strip() == 'quit':
            break
