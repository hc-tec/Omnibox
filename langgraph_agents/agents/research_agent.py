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
from ..component_contracts import (
    COMPONENT_CONTRACTS_PROMPT,
    get_contract_by_component,
    get_contract_by_id,
)

logger = logging.getLogger(__name__)


def _short_preview(value: Any, limit: int = 200) -> str:
    """将任意对象转换为可读的短字符串，避免提示词过长或格式错误。"""
    try:
        text = json.dumps(value, ensure_ascii=False)
    except Exception:
        text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


def _emit_reasoning(runtime: LangGraphRuntime, payload: Dict[str, Any]) -> None:
    """
    触发 Agent reasoning 回调（如果有）。

    Args:
        runtime: LangGraph 运行时
        payload: reasoning 数据载荷
    """
    tool_context = getattr(runtime, "tool_context", None)
    if not tool_context:
        return

    extras = getattr(tool_context, "extras", None)
    if not extras:
        return

    callback = extras.get("emit_agent_reasoning")
    if callback and callable(callback):
        try:
            callback(payload)
        except Exception as exc:
            logger.warning("emit_agent_reasoning 回调失败: %s", exc)


def _format_chat_history(chat_history: List[str]) -> str:
    """
    格式化对话历史。

    chat_history 是字符串列表，格式为 "role: content"
    """
    if not chat_history:
        return "暂无"

    # 限制显示最近的 10 轮对话，避免 prompt 过长
    recent_history = chat_history[-20:] if len(chat_history) > 20 else chat_history

    lines = []
    for entry in recent_history:
        # entry 格式是 "role: content"
        lines.append(f"  {entry}")

    return "\n".join(lines)


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
    if not isinstance(working_memory, dict) or not working_memory:
        return "暂无"
    lines = []
    for tool_id, result in working_memory.items():
        if tool_id == "filter_datasource":
            continue  # 跳过内部标记
        if tool_id == "component_contracts":
            contracts_entry = result if isinstance(result, dict) else {}
            contracts = contracts_entry.get("contracts") or {}
            if not contracts:
                continue
            lines.append("组件契约登记：")
            for entry in contracts.values():
                component_id = entry.get("component_id", "未知组件")
                contract_id = entry.get("contract_id", "未知契约")
                status = entry.get("status", "pending")
                targets = entry.get("targets") or []
                target_str = ", ".join(targets) if targets else "未指定数据引用"
                description = entry.get("description") or ""
                lines.append(
                    f"  - {component_id} ({contract_id}) [{status}] → {target_str} {description}".rstrip()
                )
            continue
        if not isinstance(result, dict):
            preview = _short_preview(result)
            lines.append(f"[{tool_id}] (unknown): {preview}")
            continue
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


def _format_raw_fetch_refs(data_stash: List[DataReference]) -> str:
    """列出所有 fetch 类工具产生的原始数据引用，提醒必须先用 data_operator 处理。"""
    raw_refs = [
        ref
        for ref in data_stash
        if ref.tool_name in {"fetch_public_data", "fetch_private_data"} and ref.status == "success"
    ]
    if not raw_refs:
        return "暂无原始数据"
    lines: List[str] = []
    for ref in raw_refs:
        data_id = ref.data_id or "无 data_id"
        lines.append(
            f"- Step {ref.step_id}: data_id={data_id}，描述：{ref.summary}。"
            f" 调用 data_operator 时使用 \"$step.{ref.step_id}\" 或 \"{data_id}\" 引用。"
        )
    return "\n".join(lines)


def _format_component_contract_registry(working_memory: Dict[str, Any]) -> str:
    """单独格式化组件契约信息，供提示词引用。"""
    if not isinstance(working_memory, dict):
        return "暂无"
    contracts_entry = working_memory.get("component_contracts")
    if not isinstance(contracts_entry, dict):
        return "暂无"
    contracts = contracts_entry.get("contracts") or {}
    if not contracts:
        return "暂无"
    lines: List[str] = []
    for entry in contracts.values():
        component_id = entry.get("component_id", "未知组件")
        contract_id = entry.get("contract_id", "未知契约")
        status = entry.get("status", "pending")
        targets = entry.get("targets") or []
        description = entry.get("description") or ""
        lines.append(
            f"- {component_id} ({contract_id}) [{status}] 目标: {', '.join(targets) if targets else '未绑定'} {description}".rstrip()
        )
    return "\n".join(lines) if lines else "暂无"


