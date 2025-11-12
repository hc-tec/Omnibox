from __future__ import annotations

"""PlannerAgent 节点实现。"""

import logging
from typing import Dict, List

from ..json_utils import parse_json_payload
from ..llm_retry import retry_with_backoff
from ..prompt_loader import load_prompt
from ..runtime import LangGraphRuntime
from ..state import DataReference, GraphState, ToolCall

logger = logging.getLogger(__name__)


def _format_data_stash(data_stash: List[DataReference]) -> str:
    if not data_stash:
        return "暂无数据"
    lines = []
    for item in data_stash:
        lines.append(
            f"- Step {item.step_id} [{item.tool_name}] ({item.status}): {item.summary}"
        )
    return "\n".join(lines)


def create_planner_node(runtime: LangGraphRuntime):
    system_prompt = load_prompt("planner_system.txt")

    # 构建工具列表供 Planner 参考
    tool_specs = runtime.tool_registry.list_tools()
    tools_info = []
    for spec in tool_specs:
        tool_desc = f"- {spec.plugin_id}: {spec.description}"
        if spec.schema and "properties" in spec.schema:
            # 添加参数信息
            params = ", ".join(spec.schema["properties"].keys())
            tool_desc += f" (参数: {params})"
        tools_info.append(tool_desc)
    available_tools = "\n".join(tools_info)

    def node(state: GraphState) -> Dict[str, ToolCall]:
        query = state.get("original_query", "")
        if not query:
            raise ValueError("PlannerAgent: original_query 为空或缺失")
        data_stash = state.get("data_stash", [])
        reflection = state.get("reflection")
        next_step = len(data_stash) + 1
        prompt_parts = [
            system_prompt,
            f"\n可用工具列表:\n{available_tools}",
            f"\noriginal_query:\n{query}",
            f"\ndata_stash:\n{_format_data_stash(data_stash)}",
        ]
        if reflection:
            prompt_parts.append(f"\nlast_reflection:\nDecision={reflection.decision}\nReasoning={reflection.reasoning}")
        prompt = "\n\n".join(prompt_parts)

        # 使用重试装饰器包装 LLM 调用
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def call_llm():
            return runtime.planner_llm.generate(prompt, temperature=0.1)

        try:
            response = call_llm()
            data = parse_json_payload(response)
            call = ToolCall(
                plugin_id=data["plugin_id"],
                args=data.get("args", {}),
                step_id=next_step,
                description=data.get("description", ""),
            )
            logger.info(
                "Planner 选择工具: %s (step %s)",
                call.plugin_id,
                call.step_id,
            )
            return {"next_tool_call": call}
        except Exception as exc:
            logger.exception("Planner 解析失败: %s", exc)
            raise

    return node

