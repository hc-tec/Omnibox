from __future__ import annotations

"""ReflectorAgent 节点实现。"""

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


def create_reflector_node(runtime: LangGraphRuntime):
    system_prompt = load_prompt("reflector_system.txt")

    def node(state: GraphState) -> Dict[str, Reflection]:
        query = state.get("original_query", "")
        if not query:
            raise ValueError("ReflectorAgent: original_query 为空或缺失")
        data_stash = state.get("data_stash", [])
        prompt = (
            f"{system_prompt}\n\n"
            f"original_query:\n{query}\n\n"
            f"collected_data:\n{_format_summaries(data_stash)}"
        )
        # 使用重试装饰器包装 LLM 调用
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def call_llm():
            return runtime.reflector_llm.generate(prompt, temperature=0.1)

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

