from __future__ import annotations

"""工具注册中心，负责将 LangGraph ToolCall 映射到具体实现。"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import logging

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext

logger = logging.getLogger(__name__)

ToolHandler = Callable[[ToolCall, ToolExecutionContext], ToolExecutionPayload]


@dataclass
class ToolSpec:
    plugin_id: str
    description: str
    handler: ToolHandler
    schema: Optional[Dict[str, Any]] = None


class ToolRegistry:
    """轻量工具注册器，避免 Planner 直接引用实现细节。"""

    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register(
        self,
        plugin_id: str,
        handler: ToolHandler,
        description: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        if plugin_id in self._tools:
            raise ValueError(f"工具 {plugin_id} 已注册")
        self._tools[plugin_id] = ToolSpec(
            plugin_id=plugin_id,
            description=description,
            handler=handler,
            schema=schema,
        )
        logger.info("注册工具: %s - %s", plugin_id, description)

    # 兼容旧接口（某些调用方使用 register_tool）
    def register_tool(
        self,
        plugin_id: str,
        handler: ToolHandler,
        description: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.register(plugin_id, handler, description, schema)

    def get(self, plugin_id: str) -> ToolSpec:
        if plugin_id not in self._tools:
            raise KeyError(f"未找到工具: {plugin_id}")
        return self._tools[plugin_id]

    def list_tools(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def execute(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        spec = self.get(call.plugin_id)
        return spec.handler(call, context)


def tool(
    registry: ToolRegistry,
    *,
    plugin_id: str,
    description: str,
    schema: Optional[Dict[str, Any]] = None,
):
    """装饰器：将函数注册为工具。"""

    def decorator(func: ToolHandler) -> ToolHandler:
        registry.register(
            plugin_id=plugin_id,
            handler=func,
            description=description,
            schema=schema,
        )
        return func

    return decorator
