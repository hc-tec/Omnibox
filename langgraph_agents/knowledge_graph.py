"""
KnowledgeGraph - 知识图谱数据结构（V5.0 Phase 5）。

用于组织和追踪数据关系、分析过程和见解发现。
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Dict, List, Optional, Set, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class NodeType(str, Enum):
    """知识图谱节点类型。"""
    DATASET = "dataset"      # 数据集节点
    ANALYSIS = "analysis"    # 分析节点
    INSIGHT = "insight"      # 见解节点


class EdgeType(str, Enum):
    """知识图谱边类型。"""
    DERIVED_FROM = "derived_from"    # 衍生关系（如：过滤数据衍生自原始数据）
    COMPARED_WITH = "compared_with"  # 对比关系（如：对比两个数据集）
    GENERATED = "generated"          # 生成关系（如：分析生成见解）


class GraphNode(BaseModel):
    """知识图谱节点。"""
    node_id: str = Field(..., description="节点唯一标识")
    node_type: NodeType = Field(..., description="节点类型")
    step_id: int = Field(..., description="关联的步骤 ID")
    data_id: Optional[str] = Field(None, description="关联的数据 ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="节点元数据")

    # 数据集节点特有字段
    record_count: Optional[int] = Field(None, description="记录数（仅数据集节点）")
    schema_info: Optional[Dict[str, str]] = Field(None, description="Schema 信息（仅数据集节点）")

    # 分析节点特有字段
    analysis_type: Optional[str] = Field(None, description="分析类型（仅分析节点）")

    # 见解节点特有字段
    insight_text: Optional[str] = Field(None, description="见解文本（仅见解节点）")
    confidence: Optional[float] = Field(None, description="置信度 0-1（仅见解节点）")


class GraphEdge(BaseModel):
    """知识图谱边。"""
    edge_id: str = Field(..., description="边唯一标识")
    edge_type: EdgeType = Field(..., description="边类型")
    source_node_id: str = Field(..., description="源节点 ID")
    target_node_id: str = Field(..., description="目标节点 ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="边元数据")


class KnowledgeGraph:
    """
    知识图谱，用于组织数据关系和分析过程。

    Phase 5 简化实现：
    - 内存存储（不持久化）
    - 基础图操作（添加节点、边、查询）
    - 血缘追踪（查找数据来源）
    """

    def __init__(self):
        """初始化知识图谱。"""
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[str, GraphEdge] = {}
        self._adjacency: Dict[str, Set[str]] = {}  # 邻接表：{node_id: {neighbor_ids}}

    def add_node(self, node: GraphNode) -> None:
        """
        添加节点到图中。

        Args:
            node: 图节点
        """
        self.nodes[node.node_id] = node
        if node.node_id not in self._adjacency:
            self._adjacency[node.node_id] = set()

        logger.debug(f"KnowledgeGraph: 添加节点 {node.node_id} (type={node.node_type})")

    def add_edge(self, edge: GraphEdge) -> None:
        """
        添加边到图中。

        Args:
            edge: 图边
        """
        # 验证节点存在
        if edge.source_node_id not in self.nodes:
            logger.warning(
                f"KnowledgeGraph: 源节点 {edge.source_node_id} 不存在，跳过添加边"
            )
            return

        if edge.target_node_id not in self.nodes:
            logger.warning(
                f"KnowledgeGraph: 目标节点 {edge.target_node_id} 不存在，跳过添加边"
            )
            return

        self.edges[edge.edge_id] = edge
        self._adjacency[edge.source_node_id].add(edge.target_node_id)

        logger.debug(
            f"KnowledgeGraph: 添加边 {edge.source_node_id} --{edge.edge_type}--> "
            f"{edge.target_node_id}"
        )

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """
        获取节点。

        Args:
            node_id: 节点 ID

        Returns:
            图节点，不存在返回 None
        """
        return self.nodes.get(node_id)

    def get_edges_from(self, node_id: str) -> List[GraphEdge]:
        """
        获取从指定节点出发的所有边。

        Args:
            node_id: 节点 ID

        Returns:
            边列表
        """
        return [
            edge for edge in self.edges.values()
            if edge.source_node_id == node_id
        ]

    def get_edges_to(self, node_id: str) -> List[GraphEdge]:
        """
        获取指向指定节点的所有边。

        Args:
            node_id: 节点 ID

        Returns:
            边列表
        """
        return [
            edge for edge in self.edges.values()
            if edge.target_node_id == node_id
        ]

    def trace_lineage(self, node_id: str, max_depth: int = 10) -> List[GraphNode]:
        """
        追溯数据血缘（向上查找所有祖先节点）。

        Args:
            node_id: 起始节点 ID
            max_depth: 最大追溯深度

        Returns:
            祖先节点列表（按深度优先顺序）
        """
        ancestors = []
        visited = set()

        def dfs(current_id: str, depth: int):
            if depth > max_depth or current_id in visited:
                return

            visited.add(current_id)

            # 查找所有指向当前节点的边
            incoming_edges = self.get_edges_to(current_id)
            for edge in incoming_edges:
                if edge.edge_type == EdgeType.DERIVED_FROM:
                    source_node = self.get_node(edge.source_node_id)
                    if source_node:
                        ancestors.append(source_node)
                        dfs(edge.source_node_id, depth + 1)

        dfs(node_id, 0)
        return ancestors

    def find_related_datasets(self, node_id: str) -> List[GraphNode]:
        """
        查找与指定节点相关的所有数据集节点。

        Args:
            node_id: 起始节点 ID

        Returns:
            相关数据集节点列表
        """
        related = []

        # 查找直接相关的节点
        outgoing_edges = self.get_edges_from(node_id)
        incoming_edges = self.get_edges_to(node_id)

        all_neighbor_ids = set()
        for edge in outgoing_edges + incoming_edges:
            if edge.source_node_id != node_id:
                all_neighbor_ids.add(edge.source_node_id)
            if edge.target_node_id != node_id:
                all_neighbor_ids.add(edge.target_node_id)

        # 过滤出数据集节点
        for neighbor_id in all_neighbor_ids:
            node = self.get_node(neighbor_id)
            if node and node.node_type == NodeType.DATASET:
                related.append(node)

        return related

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取知识图谱统计信息。

        Returns:
            统计信息字典
        """
        node_type_counts = {}
        for node in self.nodes.values():
            node_type_counts[node.node_type] = node_type_counts.get(node.node_type, 0) + 1

        edge_type_counts = {}
        for edge in self.edges.values():
            edge_type_counts[edge.edge_type] = edge_type_counts.get(edge.edge_type, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_type_counts": node_type_counts,
            "edge_type_counts": edge_type_counts
        }
