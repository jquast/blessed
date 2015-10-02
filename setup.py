#!/usr/bin/env python
"""Distutils setup script."""
import os
import setuptools


def _get_install_requires(fname):
    import sys
    result = [req_line.strip() for req_line in open(fname)
              if req_line.strip() and not req_line.startswith('#')]

    # support python2.6 by using backport of 'orderedict'
    if sys.version_info < (2, 7):
        result.append('ordereddict==1.1')

    return result


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
    install_requires=_get_install_requires(
        fname=os.path.join(HERE, 'requirements.txt')),
    long_description='{0}\n\n{1}'.format(
        _get_long_description(os.path.join(HERE, 'docs', 'intro.rst')),
        _get_long_description(os.path.join(HERE, 'docs', 'history.rst')),
    ),
    description=('A thin, practical wrapper around terminal styling, '
                 'screen positioning, and keyboard input.'),
    author='Jeff Quast, Erik Rose',
    author_email='contact@jeffquast.com',
    license='MIT',
    packages=['blessed', 'blessed.tests'],
    url='https://github.com/erikrose/blessed',
    include_package_data=True,
    zip_safe=True,
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: Console :: Curses',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: User Interfaces',
        'Topic :: Terminals'
    ],
    keywords=['terminal', 'sequences', 'tty', 'curses', 'ncurses',
              'formatting', 'style', 'color', 'console', 'keyboard',
              'ansi', 'xterm'],
)
