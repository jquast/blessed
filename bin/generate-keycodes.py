# generate keycodes for the tables in docs/keyboard.rst
# std imports
import os

# local
from blessed.keyboard import DEFAULT_SEQUENCE_MIXIN, CURSES_KEYCODE_OVERRIDE_MIXIN


def is_override(key_attr_name, code):
    return (code in [val for name, val in CURSES_KEYCODE_OVERRIDE_MIXIN] and
            key_attr_name not in [name for name, val in CURSES_KEYCODE_OVERRIDE_MIXIN])


def main():
    from blessed import Terminal
    term = Terminal()
    csv_header = """
.. csv-table:: All Terminal class attribute Keyboard codes, by name
   :delim: |
   :header: "Name"| "Value"| "Example Sequence(s)"

"""
    fname = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, 'docs', 'all_the_keys.txt'))
    with open(fname, 'w') as fout:
        print(f"write: {fout.name}")
        fout.write(csv_header)
        for key_attr_name in sorted([
                attr for attr in dir(term) if attr.startswith('KEY_')
        ]):
            # filter away F23-F63 (lol)
            if key_attr_name.startswith('KEY_F'):
                maybe_digit = key_attr_name[len('KEY_F'):]
                if maybe_digit.isdigit() and int(maybe_digit) > 23:
                    continue
            code = getattr(term, key_attr_name)
            repr_sequences = [repr(seq) for (seq, value) in DEFAULT_SEQUENCE_MIXIN if value == code]
            txt_sequences = ', '.join(repr_sequences).replace('\\', '\\\\')
            fout.write(f'    {key_attr_name} | {code}')
            if txt_sequences:
                fout.write(f'| {txt_sequences}')
            fout.write('\n')


if __name__ == '__main__':
    main()
