"""研究任务事件中心。

负责跟踪 ResearchService 运行中的任务、历史事件、监听队列以及人机交互状态。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from queue import SimpleQueue
from typing import Dict, List, Optional, Any

from services.research_constants import TaskStatus, StreamEventType, DefaultConfig


@dataclass
class ResearchTaskContext:
    """单个研究任务的运行上下文。"""

    task_id: str
    thread_id: str
    base_query: str = ""
    filter_datasource: Optional[str] = None
    status: str = TaskStatus.RUNNING
    created_at: datetime = field(default_factory=datetime.utcnow)
    human_request: Optional[str] = None
    cancelled: bool = False
    responses: List[Dict[str, Any]] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    listeners: List[SimpleQueue] = field(default_factory=list)
    last_state: Optional[Dict[str, Any]] = None
    ready_event: threading.Event = field(default_factory=threading.Event)


class ResearchTaskHub:
    """管理研究任务的实时事件与监听者。"""

    def __init__(self, history_limit: int = DefaultConfig.HISTORY_LIMIT):
        self._tasks: Dict[str, ResearchTaskContext] = {}
        self._lock = threading.Lock()
        self._history_limit = history_limit

    def ensure_task(
        self,
        task_id: str,
        thread_id: str,
        base_query: str,
        filter_datasource: Optional[str],
    ) -> ResearchTaskContext:
        with self._lock:
            context = self._tasks.get(task_id)
            if context is None:
                context = ResearchTaskContext(
                    task_id=task_id,
                    thread_id=thread_id,
                    base_query=base_query,
                    filter_datasource=filter_datasource,
                )
                self._tasks[task_id] = context
            else:
                context.thread_id = thread_id
                context.base_query = base_query
                context.filter_datasource = filter_datasource
            # 标记任务已就绪
            context.ready_event.set()
            return context

    def create_task(self, task_id: str, thread_id: str) -> ResearchTaskContext:
        """兼容旧接口，默认不带额外元数据。"""
        return self.ensure_task(task_id, thread_id, base_query="", filter_datasource=None)

    def get_task(self, task_id: str) -> Optional[ResearchTaskContext]:
        with self._lock:
            return self._tasks.get(task_id)

    def publish_event(self, task_id: str, event: Dict[str, Any]) -> None:
        """发布事件到所有监听者，并记录历史。"""
        context = self.get_task(task_id)
        if not context:
            return

        # 限制历史长度，避免内存占用
        context.history.append(event)
        if len(context.history) > self._history_limit:
            context.history = context.history[-self._history_limit :]

        for listener in list(context.listeners):
            try:
                listener.put_nowait(event)
            except Exception:
                # SimpleQueue 不会抛出 Full，但保持保险
                pass

    def register_listener(self, task_id: str) -> SimpleQueue:
        """为任务注册新的事件监听者，并回放历史事件。"""
        context = self.get_task(task_id)
        if not context:
            raise KeyError(f"未找到任务 {task_id}")

        queue: SimpleQueue = SimpleQueue()
        for event in context.history:
            queue.put_nowait(event)

        with self._lock:
            context.listeners.append(queue)
        return queue

    def unregister_listener(self, task_id: str, queue: SimpleQueue) -> None:
        context = self.get_task(task_id)
        if not context:
            return
        with self._lock:
            if queue in context.listeners:
                context.listeners.remove(queue)

    def mark_human_request(self, task_id: str, message: str) -> None:
        context = self.get_task(task_id)
        if not context:
            return
        context.status = TaskStatus.HUMAN_IN_LOOP
        context.human_request = message

    def mark_processing(self, task_id: str) -> None:
        context = self.get_task(task_id)
        if not context:
            return
        context.status = TaskStatus.PROCESSING
        context.human_request = None

    def submit_human_response(self, task_id: str, response: str) -> ResearchTaskContext:
        context = self.get_task(task_id)
        if not context:
            raise KeyError(f"未找到任务 {task_id}")
        payload = {
            "response": response,
            "timestamp": datetime.utcnow().isoformat(),
        }
        context.responses.append(payload)
        context.status = TaskStatus.PROCESSING
        self.publish_event(
            task_id,
            {
                "type": StreamEventType.HUMAN_RESPONSE_ACK,
                "task_id": task_id,
                "timestamp": payload["timestamp"],
                "data": payload,
            },
        )
        return context

    def cancel_task(self, task_id: str, reason: str = "用户取消") -> None:
        context = self.get_task(task_id)
        if not context:
            raise KeyError(f"未找到任务 {task_id}")
        context.cancelled = True
        context.status = TaskStatus.CANCELLED
        event = {
            "type": StreamEventType.CANCELLED,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {"reason": reason},
        }
        self.publish_event(task_id, event)

    def mark_completed(
        self, task_id: str, final_report: str, success: bool = True, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        context = self.get_task(task_id)
        if not context:
            return
        context.status = TaskStatus.COMPLETED if success else TaskStatus.ERROR
        context.human_request = None
        event = {
            "type": StreamEventType.COMPLETE if success else StreamEventType.ERROR,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "success": success,
                "final_report": final_report,
                "metadata": metadata or {},
            },
        }
        self.publish_event(task_id, event)

    def mark_error(self, task_id: str, message: str) -> None:
        context = self.get_task(task_id)
        if not context:
            return
        context.status = TaskStatus.ERROR
        event = {
            "type": StreamEventType.ERROR,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {"message": message},
        }
        self.publish_event(task_id, event)

    def is_cancelled(self, task_id: str) -> bool:
        context = self.get_task(task_id)
        return bool(context and context.cancelled)

    def has_task(self, task_id: str) -> bool:
        with self._lock:
            return task_id in self._tasks

    def wait_for_task(self, task_id: str, timeout: float = 10.0) -> bool:
        """
        等待任务创建就绪（使用事件机制，避免轮询）。

        Args:
            task_id: 任务ID
            timeout: 超时时间（秒），默认10秒

        Returns:
            True 表示任务已就绪，False 表示超时
        """
        # 先检查任务是否已存在
        context = self.get_task(task_id)
        if context:
            return context.ready_event.wait(timeout)

        # 任务不存在，创建一个占位上下文用于等待
        with self._lock:
            if task_id not in self._tasks:
                # 创建占位上下文（状态为 pending）
                placeholder = ResearchTaskContext(
                    task_id=task_id,
                    thread_id="",
                    status=TaskStatus.PENDING,
                )
                self._tasks[task_id] = placeholder
                context = placeholder
            else:
                context = self._tasks[task_id]

        # 等待事件触发
        return context.ready_event.wait(timeout)

    def set_last_state(self, task_id: str, state: Dict[str, Any]) -> None:
        context = self.get_task(task_id)
        if not context:
            return
        context.last_state = state
