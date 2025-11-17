"""V5.0 Phase 5 - EnhancedDataStasher 集成测试。

测试 EnhancedDataStasher 的核心功能：
1. 元数据提取和质量评分
2. 知识图谱节点创建
3. 衍生关系边创建（DERIVED_FROM）
4. 对比关系边创建（COMPARED_WITH）
"""

import pytest
from unittest.mock import Mock
from langgraph_agents.agents.enhanced_data_stasher import (
    create_enhanced_data_stasher_node
)
from langgraph_agents.knowledge_graph import (
    KnowledgeGraph,
    NodeType,
    EdgeType
)
from langgraph_agents.state import (
    EnhancedDataReference,
    GraphState,
    ToolCall,
    ToolExecutionPayload
)
from langgraph_agents.runtime import LangGraphRuntime
from langgraph_agents.storage import InMemoryResearchDataStore


@pytest.fixture
def mock_runtime():
    """创建模拟的 Runtime。"""
    runtime = Mock(spec=LangGraphRuntime)
    runtime.data_store = InMemoryResearchDataStore()
    runtime.summarizer_llm = None  # 使用兜底摘要
    runtime.cheap_summary_max_chars = 200
    return runtime


@pytest.fixture
def knowledge_graph():
    """创建空的知识图谱。"""
    return KnowledgeGraph()


class TestEnhancedDataStasherMetadata:
    """测试元数据提取功能。"""

    def test_extracts_schema_and_statistics(self, mock_runtime):
        """测试提取 Schema 和统计信息。"""
        node_fn = create_enhanced_data_stasher_node(mock_runtime)

        # 模拟工具执行结果
        raw_data = {
            "items": [
                {"id": "1", "title": "测试标题1", "view_count": 1000},
                {"id": "2", "title": "测试标题2", "view_count": 2000},
                {"id": "3", "title": None, "view_count": 3000}
            ]
        }

        pending = ToolExecutionPayload(
            call=ToolCall(
                step_id=1,
                plugin_id="fetch_public_data",
                description="获取公开数据",
                args={"route": "bilibili/user/video"}
            ),
            raw_output=raw_data,
            status="success"
        )

        state: GraphState = {
            "pending_tool_result": pending,
            "data_stash": []
        }

        result = node_fn(state)

        # 验证 data_stash 包含 EnhancedDataReference
        assert len(result["data_stash"]) == 1
        ref = result["data_stash"][0]
        assert isinstance(ref, EnhancedDataReference)

        # 验证 Schema 信息
        assert ref.schema_info is not None
        assert "id" in ref.schema_info
        assert "title" in ref.schema_info
        assert "view_count" in ref.schema_info
        assert ref.schema_info["id"] == "str"
        assert ref.schema_info["view_count"] == "int"

        # 验证统计信息
        assert ref.statistics is not None
        assert ref.statistics["record_count"] == 3
        assert "field_stats" in ref.statistics
        assert ref.statistics["field_stats"]["title"]["non_null_count"] == 2
        assert ref.statistics["field_stats"]["title"]["completeness"] == pytest.approx(2/3, rel=0.01)

        # 验证样本数据
        assert ref.sample_items is not None
        assert len(ref.sample_items) == 3

        # 验证质量评分
        assert ref.quality_score is not None
        assert ref.quality_score > 0.5
        assert ref.quality_score <= 1.0

    def test_handles_needs_user_input_status(self, mock_runtime):
        """测试 needs_user_input 状态（不存储到 data_store）。"""
        node_fn = create_enhanced_data_stasher_node(mock_runtime)

        pending = ToolExecutionPayload(
            call=ToolCall(
                step_id=1,
                plugin_id="ask_user_clarification",
                description="询问用户",
                args={"question": "请选择平台"}
            ),
            raw_output={"question": "请选择平台", "options": ["B站", "知乎"]},
            status="needs_user_input"
        )

        state: GraphState = {
            "pending_tool_result": pending,
            "data_stash": []
        }

        result = node_fn(state)

        # 验证 data_id 为 None（未存储）
        ref = result["data_stash"][0]
        assert ref.data_id is None
        assert ref.status == "needs_user_input"
        assert "等待用户澄清" in ref.summary

        # 验证元数据为 None
        assert ref.schema_info is None
        assert ref.statistics is None
        assert ref.quality_score is None


