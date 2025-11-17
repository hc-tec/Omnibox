"""V5.0 Phase 5 - 边界情况和错误处理测试。"""

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
from langgraph_agents.graph_helper import (
    get_data_lineage_summary,
    get_related_datasets_summary,
    has_sufficient_data_coverage,
    get_quality_summary,
    should_continue_research
)
from langgraph_agents.state import EnhancedDataReference, GraphState


class TestKnowledgeGraphEdgeCases:
    """测试 KnowledgeGraph 边界情况。"""

    def test_add_duplicate_node(self):
        """测试添加重复节点（应该覆盖原节点）。"""
        graph = KnowledgeGraph()

        node1 = GraphNode(
            node_id="dataset-1",
            node_type=NodeType.DATASET,
            step_id=1,
            data_id="data-123"
        )
        node2 = GraphNode(
            node_id="dataset-1",  # 相同 ID
            node_type=NodeType.DATASET,
            step_id=2,
            data_id="data-456"  # 不同数据
        )

        graph.add_node(node1)
        graph.add_node(node2)

        # 应该只有一个节点，使用最新的数据
        assert len(graph.nodes) == 1
        assert graph.get_node("dataset-1").data_id == "data-456"

    def test_add_edge_missing_source_node(self):
        """测试添加边时源节点不存在（应该被拒绝）。"""
        graph = KnowledgeGraph()

        node = GraphNode(
            node_id="dataset-2",
            node_type=NodeType.DATASET,
            step_id=2,
            data_id="data-456"
        )
        graph.add_node(node)

        edge = GraphEdge(
            edge_id="edge-1-2",
            edge_type=EdgeType.DERIVED_FROM,
            source_node_id="dataset-1",  # 不存在
            target_node_id="dataset-2"
        )

        # 实现会拒绝添加（正确行为）
        graph.add_edge(edge)
        assert len(graph.edges) == 0  # 应该被拒绝

    def test_trace_lineage_nonexistent_node(self):
        """测试追溯不存在节点的血缘。"""
        graph = KnowledgeGraph()

        ancestors = graph.trace_lineage("nonexistent-node")
        assert ancestors == []

    def test_trace_lineage_circular_dependency(self):
        """测试循环依赖检测（max_depth 限制）。"""
        graph = KnowledgeGraph()

        # 创建循环：1 -> 2 -> 3 -> 1
        for i in range(1, 4):
            node = GraphNode(
                node_id=f"dataset-{i}",
                node_type=NodeType.DATASET,
                step_id=i,
                data_id=f"data-{i}"
            )
            graph.add_node(node)

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
        edge3 = GraphEdge(
            edge_id="edge-3-1",
            edge_type=EdgeType.DERIVED_FROM,
            source_node_id="dataset-3",
            target_node_id="dataset-1"
        )

        graph.add_edge(edge1)
        graph.add_edge(edge2)
        graph.add_edge(edge3)

        # 应该在 max_depth 处停止
        ancestors = graph.trace_lineage("dataset-3", max_depth=5)
        assert len(ancestors) <= 5  # 不会无限循环

    def test_find_related_datasets_empty(self):
        """测试查找无相关数据集的节点。"""
        graph = KnowledgeGraph()

        node = GraphNode(
            node_id="dataset-1",
            node_type=NodeType.DATASET,
            step_id=1,
            data_id="data-1"
        )
        graph.add_node(node)

        related = graph.find_related_datasets("dataset-1")
        assert related == []

    def test_statistics_empty_graph(self):
        """测试空图的统计信息。"""
        graph = KnowledgeGraph()

        stats = graph.get_statistics()
        assert stats["total_nodes"] == 0
        assert stats["total_edges"] == 0
        assert stats["node_type_counts"] == {}


