#!/usr/bin/env python
"""
This script interactively demonstrates the many possible Cursor Position Report sequences that are
in conflict with vt220 function key F3, eg:

    KEY_F3 : ['\x1b[1;1R', '\x1b[1;65R']
    KEY_SHIFT_F3 : ['\x1b[1;2R', '\x1b[1;66R']
    KEY_ALT_F3 : ['\x1b[1;3R', '\x1b[1;67R']

The "F3 with modifier" is a bit rare but possible for anything "vt220"-derived, blessed
labels it under "Legacy CSI modifier", CSI_FINAL_CHAR_TO_KEYCODE in blessed/keyboard.py,

See vt220 keyboard, http://xahlee.info/kbd/vt220_terminal.html

"Hold Screen" (F1), Print Screen (F2), Setup(F3), and Break (F5) are special keys along with UP,
DOWN, HOME, END, and CENTER/BEGIN. Older programs and emulators may still sometimes use this form,
it's partly why the first few function keys are encoded in so many different forms.

This program runs in two passes, first, using default argument of ``capture_cpr=False`` for
call to inkey(), then in second pass with ``capture_cpr=True``. In the first case, many "false
matches" of KEY_modifier_F3 is matched, and in the second case, only coordinates.
"""
import blessed
import blessed.keyboard

term = blessed.Terminal()


class CaptureResponses:
    def __init__(self):
        self.key_names = dict()
        self.coords = dict()
        self.key_seqs = dict()

    def capture(self, inp):
        # track count of KEY_BY_NAME
        self.key_names[inp.name] = self.key_names.get(inp.name, 0) + 1
        # track count of sequences
        self.key_seqs[inp.name] = self.key_seqs.get(inp.name, []) + [str(inp)]
        # track count of coordinates
        self.coords[inp.cpr_yx] = self.coords.get(inp.cpr_yx, 0) + 1

    def display(self):
        # display unique list of key_names
        for key in sorted(self.key_names.keys(), key=lambda k: self.key_names[k], reverse=True):
            count = self.key_names[key]
            seqs = self.key_seqs[key]
            txt_seqs = f'{seqs[:6]}…' if len(seqs) > 6 else seqs
            print(f'{count}x {key}: {txt_seqs}')
        # and, a unique list of coordinates
        for coord, count in sorted(self.coords.items(), key=lambda kv: kv[1]):
            if count != 1:
                print(count, ':', coord)


def heading(msg):
    print()
    print(msg)
    print('=' * len(msg))


def main():
    cpr = term.u7 or '\x1b[6n'
    with term.cbreak():
        heading("Testing CPR_RESPONSE vs. Ambiguous vt220")
        cap = CaptureResponses()
        for y in range(0, term.height):
            for x in range(0, term.width):
                print(term.move_yx(y, x) + cpr, end='', flush=True)
                cap.capture(term.inkey(timeout=1))
        cap.display()

        heading("Testing CPR_RESPONSE with capture_cpr=True")
        cap = CaptureResponses()
        for y in range(0, term.height):
            for x in range(0, term.width):
                print(term.move_yx(y, x) + cpr, end='', flush=True)
                cap.capture(term.inkey(timeout=1, capture_cpr=True))
        cap.display()

        # verify number transmitted to coordinates received
        assert len(cap.coords) == term.height * term.width
        # verify all coordinate numbers received are unique
        assert len(cap.coords.keys()) == len(set(cap.coords.keys()))


if __name__ == '__main__':
    main()
