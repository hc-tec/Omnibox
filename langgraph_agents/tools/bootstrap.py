"""工具注册快捷入口。"""

from .registry import ToolRegistry
from .public_data import register_public_data_tool
from .private_notes import register_private_notes_tool
from .panel_stream import register_panel_stream_tool

# V5.0 P0 工具
from .source_discovery import register_source_discovery_tool
from .data_filter import register_data_filter_tool
from .data_compare import register_data_compare_tool
from .user_interaction import register_user_interaction_tool

# V5.0 P1 工具 (Phase 3)
from .data_aggregator import register_data_aggregator_tool
from .insights_extractor import register_insights_extractor_tool
from .private_data import register_private_data_tool
from .dataset_inspector import register_dataset_inspector_tool
from .data_operator import register_data_operator_tool

# V6.0 新工具
from .content_analysis import register_content_analysis_tool


def register_default_tools(registry: ToolRegistry) -> None:
    """
    注册所有默认工具。

    V5.0 P0 工具（探索、过滤、对比、交互）
    + V5.0 P1 工具（聚合、洞察、私有数据）
    + V4.4 兼容工具。
    """
    # V5.0 P0 核心工具
    register_source_discovery_tool(registry)
    register_data_filter_tool(registry)
    register_data_compare_tool(registry)
    register_user_interaction_tool(registry)
    register_dataset_inspector_tool(registry)
    register_data_operator_tool(registry)

    # V5.0 P1 工具 (Phase 3)
    register_data_aggregator_tool(registry)
    register_insights_extractor_tool(registry)
    register_private_data_tool(registry)

    # V6.0 新工具（内容分析）
    register_content_analysis_tool(registry)

    # V4.4 兼容工具（仍然保留）
    register_public_data_tool(registry)

    # 其他工具
    register_private_notes_tool(registry)
    register_panel_stream_tool(registry)
