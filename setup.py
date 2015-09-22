#!/usr/bin/env python
import sys
from os.path import dirname, join

import setuptools
import setuptools.command.develop
import setuptools.command.test

kwargs = {
    'install_requires': [
        'wcwidth>=0.1.4',
        'six>=1.9.0',
    ]
}

if sys.version_info < (2, 7):
    # we make use of collections.ordereddict: for python 2.6 we require the
    # assistance of the 'orderddict' module which backports the same.
    kwargs['install_requires'].extend(['ordereddict>=1.1'])

setuptools.setup(
    name='blessed',
    version='1.7',
    description=('A thin, practical wrapper around terminal coloring, '
                 'styling, positioning, and keyboard input.'),
    long_description=open(join(dirname(__file__),
                               'docs', 'intro.rst')).read(),
    author='Erik Rose, Jeff Quast',
    author_email='erikrose@grinchcentral.com',
    license='MIT',
    packages=['blessed', 'blessed.tests'],
    url='https://github.com/erikrose/blessed',
    include_package_data=True,
    test_suite='blessed.tests',
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
    **kwargs
)
