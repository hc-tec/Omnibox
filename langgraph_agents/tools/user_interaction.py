from __future__ import annotations

"""ask_user_clarification 工具实现：请求用户澄清歧义。"""

import logging
from uuid import uuid4

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool

logger = logging.getLogger(__name__)


def register_user_interaction_tool(registry: ToolRegistry) -> None:
    """向注册表注册 ask_user_clarification 工具。"""

    @tool(
        registry,
        plugin_id="ask_user_clarification",
        description="请求用户澄清歧义，提供结构化选项",
        schema={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "澄清问题（必填）",
                    "minLength": 1,
                    "maxLength": 500,
                    "examples": [
                        "您想查询哪个平台的数据？",
                        "请选择要对比的维度",
                        "数据时间范围是？"
                    ]
                },
                "options": {
                    "type": "array",
                    "description": "选项列表（必填，2-5 个）",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 5,
                    "examples": [
                        ["GitHub", "HackerNews", "知乎"],
                        ["最近一周", "最近一月", "最近一年"]
                    ]
                },
                "allow_other": {
                    "type": "boolean",
                    "description": "是否允许用户自定义输入（可选，默认 true）",
                    "default": True
                }
            },
            "required": ["question", "options"]
        }
    )
    def ask_user_clarification(
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        """
        请求用户澄清歧义。

        返回特殊状态 "needs_user_input"，触发系统等待用户输入。
        """
        # 1. 参数验证
        question = call.args.get("question")
        if not question:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "user_clarification",
                    "error_code": "E101"
                },
                status="error",
                error_message="缺少必填参数 question"
            )

        options = call.args.get("options")
        if not options:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "user_clarification",
                    "error_code": "E101"
                },
                status="error",
                error_message="缺少必填参数 options"
            )

        if not isinstance(options, list):
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "user_clarification",
                    "error_code": "E102"
                },
                status="error",
                error_message="参数 options 必须是数组类型"
            )

        if len(options) < 2 or len(options) > 5:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "user_clarification",
                    "error_code": "E102"
                },
                status="error",
                error_message="options 必须包含 2-5 个选项"
            )

        allow_other = call.args.get("allow_other", True)

        # 2. 生成澄清请求 ID
        clarification_id = f"clarify-{uuid4().hex[:8]}"

        logger.info(
            "ask_user_clarification: 请求澄清 - %s (选项: %s)",
            question,
            options
        )

        # 3. 返回特殊状态
        # 注意：这个工具不执行实际操作，而是返回一个特殊状态
        # 触发工作流路由到"等待用户输入"节点
        return ToolExecutionPayload(
            call=call,
            raw_output={
                "type": "user_clarification",
                "status": "needs_user_input",
                "clarification_id": clarification_id,
                "question": question,
                "options": options,
                "allow_other": allow_other
            },
            status="needs_user_input"  # 特殊状态
        )
