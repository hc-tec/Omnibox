from __future__ import annotations

"""search_data_sources 工具实现：探索可用数据源。"""

import logging
from typing import Any, Dict, List, Optional

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool

logger = logging.getLogger(__name__)


def _classify_sources(
    retrieved_tools: List[Dict[str, Any]],
    platforms: Optional[List[str]] = None
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    将 RAG 检索到的工具分类为公开数据源和私有数据源。

    Args:
        retrieved_tools: RAG 检索到的工具列表
        platforms: 可选的平台过滤列表

    Returns:
        (public_sources, private_sources) 元组
    """
    public_sources = []
    private_sources = []

    for tool in retrieved_tools:
        # 平台过滤
        if platforms:
            provider = tool.get("provider", "").lower()
            if provider and provider not in [p.lower() for p in platforms]:
                continue

        # 分类：根据是否需要授权
        auth_required = tool.get("requires_auth", False)

        if auth_required:
            # 私有数据源（需要授权）
            private_sources.append({
                "route_id": tool.get("route_id", ""),
                "provider": tool.get("provider", "unknown"),
                "name": tool.get("name", "未命名数据源"),
                "description": tool.get("description", ""),
                "requires_params": tool.get("requires_params", False),
                "auth_status": "unauthorized",  # 默认未授权，后续可扩展
                "auth_method": tool.get("auth_method", "unknown"),  # 授权方式（如 OAuth, Cookie 等）
            })
        else:
            # 公开数据源
            public_sources.append({
                "route_id": tool.get("route_id", ""),
                "provider": tool.get("provider", ""),
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "requires_params": tool.get("requires_params", False)
            })

    return public_sources, private_sources


def register_source_discovery_tool(registry: ToolRegistry) -> None:
    """向注册表注册 search_data_sources 工具。"""

    @tool(
        registry,
        plugin_id="search_data_sources",
        description="探索可用的数据源，支持查询 RSSHub 公开数据和私有数据源",
        schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "自然语言查询（必填）",
                    "minLength": 1,
                    "maxLength": 500,
                    "examples": [
                        "AI Agent 相关视频",
                        "B站播放量超过 50 万的技术视频",
                        "小红书上的 AI 笔记"
                    ]
                },
                "platforms": {
                    "type": "array",
                    "description": "限制特定平台（可选）",
                    "items": {
                        "enum": [
                            "bilibili",
                            "xiaohongshu",
                            "youtube",
                            "douyin",
                            "yuque",
                            "github"
                        ]
                    },
                    "minItems": 1,
                    "maxItems": 10
                }
            },
            "required": ["query"]
        }
    )
    def search_data_sources(
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        """
        探索可用的数据源。

        使用 RAG 检索器查找匹配的数据源，并分类为公开/私有数据源。
        """
        # 1. 参数验证
        query = call.args.get("query")
        if not query:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "source_discovery",
                    "error_code": "E101"
                },
                status="error",
                error_message="缺少必填参数 query"
            )

        platforms = call.args.get("platforms")
        if platforms and not isinstance(platforms, list):
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "source_discovery",
                    "error_code": "E102"
                },
                status="error",
                error_message="参数 platforms 必须是数组类型"
            )

        # 2. 检查依赖
        dq = context.data_query_service
        if dq is None or dq.rag_in_action is None:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "source_discovery",
                    "error_code": "E301"
                },
                status="error",
                error_message="RAG 检索服务不可用"
            )

        try:
            # 3. 调用 DataQueryService 进行 RAG 检索
            logger.info("search_data_sources: 查询='%s', 平台=%s", query, platforms)

            # 使用 DataQueryService.query 获取 RAG 检索结果
            # 注意：这里我们主要关心 retrieved_tools 字段
            result = dq.query(
                user_query=query,
                filter_datasource=platforms[0] if platforms and len(platforms) == 1 else None,
                use_cache=True,
                prefer_single_route=False  # 获取多个候选
            )

            # 4. 提取 retrieved_tools
            retrieved_tools = result.retrieved_tools

            if not retrieved_tools:
                # 空结果（非错误）
                logger.info("search_data_sources: 未找到匹配的数据源")
                return ToolExecutionPayload(
                    call=call,
                    raw_output={
                        "type": "source_discovery",
                        "public_sources": [],
                        "private_sources": [],
                        "auth_required": False,
                        "reasoning": "未找到匹配的数据源，建议扩大搜索范围"
                    },
                    status="success"
                )

            # 5. 分类数据源
            public_sources, private_sources = _classify_sources(retrieved_tools, platforms)

            # 6. 返回结果
            auth_required = len(private_sources) > 0

            logger.info(
                "search_data_sources: 找到 %d 个公开数据源, %d 个私有数据源",
                len(public_sources),
                len(private_sources)
            )

            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "source_discovery",
                    "public_sources": public_sources,
                    "private_sources": private_sources,
                    "auth_required": auth_required,
                    "reasoning": f"通过 RAG 检索找到 {len(retrieved_tools)} 个候选数据源"
                },
                status="success"
            )

        except TimeoutError as e:
            # LLM 调用超时
            logger.error("search_data_sources: LLM 超时 - %s", e)
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "source_discovery",
                    "error_code": "E501"
                },
                status="error",
                error_message=f"LLM 调用超时（超过 30 秒）: {e}"
            )

        except Exception as e:
            # 其他异常
            logger.exception("search_data_sources: 执行失败 - %s", e)
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "source_discovery",
                    "error_code": "E505"
                },
                status="error",
                error_message=f"未预期的异常: {e}"
            )