class TestEnhancedDataStasherGraphIntegration:
    """测试知识图谱集成功能。"""

    def test_creates_graph_node_for_successful_data(self, mock_runtime):
        """测试为成功数据创建图节点。"""
        node_fn = create_enhanced_data_stasher_node(mock_runtime)

        raw_data = {
            "items": [
                {"id": "1", "title": "测试"}
            ]
        }

        pending = ToolExecutionPayload(
            call=ToolCall(
                step_id=1,
                plugin_id="fetch_public_data",
                description="获取公开数据",
                args={"route": "bilibili/user/video"}
            ),
            raw_output=raw_data,
            status="success"
        )

        state: GraphState = {
            "pending_tool_result": pending,
            "data_stash": [],
            "knowledge_graph": KnowledgeGraph()
        }

        result = node_fn(state)

        # 验证图谱包含新节点
        graph = result["knowledge_graph"]
        assert len(graph.nodes) == 1

        node = graph.get_node("dataset-1")
        assert node is not None
        assert node.node_type == NodeType.DATASET
        assert node.step_id == 1
        assert node.data_id is not None
        assert node.metadata["tool_name"] == "fetch_public_data"

    def test_skips_graph_node_for_failed_data(self, mock_runtime):
        """测试失败数据不创建图节点。"""
        node_fn = create_enhanced_data_stasher_node(mock_runtime)

        pending = ToolExecutionPayload(
            call=ToolCall(
                step_id=1,
                plugin_id="fetch_public_data",
                description="获取公开数据",
                args={"route": "invalid"}
            ),
            raw_output={"error": "API 错误"},
            status="error",
            error_message="API 调用失败"
        )

        state: GraphState = {
            "pending_tool_result": pending,
            "data_stash": [],
            "knowledge_graph": KnowledgeGraph()
        }

        result = node_fn(state)

        # 验证图谱为空（失败数据不创建节点）
        graph = result["knowledge_graph"]
        assert len(graph.nodes) == 0

    def test_creates_derived_edge_with_source_ref(self, mock_runtime):
        """测试检测 source_ref 并创建衍生边。"""
        node_fn = create_enhanced_data_stasher_node(mock_runtime)

        # 第一步：创建源数据集
        source_data = {
            "items": [
                {"id": "1", "title": "源数据"}
            ]
        }

        pending1 = ToolExecutionPayload(
            call=ToolCall(
                step_id=1,
                plugin_id="fetch_public_data",
                description="获取公开数据",
                args={"route": "bilibili/user/video"}
            ),
            raw_output=source_data,
            status="success"
        )

        state1: GraphState = {
            "pending_tool_result": pending1,
            "data_stash": [],
            "knowledge_graph": KnowledgeGraph()
        }

        result1 = node_fn(state1)

        # 第二步：创建派生数据集（filter_data）
        filtered_data = {
            "items": [
                {"id": "1", "title": "源数据"}  # 过滤后的结果
            ]
        }

        pending2 = ToolExecutionPayload(
            call=ToolCall(
                step_id=2,
                plugin_id="filter_data",
                description="过滤数据",
                args={
                    "source_ref": {"$ref": {"step_id": 1}},
                    "conditions": [{"field": "view_count", "operator": "gt", "value": 1000}]
                }
            ),
            raw_output=filtered_data,
            status="success"
        )

        state2: GraphState = {
            "pending_tool_result": pending2,
            "last_tool_result": pending2,  # EnhancedDataStasher 需要这个
            "data_stash": result1["data_stash"],
            "knowledge_graph": result1["knowledge_graph"]
        }

        result2 = node_fn(state2)

        # 验证图谱包含两个节点
        graph = result2["knowledge_graph"]
        assert len(graph.nodes) == 2

        # 验证衍生边存在
        assert len(graph.edges) == 1
        edge_id = next(iter(graph.edges.keys()))
        edge = graph.edges[edge_id]
        assert edge.edge_type == EdgeType.DERIVED_FROM
        assert edge.source_node_id == "dataset-1"
        assert edge.target_node_id == "dataset-2"
        assert edge.metadata["operation"] == "filter_data"

    def test_creates_comparison_edges_with_compare_data(self, mock_runtime):
        """测试 compare_data 工具创建对比边。"""
        node_fn = create_enhanced_data_stasher_node(mock_runtime)

        # 创建两个源数据集
        graph = KnowledgeGraph()
        data_stash = []

        for i in range(1, 3):
            source_data = {
                "items": [{"id": str(i), "title": f"数据{i}"}]
            }

            pending = ToolExecutionPayload(
                call=ToolCall(
                    step_id=i,
                    plugin_id="fetch_public_data",
                description="获取公开数据",
                    args={"route": f"bilibili/user/video/{i}"}
                ),
                raw_output=source_data,
                status="success"
            )

            state: GraphState = {
                "pending_tool_result": pending,
                "data_stash": data_stash,
                "knowledge_graph": graph
            }

            result = node_fn(state)
            graph = result["knowledge_graph"]
            data_stash = result["data_stash"]

        # 第三步：对比两个数据集
        comparison_result = {
            "items": [
                {
                    "diff_type": "only_in_source1",
                    "item": {"id": "1", "title": "数据1"}
                }
            ]
        }

        pending3 = ToolExecutionPayload(
            call=ToolCall(
                step_id=3,
                plugin_id="compare_data",
                description="对比数据",
                args={
                    "source_refs": [
                        {"$ref": {"step_id": 1}},
                        {"$ref": {"step_id": 2}}
                    ],
                    "mode": "diff"
                }
            ),
            raw_output=comparison_result,
            status="success"
        )

        state3: GraphState = {
            "pending_tool_result": pending3,
            "last_tool_result": pending3,
            "data_stash": data_stash,
            "knowledge_graph": graph
        }

        result3 = node_fn(state3)

        # 验证图谱包含三个节点
        final_graph = result3["knowledge_graph"]
        assert len(final_graph.nodes) == 3

        # 验证对比边存在（两条）
        comparison_edges = [
            edge for edge in final_graph.edges.values()
            if edge.edge_type == EdgeType.COMPARED_WITH
        ]
        assert len(comparison_edges) == 2

        # 验证边的源和目标
        edge1 = comparison_edges[0]
        edge2 = comparison_edges[1]
        assert edge1.source_node_id == "dataset-1"
        assert edge1.target_node_id == "dataset-3"
        assert edge2.source_node_id == "dataset-2"
        assert edge2.target_node_id == "dataset-3"


