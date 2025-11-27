"""
Task Graph Schema 定义。

该模块提供 Task Graph、节点以及执行记录的基础数据结构，供 Planner 与
Executor 共同复用。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

GraphNodeType = Literal["fetch_data", "transform", "analysis", "interaction", "output"]
GraphNodeStatus = Literal["pending", "running", "success", "error", "skipped"]


@dataclass
class GraphNode:
    """任务图节点定义。"""

    id: str
    type: GraphNodeType
    description: str = ""
    tool: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    input_refs: List[str] = field(default_factory=list)
    expected_output: Optional[str] = None
    streaming_label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典。"""
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "tool": self.tool,
            "params": self.params,
            "input_refs": list(self.input_refs),
            "expected_output": self.expected_output,
            "streaming_label": self.streaming_label,
        }


@dataclass
class TaskGraph:
    """任务图，由若干节点以及元数据组成。"""

    nodes: List[GraphNode]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return next((node for node in self.nodes if node.id == node_id), None)

    def topological_order(self) -> List[GraphNode]:
        """按依赖拓扑排序，若检测到循环依赖则抛出异常。"""
        ordered: List[GraphNode] = []
        resolved = set()
        remaining = {node.id: node for node in self.nodes}

        while remaining:
            progress = False
            for node_id, node in list(remaining.items()):
                if all(ref in resolved for ref in node.input_refs):
                    ordered.append(node)
                    resolved.add(node_id)
                    remaining.pop(node_id)
                    progress = True
            if not progress:
                raise ValueError("TaskGraph 存在循环依赖，无法进行拓扑排序")
        return ordered

    def output_node_id(self) -> Optional[str]:
        if "output_node" in self.metadata:
            return self.metadata["output_node"]
        return self.nodes[-1].id if self.nodes else None


@dataclass
class NodeExecutionRecord:
    """记录单个节点执行情况。"""

    node_id: str
    node_type: GraphNodeType
    status: GraphNodeStatus
    started_at: datetime
    finished_at: datetime
    summary: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def duration(self) -> float:
        return max(self.finished_at.timestamp() - self.started_at.timestamp(), 0.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration": round(self.duration(), 3),
            "summary": self.summary,
            "error": self.error,
        }


@dataclass
class GraphExecutionResult:
    """任务图执行结果。"""

    success: bool
    final_output: Any = None
    node_results: List[NodeExecutionRecord] = field(default_factory=list)
    graph_metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_debug_payload(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "graph_metadata": self.graph_metadata,
            "nodes": [record.to_dict() for record in self.node_results],
        }


@dataclass
class TaskGraphPlan:
    """Planner 输出的任务图计划。"""

    graph: TaskGraph
    reasoning: str
    complexity: Literal["single_step", "multi_step"]
    requires_research: bool = False
    llm_trace: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerContext:
    """提供给 Planner 的上下文信息。"""

    intent_hint: Optional[str] = None
    filter_datasource: Optional[str] = None
    user_id: Optional[int] = None
