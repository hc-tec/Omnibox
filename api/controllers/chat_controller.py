"""
对话控制器
职责：处理聊天相关的REST API请求
"""

import logging
import os
from typing import Optional, Any, Dict
from dataclasses import dataclass, field
from fastapi import APIRouter, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.schemas.responses import ChatRequest, ChatResponse, ResponseMetadata, ErrorResponse
from api.schemas.panel import (
    PanelPayload,
    UIBlock,
    LayoutTree,
    LayoutNode,
    DataBlock,
    SchemaSummary,
    SchemaFieldSummary,
    SourceInfo,
)

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/v1", tags=["chat"])

# 全局服务实例（应用启动时初始化）
_chat_service: Any = None
_service_mode: str = "uninitialized"  # mock / production / uninitialized



@dataclass
class SimpleChatResponse:
    success: bool
    intent_type: str
    message: str
    data: Optional[PanelPayload] = None
    data_blocks: Dict[str, DataBlock] = field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None


class MockChatService:
    """本地/测试环境使用的模拟ChatService"""

    def __init__(self):
        self.data_query_service = None
        logger.warning("使用 MockChatService（跳过RAG/LLM初始化）")

    def chat(self, user_query: str, filter_datasource: Optional[str] = None, use_cache: bool = True) -> SimpleChatResponse:
        """返回模拟响应，满足测试和本地无依赖场景"""
        normalized = (user_query or "").strip()
        if not normalized:
            normalized = "模拟查询"

        greetings = {"你好", "您好", "hi", "hello"}
        intent_type = "chitchat" if any(greet in normalized.lower() for greet in greetings) else "data_query"

        if intent_type == "data_query":
            block_records = [
                {
                    "title": f"模拟数据：{normalized}",
                    "link": "https://example.com/mock",
                    "description": "这是模拟数据，用于本地/测试环境。",
                    "pubDate": None,
                    "author": "mock",
                }
            ]
            schema_summary = SchemaSummary(
                fields=[
                    SchemaFieldSummary(name="title", type="text", sample=[block_records[0]["title"]]),
                    SchemaFieldSummary(name="link", type="url", sample=[block_records[0]["link"]]),
                    SchemaFieldSummary(name="description", type="text", sample=[block_records[0]["description"]]),
                ],
                stats={"total": 1},
                schema_digest="List(title:text/link:url/description:text)",
            )
            data_block = DataBlock(
                id="data_block_mock",
                source_info=SourceInfo(
                    datasource="mock",
                    route="/mock/path",
                    params={"query": normalized},
                    fetched_at=None,
                    request_id="mock-request",
                ),
                records=block_records,
                stats={"total": 1},
                schema_summary=schema_summary,
                full_data_ref=None,
            )
            ui_block = UIBlock(
                id="block-mock-1",
                component="ListPanel",
                data_ref=data_block.id,
                data={
                    "items": block_records,
                    "schema": schema_summary.model_dump(),
                    "stats": data_block.stats,
                },
                props={
                    "title_field": "title",
                    "link_field": "link",
                    "description_field": "description",
                },
                options={"show_description": True, "span": 12},
                interactions=[],
                confidence=0.9,
                title=f"模拟数据：{normalized}",
            )
            layout = LayoutTree(
                mode="append",
                nodes=[
                    LayoutNode(
                        type="row",
                        id="row-1",
                        children=[ui_block.id],
                        props={"span": 12, "min_height": 320},
                    )
                ],
                history_token=None,
            )
            panel_payload = PanelPayload(mode="append", layout=layout, blocks=[ui_block])
            message = f"已获取模拟数据「{normalized}」共{len(block_records)}条（mock）"
            metadata = {
                "intent_type": intent_type,
                "intent_confidence": 0.9,
                "generated_path": "/mock/path",
                "source": "mock",
                "cache_hit": "none",
                "feed_title": "模拟数据源",
                "status": "success",
                "reasoning": "mock-service-success",
                "component_confidence": {"block-mock-1": 0.9},
            }
            data_blocks = {data_block.id: data_block}
        else:
            panel_payload = None
            data_blocks = {}
            message = "你好！这是模拟闲聊响应，我可以在真实模式下帮你获取RSS数据。"
            metadata = {
                "intent_type": intent_type,
                "intent_confidence": 0.85,
                "generated_path": None,
                "source": "mock",
                "cache_hit": "none",
                "feed_title": None,
                "status": "success",
                "reasoning": "mock-service-chitchat",
            }

        return SimpleChatResponse(
            success=True,
            intent_type=intent_type,
            message=message,
            data=panel_payload,
            data_blocks=data_blocks,
            metadata=metadata,
        )

    def close(self) -> None:
        logger.info("MockChatService关闭")

def get_chat_service() -> Any:
    """
    获取ChatService实例（依赖注入）

    Returns:
        ChatService实例
    """
    global _chat_service
    if _chat_service is None:
        raise HTTPException(
            status_code=503,
            detail="服务未初始化，请先调用initialize_services()"
        )
    return _chat_service


