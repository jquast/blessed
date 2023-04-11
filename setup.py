#!/usr/bin/env python
"""Distutils setup script."""
# std imports
import os

# 3rd party
import setuptools


def _get_install_requires(fname):
    return [req_line.strip() for req_line in open(fname)
            if req_line.strip() and not req_line.startswith('#')]


def _get_version(fname):
    import json
    return json.load(open(fname, 'r'))['version']


def _get_long_description(fname):
    import codecs
    return codecs.open(fname, 'r', 'utf8').read()


HERE = os.path.dirname(__file__)

setuptools.setup(
    name='blessed',
    version=_get_version(
        fname=os.path.join(HERE, 'version.json')),
    python_requires=">=2.7",
    install_requires=_get_install_requires(
        fname=os.path.join(HERE, 'requirements.txt')),
    long_description=_get_long_description(
        fname=os.path.join(HERE, 'docs', 'intro.rst')),
    description=('Easy, practical library for making terminal apps, by providing an elegant, '
                 'well-documented interface to Colors, Keyboard input, and screen Positioning '
                 'capabilities.'),
    author='Jeff Quast, Erik Rose, Avram Lubkin',
    author_email='contact@jeffquast.com',
    license='MIT',
    packages=['blessed', ],
    package_data={
        'blessed': [
            'py.typed',
            '_capabilities.pyi',
            'color.pyi',
            'colorspace.pyi',
            'formatters.pyi',
            'keyboard.pyi',
            'sequences.pyi',
            'terminal.pyi',
            'win_terminal.pyi',
        ],
    },
    url='https://github.com/jquast/blessed',
    project_urls={'Documentation': 'https://blessed.readthedocs.io'},
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: Console :: Curses',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: User Interfaces',
        'Topic :: Terminals',
        'Typing :: Typed',
    ],
    keywords=['terminal', 'sequences', 'tty', 'curses', 'ncurses',
              'formatting', 'style', 'color', 'console', 'keyboard',
              'ansi', 'xterm'],
)
