from __future__ import annotations

"""DataStasher 节点实现。"""

import json
import logging
from typing import Dict, List

from ..prompt_loader import load_prompt
from ..runtime import LangGraphRuntime
from ..state import DataReference, GraphState, ToolExecutionPayload
from ..utils.raw_schema_profiler import summarize_payload

logger = logging.getLogger(__name__)


def _ensure_serializable(payload) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(payload), ensure_ascii=False)


def _smart_default_summary(payload, max_chars: int) -> str:
    """
    生成智能默认摘要（无LLM时使用）。

    根据数据类型提取关键信息，而不是简单截断。
    """
    if not isinstance(payload, dict):
        text = _ensure_serializable(payload)
        return (text[: max_chars - 3] + "...") if len(text) > max_chars else text

    data_type = payload.get("type", "unknown")

    # 数据获取类
    if data_type == "rss_public_data":
        items = payload.get("items", [])
        count = len(items)
        feed_title = payload.get("feed_title", "未知来源")

        if items and isinstance(items[0], dict):
            first_title = items[0].get("title", "")[:30]
            return f"{feed_title}获取{count}条数据。最新: {first_title}..."
        return f"{feed_title}获取{count}条数据"

    # 数据过滤类
    if data_type == "data_filter":
        total_before = payload.get("total_before_filter", 0)
        total_after = payload.get("total_after_filter", 0)
        returned = payload.get("returned", 0)
        return f"从{total_before}条中筛选出{total_after}条，返回{returned}条"

    # 数据聚合类
    if data_type == "data_aggregation":
        groups = payload.get("groups", [])
        total = payload.get("total_groups", len(groups))
        return f"聚合统计完成，共{total}个分组"

    # 数据对比类
    if data_type == "data_comparison":
        common = len(payload.get("common_themes", []))
        diff = len(payload.get("differences", []))
        return f"对比完成，发现{common}个共同主题，{diff}个差异点"

    # 洞察提取类
    if data_type == "insight_extraction":
        insights = payload.get("insights", [])
        return f"提取{len(insights)}个核心洞察"

    # 数据源发现类
    if data_type == "source_discovery":
        public = len(payload.get("public_sources", []))
        private = len(payload.get("private_sources", []))
        return f"发现{public}个公开数据源，{private}个私有数据源"

    # 用户澄清类
    if data_type == "user_clarification":
        question = payload.get("question", "未知问题")
        return f"等待用户澄清: {question[:50]}"

    # 默认：截断
    text = _ensure_serializable(payload)
    return (text[: max_chars - 3] + "...") if len(text) > max_chars else text


def _default_summary(payload, max_chars: int) -> str:
    """向后兼容的默认摘要函数。"""
    return _smart_default_summary(payload, max_chars)


def create_data_stasher_node(runtime: LangGraphRuntime):
    summarizer_prompt = load_prompt("summarizer_system.txt")

    def summarize(raw_output: object, state: GraphState) -> str:
        if runtime.summarizer_llm is None:
            return _default_summary(raw_output, runtime.cheap_summary_max_chars)
        prompt = (
            f"{summarizer_prompt}\n\n"
            f"original_query: {state.get('original_query','')}\n"
            f"raw_data:\n{_ensure_serializable(raw_output)}"
        )
        try:
            text = runtime.summarizer_llm.generate(prompt, temperature=0.2)
            text = text.strip()
            if not text:
                raise ValueError("empty summary")
            return text[: runtime.cheap_summary_max_chars]
        except Exception as exc:
            logger.warning("摘要 LLM 失败，使用兜底摘要: %s", exc)
            return _default_summary(raw_output, runtime.cheap_summary_max_chars)

    def node(state: GraphState) -> Dict[str, object]:
        pending: ToolExecutionPayload | None = state.get("pending_tool_result")
        if pending is None:
            return {}

        raw_output = pending.raw_output

        # V5.0 P0: 优化人机交互流程
        # needs_user_input 状态不存储到 data_store，避免污染数据
        if pending.status == "needs_user_input":
            data_id = None
            summary = f"等待用户澄清: {raw_output.get('question', '未知问题')}"
            logger.info(
                "DataStasher: 跳过存储 needs_user_input 状态 (step=%s)",
                pending.call.step_id
            )
        else:
            # 正常数据：保存到 data_store
            data_id = runtime.data_store.save(raw_output)
            summary = summarize(raw_output, state)
            logger.info(
                "DataStasher 完成: step=%s tool=%s data_id=%s",
                pending.call.step_id,
                pending.call.plugin_id,
                data_id,
            )
            if isinstance(raw_output, dict):
                schema_info = summarize_payload(raw_output)
                runtime.schema_registry.register(
                    data_id,
                    raw_schema=schema_info.get("schema", {}),
                    samples=schema_info.get("samples", []),
                    metadata=schema_info.get("metadata") or {"sample_count": schema_info.get("sample_count", 0)},
                )

        data_ref = DataReference(
            step_id=pending.call.step_id,
            tool_name=pending.call.plugin_id,
            data_id=data_id,
            summary=summary,
            status=pending.status,
            error_message=pending.error_message,
        )

        data_stash: List[DataReference] = list(state.get("data_stash", []))
        data_stash.append(data_ref)

        # V5.0 P0: 保留 last_tool_result 供 Reflector 检查状态
        return {
            "data_stash": data_stash,
            "pending_tool_result": None,
            "last_tool_result": pending,
        }

    return node
