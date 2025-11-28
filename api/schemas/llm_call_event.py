"""LLM 调用事件模型 - 用于前端可观测性。"""

from __future__ import annotations

from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LLMCallEvent:
    """
    LLM 调用事件（用于 WebSocket 推送）。

    设计目标：
    - 实时追踪所有 LLM 调用（Planner、Reflector、Synthesizer、订阅解析等）
    - 前端可视化 LLM 调用时间线
    - 支持开发者模式查看详细 prompt/response
    """

    # 基础标识
    call_id: str  # 调用唯一 ID（UUID）
    role: Literal[
        "planner",         # 规划器
        "reflector",       # 反思器
        "synthesizer",     # 综合器
        "research_agent",  # V6.0 单Agent 节点
        "router",          # 路由器
        "tool_executor",   # 工具执行器
        "data_stasher",    # 数据摘要生成
        "entity_resolver", # 订阅实体解析
        "query_parser",    # 查询解析（RAG）
        "other",           # 其他
    ]
    status: Literal["started", "completed", "failed"]

    # 关联信息
    step_id: Optional[int] = None  # 关联的执行步骤（如果有）
    stream_id: Optional[str] = None  # 关联的 stream_id

    # 时间信息
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: Optional[int] = None  # 耗时（毫秒）

    # Token 统计
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    # 调用内容（可选，开发者模式时返回）
    prompt_preview: Optional[str] = None  # Prompt 预览（前 200 字符）
    response_preview: Optional[str] = None  # Response 预览（前 200 字符）
    full_prompt: Optional[str] = None  # 完整 Prompt（仅开发者模式）
    full_response: Optional[str] = None  # 完整 Response（仅开发者模式）

    # 错误信息
    error_message: Optional[str] = None

    # 元信息
    model: Optional[str] = None
    temperature: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 WebSocket JSON 序列化）。"""
        return {
            "call_id": self.call_id,
            "role": self.role,
            "status": self.status,
            "step_id": self.step_id,
            "stream_id": self.stream_id,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "prompt_preview": self.prompt_preview,
            "response_preview": self.response_preview,
            "full_prompt": self.full_prompt,
            "full_response": self.full_response,
            "error_message": self.error_message,
            "model": self.model,
            "temperature": self.temperature,
            "metadata": self.metadata,
        }

    @staticmethod
    def create_preview(text: str, max_length: int = 200) -> str:
        """创建文本预览（截断长文本）。"""
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."


@dataclass
class LLMCallTracker:
    """
    LLM 调用追踪器（内存版本）。

    用途：
    - 收集一次查询中的所有 LLM 调用
    - 通过 callback 实时推送到前端
    - 提供统计和查询接口
    """

    stream_id: str
    callback: Optional[callable] = None  # WebSocket 推送回调
    dev_mode: bool = False  # 是否启用开发者模式（返回完整 prompt/response）

    # 内部状态
    calls: Dict[str, LLMCallEvent] = field(default_factory=dict)

    def start_call(
        self,
        call_id: str,
        role: str,
        step_id: Optional[int] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录 LLM 调用开始（仅内部记录，不推送到前端）。"""
        event = LLMCallEvent(
            call_id=call_id,
            role=role,
            status="started",
            step_id=step_id,
            stream_id=self.stream_id,
            model=model,
            temperature=temperature,
            metadata=metadata or {},
        )
        self.calls[call_id] = event
        # 注意：不在 start 时推送，只在 complete/fail 时推送，避免重复事件

    def complete_call(
        self,
        call_id: str,
        prompt: str,
        response: str,
        duration_ms: int,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
    ) -> None:
        """记录 LLM 调用完成。"""
        if call_id not in self.calls:
            return

        event = self.calls[call_id]
        event.status = "completed"
        event.duration_ms = duration_ms
        event.prompt_tokens = prompt_tokens
        event.completion_tokens = completion_tokens
        event.total_tokens = total_tokens
        # 调试面板显示完整内容，不截断
        event.prompt_preview = prompt
        event.response_preview = response
        event.full_prompt = prompt
        event.full_response = response

        # 推送到前端
        if self.callback:
            self.callback(event)

    def fail_call(
        self,
        call_id: str,
        error_message: str,
        duration_ms: int,
    ) -> None:
        """记录 LLM 调用失败。"""
        if call_id not in self.calls:
            return

        event = self.calls[call_id]
        event.status = "failed"
        event.duration_ms = duration_ms
        event.error_message = error_message

        # 推送到前端
        if self.callback:
            self.callback(event)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息。"""
        total_calls = len(self.calls)
        total_tokens = sum(
            e.total_tokens for e in self.calls.values() if e.total_tokens
        )
        total_duration = sum(
            e.duration_ms for e in self.calls.values() if e.duration_ms
        )

        # 按角色统计
        by_role = {}
        for event in self.calls.values():
            role = event.role
            if role not in by_role:
                by_role[role] = {"count": 0, "tokens": 0, "duration_ms": 0}
            by_role[role]["count"] += 1
            by_role[role]["tokens"] += event.total_tokens or 0
            by_role[role]["duration_ms"] += event.duration_ms or 0

        return {
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "total_duration_ms": total_duration,
            "by_role": by_role,
        }
