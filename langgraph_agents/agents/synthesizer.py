from __future__ import annotations

"""SynthesizerAgent 节点实现。"""

import json
import logging
from typing import Dict, List

from ..json_utils import parse_json_payload
from ..llm_retry import retry_with_backoff
from ..prompt_loader import load_prompt
from ..runtime import LangGraphRuntime
from ..state import DataReference, GraphState

logger = logging.getLogger(__name__)


def _build_data_summaries(references: List[DataReference]) -> List[Dict]:
    """
    构建数据引用的摘要信息（仅用于 LLM 推理）。

    重要：不加载完整原始数据，避免超过 LLM token 限制。
    Synthesizer 应该基于数据摘要进行推理，而非原始数据。
    """
    summaries = []
    for ref in references:
        summaries.append(
            {
                "data_id": ref.data_id,
                "tool": ref.tool_name,
                "status": ref.status,
                "summary": ref.summary,  # 只使用摘要，不加载原始数据
            }
        )
    return summaries


def create_synthesizer_node(runtime: LangGraphRuntime):
    system_prompt = load_prompt("synthesizer_system.txt")

    def node(state: GraphState) -> Dict[str, str]:
        query = state.get("original_query", "")
        data_stash = state.get("data_stash", [])
        summaries = _build_data_summaries(data_stash)
        prompt = (
            f"{system_prompt}\n\n"
            f"original_query:\n{query}\n\n"
            f"data_references:\n{json.dumps(summaries, ensure_ascii=False)}"
        )
        # 使用重试装饰器包装 LLM 调用
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def call_llm():
            return runtime.synthesizer_llm.generate(prompt, temperature=0.2, role="synthesizer")

        try:
            response = call_llm()
            parsed = parse_json_payload(response)
            final_report = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.exception("Synthesizer 解析失败: %s", exc)
            final_report = json.dumps(
                {
                    "summary": "生成总结失败",
                    "evidence": [],
                    "next_actions": [],
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )

        return {"final_report": final_report}

    return node

