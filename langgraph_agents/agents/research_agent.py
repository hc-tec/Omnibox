"""
V6.0 单Agent研究节点实现。

融合 Planner、Reflector、Synthesizer 的功能，在单次 LLM 调用中完成：
1. 评估当前状态
2. 决定下一步动作（调用工具/完成任务/请求澄清）
3. 如果完成，生成最终报告
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Literal, Optional, Any

from ..json_utils import parse_json_payload
from ..llm_retry import retry_with_backoff
from ..prompt_loader import load_prompt
from ..runtime import LangGraphRuntime
from ..state import DataReference, GraphState, ToolCall

logger = logging.getLogger(__name__)


def _format_data_stash(data_stash: List[DataReference]) -> str:
    """格式化已获取的数据摘要。"""
    if not data_stash:
        return "暂无数据"
    lines = []
    for item in data_stash:
        status_icon = "✓" if item.status == "success" else "✗" if item.status == "error" else "?"
        lines.append(
            f"[Step {item.step_id}] {item.tool_name} ({status_icon}): {item.summary}"
        )
        if item.data_id:
            lines.append(f"  → data_id: {item.data_id}")
    return "\n".join(lines)


def _format_working_memory(working_memory: Dict) -> str:
    """格式化轻量工具结果。"""
    if not working_memory:
        return "暂无"
    lines = []
    for tool_id, result in working_memory.items():
        if tool_id == "filter_datasource":
            continue  # 跳过内部标记
        status = result.get("status", "unknown")
        description = result.get("description", "")
        step_id = result.get("step_id", "?")
        lines.append(f"[Step {step_id}] {tool_id} ({status}): {description}")
    return "\n".join(lines) if lines else "暂无"


def _extract_executed_tools(data_stash: List[DataReference]) -> str:
    """提取已执行的工具列表。"""
    if not data_stash:
        return "暂无"
    tools = [f"{ref.tool_name}({ref.status})" for ref in data_stash]
    return " → ".join(tools)


def create_research_agent_node(runtime: LangGraphRuntime):
    """
    创建单Agent研究节点。

    该节点融合了 Planner、Reflector、Synthesizer 的功能：
    - 分析当前状态
    - 决定下一步：调用工具 / 完成任务 / 请求澄清
    - 如果完成，直接生成最终报告
    """
    system_prompt = load_prompt("research_agent_system.txt")

    # 构建工具列表供 Agent 参考
    tool_specs = runtime.tool_registry.list_tools()
    tools_info = []
    for spec in tool_specs:
        tool_desc = f"- {spec.plugin_id}: {spec.description}"
        if spec.schema and "properties" in spec.schema:
            params = ", ".join(spec.schema["properties"].keys())
            tool_desc += f" (参数: {params})"
        tools_info.append(tool_desc)
    available_tools = "\n".join(tools_info)

    def node(state: GraphState) -> Dict[str, Any]:
        query = state.get("original_query", "")
        if not query:
            raise ValueError("ResearchAgent: original_query 为空或缺失")

        data_stash = state.get("data_stash", [])
        working_memory = state.get("working_memory", {})
        next_step = len(data_stash) + 1

        # 检查是否有上一步工具执行结果需要处理
        last_tool_result = state.get("last_tool_result")
        tool_status_note = ""
        if last_tool_result and hasattr(last_tool_result, "status"):
            if last_tool_result.status == "needs_user_input":
                tool_status_note = "\n⚠️ 上一步工具返回 'needs_user_input' 状态，需要请求用户澄清。"
            elif last_tool_result.status == "error":
                tool_status_note = f"\n⚠️ 上一步工具执行失败: {last_tool_result.error_message}"

        # 构建 prompt
        prompt_parts = [
            system_prompt,
            f"\n## 可用工具列表\n{available_tools}",
            f"\n## 用户查询\n{query}",
            f"\n## 已执行的工具链\n{_extract_executed_tools(data_stash)}",
            f"\n## 已获取的数据（data_stash）\n{_format_data_stash(data_stash)}",
        ]

        if working_memory:
            prompt_parts.append(f"\n## 工作记忆（轻量工具结果）\n{_format_working_memory(working_memory)}")

        if tool_status_note:
            prompt_parts.append(tool_status_note)

        prompt_parts.append(f"\n## 当前步骤编号\n{next_step}")

        prompt = "\n".join(prompt_parts)

        # 使用重试装饰器包装 LLM 调用
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def call_llm():
            return runtime.planner_llm.generate(prompt, temperature=0.1, role="research_agent")

        try:
            response = call_llm()
            data = parse_json_payload(response)
            return _process_agent_decision(data, next_step, state)

        except Exception as exc:
            logger.exception("ResearchAgent 解析失败: %s", exc)
            # 发生错误时，尝试继续（返回一个安全的 FINISH）
            return {
                "final_report": json.dumps({
                    "summary": "处理过程中发生错误",
                    "evidence": [],
                    "next_actions": [],
                    "error": str(exc),
                }, ensure_ascii=False, indent=2),
                "next_tool_call": None,
            }

    return node


def _process_agent_decision(
    data: Dict[str, Any],
    next_step: int,
    state: GraphState,
) -> Dict[str, Any]:
    """
    处理 Agent 的决策结果。

    返回适当的状态更新。
    """
    decision = data.get("decision", "CONTINUE")
    reasoning = data.get("reasoning", "")

    logger.info("ResearchAgent 决策: %s - %s", decision, reasoning[:100])

    if decision == "FINISH":
        # 任务完成，生成最终报告
        final_report = data.get("final_report", {})
        if isinstance(final_report, str):
            # 如果已经是字符串，直接使用
            report_str = final_report
        else:
            # 否则序列化为 JSON
            report_str = json.dumps(final_report, ensure_ascii=False, indent=2)

        return {
            "final_report": report_str,
            "next_tool_call": None,
            "agent_decision": "FINISH",
            "agent_reasoning": reasoning,
        }

    elif decision == "REQUEST_CLARIFICATION":
        # 需要用户澄清
        clarification = data.get("clarification", {})
        question = clarification.get("question", "需要更多信息")
        options = clarification.get("options", [])

        # 构造 ask_user_clarification 工具调用
        tool_call = ToolCall(
            plugin_id="ask_user_clarification",
            args={"question": question, "options": options},
            step_id=next_step,
            description=f"请求用户澄清: {question}",
        )

        return {
            "next_tool_call": tool_call,
            "agent_decision": "REQUEST_CLARIFICATION",
            "agent_reasoning": reasoning,
        }

    else:  # CONTINUE
        # 继续执行，调用工具
        tool_call_data = data.get("tool_call", {})
        if not tool_call_data or not tool_call_data.get("plugin_id"):
            # 没有有效的工具调用，默认结束
            logger.warning("ResearchAgent CONTINUE 但没有 tool_call，强制 FINISH")
            return {
                "final_report": json.dumps({
                    "summary": "任务已完成（无更多工具调用）",
                    "evidence": [],
                    "next_actions": [],
                }, ensure_ascii=False, indent=2),
                "next_tool_call": None,
                "agent_decision": "FINISH",
                "agent_reasoning": "无更多工具调用",
            }

        tool_call = ToolCall(
            plugin_id=tool_call_data["plugin_id"],
            args=tool_call_data.get("args", {}),
            step_id=next_step,
            description=tool_call_data.get("description", ""),
        )

        logger.info(
            "ResearchAgent 选择工具: %s (step %s)",
            tool_call.plugin_id,
            tool_call.step_id,
        )

        return {
            "next_tool_call": tool_call,
            "agent_decision": "CONTINUE",
            "agent_reasoning": reasoning,
        }
