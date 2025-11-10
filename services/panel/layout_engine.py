"""
根据UI块生成布局树的简单布局引擎。
"""

import uuid
import math
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
        batch_id = uuid.uuid4().hex[:8]

        grid_columns = 12
        base_row_height = 220
        current_x = 0
        current_y = 0
        current_row_height = 1

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

            width_units = grid_columns
            if span is not None:
                try:
                    width_units = max(1, min(int(span), grid_columns))
                except (ValueError, TypeError):
                    width_units = grid_columns

            if hint and hint.order is not None:
                props["order"] = hint.order
            if hint and hint.priority is not None:
                props["priority"] = hint.priority
            if hint and hint.min_height is not None:
                props["min_height"] = hint.min_height
            if hint and hint.responsive:
                props["responsive"] = hint.responsive

            min_height = None
            if hint and hint.min_height is not None:
                min_height = hint.min_height
            elif block.options:
                min_height = block.options.get("min_height") or block.options.get("minHeight")
            height_units = max(1, math.ceil((min_height or base_row_height) / base_row_height))

            if current_x + width_units > grid_columns:
                current_x = 0
                current_y += current_row_height
                current_row_height = 1

            props["grid"] = {
                "x": current_x,
                "y": current_y,
                "w": width_units,
                "h": height_units,
                "minH": max(1, math.ceil((min_height or base_row_height) / base_row_height)),
            }

            current_x += width_units
            current_row_height = max(current_row_height, height_units)
            if current_x >= grid_columns:
                current_x = 0
                current_y += current_row_height
                current_row_height = 1

            nodes.append(
                LayoutNode(
                    type="row",
                    id=node_id,
                    children=[block.id],
                    props=props,
                )
            )

        return LayoutTree(mode=mode, nodes=nodes, history_token=history_token)
