# std imports
from typing import Dict, Tuple, Callable

_RGB = Tuple[int, int, int]

def rgb_to_xyz(red: int, green: int, blue: int) -> Tuple[float, float, float]: ...
def xyz_to_lab(
    x_val: float, y_val: float, z_val: float
) -> Tuple[float, float, float]: ...
def rgb_to_lab(red: int, green: int, blue: int) -> Tuple[float, float, float]: ...
def dist_rgb(rgb1: _RGB, rgb2: _RGB) -> float: ...
def dist_rgb_weighted(rgb1: _RGB, rgb2: _RGB) -> float: ...
def dist_cie76(rgb1: _RGB, rgb2: _RGB) -> float: ...
def dist_cie94(rgb1: _RGB, rgb2: _RGB) -> float: ...
def dist_cie2000(rgb1: _RGB, rgb2: _RGB) -> float: ...

COLOR_DISTANCE_ALGORITHMS: Dict[str, Callable[[_RGB, _RGB], float]]