"""工具注册快捷入口。"""

from .registry import ToolRegistry
from .public_data import register_public_data_tool
from .private_notes import register_private_notes_tool


def register_default_tools(registry: ToolRegistry) -> None:
    register_public_data_tool(registry)
    register_private_notes_tool(registry)

