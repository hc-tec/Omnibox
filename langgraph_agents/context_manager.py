"""
分层记忆与上下文管理系统。

V6.0 Phase 3: 实现分层记忆架构，优化 LLM 上下文使用。

记忆层次：
- L1 (Working Memory): 当前步骤的即时数据，最高优先级
- L2 (Session Memory): 当前会话的数据摘要（data_stash）
- L3 (Conversation Memory): 对话历史的压缩摘要
- L4 (Long-term Memory): 持久化的知识和经验（可选）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .state import DataReference, GraphState

logger = logging.getLogger(__name__)


@dataclass
class MemoryLayer:
    """单个记忆层。"""
    name: str
    priority: int  # 越小优先级越高
    max_tokens: int  # 最大 token 数
    content: str = ""
    estimated_tokens: int = 0

    def update(self, content: str, estimated_tokens: int = 0):
        """更新记忆内容。"""
        self.content = content
        self.estimated_tokens = estimated_tokens or self._estimate_tokens(content)

    def _estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数（简化实现：1 token ≈ 2 中文字符或 4 英文字符）。"""
        if not text:
            return 0
        # 简化估算：中文约 2 字符/token，英文约 4 字符/token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_chars = len(text) - chinese_chars
        return chinese_chars // 2 + english_chars // 4 + 10  # 加一点 buffer


@dataclass
class ContextBudget:
    """上下文 token 预算。"""
    total_budget: int = 8000  # 总 token 预算
    system_prompt_budget: int = 2000  # 系统 prompt 预算
    tool_list_budget: int = 1000  # 工具列表预算
    response_buffer: int = 1500  # 响应预留空间

    @property
    def available_for_memory(self) -> int:
        """可用于记忆的 token 数。"""
        return (
            self.total_budget
            - self.system_prompt_budget
            - self.tool_list_budget
            - self.response_buffer
        )