class TestEnhancedDataStasherComplexScenarios:
    """测试复杂场景。"""

    def test_multi_step_workflow_with_lineage(self, mock_runtime):
        """测试多步工作流的完整血缘链。"""
        node_fn = create_enhanced_data_stasher_node(mock_runtime)

        graph = KnowledgeGraph()
        data_stash = []

        # 步骤 1: 获取原始数据
        raw_data = {
            "items": [
                {"id": "1", "view_count": 500},
                {"id": "2", "view_count": 1500},
                {"id": "3", "view_count": 2500}
            ]
        }

        pending1 = ToolExecutionPayload(
            call=ToolCall(
                step_id=1,
                plugin_id="fetch_public_data",
                description="获取公开数据",
                args={"route": "bilibili/user/video"}
            ),
            raw_output=raw_data,
            status="success"
        )

        state1: GraphState = {
            "pending_tool_result": pending1,
            "data_stash": data_stash,
            "knowledge_graph": graph
        }
        result1 = node_fn(state1)
        graph = result1["knowledge_graph"]
        data_stash = result1["data_stash"]

        # 步骤 2: 过滤数据（view_count > 1000）
        filtered_data = {
            "items": [
                {"id": "2", "view_count": 1500},
                {"id": "3", "view_count": 2500}
            ]
        }

        pending2 = ToolExecutionPayload(
            call=ToolCall(
                step_id=2,
                plugin_id="filter_data",
                description="过滤数据",
                args={
                    "source_ref": {"$ref": {"step_id": 1}},
                    "conditions": [{"field": "view_count", "operator": "gt", "value": 1000}]
                }
            ),
            raw_output=filtered_data,
            status="success"
        )

        state2: GraphState = {
            "pending_tool_result": pending2,
            "last_tool_result": pending2,
            "data_stash": data_stash,
            "knowledge_graph": graph
        }
        result2 = node_fn(state2)
        graph = result2["knowledge_graph"]
        data_stash = result2["data_stash"]

        # 步骤 3: 聚合统计
        aggregated_data = {
            "items": [
                {"view_count_sum": 4000, "count": 2}
            ]
        }

        pending3 = ToolExecutionPayload(
            call=ToolCall(
                step_id=3,
                plugin_id="aggregate_data",
                description="聚合数据",
                args={
                    "source_ref": {"$ref": {"step_id": 2}},
                    "aggregations": [{"function": "sum", "field": "view_count"}]
                }
            ),
            raw_output=aggregated_data,
            status="success"
        )

        state3: GraphState = {
            "pending_tool_result": pending3,
            "last_tool_result": pending3,
            "data_stash": data_stash,
            "knowledge_graph": graph
        }
        result3 = node_fn(state3)
        final_graph = result3["knowledge_graph"]

        # 验证完整血缘链：1 -> 2 -> 3
        assert len(final_graph.nodes) == 3
        assert len(final_graph.edges) == 2

        # 验证血缘追溯
        ancestors = final_graph.trace_lineage("dataset-3")
        assert len(ancestors) == 2
        assert ancestors[0].node_id == "dataset-2"
        assert ancestors[1].node_id == "dataset-1"

    def test_handles_empty_data_gracefully(self, mock_runtime):
        """测试优雅处理空数据。"""
        node_fn = create_enhanced_data_stasher_node(mock_runtime)

        empty_data = {"items": []}

        pending = ToolExecutionPayload(
            call=ToolCall(
                step_id=1,
                plugin_id="filter_data",
                description="过滤数据",
                args={"source_ref": {"$ref": {"step_id": 0}}}
            ),
            raw_output=empty_data,
            status="success"
        )

        state: GraphState = {
            "pending_tool_result": pending,
            "data_stash": [],
            "knowledge_graph": KnowledgeGraph()
        }

        result = node_fn(state)

        # 验证引用被创建（即使数据为空）
        ref = result["data_stash"][0]
        assert ref.data_id is not None
        assert ref.statistics is not None
        assert ref.statistics["record_count"] == 0

        # 空数据无法提取 schema，所以不会创建图节点
        graph = result["knowledge_graph"]
        assert len(graph.nodes) == 0
        # 但数据引用仍然被保存
        assert ref.schema_info is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