class TestMetadataExtractorEdgeCases:
    """测试元数据提取器边界情况。"""

    def test_extract_schema_empty_list(self):
        """测试提取空列表的 Schema。"""
        data = {"items": []}
        schema = extract_schema_info(data)
        assert schema is None

    def test_extract_schema_data_field(self):
        """测试从 'data' 字段提取 Schema。"""
        data = {
            "data": [
                {"id": "1", "name": "测试"}
            ]
        }
        schema = extract_schema_info(data)
        assert schema is not None
        assert "id" in schema
        assert "name" in schema

    def test_extract_schema_plain_list(self):
        """测试直接列表格式。"""
        data = [
            {"id": "1", "name": "测试"}
        ]
        schema = extract_schema_info(data)
        assert schema is not None
        assert "id" in schema

    def test_extract_schema_mixed_types(self):
        """测试字段类型不一致（使用第一条的类型）。"""
        data = {
            "items": [
                {"value": 100},  # int
                {"value": "text"}  # str
            ]
        }
        schema = extract_schema_info(data)
        assert schema is not None
        assert schema["value"] == "int"  # 使用第一条

    def test_extract_schema_nested_objects(self):
        """测试嵌套对象（只提取第一层）。"""
        data = {
            "items": [
                {
                    "id": "1",
                    "author": {"name": "张三", "age": 30}
                }
            ]
        }
        schema = extract_schema_info(data)
        assert schema is not None
        assert schema["id"] == "str"
        assert schema["author"] == "dict"

    def test_extract_statistics_empty_list(self):
        """测试空列表的统计信息。"""
        data = {"items": []}
        stats = extract_statistics(data)
        assert stats is not None
        assert stats["record_count"] == 0

    def test_extract_statistics_all_null_field(self):
        """测试所有值都是 None 的字段。"""
        data = {
            "items": [
                {"id": "1", "title": None},
                {"id": "2", "title": None}
            ]
        }
        stats = extract_statistics(data)
        assert stats["field_stats"]["title"]["non_null_count"] == 0
        assert stats["field_stats"]["title"]["completeness"] == 0.0

    def test_extract_sample_items_less_than_sample_size(self):
        """测试数据量少于 sample_size。"""
        data = {
            "items": [
                {"id": "1"},
                {"id": "2"}
            ]
        }
        samples = extract_sample_items(data, sample_size=5)
        assert len(samples) == 2  # 只有 2 条，全部返回

    def test_calculate_quality_score_no_schema(self):
        """测试没有 Schema 时的质量评分。"""
        score = calculate_quality_score(None, None)
        assert score == 0.5  # 默认中等质量

    def test_calculate_quality_score_exact_value(self):
        """测试质量评分的精确值。"""
        schema = {"id": "str", "title": "str"}
        stats = {
            "field_stats": {
                "id": {"completeness": 1.0},
                "title": {"completeness": 0.8}
            }
        }
        score = calculate_quality_score(schema, stats)

        # 计算：schema 完整性 = 1.0
        #      字段完整性 = (1.0 + 0.8) / 2 = 0.9
        #      平均 = (1.0 + 0.9) / 2 = 0.95
        assert score == pytest.approx(0.95, rel=0.01)


class TestGraphHelperFunctions:
    """测试 GraphHelper 辅助函数。"""

    def test_get_data_lineage_summary_no_graph(self):
        """测试没有知识图谱时的血缘摘要。"""
        state: GraphState = {}
        summary = get_data_lineage_summary(state, step_id=1)
        assert summary == "无知识图谱信息"

    def test_get_data_lineage_summary_no_ancestors(self):
        """测试原始数据（无上游依赖）。"""
        graph = KnowledgeGraph()
        node = GraphNode(
            node_id="dataset-1",
            node_type=NodeType.DATASET,
            step_id=1,
            data_id="data-1"
        )
        graph.add_node(node)

        state: GraphState = {"knowledge_graph": graph}
        summary = get_data_lineage_summary(state, step_id=1)
        assert summary == "原始数据（无上游依赖）"

    def test_has_sufficient_data_coverage(self):
        """测试数据覆盖检查。"""
        state: GraphState = {
            "data_stash": [
                EnhancedDataReference(
                    step_id=1,
                    tool_name="fetch_public_data",
                    data_id="data-1",
                    summary="测试",
                    status="success"
                ),
                EnhancedDataReference(
                    step_id=2,
                    tool_name="filter_data",
                    data_id="data-2",
                    summary="测试",
                    status="success"
                ),
                EnhancedDataReference(
                    step_id=3,
                    tool_name="compare_data",
                    data_id=None,  # 失败的
                    summary="错误",
                    status="error"
                )
            ]
        }

        # 最少 2 个成功数据集
        assert has_sufficient_data_coverage(state, min_datasets=2) is True
        assert has_sufficient_data_coverage(state, min_datasets=3) is False

    def test_get_quality_summary_no_quality_scores(self):
        """测试没有质量评分时的摘要。"""
        state: GraphState = {
            "data_stash": [
                EnhancedDataReference(
                    step_id=1,
                    tool_name="fetch_public_data",
                    data_id="data-1",
                    summary="测试"
                    # 没有 quality_score
                )
            ]
        }

        summary = get_quality_summary(state)
        assert summary == "无质量评分数据"

    def test_should_continue_research_with_error(self):
        """测试有错误时应该停止。"""
        state: GraphState = {
            "last_error": "测试错误"
        }
        assert should_continue_research(state) is False

    def test_should_continue_research_insufficient_data(self):
        """测试数据不足时应该继续。"""
        state: GraphState = {
            "data_stash": []
        }
        assert should_continue_research(state) is True

    def test_should_continue_research_enough_data(self):
        """测试数据充足时应该停止。"""
        state: GraphState = {
            "data_stash": [
                EnhancedDataReference(
                    step_id=i,
                    tool_name="fetch_public_data",
                    data_id=f"data-{i}",
                    summary="测试",
                    status="success"
                )
                for i in range(1, 4)
            ]
        }
        assert should_continue_research(state) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