class HierarchicalMemoryManager:
    """
    分层记忆管理器。

    负责：
    1. 管理不同层次的记忆
    2. 根据 token 预算动态调整各层内容
    3. 提供压缩和摘要功能
    """

    # 各层的默认 token 分配比例
    DEFAULT_LAYER_RATIOS = {
        "L1_working": 0.15,  # 15% 给工作记忆
        "L2_session": 0.40,  # 40% 给会话记忆（data_stash）
        "L3_conversation": 0.35,  # 35% 给对话历史
        "L4_longterm": 0.10,  # 10% 给长期记忆
    }

    def __init__(
        self,
        budget: Optional[ContextBudget] = None,
        layer_ratios: Optional[Dict[str, float]] = None,
    ):
        """
        初始化记忆管理器。

        Args:
            budget: 上下文 token 预算
            layer_ratios: 各层的 token 分配比例
        """
        self.budget = budget or ContextBudget()
        self.ratios = layer_ratios or self.DEFAULT_LAYER_RATIOS

        # 初始化各层
        available = self.budget.available_for_memory
        self.layers: Dict[str, MemoryLayer] = {
            "L1_working": MemoryLayer(
                name="工作记忆",
                priority=1,
                max_tokens=int(available * self.ratios["L1_working"]),
            ),
            "L2_session": MemoryLayer(
                name="会话记忆",
                priority=2,
                max_tokens=int(available * self.ratios["L2_session"]),
            ),
            "L3_conversation": MemoryLayer(
                name="对话历史",
                priority=3,
                max_tokens=int(available * self.ratios["L3_conversation"]),
            ),
            "L4_longterm": MemoryLayer(
                name="长期记忆",
                priority=4,
                max_tokens=int(available * self.ratios["L4_longterm"]),
            ),
        }

        # 使用统计
        self._usage_stats = {
            "total_updates": 0,
            "compressions": 0,
            "overflow_events": 0,
        }

    def update_from_state(self, state: GraphState) -> None:
        """
        从 GraphState 更新各层记忆。

        Args:
            state: 当前图状态
        """
        # L1: 工作记忆（轻量工具结果）
        working_memory = state.get("working_memory", {})
        l1_content = self._format_working_memory(working_memory)
        self.layers["L1_working"].update(l1_content)

        # L2: 会话记忆（data_stash 摘要）
        data_stash = state.get("data_stash", [])
        l2_content = self._format_data_stash(data_stash)
        self.layers["L2_session"].update(l2_content)

        # L3: 对话历史
        chat_history = state.get("chat_history", [])
        l3_content = self._format_chat_history(chat_history)
        self.layers["L3_conversation"].update(l3_content)

        # L4: 长期记忆（如果有知识图谱）
        knowledge_graph = state.get("knowledge_graph")
        l4_content = self._format_knowledge_graph(knowledge_graph)
        self.layers["L4_longterm"].update(l4_content)

        self._usage_stats["total_updates"] += 1

    def get_context_string(self, max_tokens: Optional[int] = None) -> str:
        """
        获取用于 LLM 的上下文字符串。

        按优先级排列各层内容，确保不超过 token 预算。

        Args:
            max_tokens: 可选的最大 token 数限制

        Returns:
            格式化的上下文字符串
        """
        budget = max_tokens or self.budget.available_for_memory
        parts = []
        used_tokens = 0

        # 按优先级排序
        sorted_layers = sorted(
            self.layers.values(),
            key=lambda x: x.priority
        )

        for layer in sorted_layers:
            if not layer.content:
                continue

            # 检查是否超预算
            if used_tokens + layer.estimated_tokens > budget:
                # 需要压缩
                remaining = budget - used_tokens
                if remaining > 100:  # 至少要有 100 token
                    compressed = self._compress_content(
                        layer.content,
                        remaining
                    )
                    parts.append(f"## {layer.name}\n{compressed}")
                    used_tokens += remaining
                    self._usage_stats["compressions"] += 1
                else:
                    self._usage_stats["overflow_events"] += 1
                break
            else:
                parts.append(f"## {layer.name}\n{layer.content}")
                used_tokens += layer.estimated_tokens

        return "\n\n".join(parts)

    def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计。"""
        return {
            **self._usage_stats,
            "layers": {
                name: {
                    "estimated_tokens": layer.estimated_tokens,
                    "max_tokens": layer.max_tokens,
                    "utilization": (
                        layer.estimated_tokens / layer.max_tokens
                        if layer.max_tokens > 0 else 0
                    ),
                }
                for name, layer in self.layers.items()
            },
            "total_estimated_tokens": sum(
                layer.estimated_tokens for layer in self.layers.values()
            ),
            "budget_available": self.budget.available_for_memory,
        }

    def _format_working_memory(self, working_memory: Dict[str, Any]) -> str:
        """格式化工作记忆。"""
        if not isinstance(working_memory, dict) or not working_memory:
            return ""

        lines = []
        for tool_id, result in working_memory.items():
            if tool_id == "filter_datasource":
                continue
            if not isinstance(result, dict):
                preview = str(result)
                preview = preview if len(preview) <= 200 else preview[:200] + "…"
                lines.append(f"- [{tool_id}]: {preview}")
                continue
            status = result.get("status", "unknown")
            description = result.get("description", "")
            step_id = result.get("step_id", "?")
            lines.append(f"- [Step {step_id}] {tool_id}: {description} ({status})")

        return "\n".join(lines) if lines else ""

    def _format_data_stash(self, data_stash: List[DataReference]) -> str:
        """格式化会话记忆（data_stash）。"""
        if not data_stash:
            return ""

        lines = []
        for ref in data_stash:
            status_icon = (
                "✓" if ref.status == "success"
                else "✗" if ref.status == "error"
                else "?"
            )
            lines.append(
                f"- [Step {ref.step_id}] {ref.tool_name} ({status_icon}): {ref.summary}"
            )
            if ref.data_id:
                lines.append(f"  data_id: {ref.data_id}")

        return "\n".join(lines)

    def _format_chat_history(self, chat_history: List[str]) -> str:
        """格式化对话历史。"""
        if not chat_history:
            return ""

        # 只保留最近的几条
        recent = chat_history[-5:]
        return "\n".join(recent)

    def _format_knowledge_graph(self, knowledge_graph: Any) -> str:
        """格式化知识图谱摘要。"""
        if not knowledge_graph:
            return ""

        # 如果有 get_statistics 方法
        if hasattr(knowledge_graph, "get_statistics"):
            stats = knowledge_graph.get_statistics()
            return (
                f"知识图谱: {stats.get('node_count', 0)} 节点, "
                f"{stats.get('edge_count', 0)} 边"
            )

        return ""

    def _compress_content(self, content: str, target_tokens: int) -> str:
        """
        压缩内容到目标 token 数。

        简化实现：按比例截断。
        """
        current_tokens = self.layers["L1_working"]._estimate_tokens(content)
        if current_tokens <= target_tokens:
            return content

        # 计算保留比例
        ratio = target_tokens / current_tokens
        target_chars = int(len(content) * ratio * 0.9)  # 留点 buffer

        return content[:target_chars] + "...(已压缩)"


class ContextUsageMonitor:
    """
    上下文使用监控器。

    跟踪和报告上下文使用情况，帮助优化记忆管理。
    """

    def __init__(self):
        """初始化监控器。"""
        self._history: List[Dict[str, Any]] = []
        self._alerts: List[str] = []

    def record(self, stats: Dict[str, Any]) -> None:
        """记录一次使用统计。"""
        self._history.append({
            "timestamp": __import__("time").time(),
            **stats,
        })

        # 检查是否需要告警
        total = stats.get("total_estimated_tokens", 0)
        budget = stats.get("budget_available", 1)
        utilization = total / budget if budget > 0 else 0

        if utilization > 0.9:
            self._alerts.append(f"高上下文使用率告警: {utilization:.1%}")
            logger.warning("上下文使用率过高: %.1f%%", utilization * 100)

    def get_summary(self) -> Dict[str, Any]:
        """获取监控摘要。"""
        if not self._history:
            return {"status": "no_data"}

        recent = self._history[-10:]  # 最近 10 条
        avg_utilization = sum(
            h.get("total_estimated_tokens", 0) / h.get("budget_available", 1)
            for h in recent
        ) / len(recent)

        return {
            "total_records": len(self._history),
            "recent_avg_utilization": avg_utilization,
            "alerts_count": len(self._alerts),
            "recent_alerts": self._alerts[-5:],
        }

    def clear_alerts(self) -> None:
        """清除告警。"""
        self._alerts.clear()


# 全局实例
default_memory_manager = HierarchicalMemoryManager()
default_monitor = ContextUsageMonitor()


def get_optimized_context(state: GraphState) -> str:
    """
    获取优化后的上下文字符串。

    便捷函数，使用默认管理器。

    Args:
        state: 当前图状态

    Returns:
        优化后的上下文字符串
    """
    default_memory_manager.update_from_state(state)
    context = default_memory_manager.get_context_string()

    # 记录使用情况
    stats = default_memory_manager.get_usage_stats()
    default_monitor.record(stats)

    return context
