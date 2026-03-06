#!/usr/bin/env python3
"""Line editor demo with styled input, history, and horizontal scrolling."""
from blessed import Terminal
from blessed.line_editor import LineEditor, LineHistory

term = Terminal()
history = LineHistory()
PROMPT = ">>> "
PROMPT_W = len(PROMPT)


def emit(text):
    """Write text to stdout without newline."""
    print(text, end="", flush=True)


with term.cbreak(), term.hidden_cursor():
    print("Line editor demo. Up/Down=history, Right=accept suggestion, "
          "Ctrl+D=quit.\n")
    while True:
        width = min(term.width - PROMPT_W, 40)
        ed = LineEditor(history=history, max_width=width, limit=200,
                        bg_sgr=term.on_brown)
        emit(PROMPT)
        row = term.get_location()[0]
        emit(ed.render(term, row, width))
        while True:
            key = term.inkey()
            result = ed.feed_key(key)
            if result.bell:
                emit(result.bell)
            if result.changed:
                # try fast-path for common cases, fall back to full redraw
                key_str = str(key)
                out = None
                if key_str and key_str.isprintable() and len(key_str) == 1:
                    out = ed.render_insert(term, row, key_str)
                elif getattr(key, "name", None) == "KEY_BACKSPACE":
                    out = ed.render_backspace(term, row)
                if out is None:
                    out = ed.render(term, row, width)
                emit(out)
            if result.line is not None:
                print()
                if result.line:
                    print(f"  => {result.line!r}")
                break
            if result.eof:
                print()
                raise SystemExit
            if result.interrupt:
                print("^C")
                break
