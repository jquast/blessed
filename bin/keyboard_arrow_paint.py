#!/usr/bin/env python3
from blessed import Terminal

header_msg = "Press arrow keys (or 'q' to quit): "
term = Terminal()
position = [term.height // 2, term.width // 2]
with term.cbreak(), term.fullscreen(), term.hidden_cursor():
    print(term.home + header_msg + term.clear_eos)

    while True:
        # show arrow-controlled block
        print(term.move_yx(*position) + '█', end='', flush=True)

        # get key,
        key = term.inkey()

        # take action,
        if key == 'q':
            break
        if key.name == 'KEY_UP':
            position[0] = max(0, position[0] - 1)
        elif key.name == 'KEY_LEFT':
            position[1] = max(0, position[1] - 1)
        elif key.name == 'KEY_DOWN':
            position[0] = min(term.height, position[0] + 1)
        elif key.name == 'KEY_RIGHT':
            position[1] = min(term.width, position[1] + 1)
