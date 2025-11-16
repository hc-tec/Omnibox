"""Tool 注册与实现命名空间。"""

from .public_data import register_public_data_tool
from .source_discovery import register_source_discovery_tool
from .data_filter import register_data_filter_tool
from .data_compare import register_data_compare_tool
from .user_interaction import register_user_interaction_tool

__all__ = [
    "register_public_data_tool",
    "register_source_discovery_tool",
    "register_data_filter_tool",
    "register_data_compare_tool",
    "register_user_interaction_tool",
    "register_v5_p0_tools",
]


def register_v5_p0_tools(registry) -> None:
    """注册所有 V5.0 Phase 1 (P0) 工具。"""
    register_source_discovery_tool(registry)
    register_data_filter_tool(registry)
    register_data_compare_tool(registry)
    register_user_interaction_tool(registry)
