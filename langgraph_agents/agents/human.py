from __future__ import annotations

"""人类回路节点。"""

from typing import Dict

from ..state import GraphState


def create_wait_for_human_node():
    def node(state: GraphState) -> Dict[str, str]:
        reflection = state.get("reflection")
        request = (
            reflection.reasoning
            if reflection
            else "需要用户提供更多上下文以继续研究。"
        )
        return {"human_in_loop_request": request}

    return node

