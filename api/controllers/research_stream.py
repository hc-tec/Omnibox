"""
WebSocket 研究流式控制器
支持复杂研究任务的实时进度推送
"""

import logging
import asyncio
from uuid import uuid4
from typing import Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from api.schemas.stream_messages import (
    ResearchStartMessage,
    ResearchStepMessage,
    ResearchPanelMessage,
    ResearchAnalysisMessage,
    ResearchCompleteMessage,
    ResearchErrorMessage,
)
from api.controllers.chat_controller import get_chat_service

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/v1/chat", tags=["research-stream"])


def generate_task_id() -> str:
    """
    生成唯一的研究任务 ID

    Returns:
        格式为 "task-{uuid}" 的任务 ID
    """
    return f"task-{uuid4().hex[:16]}"


@router.websocket("/research-stream")
async def research_stream(
    websocket: WebSocket,
    chat_service: Any = Depends(get_chat_service)
):
    """
    WebSocket 研究流式接口

    专用于复杂研究任务，实时推送研究进度、数据面板和分析结果。

    消息格式:
    - 客户端发送:
      {
        "query": "查看 up主15616847 的视频并分析方向",
        "filter_datasource": null,
        "use_cache": true,
        "layout_snapshot": null
      }

    - 服务端推送消息类型:
      - research_start: 研究开始，包含执行计划
      - research_step: 步骤状态更新（processing/success/error）
      - research_panel: 数据面板推送
      - research_analysis: 分析结果推送
      - research_complete: 研究完成
      - research_error: 错误消息

    连接地址: ws://host:port/api/v1/chat/research-stream

    Example:
        ```python
        import asyncio
        import websockets
        import json

        async def test():
            uri = "ws://localhost:8000/api/v1/chat/research-stream"
            async with websockets.connect(uri) as ws:
                # 发送研究请求
                await ws.send(json.dumps({
                    "query": "查看 up主15616847 的视频并分析方向"
                }))

                # 接收流式消息
                async for message in ws:
                    data = json.loads(message)
                    print(f"[{data['type']}] {data}")

                    if data['type'] == 'research_complete':
                        break

        asyncio.run(test())
        ```
    """
    # 接受连接
    await websocket.accept()
    initial_task_id = websocket.query_params.get("task_id")
    task_id = initial_task_id or generate_task_id()
    logger.info("[%s] WebSocket 研究连接已建立", task_id)

    try:
        # 接收研究请求
        request_data = await websocket.receive_json()
        user_query = request_data.get("query", "")
        filter_datasource = request_data.get("filter_datasource")
        use_cache = request_data.get("use_cache", True)
        layout_snapshot = request_data.get("layout_snapshot")
        client_task_id = request_data.get("task_id")
        if client_task_id:
            task_id = client_task_id

        logger.info("[%s] 收到研究请求: %s", task_id, user_query)

        # 验证查询
        if not user_query or not user_query.strip():
            error_msg = {
                "type": "research_error",
                "stream_id": f"stream-{uuid4().hex[:16]}",
                "task_id": task_id,
                "step_id": None,
                "error_code": "VALIDATION_ERROR",
                "error_message": "查询不能为空",
                "timestamp": "",
            }
            await websocket.send_json(error_msg)
            await websocket.close()
            return

        # 检查 ChatService 是否有流式研究方法
        if not hasattr(chat_service, '_handle_complex_research_streaming'):
            error_msg = {
                "type": "research_error",
                "stream_id": f"stream-{uuid4().hex[:16]}",
                "task_id": task_id,
                "step_id": None,
                "error_code": "NOT_SUPPORTED",
                "error_message": "ChatService 不支持流式研究（缺少 _handle_complex_research_streaming 方法）",
                "timestamp": "",
            }
            await websocket.send_json(error_msg)
            await websocket.close()
            return

        # 创建流式生成器
        message_generator = chat_service._handle_complex_research_streaming(
            task_id=task_id,
            user_query=user_query,
            filter_datasource=filter_datasource,
            use_cache=use_cache,
            intent_confidence=0.95,  # 研究模式固定高置信度
            layout_snapshot=layout_snapshot,
        )

        # 在线程池中逐个获取消息并推送
        while True:
            try:
                # 在线程池中调用 next() 获取下一个消息
                message = await asyncio.to_thread(next, message_generator, None)

                if message is None:
                    # 生成器耗尽
                    break

                # 发送消息
                await websocket.send_json(message)
                logger.debug("[%s] 推送消息: %s", task_id, message.get("type"))

                # 如果是完成消息，记录日志
                if message.get("type") == "research_complete":
                    success = message.get("success", False)
                    total_time = message.get("total_time", 0)
                    logger.info(
                        "[%s] 研究完成 (success=%s, total_time=%.2fs)",
                        task_id,
                        success,
                        total_time
                    )

            except StopIteration:
                # 生成器结束
                break

            except Exception as exc:
                logger.error("[%s] 消息推送失败: %s", task_id, exc, exc_info=True)
                # 推送错误消息
                error_msg = {
                    "type": "research_error",
                    "stream_id": f"stream-{uuid4().hex[:16]}",
                    "task_id": task_id,
                    "step_id": None,
                    "error_code": "PUSH_ERROR",
                    "error_message": f"消息推送失败: {str(exc)}",
                    "timestamp": "",
                }
                try:
                    await websocket.send_json(error_msg)
                except:
                    pass
                break

        logger.info("[%s] 流式研究处理完成", task_id)

    except WebSocketDisconnect:
        logger.info("[%s] 客户端断开连接", task_id)

    except Exception as exc:
        logger.error("[%s] WebSocket 处理失败: %s", task_id, exc, exc_info=True)
        try:
            error_msg = {
                "type": "research_error",
                "stream_id": f"stream-{uuid4().hex[:16]}",
                "task_id": task_id,
                "step_id": None,
                "error_code": "INTERNAL_ERROR",
                "error_message": f"服务器内部错误: {str(exc)}",
                "timestamp": "",
            }
            await websocket.send_json(error_msg)
        except:
            pass

    finally:
        try:
            await websocket.close()
            logger.info("[%s] WebSocket 连接已关闭", task_id)
        except:
            pass
