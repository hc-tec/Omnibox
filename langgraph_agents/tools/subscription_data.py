from __future__ import annotations

"""订阅数据查询工具（Phase 2 新增）

从用户订阅中查询数据，相比实时搜索更快、更准确。
当用户提到已订阅的UP主/专栏/仓库时，优先使用此工具。
"""

import logging
from typing import Any, Dict, Optional

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool

logger = logging.getLogger(__name__)


def _format_subscription_success_payload(
    subscription_id: int,
    display_name: str,
    path: str,
    action_display_name: str,
    feed_data: Dict[str, Any],
    similarity: float
) -> Dict[str, Any]:
    """格式化订阅查询成功的返回数据"""
    return {
        "type": "subscription_data",
        "subscription_id": subscription_id,
        "display_name": display_name,
        "path": path,
        "action": action_display_name,
        "similarity": similarity,
        "feed_title": feed_data.get("feed_title", display_name),
        "items": feed_data.get("items", []),
        "source": "subscription",
    }


def register_subscription_data_tool(registry: ToolRegistry) -> None:
    """向注册表写入 fetch_subscription_data 工具"""

    @tool(
        registry,
        plugin_id="fetch_subscription_data",
        description=(
            "从用户订阅中查询数据（更快、更准确）。"
            "当用户提到已订阅的UP主/专栏/仓库时优先使用此工具。"
            "支持自然语言查询，如'科技美学的投稿'、'那岩的动态'、'langchain的issues'。"
        ),
        schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "自然语言查询，如'科技美学的投稿视频'、'少数派的最新文章'",
                },
                "subscription_name": {
                    "type": "string",
                    "description": "订阅名称（可选），如果明确知道订阅名可直接指定，避免语义搜索",
                },
            },
            "required": ["query"],
        },
    )
    def fetch_subscription_data(
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        """从订阅系统查询数据

        流程：
        1. 使用 SubscriptionResolver 解析查询
        2. 如果找到匹配订阅，使用 DataQueryService 获取数据
        3. 返回订阅数据
        """
        from services.subscription.subscription_resolver import SubscriptionResolver

        query = call.args.get("query")
        if not query:
            raise ValueError("fetch_subscription_data 需要 query 参数")

        subscription_name = call.args.get("subscription_name")

        # 获取用户 ID（从 context 获取，支持游客模式）
        user_id = context.extras.get("user_id")  # None = 游客模式，查询公共订阅

        if user_id is None:
            logger.info("游客模式：user_id=None，将查询所有公共订阅")

        logger.info(
            f"订阅查询: '{query}' (subscription_name='{subscription_name}', user_id={user_id})"
        )

        try:
            # Step 1: 获取 LLM 客户端
            # 优先从 context.extras 获取，否则创建临时客户端
            llm_client = context.extras.get("llm_client")
            if not llm_client:
                # 创建临时 LLM 客户端
                from query_processor.llm_client import LLMClient
                llm_client = LLMClient()
                logger.warning("未从 context 获取 llm_client，创建临时客户端")

            # Step 2: 解析订阅
            resolver = SubscriptionResolver(llm_client)

            # 如果指定了订阅名称，优先精确匹配
            if subscription_name:
                # TODO: 实现精确匹配逻辑
                logger.info(f"使用精确订阅名称: {subscription_name}")

            result = resolver.resolve(query, user_id, min_similarity=0.7)

            if not result:
                error_msg = f"未找到匹配的订阅（相似度 >= 0.7）: '{query}'"
                logger.info(error_msg)
                return ToolExecutionPayload(
                    call=call,
                    raw_output={
                        "type": "subscription_data",
                        "status": "not_found",
                        "reasoning": error_msg,
                        "suggestion": "可以尝试使用 fetch_public_data 进行实时搜索",
                    },
                    status="error",
                    error_message=error_msg,
                )

            # Step 2: 使用 DataQueryService 获取数据
            dq = context.data_query_service
            if dq is None:
                raise RuntimeError("DataQueryService 未注入")

            path = result["path"]
            logger.info(
                f"订阅匹配成功: '{result['display_name']}' (similarity={result['similarity']:.3f}), "
                f"path='{path}'"
            )

            # 直接使用 RSSHub 路径查询
            feed_result = dq.query(
                user_query=path,  # 使用路径而非自然语言
                filter_datasource="rsshub",  # 明确指定 rsshub
                use_cache=True,
            )

            if feed_result.status == "success":
                payload = _format_subscription_success_payload(
                    subscription_id=result["subscription_id"],
                    display_name=result["display_name"],
                    path=path,
                    action_display_name=result["action_display_name"],
                    feed_data={
                        "feed_title": feed_result.feed_title,
                        "items": feed_result.items,
                    },
                    similarity=result["similarity"],
                )
                logger.info(
                    f"订阅数据获取成功: {len(feed_result.items)} 条数据 "
                    f"(cache_hit={feed_result.cache_hit})"
                )
                return ToolExecutionPayload(
                    call=call, raw_output=payload, status="success"
                )

            # 数据获取失败
            error_msg = (
                f"订阅解析成功，但数据获取失败: {feed_result.reasoning or 'unknown error'}"
            )
            logger.warning(error_msg)
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "subscription_data",
                    "status": feed_result.status,
                    "subscription_id": result["subscription_id"],
                    "display_name": result["display_name"],
                    "path": path,
                    "reasoning": feed_result.reasoning,
                },
                status="error",
                error_message=error_msg,
            )

        except Exception as e:
            error_msg = f"订阅查询失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "subscription_data",
                    "status": "error",
                    "reasoning": error_msg,
                },
                status="error",
                error_message=error_msg,
            )
