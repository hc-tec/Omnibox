"""V5.0 Phase 5 - KnowledgeGraph 和增强元数据测试。"""

import pytest
from langgraph_agents.knowledge_graph import (
    KnowledgeGraph,
    GraphNode,
    GraphEdge,
    NodeType,
    EdgeType
)
from langgraph_agents.metadata_extractor import (
    extract_schema_info,
    extract_statistics,
    extract_sample_items,
    calculate_quality_score
)
from langgraph_agents.state import EnhancedDataReference


class TestKnowledgeGraph:
    """测试 KnowledgeGraph 核心功能。"""

    def test_add_node(self):
        """测试添加节点。"""
        graph = KnowledgeGraph()

        node = GraphNode(
            node_id="dataset-1",
            node_type=NodeType.DATASET,
            step_id=1,
            data_id="data-123",
            record_count=100
        )

        graph.add_node(node)

        assert len(graph.nodes) == 1
        assert graph.get_node("dataset-1") == node

    def test_add_edge(self):
        """测试添加边。"""
        graph = KnowledgeGraph()

        # 添加两个节点
        node1 = GraphNode(
            node_id="dataset-1",
            node_type=NodeType.DATASET,
            step_id=1,
            data_id="data-123"
        )
        node2 = GraphNode(
            node_id="dataset-2",
            node_type=NodeType.DATASET,
            step_id=2,
            data_id="data-456"
        )

        graph.add_node(node1)
        graph.add_node(node2)

        # 添加边
        edge = GraphEdge(
            edge_id="edge-1-2",
            edge_type=EdgeType.DERIVED_FROM,
            source_node_id="dataset-1",
            target_node_id="dataset-2"
        )

        graph.add_edge(edge)

        assert len(graph.edges) == 1
        assert edge.edge_id in graph.edges

    def test_trace_lineage(self):
        """测试数据血缘追溯。"""
        graph = KnowledgeGraph()

        # 创建数据血缘链：dataset-1 -> dataset-2 -> dataset-3
        for i in range(1, 4):
            node = GraphNode(
                node_id=f"dataset-{i}",
                node_type=NodeType.DATASET,
                step_id=i,
                data_id=f"data-{i}"
            )
            graph.add_node(node)

        # 添加衍生边
        edge1 = GraphEdge(
            edge_id="edge-1-2",
            edge_type=EdgeType.DERIVED_FROM,
            source_node_id="dataset-1",
            target_node_id="dataset-2"
        )
        edge2 = GraphEdge(
            edge_id="edge-2-3",
            edge_type=EdgeType.DERIVED_FROM,
            source_node_id="dataset-2",
            target_node_id="dataset-3"
        )

        graph.add_edge(edge1)
        graph.add_edge(edge2)

        # 追溯 dataset-3 的血缘
        ancestors = graph.trace_lineage("dataset-3")

        assert len(ancestors) == 2
        assert ancestors[0].node_id == "dataset-2"
        assert ancestors[1].node_id == "dataset-1"

    def test_find_related_datasets(self):
        """测试查找相关数据集。"""
        graph = KnowledgeGraph()

        # 创建三个数据集
        for i in range(1, 4):
            node = GraphNode(
                node_id=f"dataset-{i}",
                node_type=NodeType.DATASET,
                step_id=i,
                data_id=f"data-{i}"
            )
            graph.add_node(node)

        # dataset-1 和 dataset-2 对比生成 dataset-3
        edge1 = GraphEdge(
            edge_id="edge-1-3",
            edge_type=EdgeType.COMPARED_WITH,
            source_node_id="dataset-1",
            target_node_id="dataset-3"
        )
        edge2 = GraphEdge(
            edge_id="edge-2-3",
            edge_type=EdgeType.COMPARED_WITH,
            source_node_id="dataset-2",
            target_node_id="dataset-3"
        )

        graph.add_edge(edge1)
        graph.add_edge(edge2)

        # 查找 dataset-3 的相关数据集
        related = graph.find_related_datasets("dataset-3")

        assert len(related) == 2
        assert any(node.node_id == "dataset-1" for node in related)
        assert any(node.node_id == "dataset-2" for node in related)

    def test_get_statistics(self):
        """测试获取统计信息。"""
        graph = KnowledgeGraph()

        # 添加节点和边
        node1 = GraphNode(
            node_id="dataset-1",
            node_type=NodeType.DATASET,
            step_id=1,
            data_id="data-1"
        )
        node2 = GraphNode(
            node_id="insight-1",
            node_type=NodeType.INSIGHT,
            step_id=2,
            insight_text="测试见解"
        )

        graph.add_node(node1)
        graph.add_node(node2)

        edge = GraphEdge(
            edge_id="edge-1-2",
            edge_type=EdgeType.GENERATED,
            source_node_id="dataset-1",
            target_node_id="insight-1"
        )
        graph.add_edge(edge)

        stats = graph.get_statistics()

        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 1
        assert stats["node_type_counts"][NodeType.DATASET] == 1
        assert stats["node_type_counts"][NodeType.INSIGHT] == 1


