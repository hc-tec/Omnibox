from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from api.schemas.panel import ComponentInteraction, LayoutHint, SourceInfo


@dataclass
class AdapterBlockPlan:
    component_id: str
    props: Dict[str, Any]
    options: Dict[str, Any] = field(default_factory=dict)
    interactions: List[ComponentInteraction] = field(default_factory=list)
    title: Optional[str] = None
    layout_hint: Optional[LayoutHint] = None
    confidence: float = 0.6


@dataclass
class RouteAdapterResult:
    records: List[Dict[str, Any]]
    block_plans: List[AdapterBlockPlan] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


RouteAdapter = Callable[[SourceInfo, Sequence[Dict[str, Any]]], RouteAdapterResult]


def _default_adapter(_: SourceInfo, records: Sequence[Dict[str, Any]]) -> RouteAdapterResult:
    return RouteAdapterResult(records=list(records))


class RouteAdapterRegistry:
    def __init__(self):
        self._routes: List[tuple[str, RouteAdapter]] = []

    def register(self, route: str, adapter: RouteAdapter) -> None:
        normalized = self._normalize(route)
        for idx, (existing_route, _) in enumerate(self._routes):
            if existing_route == normalized:
                self._routes[idx] = (normalized, adapter)
                break
        else:
            self._routes.append((normalized, adapter))
            self._routes.sort(key=lambda item: len(item[0]), reverse=True)

    def get(self, route: str) -> RouteAdapter:
        if not route:
            return _default_adapter

        target = self._normalize(route)
        for registered, adapter in self._routes:
            if target == registered:
                return adapter
            if self._is_prefix_match(target, registered):
                return adapter
        return _default_adapter

    def clear(self) -> None:
        self._routes.clear()

    @staticmethod
    def _normalize(route: str) -> str:
        route = (route or "").strip()
        if not route.startswith("/"):
            route = f"/{route}"
        if route != "/" and route.endswith("/"):
            return route.rstrip("/")
        return route or "/"

    @staticmethod
    def _is_prefix_match(target: str, registered: str) -> bool:
        if not registered:
            return False
        if target.startswith(registered):
            remainder = target[len(registered) :]
            if not remainder:
                return True
            if registered.endswith("/"):
                return True
            return remainder.startswith("/")
        return False


_registry = RouteAdapterRegistry()


def register_route_adapter(route: str, adapter: RouteAdapter) -> None:
    _registry.register(route, adapter)


def get_route_adapter(route: str) -> RouteAdapter:
    return _registry.get(route)


def clear_route_adapters() -> None:
    _registry.clear()


def route_adapter(*routes: str) -> Callable[[RouteAdapter], RouteAdapter]:
    if not routes:
        raise ValueError("At least one route must be provided for registration.")

    def decorator(func: RouteAdapter) -> RouteAdapter:
        for route in routes:
            register_route_adapter(route, func)
        return func

    return decorator
