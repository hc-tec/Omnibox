"""
根据UI块生成布局树的简单布局引擎。
"""

import uuid
from typing import Dict, List, Optional

from api.schemas.panel import LayoutHint, LayoutNode, LayoutTree, UIBlock


class LayoutEngine:
    """依据组件顺序生成布局树结构。"""

    def build(
        self,
        mode: str,
        blocks: List[UIBlock],
        layout_hints: Optional[Dict[str, LayoutHint]] = None,
        history_token: Optional[str] = None,
    ) -> LayoutTree:
        layout_hints = layout_hints or {}
        nodes: List[LayoutNode] = []
        # 使用 UUID 确保每次生成的 node id 唯一，支持 append 模式
        batch_id = uuid.uuid4().hex[:8]
        for index, block in enumerate(blocks, start=1):
            node_id = f"row-{batch_id}-{index}"
            hint = layout_hints.get(block.id)
            props: Dict[str, object] = {}

            span = None
            if hint and hint.span is not None:
                span = hint.span
            else:
                span = (
                    (block.options or {}).get("span")
                    if block.options
                    else (block.props or {}).get("span")
                )
            if span:
                props["span"] = span

            if hint and hint.order is not None:
                props["order"] = hint.order
            if hint and hint.priority is not None:
                props["priority"] = hint.priority
            if hint and hint.min_height is not None:
                props["min_height"] = hint.min_height
            if hint and hint.responsive:
                props["responsive"] = hint.responsive

            nodes.append(
                LayoutNode(
                    type="row",
                    id=node_id,
                    children=[block.id],
                    props=props,
                )
            )

        return LayoutTree(mode=mode, nodes=nodes, history_token=history_token)
