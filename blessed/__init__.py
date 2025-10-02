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
from blessed.dec_modes import DecPrivateMode

__all__ = ('Terminal', 'DecPrivateMode')
__version__ = "1.22.0"
