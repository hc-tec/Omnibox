from __future__ import annotations

"""对接现有 DataQueryService 的公共数据工具。"""

import logging
from typing import Any, Dict, Optional

from services.data_query_service import DataQueryResult

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool

logger = logging.getLogger(__name__)


def _format_success_payload(
    result: DataQueryResult,
    *,
    payload_ref: Optional[str] = None,
    inline_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """格式化成功响应的 payload（纯粹的数据获取结果）。"""
    datasets_meta = [
        dataset.to_metadata()
        for dataset in (result.datasets or [])
        if hasattr(dataset, "to_metadata")
    ]
    payload_section: Dict[str, Any] = {}
    if payload_ref:
        payload_section["payload_ref"] = payload_ref
    elif inline_payload:
        payload_section["payload"] = inline_payload
    elif result.payload:
        payload_section["payload"] = result.payload
    return {
        "type": "rss_public_data",
        "feed_title": result.feed_title,
        "generated_path": result.generated_path,
        "items": result.items,
        "item_count": len(result.items),
        "source": result.source,
        "cache_hit": result.cache_hit,
        "reasoning": result.reasoning,
        "datasets": datasets_meta,
        **payload_section,
    }


def register_public_data_tool(registry: ToolRegistry) -> None:
    """向注册表写入 fetch_public_data 工具。"""

    @tool(
        registry,
        plugin_id="fetch_public_data",
        description="使用 DataQueryService 查询 RSSHub 公共数据",
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言查询"},
                "filter_datasource": {
                    "type": "string",
                    "description": "限制特定数据源（可选）",
                },
            },
            "required": ["query"],
        },
    )
    def fetch_public_data(
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        dq = context.data_query_service
        extras = context.extras or {}
        data_store = extras.get("data_store")
        if dq is None:
            raise RuntimeError("DataQueryService 未注入，无法调用 fetch_public_data")

        query = call.args.get("query")
        if not query:
            raise ValueError("fetch_public_data 需要 query 参数")

        filter_ds: Optional[str] = call.args.get("filter_datasource")
        logger.info("调用 DataQueryService: %s", query)
        result = dq.query(
            user_query=query,
            filter_datasource=filter_ds,
            use_cache=True,
            raw_mode=True,
        )

        if result.status == "success":
            payload_ref: Optional[str] = None
            inline_payload: Optional[Dict[str, Any]] = None
            if result.payload:
                if data_store is not None:
                    payload_ref = data_store.save(result.payload)
                else:
                    inline_payload = result.payload
            payload = _format_success_payload(result, payload_ref=payload_ref, inline_payload=inline_payload)
            return ToolExecutionPayload(call=call, raw_output=payload, status="success")

        # V5.0 修复：needs_clarification 应该触发用户澄清流程，而非返回 error
        if result.status == "needs_clarification":
            clarification_msg = result.clarification_question or result.reasoning or "需要更多信息"
            logger.info("fetch_public_data 需要澄清: %s", clarification_msg)
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "clarification_request",
                    "question": clarification_msg,
                    "original_query": query,
                    "reasoning": result.reasoning,
                },
                status="needs_user_input",
                error_message=None,
            )

        # 其他非成功状态（not_found, error 等）
        error_msg = result.reasoning or "DataQueryService 返回非 success"
        logger.warning("fetch_public_data 失败: %s", error_msg)
        return ToolExecutionPayload(
            call=call,
            raw_output={
                "type": "rss_public_data",
                "status": result.status,
                "clarification_question": result.clarification_question,
                "reasoning": result.reasoning,
            },
            status="error",
            error_message=error_msg,
        )
