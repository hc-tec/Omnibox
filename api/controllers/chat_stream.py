"""
WebSocket流式对话控制器
按阶段推送处理进度：intent → rag → fetch → summary
"""

import logging
import uuid
import time
from typing import Generator, Optional, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.schemas.stream_messages import (
    StageMessage,
    DataMessage,
    ErrorMessage,
    CompleteMessage,
    StreamStage,
    STAGE_DESCRIPTIONS,
    STAGE_PROGRESS,
)
from api.controllers.chat_controller import get_chat_service

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/v1", tags=["chat-stream"])


def generate_stream_id() -> str:
    """
    生成唯一的流ID

    Returns:
        格式为 "stream-{uuid}" 的流ID
    """
    return f"stream-{uuid.uuid4().hex[:12]}"


def stream_chat_processing(
    chat_service: Any,
    user_query: str,
    stream_id: str,
    filter_datasource: Optional[str] = None,
    use_cache: bool = True,
    layout_snapshot: Optional[list[dict]] = None,
) -> Generator[dict, None, None]:
    """
    流式处理对话（同步生成器，在线程池中执行）

    按阶段yield消息：
    1. intent阶段 - 意图识别
    2. rag阶段 - RAG检索（数据查询时）
    3. fetch阶段 - 数据获取
    4. summary阶段 - 结果总结

    Args:
        chat_service: ChatService实例
        user_query: 用户查询
        stream_id: 流ID
        filter_datasource: 数据源过滤
        use_cache: 是否使用缓存

    Yields:
        流式消息字典
    """
    start_time = time.time()

    try:
        # ========== 阶段1: 意图识别 ==========
        yield StageMessage(
            stream_id=stream_id,
            stage=StreamStage.INTENT,
            message=STAGE_DESCRIPTIONS[StreamStage.INTENT],
            progress=STAGE_PROGRESS[StreamStage.INTENT],
        ).model_dump()

        # 调用意图识别（如果chat_service有intent_service属性）
        intent_result = None
        if hasattr(chat_service, 'intent_service') and chat_service.intent_service:
            intent_result = chat_service.intent_service.recognize(user_query)
            yield DataMessage(
                stream_id=stream_id,
                stage=StreamStage.INTENT,
                data={
                    "intent_type": intent_result.intent_type,
                    "confidence": intent_result.confidence,
                    "reasoning": intent_result.reasoning,
                }
            ).model_dump()
        else:
            # MockChatService没有intent_service，直接判断
            greetings = {"你好", "您好", "hi", "hello"}
            intent_type = "chitchat" if any(g in user_query.lower() for g in greetings) else "data_query"
            yield DataMessage(
                stream_id=stream_id,
                stage=StreamStage.INTENT,
                data={
                    "intent_type": intent_type,
                    "confidence": 0.9,
                    "reasoning": "简单规则判断",
                }
            ).model_dump()
            intent_result = type('obj', (object,), {'intent_type': intent_type, 'confidence': 0.9})()

        # ========== 阶段2: RAG检索（仅数据查询需要）==========
        if intent_result.intent_type == "data_query":
            yield StageMessage(
                stream_id=stream_id,
                stage=StreamStage.RAG,
                message=STAGE_DESCRIPTIONS[StreamStage.RAG],
                progress=STAGE_PROGRESS[StreamStage.RAG],
            ).model_dump()

            # RAG检索在chat_service.chat内部完成，这里模拟推送进度
            # 实际场景可以通过回调或事件机制从Service层获取中间结果
            yield DataMessage(
                stream_id=stream_id,
                stage=StreamStage.RAG,
                data={
                    "status": "retrieving",
                    "message": "正在检索相关数据源..."
                }
            ).model_dump()

        # ========== 阶段3: 数据获取 ==========
        yield StageMessage(
            stream_id=stream_id,
            stage=StreamStage.FETCH,
            message=STAGE_DESCRIPTIONS[StreamStage.FETCH],
            progress=STAGE_PROGRESS[StreamStage.FETCH],
        ).model_dump()

        # 调用ChatService获取完整响应
        response = chat_service.chat(
            user_query=user_query,
            filter_datasource=filter_datasource,
            use_cache=use_cache,
            layout_snapshot=layout_snapshot,
        )

        # 推送数据
        items_count = 0
        if getattr(response, "data_blocks", None):
            for block in response.data_blocks.values():
                block_total = 0
                if isinstance(block, dict):
                    block_total = block.get("stats", {}).get("total") or len(block.get("records", []))
                else:
                    block_total = block.stats.get("total") if block.stats else 0
                    if not block_total:
                        block_total = len(block.records)
                items_count += block_total

        panel_block_count = len(response.data.blocks) if response.data else 0

        yield DataMessage(
            stream_id=stream_id,
            stage=StreamStage.FETCH,
            data={
                "items_count": items_count,
                "block_count": panel_block_count,
                "cache_hit": response.metadata.get("cache_hit") if response.metadata else None,
                "source": response.metadata.get("source") if response.metadata else None,
            }
        ).model_dump()

        # ========== 阶段4: 结果总结 ==========
        yield StageMessage(
            stream_id=stream_id,
            stage=StreamStage.SUMMARY,
            message=STAGE_DESCRIPTIONS[StreamStage.SUMMARY],
            progress=STAGE_PROGRESS[StreamStage.SUMMARY],
        ).model_dump()

        # 推送最终结果
        panel_payload = (
            response.data.model_dump()
            if response.data and hasattr(response.data, "model_dump")
            else response.data
        )
        panel_blocks_dump = {}
        if getattr(response, "data_blocks", None):
            for key, block in response.data_blocks.items():
                if hasattr(block, "model_dump"):
                    panel_blocks_dump[key] = block.model_dump()
                else:
                    panel_blocks_dump[key] = block

        yield DataMessage(
            stream_id=stream_id,
            stage=StreamStage.SUMMARY,
            data={
                "success": response.success,
                "intent_type": response.intent_type,
                "message": response.message,
                "data": panel_payload,
                "data_blocks": panel_blocks_dump,
                "metadata": response.metadata,
            }
        ).model_dump()

        # ========== 完成 ==========
        total_time = time.time() - start_time
        yield CompleteMessage(
            stream_id=stream_id,
            success=response.success,
            message=response.message,
            total_time=total_time,
        ).model_dump()

    except Exception as e:
        logger.error(f"[{stream_id}] 流式处理失败: {e}", exc_info=True)
        yield ErrorMessage(
            stream_id=stream_id,
            error_code="STREAM_ERROR",
            error_message=f"处理失败: {str(e)}",
            stage=None,
        ).model_dump()

        # 发送失败的完成消息
        total_time = time.time() - start_time
        yield CompleteMessage(
            stream_id=stream_id,
            success=False,
            message=f"处理失败: {str(e)}",
            total_time=total_time,
        ).model_dump()


