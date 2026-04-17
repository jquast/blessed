#!/usr/bin/env python
# Shis script demonstrates that many possible Cursor Position Report
# sequences are in conflict with vt220 function key F3, eg:
#
# KEY_F3 : ['\x1b[1;1R', '\x1b[1;65R']
# KEY_SHIFT_F3 : ['\x1b[1;2R', '\x1b[1;66R']
# KEY_ALT_F3 : ['\x1b[1;3R', '\x1b[1;67R']
#
# From infocmp:
#
#        kf15= '\E[1;2R'.
#        kf27= '\E[1;5R'.
#        kf39= '\E[1;6R'.
#        kf51= '\E[1;3R'.
#        kf63= '\E[1;4R'.
#
# This F3 with modifier input is a bit unique, rarely but sometimes still used by terminal
# emulators that are "vt220" derived, which they all try to be at heart, we call this
# "Legacy CSI modifier sequence", CSI_FINAL_CHAR_TO_KEYCODE in blessed/keyboard.py.
#
# http://xahlee.info/kbd/vt220_terminal.html
#
# These have a special encoding partly because they were special and local to the vt220,
# "Hold Screen" (F1), Print Screen (F2), Setup(F3), and Break (F5).
#
# As written about DEFAULT_SEQUENCE_MIXIN in blessed/keybaord.py, blessed takes an approach of
# capturing most any kind of keyboard input sequence no matter current TERM type, because many
# terminals emit sequences not described in their terminfo entries, we take a "catch all" approach.
# 
# And so, we must chose between being able to capture coordinates in the KEY_CPR_RESPONSE,
# or, leave it undescribed and allow 
# 
# it's quite a mess!
# Very few terminals are emit them, mainly because the
# PF1-PF4 keys on the vt220 perfor, I think F3 is "Setup" key
# KEY_CPR_RESPONSE is ambigious and in conflict with false key
# detection of F3 key on the first row
import blessed
import blessed.keyboard

term = blessed.Terminal()


class CaptureResponses:
    def __init__(self):
        self.key_names = dict()
        self.key_seqs = dict()

    def capture(self, inp):
        # track unique count of KEY_BY_NAME matches
        self.key_names[inp.name] = self.key_names.get(inp.name, 0) + 1
        # track itemized list of sequences matching it
        self.key_seqs[inp.name] = self.key_seqs.get(inp.name, []) + [str(inp)]

    def display(self):
        for key in sorted(self.key_names.keys(), key=lambda k: self.key_names[k], reverse=True):
            count = self.key_names[key]
            seqs = self.key_seqs[key]
            txt_seqs = f'{seqs[:10]}..' if len(seqs) > 10 else seqs
            print(count, key, ':', txt_seqs)
        ys, xs = [], []
        for key in self.key_seqs:
            for seq in self.key_seqs[key]:
                print(repr(blessed.keyboard._match_cpr_response(seq)))

with term.cbreak():
    cap = CaptureResponses()
    cpr = term.u7 or '\x1b[6n'
    for y in range(0, term.height):
        for x in range(0, term.width):
            print(term.move_yx(y, x) + cpr, end='', flush=True)
            cap.capture(term.inkey(timeout=1))
    cap.display()
