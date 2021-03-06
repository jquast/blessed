#!/usr/bin/env python3
# std imports
import os
import re
import json


def main():
    # I don't know why, we maintain __version__ in blessed, because that's
    # how it was done a long time ago before pip, anyway we do basic
    # code generation, version.json -> __init__.py
    fpath_json = os.path.join(os.path.dirname(__file__), 'version.json')
    version = json.load(open(fpath_json, 'r'))['version']
    fpath_py = os.path.join(os.path.dirname(__file__), 'blessed', '__init__.py')
    prev_text = open(fpath_py, 'r').read()
    next_text = re.sub(r"(__version__ = )(.*)$", r'\1"{0}"'.format(version),
                       prev_text, flags=re.MULTILINE)
    if prev_text != next_text:
        print('Updating blessed.__version__ to {}'.format(version))
        open(fpath_py, 'w').write(next_text)


if __name__ == '__main__':
    main()
