#!/usr/bin/env python3
import json
import sys
import os

json_version = os.path.join(
    os.path.dirname(__file__), os.path.pardir, 'version.json')

init_file = os.path.join(
    os.path.dirname(__file__), os.path.pardir, 'blessed', '__init__.py')

def main(bump_arg):
    assert bump_arg in ('--minor', '--major', '--release'), bump_arg

    with open(json_version, 'r') as fin:
        data = json.load(fin)

    release, major, minor = map(int, data['version'].split('.'))
    release = release + 1 if bump_arg == '--release' else release
    major = major + 1 if bump_arg == '--major' else major
    minor = minor + 1 if bump_arg == '--minor' else minor
    new_version = '.'.join(map(str, [release, major, minor]))
    new_data = {'version': new_version}

    with open(json_version, 'w') as fout:
        json.dump(new_data, fout)

    with open(init_file, 'r') as fin:
        file_contents = fin.readlines()

    new_contents = []
    for line in file_contents:
        if line.startswith('__version__ = '):
            line = '__version__ = {!r}\n'.format(new_version)
        new_contents.append(line)

    with open(init_file, 'w') as fout:
        fout.writelines(new_contents)

if __name__ == '__main__':
    main(sys.argv[1])
