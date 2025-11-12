import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from api.controllers.chat_controller import get_chat_service
from services.research_service import ResearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/research", tags=["research"])


class HumanResponsePayload(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=128, description="研究任务ID")
    response: str = Field(..., min_length=1, description="用户输入的补充信息")


class CancelTaskPayload(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=128, description="研究任务ID")
    reason: Optional[str] = Field(default=None, description="取消原因")


def _get_research_service() -> ResearchService:
    chat_service: Any = get_chat_service()
    research_service = getattr(chat_service, "research_service", None)
    if research_service is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="研究服务未启用")
    return research_service


async def _wait_for_task(research_service: ResearchService, task_id: str, timeout: float = 10.0) -> None:
    """
    等待研究任务注册（使用事件驱动机制，避免轮询）。

    Args:
        research_service: 研究服务实例
        task_id: 任务ID
        timeout: 超时时间（秒），默认10秒

    Raises:
        HTTPException: 任务在超时时间内未创建
    """
    loop = asyncio.get_running_loop()
    # 在线程池中等待任务就绪（阻塞操作）
    ready = await loop.run_in_executor(
        None,
        research_service.task_hub.wait_for_task,
        task_id,
        timeout,
    )
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 {task_id} 在 {timeout} 秒内未创建",
        )


@router.post("/human-response")
async def submit_human_response(
    payload: HumanResponsePayload,
    research_service: ResearchService = Depends(_get_research_service),
):
    """提交 ActionInbox 中的人工回复。"""
    research_service.submit_human_response(payload.task_id, payload.response)
    return {"success": True}


@router.post("/cancel")
async def cancel_task(
    payload: CancelTaskPayload,
    research_service: ResearchService = Depends(_get_research_service),
):
    """取消正在执行的研究任务。"""
    reason = payload.reason or "用户取消"
    research_service.cancel_task(payload.task_id, reason)
    return {"success": True}


@router.websocket("/stream")
async def research_stream(websocket: WebSocket):
    """研究任务实时推送 WebSocket。"""
    params = websocket.query_params
    task_id = params.get("task_id")
    if not task_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="task_id 参数必填")
        return

    try:
        research_service = _get_research_service()
    except HTTPException as exc:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=exc.detail)
        return

    await websocket.accept()

    queue = None
    try:
        await _wait_for_task(research_service, task_id)
        queue = research_service.register_stream(task_id)
    except HTTPException as exc:
        await websocket.send_json({"type": "error", "task_id": task_id, "data": {"message": exc.detail}})
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=exc.detail)
        return
    except Exception as exc:  # pragma: no cover - 防御性
        await websocket.send_json({"type": "error", "task_id": task_id, "data": {"message": str(exc)}})
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="初始化失败")
        return

    loop = asyncio.get_running_loop()

    try:
        while True:
            event = await loop.run_in_executor(None, queue.get)
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.info("研究任务 %s 的 WebSocket 断开", task_id)
    except Exception as exc:  # pragma: no cover
        logger.error("研究任务 %s WebSocket 失败: %s", task_id, exc, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "task_id": task_id, "data": {"message": str(exc)}})
        except Exception:
            pass
    finally:
        if queue is not None:
            research_service.unregister_stream(task_id, queue)
        await websocket.close()
