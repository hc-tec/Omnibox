from __future__ import annotations

"""DataStasher 节点实现。"""

import json
import logging
from typing import Dict, List

from ..prompt_loader import load_prompt
from ..runtime import LangGraphRuntime
from ..state import DataReference, GraphState, ToolExecutionPayload

logger = logging.getLogger(__name__)


def _ensure_serializable(payload) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(payload), ensure_ascii=False)


def _default_summary(payload, max_chars: int) -> str:
    text = _ensure_serializable(payload)
    return (text[: max_chars - 3] + "...") if len(text) > max_chars else text


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
        data_id = runtime.data_store.save(raw_output)
        summary = summarize(raw_output, state)
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
        logger.info(
            "DataStasher 完成: step=%s tool=%s data_id=%s",
            data_ref.step_id,
            data_ref.tool_name,
            data_id,
        )
        return {"data_stash": data_stash, "pending_tool_result": None}

    return node