def initialize_services():
    """初始化服务（应用启动时调用）"""
    global _chat_service, _service_mode

    mode = os.getenv("CHAT_SERVICE_MODE", "auto").lower()
    if mode not in {"auto", "mock", "production"}:
        logger.warning("CHAT_SERVICE_MODE=%s 无效，回退为 auto", mode)
        mode = "auto"

    if mode == "mock":
        _chat_service = MockChatService()
        _service_mode = "mock"
        return

    try:
        from orchestrator.rag_in_action import create_rag_in_action
        from services.data_query_service import DataQueryService
        from services.chat_service import ChatService
        logger.info("初始化服务（模式：%s）...", mode)

        rag_in_action = create_rag_in_action()
        data_query_service = DataQueryService(rag_in_action)
        _chat_service = ChatService(
            data_query_service,
            manage_data_service=True,
        )
        _service_mode = "production"
        logger.info("✓ 服务初始化完成（production模式）")

    except Exception as e:
        logger.error(f"服务初始化失败: {e}", exc_info=True)
        if mode == "production":
            raise

        logger.warning("无法初始化真实服务，回退至MockChatService（auto模式）")
        _chat_service = MockChatService()
        _service_mode = "mock"


def shutdown_services():
    """关闭服务（应用关闭时调用）"""
    global _chat_service, _service_mode

    if _chat_service is not None:
        try:
            logger.info("关闭服务...")
            _chat_service.close()
            logger.info("✓ 服务已关闭")
        except Exception as e:
            logger.error(f"服务关闭失败: {e}", exc_info=True)
        finally:
            _chat_service = None
            _service_mode = "uninitialized"


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        200: {"description": "成功", "model": ChatResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器内部错误", "model": ErrorResponse},
        503: {"description": "服务不可用", "model": ErrorResponse},
    },
    summary="对话接口",
    description="处理用户查询，自动识别意图并返回数据或闲聊响应"
)
async def chat(
    request: ChatRequest,
    chat_service: Any = Depends(get_chat_service)
) -> ChatResponse:
    """
    对话接口

    处理流程：
    1. 意图识别（数据查询/闲聊）
    2. 根据意图路由到对应服务
    3. 返回统一格式的响应

    Args:
        request: 对话请求（包含query、filter_datasource、use_cache）
        chat_service: ChatService实例（依赖注入）

    Returns:
        ChatResponse: 对话响应

    Raises:
        HTTPException: 请求参数错误或服务器错误
    """
    try:
        logger.info(f"收到对话请求: {request.query}")

        # 使用run_in_threadpool避免阻塞事件循环
        # ChatService是同步实现，需要在线程池中执行
        response = await run_in_threadpool(
            chat_service.chat,
            user_query=request.query,
            filter_datasource=request.filter_datasource,
            use_cache=request.use_cache,
            layout_snapshot=request.layout_snapshot,
        )

        metadata = None
        if response.metadata:
            # 确保所有字段都传递，即使是None值
            metadata = ResponseMetadata(
                intent_type=response.metadata.get("intent_type"),
                intent_confidence=response.metadata.get("intent_confidence"),
                generated_path=response.metadata.get("generated_path"),
                source=response.metadata.get("source"),
                cache_hit=response.metadata.get("cache_hit"),
                feed_title=response.metadata.get("feed_title"),
                status=response.metadata.get("status"),
                reasoning=response.metadata.get("reasoning"),
                component_confidence=response.metadata.get("component_confidence"),
                debug=response.metadata.get("debug"),
            )

        return ChatResponse(
            success=response.success,
            message=response.message,
            data=response.data,
            data_blocks=response.data_blocks,
            metadata=metadata,
        )

    except Exception as e:
        logger.error(f"对话请求处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"服务器内部错误: {str(e)}"
        )


@router.get(
    "/health",
    response_model=dict,
    summary="健康检查",
    description="检查服务健康状态"
)
async def health_check() -> dict:
    """健康检查接口"""
    try:
        if _chat_service is None:
            return {
                "status": "unhealthy",
                "version": "1.0.0",
                "mode": _service_mode,
                "services": {
                    "chat_service": "not_initialized",
                    "rsshub": "unknown",
                    "rag": "unknown",
                    "cache": "unknown",
                },
            }

        if _service_mode == "mock":
            return {
                "status": "healthy",
                "version": "1.0.0",
                "mode": "mock",
                "services": {
                    "chat_service": "mock",
                    "rsshub": "mock",
                    "rag": "mock",
                    "cache": "mock",
                },
            }

        rsshub_status = "unknown"
        try:
            data_service = getattr(_chat_service, "data_query_service", None)
            if data_service and getattr(data_service, "data_executor", None):
                data_executor = data_service.data_executor
                if data_executor.ensure_rsshub_alive():
                    rsshub_status = "local"
                else:
                    rsshub_status = "fallback"
            else:
                rsshub_status = "unknown"
        except Exception as exc:
            logger.warning(f"RSSHub健康检查失败: {exc}")
            rsshub_status = "error"

        return {
            "status": "healthy",
            "version": "1.0.0",
            "mode": _service_mode,
            "services": {
                "chat_service": "ready",
                "rsshub": rsshub_status,
                "rag": "ready",
                "cache": "ready",
            },
        }

    except Exception as exc:
        logger.error(f"健康检查失败: {exc}", exc_info=True)
        return {
            "status": "unhealthy",
            "version": "1.0.0",
            "mode": _service_mode,
            "error": str(exc),
        }


@router.get(
    "/metrics",
    response_model=dict,
    summary="运维指标",
    description="获取系统运行指标（缓存命中率、降级次数、响应耗时等）"
)
async def get_metrics() -> dict:
    """
    获取运维指标接口

    返回系统运行统计：
    - 缓存命中率（RAG/RSS）
    - RSSHub降级率
    - API成功率
    - WebSocket连接数
    - 响应耗时统计（平均/P95）
    - 运行时长

    Returns:
        运维指标字典
    """
    try:
        from monitoring import get_metrics_collector

        metrics = get_metrics_collector()
        return {
            "status": "success",
            "data": metrics.get_summary()
        }

    except Exception as e:
        logger.error(f"获取指标失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "data": None
        }

