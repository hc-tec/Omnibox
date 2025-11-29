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
from .component_planner import (
    ComponentPlannerConfig,
    PlannerContext,
    PlannerDecision,
    plan_components_for_route,
)
from .panel_generator import PanelBlockInput, PanelGenerator, PanelGenerationResult
from .llm_component_planner import LLMComponentPlanner
from .schema_summary import SchemaSummaryBuilder
from .panel_spec import (
    StructuredDataEnvelope,
    StructuredDataSchema,
    DisplaySchema,
    PanelDSL,
    PanelNode,
    DataBinding,
    TransformationSpec,
    EventHandlerSpec,
    validate_panel_dsl,
    validate_envelope,
    PanelSpecError,
)
from .dsl_runtime import PanelDSLParser, PanelDSLValidationError
from .dsl_renderer import PanelDSLRenderer
from .sandbox_executor import SandboxExecutor, SandboxExecutionError
from .view_model_builder import GeneratedViewModel, ViewModelBuilder
from .runtime import PanelRuntime

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
    "PlannerContext",
    "LLMComponentPlanner",
    "PlannerDecision",
    "plan_components_for_route",
    "SchemaSummaryBuilder",
    "StructuredDataEnvelope",
    "StructuredDataSchema",
    "DisplaySchema",
    "PanelDSL",
    "PanelNode",
    "DataBinding",
    "TransformationSpec",
    "EventHandlerSpec",
    "validate_panel_dsl",
    "validate_envelope",
    "PanelSpecError",
    "PanelDSLParser",
    "PanelDSLValidationError",
    "PanelDSLRenderer",
    "SandboxExecutor",
    "SandboxExecutionError",
    "GeneratedViewModel",
    "ViewModelBuilder",
    "PanelRuntime",
]
