"""
Route adapter package.
"""

from .registry import (
    AdapterBlockPlan,
    AdapterExecutionContext,
    ComponentManifestEntry,
    RouteAdapter,
    RouteAdapterManifest,
    RouteAdapterResult,
    clear_route_adapters,
    get_route_adapter,
    get_route_manifest,
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
    "AdapterExecutionContext",
    "ComponentManifestEntry",
    "RouteAdapter",
    "RouteAdapterManifest",
    "RouteAdapterResult",
    "register_route_adapter",
    "route_adapter",
    "get_route_adapter",
    "get_route_manifest",
    "clear_route_adapters",
]
