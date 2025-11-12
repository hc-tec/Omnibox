from __future__ import annotations

"""LangGraph 工具：在研究过程中推送实时数据卡片预览。"""

import logging
from typing import Any, Dict, List, Optional

# 常量定义
MAX_PREVIEW_ITEMS = 20  # 单张预览卡片最多显示的记录数
MAX_PREVIEW_FIELDS = 3  # 每条记录最多保留的字段数，避免 payload 过大

from services.data_query_service import DataQueryResult, QueryDataset

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool

logger = logging.getLogger(__name__)


def register_panel_stream_tool(registry: ToolRegistry) -> None:
    """注册 emit_panel_preview 工具，用于查询公共数据并推送到前端。"""

    @tool(
        registry,
        plugin_id="emit_panel_preview",
        description="查询公共数据并将结果以卡片形式实时推送给前端（只显示前几条记录）",
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言查询"},
                "filter_datasource": {"type": "string", "description": "限定数据源（可选）"},
                "max_items": {
                    "type": "integer",
                    "description": "单张卡片包含的最大记录数（默认 6 条）",
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
        },
    )
    def emit_panel_preview(call: ToolCall, context: ToolExecutionContext) -> ToolExecutionPayload:
        dq = context.data_query_service
        emitter = (context.extras or {}).get("emit_panel_preview")

        if dq is None or emitter is None:
            raise RuntimeError("ResearchService 未注入 DataQueryService 或事件回调，无法推送面板数据")

        query = call.args.get("query")
        if not query:
            raise ValueError("emit_panel_preview 需要提供 query 字段")

        filter_ds: Optional[str] = call.args.get("filter_datasource")
        try:
            max_items = int(call.args.get("max_items", 6) or 6)
        except (TypeError, ValueError):
            max_items = 6
        max_items = max(1, min(max_items, MAX_PREVIEW_ITEMS))

        logger.info("ResearchService emit_panel_preview: %s", query)
        result = dq.query(
            user_query=query,
            filter_datasource=filter_ds,
            use_cache=True,
        )

        if result.status != "success":
            error_msg = result.reasoning or "数据查询失败"
            logger.warning("emit_panel_preview 查询失败: %s", error_msg)
            return ToolExecutionPayload(
                call=call,
                raw_output={"type": "panel_preview", "status": result.status, "reasoning": error_msg},
                status="error",
                error_message=error_msg,
            )

        previews = _build_preview_payload(result, max_items=max_items)
        emitter({"previews": previews, "query": query})

        return ToolExecutionPayload(
            call=call,
            raw_output={"type": "panel_preview", "count": len(previews)},
            status="success",
        )


def _build_preview_payload(result: DataQueryResult, max_items: int) -> List[Dict[str, Any]]:
    """构建预览数据负载（统一使用 QueryDataset 类型）。"""
    # 统一转换为 QueryDataset 类型
    datasets: List[QueryDataset] = result.datasets or []
    if not datasets:
        # 从 DataQueryResult 构造单个数据集
        datasets = [
            QueryDataset(
                route_id=None,
                provider=None,
                name=result.feed_title,
                generated_path=result.generated_path,
                items=result.items,
                feed_title=result.feed_title,
                source=result.source,
                cache_hit=result.cache_hit,
                reasoning=result.reasoning,
                payload=result.payload,
            )
        ]

    previews: List[Dict[str, Any]] = []
    for dataset in datasets:
        # 此时确保 dataset 一定是 QueryDataset 类型
        sliced = (dataset.items or [])[:max_items]
        preview_items = [_trim_record(record) for record in sliced]
        previews.append(
            {
                "preview_id": f"{dataset.generated_path or 'dataset'}-{len(previews)+1}",
                "title": dataset.feed_title or "数据卡片",
                "items": preview_items,
                "generated_path": dataset.generated_path,
                "source": dataset.source,
            }
        )
    return previews


def _trim_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """仅保留前N个字段，避免 payload 过大。"""
    if not isinstance(record, dict):
        return {"value": record}
    trimmed = list(record.items())[:MAX_PREVIEW_FIELDS]
    return {key: value for key, value in trimmed}
