"""
A thin, practical wrapper around terminal capabilities in Python.

http://pypi.python.org/pypi/blessed
"""
# std imports
import platform as _platform

# isort: off
if _platform.system() == 'Windows':
    from blessed.win_terminal import Terminal
else:
    from blessed.terminal import Terminal  # type: ignore

__all__ = ('Terminal',)
__version__ = "1.25.0"
