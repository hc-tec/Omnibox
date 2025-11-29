"""
WebSocket流式对话控制器
按阶段推送处理进度：intent → rag → fetch → summary
"""

import logging
import uuid
import time
import threading
from queue import Queue, Empty
from typing import Generator, Optional, Any, Dict
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
    GraphNodeMessage,
    LLMCallMessage,
    ResearchStepMessage,
    StreamStage,
    STAGE_DESCRIPTIONS,
    STAGE_PROGRESS,
)
from api.schemas.llm_call_event import LLMCallTracker, LLMCallEvent
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
    task_id: Optional[str] = None,
) -> Generator[dict, None, None]:
    """
    流式处理对话（同步生成器，在线程池中执行）

    按阶段yield消息：
    1. intent阶段 - 意图识别
    2. rag阶段 - RAG检索（数据查询时）
    3. fetch阶段 - 数据获取
    4. summary阶段 - 结果总结
    5. llm_call消息 - LLM 调用追踪事件（V5.0 可观测性）

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

        # ========== 构建事件队列，实时接收 LangGraph 回调 ==========
        event_queue: Queue = Queue()
        result_holder: Dict[str, Any] = {}

        llm_events: list[LLMCallEvent] = []

        def enqueue_llm_event(event: LLMCallEvent) -> None:
            llm_events.append(event)
            event_queue.put(("llm_call", event))

        llm_tracker = LLMCallTracker(
            stream_id=stream_id,
            callback=enqueue_llm_event,
            dev_mode=False,
        )

        def emit_panel_preview(payload: Dict[str, Any]) -> None:
            event_queue.put(("panel_preview", payload))

        def run_chat():
            try:
                response = chat_service.chat(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    layout_snapshot=layout_snapshot,
                    force_execute=True,
                    llm_tracker=llm_tracker,
                    panel_callback=emit_panel_preview,
                )
                result_holder["response"] = response
            except Exception as exc:  # pragma: no cover
                result_holder["error"] = exc
            finally:
                event_queue.put(("done", None))

        worker = threading.Thread(target=run_chat, daemon=True)
        worker.start()

        # ========== 阶段3: 数据获取 ==========
        yield StageMessage(
            stream_id=stream_id,
            stage=StreamStage.FETCH,
            message=STAGE_DESCRIPTIONS[StreamStage.FETCH],
            progress=STAGE_PROGRESS[StreamStage.FETCH],
        ).model_dump()

        preview_counter = 0
        while True:
            try:
                event_type, payload = event_queue.get(timeout=0.1)
            except Empty:
                if worker.is_alive():
                    continue
                else:
                    break

            if event_type == "done":
                if not worker.is_alive():
                    break
                continue

            if event_type == "llm_call":
                event = payload
                if isinstance(event, LLMCallEvent):
                    message = LLMCallMessage(
                        stream_id=event.stream_id or stream_id,
                        call_id=event.call_id,
                        role=event.role,
                        status=event.status,
                        step_id=event.step_id,
                        duration_ms=event.duration_ms,
                        prompt_tokens=event.prompt_tokens,
                        completion_tokens=event.completion_tokens,
                        total_tokens=event.total_tokens,
                        prompt_preview=event.prompt_preview,
                        response_preview=event.response_preview,
                        model=event.model,
                        temperature=event.temperature,
                        timestamp=event.timestamp,
                    ).model_dump()
                    yield message
                continue

            if event_type == "panel_preview":
                preview_counter += 1
                preview_payload = payload or {}
                previews = preview_payload.get("previews") or []
                first_preview = previews[0] if previews else {}
                title = first_preview.get("title") or preview_payload.get("source_query") or "数据预览"
                route = first_preview.get("generated_path")
                source = first_preview.get("source")
                item_count = len(first_preview.get("items") or [])
                step_message = ResearchStepMessage(
                    stream_id=stream_id,
                    task_id=task_id or stream_id,
                    step_id=f"preview_{preview_counter}",
                    step_type="data_fetch",
                    action=f"生成数据预览：{title}",
                    status="success",
                    details={
                        "route": route,
                        "datasource": source,
                        "item_count": item_count,
                        "preview_id": first_preview.get("preview_id"),
                    },
                ).model_dump()
                yield step_message
                continue

        if "error" in result_holder:
            raise result_holder["error"]

        response = result_holder.get("response")
        if response is None:
            raise RuntimeError("查询响应为空")

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

        metadata = getattr(response, "metadata", None) or {}
        refresh_metadata = metadata.get("refresh_metadata") if isinstance(metadata, dict) else None
        route_hint = None
        feed_title = None
        if isinstance(metadata, dict):
            feed_title = metadata.get("feed_title")
            if isinstance(refresh_metadata, dict):
                route_hint = refresh_metadata.get("generated_path") or refresh_metadata.get("route_id")
            if not route_hint:
                route_hint = metadata.get("generated_path")
            if not route_hint:
                datasets_meta = metadata.get("datasets")
                if isinstance(datasets_meta, list) and datasets_meta:
                    first_dataset = datasets_meta[0]
                    if isinstance(first_dataset, dict):
                        route_hint = first_dataset.get("generated_path") or first_dataset.get("route")

        yield DataMessage(
            stream_id=stream_id,
            stage=StreamStage.FETCH,
            data={
                "items_count": items_count,
                "block_count": panel_block_count,
                "cache_hit": metadata.get("cache_hit") if isinstance(metadata, dict) else None,
                "source": metadata.get("source") if isinstance(metadata, dict) else None,
                "route": route_hint,
                "feed_title": feed_title,
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

        if response.metadata:
            task_graph_meta = response.metadata.get("task_graph")
            if task_graph_meta:
                plan_nodes = {node.get("id"): node for node in task_graph_meta.get("graph", [])}
                for record in task_graph_meta.get("nodes", []):
                    plan_info = plan_nodes.get(record.get("node_id"), {})
                    yield GraphNodeMessage(
                        stream_id=stream_id,
                        node_id=record.get("node_id", ""),
                        node_type=record.get("node_type", "fetch_data"),
                        status=record.get("status", "success"),
                        description=plan_info.get("description"),
                        input_refs=plan_info.get("input_refs") or [],
                        summary=record.get("summary"),
                        error=record.get("error"),
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

        # V5.0 可观测性：即使失败也推送已收集的 LLM 调用事件
        for event in llm_events:
            yield LLMCallMessage(
                stream_id=stream_id,
                call_id=event.call_id,
                role=event.role,
                status=event.status,
                step_id=event.step_id,
                duration_ms=event.duration_ms,
                prompt_tokens=event.prompt_tokens,
                completion_tokens=event.completion_tokens,
                total_tokens=event.total_tokens,
                prompt_preview=event.prompt_preview,
                response_preview=event.response_preview,
                full_prompt=event.full_prompt,
                full_response=event.full_response,
                error_message=event.error_message,
                model=event.model,
                temperature=event.temperature,
                metadata=event.metadata,
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
    统一 WebSocket 流式对话接口（V5.0 Task Graph 架构）

    所有数据查询统一通过 Task Graph 处理，按阶段推送进度。

    消息格式:
    - 客户端发送:
      {
        "query": "...",
        "filter_datasource": null,
        "use_cache": true,
        "mode": "auto" | "simple" | "research",
        "layout_snapshot": [...] (可选)
      }
    - 服务端推送: 参见 api/schemas/stream_messages.py
      - stage: 阶段进度
      - data: 阶段数据
      - graph_node: Task Graph 节点执行信息
      - complete: 完成消息

    连接地址: ws://host:port/api/v1/chat/stream

    Example:
        ```python
        async def test():
            uri = "ws://localhost:8000/api/v1/chat/stream"
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({
                    "query": "B站影视飓风投稿视频中，标题包含英雄联盟的视频",
                    "mode": "research"  # Task Graph 会自动规划 fetch + filter
                }))
                async for message in ws:
                    data = json.loads(message)
                    print(f"[{data['type']}] {data}")
                    if data['type'] == 'complete':
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

        # V5.0 架构：所有模式统一使用 Task Graph
        # mode 参数会传递给 chat_service.chat()，由其内部决定处理方式
        # - "auto": 自动意图分类后路由
        # - "simple": 强制简单查询
        # - "research": 强制复杂查询（Task Graph 多节点规划）
        logger.info(f"[{stream_id}] 启动流式查询 (mode={mode})")

        # 统一使用 stream_chat_processing，它内部调用 chat_service.chat()
        # chat_service.chat() 现在统一通过 Task Graph 处理所有数据查询
        message_generator = stream_chat_processing(
            chat_service=chat_service,
            user_query=user_query,
            stream_id=stream_id,
            filter_datasource=filter_datasource,
            use_cache=use_cache,
            layout_snapshot=layout_snapshot,
            task_id=task_id,
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

