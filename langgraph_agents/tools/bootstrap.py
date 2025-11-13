"""工具注册快捷入口。"""

from .registry import ToolRegistry
from .public_data import register_public_data_tool
from .private_notes import register_private_notes_tool
from .panel_stream import register_panel_stream_tool
from .subscription_data import register_subscription_data_tool


def register_default_tools(registry: ToolRegistry) -> None:
    register_subscription_data_tool(registry)  # Phase 2: 优先订阅查询
    register_public_data_tool(registry)
    register_private_notes_tool(registry)
    register_panel_stream_tool(registry)
