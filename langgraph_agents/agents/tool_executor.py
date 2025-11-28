from __future__ import annotations

"""ToolExecutor 节点实现。"""

import logging
from typing import Dict

from ..runtime import LangGraphRuntime, ToolExecutionContext
from ..state import GraphState, ToolExecutionPayload

logger = logging.getLogger(__name__)


def create_tool_executor_node(runtime: LangGraphRuntime):
    def node(state: GraphState) -> Dict[str, object]:
        call = state.get("next_tool_call")
        if call is None:
            logger.warning("ToolExecutor 未收到 ToolCall")
            return {"last_error": "缺少 ToolCall"}

        # V6.0 Phase 2: 注入 data_stash 到工具上下文，支持工具间数据引用
        # 创建增强的上下文副本，避免修改原始 runtime.tool_context
        enhanced_extras = dict(runtime.tool_context.extras)
        enhanced_extras["data_stash"] = state.get("data_stash", [])
        enhanced_extras["working_memory"] = state.get("working_memory", {})
        enhanced_extras["data_store"] = runtime.data_store
        enhanced_extras["schema_registry"] = runtime.schema_registry

        enhanced_context = ToolExecutionContext(
            data_query_service=runtime.tool_context.data_query_service,
            note_backend=runtime.tool_context.note_backend,
            extras=enhanced_extras,
        )

        try:
            payload = runtime.tool_registry.execute(call, enhanced_context)
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
