from __future__ import annotations

"""RouterAgent 节点实现。"""

import logging
from typing import Dict

from ..json_utils import parse_json_payload
from ..llm_retry import retry_with_backoff
from ..prompt_loader import load_prompt
from ..runtime import LangGraphRuntime
from ..state import GraphState, RouterDecision

logger = logging.getLogger(__name__)


def create_router_node(runtime: LangGraphRuntime):
    system_prompt = load_prompt("router_system.txt")

    def node(state: GraphState) -> Dict[str, RouterDecision]:
        query = state.get("original_query", "")
        if not query:
            raise ValueError("RouterAgent: original_query 为空或缺失")
        history = "\n".join(state.get("chat_history", [])) or "（无历史）"
        prompt = (
            f"{system_prompt}\n\n"
            f"historic_messages:\n{history}\n\n"
            f"original_query:\n{query}\n"
        )
        # 使用重试装饰器包装 LLM 调用
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def call_llm():
            return runtime.router_llm.generate(prompt, temperature=0.0)

        try:
            response = call_llm()
            data = parse_json_payload(response)
            decision = RouterDecision(route=data["route"], reasoning=data.get("reasoning", ""))
        except Exception as exc:
            # 仅捕获解析错误，LLM调用错误由重试机制处理
            logger.warning("RouterAgent 解析失败，回退至 complex_research: %s", exc)
            decision = RouterDecision(route="complex_research", reasoning=f"解析错误: {exc}")
        return {"router_decision": decision}

    return node

