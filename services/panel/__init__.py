"""
智能数据面板产出的工具集合。
"""

from .adapters import (
    AdapterBlockPlan,
    RouteAdapter,
    RouteAdapterResult,
    clear_route_adapters,
    get_route_adapter,
    route_adapter,
    register_route_adapter,
)
from .component_registry import ComponentDefinition, ComponentRegistry
from .data_block_builder import BlockBuildResult, DataBlockBuilder
from .layout_engine import LayoutEngine
from .component_planner import ComponentPlannerConfig, plan_components_for_route
from .panel_generator import PanelBlockInput, PanelGenerator, PanelGenerationResult
from .schema_summary import SchemaSummaryBuilder

__all__ = [
    "AdapterBlockPlan",
    "RouteAdapter",
    "RouteAdapterResult",
    "register_route_adapter",
    "route_adapter",
    "get_route_adapter",
    "clear_route_adapters",
    "ComponentDefinition",
    "ComponentRegistry",
    "BlockBuildResult",
    "DataBlockBuilder",
    "LayoutEngine",
    "PanelBlockInput",
    "PanelGenerator",
    "PanelGenerationResult",
    "ComponentPlannerConfig",
    "plan_components_for_route",
    "SchemaSummaryBuilder",
]
