from __future__ import annotations

"""LangGraph 工具：在研究过程中推送实时数据卡片预览。"""

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

# 常量定义
MAX_PREVIEW_ITEMS = 20  # 单张预览卡片最多显示的记录数
MAX_PREVIEW_FIELDS = 3  # 每条记录最多保留的字段数，避免 payload 过大

from services.data_query_service import DataQueryResult, QueryDataset
from services.panel.panel_generator import PanelGenerator, PanelBlockInput
from api.schemas.panel import SourceInfo

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool
from .data_ref_resolver import create_resolver_from_context, ResolvedData
from .data_payload_utils import unwrap_payload, extract_records, build_source_metadata, select_non_empty

logger = logging.getLogger(__name__)
_PANEL_GENERATOR = PanelGenerator()


def register_panel_stream_tool(registry: ToolRegistry) -> None:
    """注册 emit_panel_preview 工具，用于查询公共数据并推送到前端。"""

    @tool(
        registry,
        plugin_id="emit_panel_preview",
        description="将已有数据引用渲染为面板，并将结果以卡片形式实时推送给前端（只显示前几条记录）",
        schema={
            "type": "object",
            "properties": {
                "source_ref": {
                    "type": ["string", "integer"],
                    "description": "数据引用（data_id 或 $step.N），指向需要渲染的记录",
                },
                "query": {"type": "string", "description": "自然语言查询（兼容模式，可选）"},
                "filter_datasource": {"type": "string", "description": "限定数据源（仅 query 模式有效）"},
                "max_items": {
                    "type": "integer",
                    "description": "单张卡片包含的最大记录数（默认 6 条）",
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": [],
        },
    )
    def emit_panel_preview(call: ToolCall, context: ToolExecutionContext) -> ToolExecutionPayload:
        dq = context.data_query_service
        extras = context.extras or {}
        emitter = extras.get("emit_panel_preview")
        data_store = extras.get("data_store")

        if emitter is None:
            logger.warning("emit_panel_preview 工具未注入回调，跳过实时卡片推送")
            return ToolExecutionPayload(
                call=call,
                raw_output={"type": "panel_preview", "skipped": True, "reason": "callback_not_available"},
                status="success",
            )

        source_ref = call.args.get("source_ref")
        query = call.args.get("query")
        if not source_ref and not query:
            raise ValueError("emit_panel_preview 需要提供 query 或 source_ref 字段")

        filter_ds: Optional[str] = call.args.get("filter_datasource")
        try:
            max_items = int(call.args.get("max_items", 6) or 6)
        except (TypeError, ValueError):
            max_items = 6
        max_items = max(1, min(max_items, MAX_PREVIEW_ITEMS))

        if source_ref:
            if data_store is None:
                raise RuntimeError("数据存储不可用，无法通过 source_ref 渲染面板")
            preview_payload = _build_panel_from_source_ref(
                source_ref=source_ref,
                context=context,
                data_store=data_store,
                max_items=max_items,
            )
        else:
            if dq is None:
                raise RuntimeError("DataQueryService 未注入，无法根据 query 获取数据")
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
            preview_payload = {"previews": previews, "query": query}

        emitter(preview_payload)

        return ToolExecutionPayload(
            call=call,
            raw_output={
                "type": "panel_preview",
                "count": len(preview_payload.get("previews", [])),
                "has_panel_payload": "panel_payload" in preview_payload,
            },
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


def _build_panel_from_source_ref(
    source_ref: Any,
    context: ToolExecutionContext,
    data_store,
    *,
    max_items: int,
) -> Dict[str, Any]:
    resolver = create_resolver_from_context(context)
    if resolver is None:
        raise ValueError("无法解析数据引用：缺少 data_store")

    resolved: ResolvedData = resolver.resolve(source_ref, require_success=False)
    envelope = resolved.data
    if not isinstance(envelope, dict):
        raise ValueError("source_ref 指向的内容不是 dict，无法渲染")

    dataset_payload, payload_ref = unwrap_payload(envelope, data_store)
    if not isinstance(dataset_payload, dict):
        raise ValueError("无法解析数据内容，缺少 payload 结构")

    source_metadata = build_source_metadata(dataset_payload, resolved.source_data_id, resolved.source_step_id, payload_ref)
    envelope_meta = envelope.get("metadata") or {}
    stats = dict(envelope_meta)
    stats.setdefault("instruction", envelope_meta.get("instruction"))
    stats.update({k: v for k, v in source_metadata.items() if v is not None})

    route = select_non_empty(
        envelope.get("generated_path"),
        dataset_payload.get("generated_path"),
        dataset_payload.get("route"),
        stats.get("generated_path"),
        stats.get("route"),
    )
    if not route:
        raise ValueError("缺少 generated_path，无法确定面板适配器")

    preview_source_records = extract_records(dataset_payload)
    if not preview_source_records:
        if isinstance(dataset_payload, dict):
            logger.warning(
                "emit_panel_preview: 无 items 字段，使用 payload 作为单条记录 (source_ref=%s data_id=%s route=%s)",
                source_ref,
                resolved.source_data_id,
                route,
            )
            preview_source_records = [dataset_payload]
        else:
            raise ValueError("数据为空，无法渲染面板")

    datasource = stats.get("source_datasource") or stats.get("datasource") or dataset_payload.get("source") or "rsshub"
    source_info = SourceInfo(
        datasource=datasource,
        route=route,
        params={},
        fetched_at=None,
        request_id=None,
    )

    block_input = PanelBlockInput(
        block_id=f"panel-{uuid4().hex[:8]}",
        records=preview_source_records,
        source_info=source_info,
        title=dataset_payload.get("feed_title") or dataset_payload.get("title"),
        full_data_ref=resolved.source_data_id,
        stats=stats,
        requested_components=None,
    )

    panel_result = _PANEL_GENERATOR.generate(mode="append", block_inputs=[block_input])

    preview_items = [_trim_record(record) for record in preview_source_records[:max_items]]
    preview_payload = {
        "previews": [
            {
                "preview_id": f"{resolved.source_data_id or source_ref}-{uuid4().hex[:6]}",
                "title": dataset_payload.get("feed_title") or envelope_meta.get("instruction") or "数据预览",
                "items": preview_items,
                "generated_path": route,
                "source": datasource,
            }
        ],
        "panel_payload": panel_result.payload.model_dump(),
        "panel_data_blocks": {key: block.model_dump() for key, block in panel_result.data_blocks.items()},
        "source_query": envelope_meta.get("instruction") or dataset_payload.get("feed_title") or route,
        "stats": stats,
    }
    return preview_payload
