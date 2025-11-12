from __future__ import annotations

"""对接现有 DataQueryService 的公共数据工具。"""

import logging
from typing import Any, Dict, Optional

from services.data_query_service import DataQueryResult

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool

logger = logging.getLogger(__name__)


def _format_success_payload(result: DataQueryResult) -> Dict[str, Any]:
    return {
        "type": "rss_public_data",
        "feed_title": result.feed_title,
        "generated_path": result.generated_path,
        "items": result.items,
        "source": result.source,
        "cache_hit": result.cache_hit,
        "reasoning": result.reasoning,
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
        )

        if result.status == "success":
            payload = _format_success_payload(result)
            return ToolExecutionPayload(call=call, raw_output=payload, status="success")

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

