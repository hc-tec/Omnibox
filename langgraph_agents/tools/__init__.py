"""Tool 注册与实现命名空间。"""

from .public_data import register_public_data_tool
from .source_discovery import register_source_discovery_tool
from .data_filter import register_data_filter_tool
from .data_compare import register_data_compare_tool
from .user_interaction import register_user_interaction_tool
from .dataset_inspector import register_dataset_inspector_tool
from .data_operator import register_data_operator_tool
from .data_ref_resolver import (
    DataRefResolver,
    ResolvedData,
    create_resolver_from_context,
)
from .execution_wrapper import (
    ToolExecutionWrapper,
    ToolTimeoutError,
    ToolRetryExhaustedError,
    execute_with_protection,
    with_timeout,
    with_retry,
)

__all__ = [
    "register_public_data_tool",
    "register_source_discovery_tool",
    "register_data_filter_tool",
    "register_data_compare_tool",
    "register_user_interaction_tool",
    "register_dataset_inspector_tool",
    "register_data_operator_tool",
    "register_v5_p0_tools",
    # V6.0 Phase 2: 数据引用解析器
    "DataRefResolver",
    "ResolvedData",
    "create_resolver_from_context",
    # V6.0 Phase 2.3: 执行保护
    "ToolExecutionWrapper",
    "ToolTimeoutError",
    "ToolRetryExhaustedError",
    "execute_with_protection",
    "with_timeout",
    "with_retry",
]


def register_v5_p0_tools(registry) -> None:
    """注册所有 V5.0 Phase 1 (P0) 工具。"""
    register_source_discovery_tool(registry)
    register_data_filter_tool(registry)
    register_data_compare_tool(registry)
    register_user_interaction_tool(registry)
    register_dataset_inspector_tool(registry)
    register_data_operator_tool(registry)