class TestMetadataExtractor:
    """测试元数据提取器。"""

    def test_extract_schema_info(self):
        """测试 Schema 提取。"""
        data = {
            "items": [
                {"id": "1", "title": "测试", "view_count": 100},
                {"id": "2", "title": "测试2", "view_count": 200}
            ]
        }

        schema = extract_schema_info(data)

        assert schema is not None
        assert "id" in schema
        assert "title" in schema
        assert "view_count" in schema
        assert schema["id"] == "str"
        assert schema["view_count"] == "int"

    def test_extract_statistics(self):
        """测试统计信息提取。"""
        data = {
            "items": [
                {"id": "1", "title": "测试", "view_count": 100},
                {"id": "2", "title": None, "view_count": 200}
            ]
        }

        stats = extract_statistics(data)

        assert stats is not None
        assert stats["record_count"] == 2
        assert "field_stats" in stats
        assert stats["field_stats"]["title"]["non_null_count"] == 1
        assert stats["field_stats"]["title"]["completeness"] == 0.5

    def test_extract_sample_items(self):
        """测试样本数据提取。"""
        data = {
            "items": [
                {"id": "1"},
                {"id": "2"},
                {"id": "3"},
                {"id": "4"},
                {"id": "5"}
            ]
        }

        samples = extract_sample_items(data, sample_size=3)

        assert samples is not None
        assert len(samples) == 3
        assert samples[0]["id"] == "1"
        assert samples[2]["id"] == "3"

    def test_calculate_quality_score(self):
        """测试质量评分计算。"""
        schema = {"id": "str", "title": "str"}
        stats = {
            "field_stats": {
                "id": {"completeness": 1.0},
                "title": {"completeness": 0.8}
            }
        }

        score = calculate_quality_score(schema, stats)

        assert score > 0.5  # 应该是一个合理的分数
        assert score <= 1.0


class TestEnhancedDataReference:
    """测试 EnhancedDataReference。"""

    def test_create_enhanced_reference(self):
        """测试创建增强的数据引用。"""
        ref = EnhancedDataReference(
            step_id=1,
            tool_name="fetch_public_data",
            data_id="data-123",
            summary="测试数据",
            schema_info={"id": "str", "title": "str"},
            statistics={"record_count": 10},
            sample_items=[{"id": "1", "title": "测试"}],
            quality_score=0.95
        )

        assert ref.step_id == 1
        assert ref.schema_info["id"] == "str"
        assert ref.statistics["record_count"] == 10
        assert ref.quality_score == 0.95

    def test_enhanced_reference_backward_compatible(self):
        """测试 EnhancedDataReference 向后兼容性。"""
        # 可以像 DataReference 一样创建（不提供增强字段）
        ref = EnhancedDataReference(
            step_id=1,
            tool_name="fetch_public_data",
            data_id="data-123",
            summary="测试数据"
        )

        assert ref.step_id == 1
        assert ref.schema_info is None
        assert ref.statistics is None
        assert ref.quality_score is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
