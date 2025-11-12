from __future__ import annotations

"""ToolExecutor 节点实现。"""

import logging
from typing import Dict

from ..runtime import LangGraphRuntime
from ..state import GraphState, ToolExecutionPayload

logger = logging.getLogger(__name__)


def create_tool_executor_node(runtime: LangGraphRuntime):
    def node(state: GraphState) -> Dict[str, object]:
        call = state.get("next_tool_call")
        if call is None:
            logger.warning("ToolExecutor 未收到 ToolCall")
            return {"last_error": "缺少 ToolCall"}

        try:
            payload = runtime.tool_registry.execute(call, runtime.tool_context)
        except Exception as exc:
            logger.exception("工具执行失败: %s", exc)
            payload = ToolExecutionPayload(
                call=call,
                status="error",
                error_message=str(exc),
                raw_output=None,
            )

        return {
            "pending_tool_result": payload,
            "next_tool_call": None,
        }

    return node

