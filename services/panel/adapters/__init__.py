"""
Route adapter package.
"""

from .registry import (
    AdapterBlockPlan,
    RouteAdapter,
    RouteAdapterResult,
    clear_route_adapters,
    get_route_adapter,
    register_route_adapter,
    route_adapter,
)

# Ensure adapters are registered on import.
from . import hupu  # noqa: F401
from . import bilibili  # noqa: F401
from . import github  # noqa: F401
from . import generic  # noqa: F401

__all__ = [
    "AdapterBlockPlan",
    "RouteAdapter",
    "RouteAdapterResult",
    "register_route_adapter",
    "route_adapter",
    "get_route_adapter",
    "clear_route_adapters",
]