@router.websocket("/chat/stream")
async def chat_stream(
    websocket: WebSocket,
    chat_service: Any = Depends(get_chat_service)
):
    """
    统一 WebSocket 流式对话接口

    支持两种模式：
    1. 普通查询模式 (mode != "research"): 返回 stage/data/error/complete 消息
    2. 研究模式 (mode == "research"): 返回 research_* 消息

    消息格式:
    - 客户端发送:
      {
        "query": "...",
        "filter_datasource": null,
        "use_cache": true,
        "mode": "auto" | "simple" | "research",
        "task_id": "task-xxx" (可选，研究模式使用)
      }
    - 服务端推送: 参见 api/schemas/stream_messages.py

    连接地址: ws://host:port/api/v1/chat/stream
    查询参数: ?task_id=xxx (可选，研究模式使用)

    Example (普通模式):
        ```python
        async def test():
            uri = "ws://localhost:8000/api/v1/chat/stream"
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({"query": "虎扑步行街最新帖子"}))
                async for message in ws:
                    data = json.loads(message)
                    print(f"[{data['type']}] {data}")
                    if data['type'] == 'complete':
                        break
        ```

    Example (研究模式):
        ```python
        async def test():
            uri = "ws://localhost:8000/api/v1/chat/stream?task_id=task-123"
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({
                    "query": "分析up主行业101的视频",
                    "mode": "research"
                }))
                async for message in ws:
                    data = json.loads(message)
                    print(f"[{data['type']}] {data}")
                    if data['type'] == 'research_complete':
                        break
        ```
    """
    # 接受连接
    await websocket.accept()

    # 从查询参数或后续请求中获取 task_id
    initial_task_id = websocket.query_params.get("task_id")
    stream_id = generate_stream_id()
    logger.info(f"[{stream_id}] WebSocket连接已建立 (task_id={initial_task_id})")

    try:
        # 接收查询请求
        request_data = await websocket.receive_json()
        user_query = request_data.get("query", "")
        filter_datasource = request_data.get("filter_datasource")
        use_cache = request_data.get("use_cache", True)
        layout_snapshot = request_data.get("layout_snapshot")
        mode = request_data.get("mode", "auto")
        task_id = request_data.get("task_id") or initial_task_id

        logger.info(f"[{stream_id}] 收到查询: {user_query} (mode={mode}, task_id={task_id})")

        # 验证查询
        if not user_query or not user_query.strip():
            if mode == "research":
                error_msg = {
                    "type": "research_error",
                    "stream_id": stream_id,
                    "task_id": task_id or f"task-{uuid.uuid4().hex[:16]}",
                    "step_id": None,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": "查询不能为空",
                    "timestamp": "",
                }
            else:
                error_msg = ErrorMessage(
                    stream_id=stream_id,
                    error_code="VALIDATION_ERROR",
                    error_message="查询不能为空",
                    stage=None,
                ).model_dump()
            await websocket.send_json(error_msg)
            await websocket.close()
            return

        import asyncio

        # 根据模式选择不同的生成器
        if mode == "research":
            # 研究模式：调用 ChatService 的流式研究方法
            if not hasattr(chat_service, '_handle_complex_research_streaming'):
                error_msg = {
                    "type": "research_error",
                    "stream_id": stream_id,
                    "task_id": task_id or f"task-{uuid.uuid4().hex[:16]}",
                    "step_id": None,
                    "error_code": "NOT_SUPPORTED",
                    "error_message": "ChatService 不支持流式研究（缺少 _handle_complex_research_streaming 方法）",
                    "timestamp": "",
                }
                await websocket.send_json(error_msg)
                await websocket.close()
                return

            # 确保有 task_id
            if not task_id:
                task_id = f"task-{uuid.uuid4().hex[:16]}"

            logger.info(f"[{stream_id}] 启动研究模式 (task_id={task_id})")

            # 创建研究模式生成器
            message_generator = chat_service._handle_complex_research_streaming(
                task_id=task_id,
                user_query=user_query,
                filter_datasource=filter_datasource,
                use_cache=use_cache,
                intent_confidence=0.95,  # 研究模式固定高置信度
                layout_snapshot=layout_snapshot,
            )
        else:
            # 普通模式：使用原有的流式处理
            logger.info(f"[{stream_id}] 启动普通查询模式")

            # 创建普通模式生成器
            message_generator = stream_chat_processing(
                chat_service=chat_service,
                user_query=user_query,
                stream_id=stream_id,
                filter_datasource=filter_datasource,
                use_cache=use_cache,
                layout_snapshot=layout_snapshot,
            )

        # 在线程池中逐个获取消息
        while True:
            try:
                # 在线程池中调用next()获取下一个消息
                message = await asyncio.to_thread(next, message_generator, None)
                if message is None:
                    break

                # 发送消息
                await websocket.send_json(message)
                logger.debug(f"[{stream_id}] 推送消息: {message['type']}")

            except StopIteration:
                break
            except Exception as e:
                logger.error(f"[{stream_id}] 消息推送失败: {e}", exc_info=True)
                break

        logger.info(f"[{stream_id}] 流式处理完成")

    except WebSocketDisconnect:
        logger.info(f"[{stream_id}] 客户端断开连接")
    except Exception as e:
        logger.error(f"[{stream_id}] WebSocket处理失败: {e}", exc_info=True)
        try:
            error_msg = ErrorMessage(
                stream_id=stream_id,
                error_code="INTERNAL_ERROR",
                error_message=f"服务器内部错误: {str(e)}",
                stage=None,
            )
            await websocket.send_json(error_msg.model_dump())
        except:
            pass
    finally:
        try:
            await websocket.close()
            logger.info(f"[{stream_id}] WebSocket连接已关闭")
        except:
            pass

