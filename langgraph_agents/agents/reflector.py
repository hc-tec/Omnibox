from __future__ import annotations

"""
ReflectorAgent 节点实现。

⚠️ V6.0 废弃警告 ⚠️
此模块已被 ResearchAgent 取代。
ResearchAgent 融合了 Planner + Reflector + Synthesizer 的功能。
保留此代码仅用于向后兼容和测试，新功能请使用 research_agent.py。
"""

import logging
from typing import Dict, List

from ..json_utils import parse_json_payload
from ..llm_retry import retry_with_backoff
from ..prompt_loader import load_prompt
from ..runtime import LangGraphRuntime
from ..state import DataReference, GraphState, Reflection

logger = logging.getLogger(__name__)


def _format_summaries(data_stash: List[DataReference]) -> str:
    if not data_stash:
        return "暂无数据"
    parts = []
    for ref in data_stash:
        parts.append(
            f"[Step {ref.step_id}] {ref.tool_name} ({ref.status}): {ref.summary}"
        )
    return "\n".join(parts)


def _format_working_memory(working_memory: Dict) -> str:
    """格式化轻量工具结果（working_memory）。"""
    if not working_memory:
        return "暂无"
    lines = []
    for tool_id, result in working_memory.items():
        status = result.get("status", "unknown")
        description = result.get("description", "")
        step_id = result.get("step_id", "?")
        lines.append(f"[Step {step_id}] {tool_id} ({status}): {description}")
    return "\n".join(lines)


def _extract_executed_tools(data_stash: List[DataReference]) -> str:
    """提取已执行的工具列表（帮助 Reflector 判断任务完成度）。"""
    if not data_stash:
        return "暂无"
    tools = [ref.tool_name for ref in data_stash]
    return ", ".join(tools)


def create_reflector_node(runtime: LangGraphRuntime):
    system_prompt = load_prompt("reflector_system.txt")

    def node(state: GraphState) -> Dict[str, Reflection]:
        query = state.get("original_query", "")
        if not query:
            raise ValueError("ReflectorAgent: original_query 为空或缺失")
        data_stash = state.get("data_stash", [])
        working_memory = state.get("working_memory", {})
        last_reflection = state.get("reflection")

        # V5.0 P0: 检查最后一次工具执行状态
        last_tool_result = state.get("last_tool_result")
        tool_status_note = ""

        if last_tool_result and hasattr(last_tool_result, "status"):
            if last_tool_result.status == "needs_user_input":
                # 工具请求用户输入，直接返回 REQUEST_HUMAN_CLARIFICATION
                tool_status_note = "\n\n⚠️ 最后一步工具返回 'needs_user_input' 状态，需要用户澄清。"
                logger.info("Reflector: 检测到 needs_user_input 状态")

        # 构建增强的 prompt
        prompt_parts = [
            system_prompt,
            f"\noriginal_query:\n{query}",
            f"\n已执行的工具:\n{_extract_executed_tools(data_stash)}",
            f"\ncollected_data:\n{_format_summaries(data_stash)}",
        ]

        # 添加轻量工具结果
        if working_memory:
            prompt_parts.append(f"\nworking_memory (轻量工具结果):\n{_format_working_memory(working_memory)}")

        # 添加上一轮反思结果（帮助理解执行历史）
        if last_reflection:
            prompt_parts.append(f"\nlast_reflection:\nDecision={last_reflection.decision}\nReasoning={last_reflection.reasoning}")

        if tool_status_note:
            prompt_parts.append(tool_status_note)

        prompt = "\n".join(prompt_parts)

        # 使用重试装饰器包装 LLM 调用
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def call_llm():
            return runtime.reflector_llm.generate(prompt, temperature=0.1, role="reflector")

        try:
            response = call_llm()
            data = parse_json_payload(response)
            reflection = Reflection(
                decision=data["decision"],
                reasoning=data.get("reasoning", ""),
            )
        except Exception as exc:
            # 仅捕获解析错误
            logger.warning("Reflector 解析失败，默认 CONTINUE: %s", exc)
            reflection = Reflection(decision="CONTINUE", reasoning=f"解析错误: {exc}")

        return {"reflection": reflection}

    return node