def _extract_component_contract_payloads(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从 LLM 输出中提取 component_contract 定义（兼容单个或数组）。"""
    if "component_contract" not in data:
        return []
    payload = data["component_contract"]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _merge_component_contracts(
    state: GraphState,
    payloads: List[Dict[str, Any]],
    step_id: int,
) -> Optional[Dict[str, Any]]:
    """将新增的组件契约写入 working_memory."""
    if not payloads:
        return None

    state_working_memory = state.get("working_memory", {})
    working_memory = dict(state_working_memory) if isinstance(state_working_memory, dict) else {}
    raw_entry = working_memory.get("component_contracts", {})
    current_entry = dict(raw_entry) if isinstance(raw_entry, dict) else {}
    raw_contracts = current_entry.get("contracts", {})
    existing_contracts = dict(raw_contracts) if isinstance(raw_contracts, dict) else {}

    updated = False
    for payload in payloads:
        component_id = payload.get("component_id")
        contract_id = payload.get("contract_id")
        if component_id and not contract_id:
            contract_def = get_contract_by_component(component_id)
            if contract_def:
                contract_id = contract_def.contract_id
        if not component_id or not contract_id:
            continue
        targets = payload.get("targets")
        if isinstance(targets, str):
            targets = [targets]
        if not targets:
            targets = [f"$step.{step_id}"]
        normalized_targets = []
        for target in targets:
            if isinstance(target, str):
                normalized_targets.append(target)
        if not normalized_targets:
            normalized_targets = [f"$step.{step_id}"]
        record = existing_contracts.get(contract_id, {}).copy()
        record.update(
            {
                "component_id": component_id,
                "contract_id": contract_id,
                "status": payload.get("status", "planned"),
                "description": payload.get("description", ""),
                "targets": normalized_targets,
                "notes": payload.get("notes"),
                "last_updated_step": step_id,
            }
        )
        existing_contracts[contract_id] = record
        updated = True

    if not updated:
        return None

    current_entry.update(
        {
            "step_id": step_id,
            "status": "info",
            "description": f"{len(existing_contracts)} 个组件契约已登记",
            "contracts": existing_contracts,
        }
    )
    working_memory["component_contracts"] = current_entry
    return working_memory


def _select_display_contract(
    working_memory: Dict[str, Any],
    data_stash: List[DataReference],
    default_contract_id: str = "ListPanel-contract-v3",
) -> Optional[str]:
    """选择用于展示的契约：优先 working_memory 登记 → 数据 metadata → 默认 ListPanel。"""
    if isinstance(working_memory, dict):
        contracts_entry = working_memory.get("component_contracts") or {}
        contracts = contracts_entry.get("contracts") or {}
        for record in contracts.values():
            if record.get("status") in {"planned", "applied"}:
                cid = record.get("contract_id")
                if cid and get_contract_by_id(cid):
                    return cid

    # 从最近的 data_stash metadata 猜测
    for ref in reversed(data_stash or []):
        meta = getattr(ref, "metadata", None) or {}
        cid = None
        if isinstance(meta, dict):
            cid = meta.get("contract_id")
        if not cid and hasattr(ref, "summary"):
            # 无法从 summary 推断，不再靠启发式
            pass
        if cid and get_contract_by_id(cid):
            return cid

    # 兜底
    if get_contract_by_id(default_contract_id):
        return default_contract_id
    return None


def _select_data_ref_for_display(data_stash: List[DataReference]) -> Optional[DataReference]:
    """选择最近的成功数据引用，用于展示/改呈现。"""
    for ref in reversed(data_stash or []):
        if getattr(ref, "status", None) == "success" and getattr(ref, "data_id", None):
            return ref
    return None


def _bump_error_counter(state: GraphState, plugin_id: str, error_code: str) -> int:
    """记录同一工具+错误码的连续失败次数，返回最新计数。"""
    error_counters = state.get("error_counters") or {}
    key = f"{plugin_id}:{error_code}"
    count = error_counters.get(key, 0) + 1
    error_counters[key] = count
    state["error_counters"] = error_counters
    return count


def _extract_error_code_from_result(result: Any) -> Optional[str]:
    """从工具执行结果中提取错误码，兼容 raw_output.error / error_code。"""
    if not result or getattr(result, "status", None) != "error":
        return None
    raw_output = getattr(result, "raw_output", None)
    if isinstance(raw_output, dict):
        if raw_output.get("error_code"):
            return str(raw_output["error_code"])
        if raw_output.get("error"):
            return str(raw_output["error"])
    err = getattr(result, "error_message", None)
    return str(err) if err else None


def _recent_tool_repeats(data_stash: List[DataReference], plugin_id: str, limit: int = 3) -> int:
    """
    统计 data_stash 末尾连续出现同一工具的次数。

    用于防止无进展的重复调用（即便 status=success 也会检查）。
    """
    count = 0
    for ref in reversed(data_stash or []):
        if ref.tool_name == plugin_id:
            count += 1
            if count >= limit:
                break
        else:
            break
    return count


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
        chat_history = state.get("chat_history", [])  # Session 多轮对话历史
        next_step = len(data_stash) + 1
        default_contract_id = _select_display_contract(working_memory, data_stash)

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
            "\n## 数据处理约束\n- 对 fetch_public_data / fetch_private_data 获取的原始 RSS 数据，必须先调用 data_operator（source_ref 使用 \"$step.N\" 或 data_id）进行过滤/清洗，再进入后续分析或总结。\n- 禁止直接基于适配器 / 面板层数据编写逻辑。",
            f"\n## 可用工具列表\n{available_tools}",
            f"\n## 用户当前查询\n{query}",
        ]

        # 添加对话历史（Session 多轮对话支持）
        if chat_history:
            prompt_parts.append(
                f"\n## 对话历史（重要：需要结合历史上下文理解当前查询）\n{_format_chat_history(chat_history)}"
            )

        prompt_parts.extend([
            f"\n## 已执行的工具链\n{_extract_executed_tools(data_stash)}",
            f"\n## 已获取的数据（data_stash）\n{_format_data_stash(data_stash)}",
        ])

        prompt_parts.append(
            f"\n## 原始 RSS 数据引用（必须先用 data_operator 处理）\n{_format_raw_fetch_refs(data_stash)}"
        )

        if working_memory:
            prompt_parts.append(f"\n## 工作记忆（轻量工具结果）\n{_format_working_memory(working_memory)}")
        prompt_parts.append(
            f"\n## 已登记的组件契约\n{_format_component_contract_registry(working_memory)}"
        )
        prompt_parts.append(f"\n## 组件契约参考\n{COMPONENT_CONTRACTS_PROMPT}")

        if tool_status_note:
            prompt_parts.append(tool_status_note)

        prompt_parts.append(f"\n## 当前步骤编号\n{next_step}")

        prompt = "\n".join(prompt_parts)

        # 规划开始前推送“思考中”状态，供前端实时展示
        _emit_reasoning(
            runtime,
            {
                "step_id": next_step,
                "decision": "PLANNING",
                "reasoning": "生成执行摘要并规划下一步…",
                "status": "processing",
            },
        )

        # 使用重试装饰器包装 LLM 调用
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def call_llm():
            return runtime.planner_llm.generate(prompt, temperature=0.1, role="research_agent")

        try:
            response = call_llm()
            data = parse_json_payload(response)
            return _process_agent_decision(data, next_step, state, runtime)

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
    runtime: LangGraphRuntime,
) -> Dict[str, Any]:
    """
    处理 Agent 的决策结果。

    返回适当的状态更新。
    """
    data_stash = state.get("data_stash", [])
    decision = data.get("decision", "CONTINUE")
    reasoning = data.get("reasoning", "")
    contract_payloads = _extract_component_contract_payloads(data)
    updated_working_memory = _merge_component_contracts(state, contract_payloads, next_step)

    logger.info("ResearchAgent 决策: %s - %s", decision, reasoning[:100])

    # 触发 reasoning 回调（如果有）
    _emit_reasoning(
        runtime,
        {
            "step_id": next_step,
            "decision": decision,
            "reasoning": reasoning,
            "tool_call": data.get("tool_call"),
        },
    )

    # 读取工具错误码，避免无限循环（最多 3 次同一错误）
    last_tool_result = state.get("last_tool_result")
    last_error_code = _extract_error_code_from_result(last_tool_result)

    error_counters = state.get("error_counters") or {}
    last_plugin = getattr(last_tool_result.call, "plugin_id", None) if last_tool_result and last_tool_result.call else None
    if last_error_code and last_plugin:
        _bump_error_counter(state, last_plugin, last_error_code)
        error_counters = state.get("error_counters") or {}

    if decision == "CONTINUE":
        tool_call_data = data.get("tool_call") or {}
        plugin_id = tool_call_data.get("plugin_id")
        if plugin_id:
            # 若该工具同一错误累计 >=3，直接终止，避免循环
            for key, cnt in (error_counters or {}).items():
                if key.startswith(f"{plugin_id}:") and cnt >= 3:
                    logger.warning("重复失败同一工具>=3次，终止循环: %s (%s)", plugin_id, key.split(":", 1)[1])
                    return {
                        "final_report": json.dumps(
                            {
                                "summary": f"任务停止：{plugin_id} 连续失败 {cnt} 次，请调整指令或数据。",
                                "evidence": [],
                                "next_actions": [],
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                        "next_tool_call": None,
                        "agent_decision": "FINISH",
                        "agent_reasoning": reasoning,
                        "last_error_code": last_error_code,
                    }

    if decision == "FINISH":
        # 任务完成，生成最终报告
        final_report = data.get("final_report", {})
        if isinstance(final_report, str):
            # 如果已经是字符串，直接使用
            report_str = final_report
        else:
            # 否则序列化为 JSON
            report_str = json.dumps(final_report, ensure_ascii=False, indent=2)

        result = {
            "final_report": report_str,
            "next_tool_call": None,
            "agent_decision": "FINISH",
            "agent_reasoning": reasoning,
        }
        if updated_working_memory is not None:
            result["working_memory"] = updated_working_memory
        return result

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

        result = {
            "next_tool_call": tool_call,
            "agent_decision": "REQUEST_CLARIFICATION",
            "agent_reasoning": reasoning,
        }
        if updated_working_memory is not None:
            result["working_memory"] = updated_working_memory
        return result

    else:  # CONTINUE
        # 继续执行，调用工具
        tool_call_data = data.get("tool_call", {})
        if not tool_call_data or not tool_call_data.get("plugin_id"):
            # 没有有效的工具调用，默认结束
            logger.warning("ResearchAgent CONTINUE 但没有 tool_call，强制 FINISH")
            return {
                "final_report": json.dumps(
                    {
                        "summary": "任务已完成（无更多工具调用）",
                        "evidence": [],
                        "next_actions": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "next_tool_call": None,
                "agent_decision": "FINISH",
                "agent_reasoning": "无更多工具调用",
            }

        # 如果是展示需求且缺少契约/映射，尝试自动填充 contract_id/field_mapping
        args = tool_call_data.get("args", {}) or {}
        if tool_call_data.get("plugin_id") == "emit_panel_preview":
            if "contract_id" not in args:
                auto_contract = _select_display_contract(state.get("working_memory", {}), state.get("data_stash", []))
                if auto_contract:
                    args["contract_id"] = auto_contract
            # 展示请求优先复用最近成功数据引用
            if "source_ref" not in args:
                ref = _select_data_ref_for_display(state.get("data_stash", []))
                if ref and ref.data_id:
                    args["source_ref"] = ref.data_id

            # 如果上一轮已成功生成同一契约+数据的面板，直接结束，避免重复推送
            last_tool_result = state.get("last_tool_result")
            if (
                last_tool_result
                and getattr(last_tool_result, "status", None) == "success"
                and getattr(getattr(last_tool_result, "call", None), "plugin_id", None) == "emit_panel_preview"
            ):
                last_args = getattr(getattr(last_tool_result, "call", None), "args", {}) or {}
                same_source = args.get("source_ref") == last_args.get("source_ref")
                same_contract = (args.get("contract_id") or None) == (last_args.get("contract_id") or None)
                if same_source and same_contract:
                    last_ref = data_stash[-1] if data_stash else None
                    report_payload = {
                        "summary": last_ref.summary if last_ref else "表格已生成，可直接查看。",
                        "evidence": [
                            {
                                "data_id": last_ref.data_id,
                                "tool": last_ref.tool_name,
                                "step": last_ref.step_id,
                            }
                        ] if last_ref else [],
                        "next_actions": [],
                    }
                    result = {
                        "final_report": json.dumps(report_payload, ensure_ascii=False, indent=2),
                        "next_tool_call": None,
                        "agent_decision": "FINISH",
                        "agent_reasoning": reasoning,
                    }
                    if updated_working_memory is not None:
                        result["working_memory"] = updated_working_memory
                    return result

        # 防止无进展的重复调用（同一工具连续 ≥3 次）
        recent_repeat = _recent_tool_repeats(state.get("data_stash", []), tool_call_data.get("plugin_id"), limit=3)
        if recent_repeat >= 3:
            logger.warning("同一工具连续成功执行 %s 次，停止以避免循环: %s", recent_repeat, tool_call_data.get("plugin_id"))
            return {
                "final_report": json.dumps(
                    {
                        "summary": f"任务停止：{tool_call_data.get('plugin_id')} 已连续执行 {recent_repeat} 次且未结束，可能陷入循环，请调整指令。",
                        "evidence": [],
                        "next_actions": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "next_tool_call": None,
                "agent_decision": "FINISH",
                "agent_reasoning": reasoning,
            }
        tool_call = ToolCall(
            plugin_id=tool_call_data["plugin_id"],
            args=args,
            step_id=next_step,
            description=tool_call_data.get("description", ""),
        )

        logger.info(
            "ResearchAgent 选择工具: %s (step %s)",
            tool_call.plugin_id,
            tool_call.step_id,
        )

        result = {
            "next_tool_call": tool_call,
            "agent_decision": "CONTINUE",
            "agent_reasoning": reasoning,
        }
        if last_error_code:
            result["last_error_code"] = last_error_code
        if updated_working_memory is not None:
            result["working_memory"] = updated_working_memory
        return result
