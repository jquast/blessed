"""Type hint for terminal capability builder patterns"""

# std imports
from typing import Any, Dict, Tuple, OrderedDict

CAPABILITY_DATABASE: OrderedDict[str, Tuple[str, Dict[str, Any]]]
CAPABILITIES_RAW_MIXIN: Dict[str, str]
CAPABILITIES_ADDITIVES: Dict[str, Tuple[str, str]]
CAPABILITIES_HORIZONTAL_DISTANCE: Dict[str, int]
CAPABILITIES_CAUSE_MOVEMENT: Tuple[str, ...]
