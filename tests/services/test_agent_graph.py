import json
import pytest

from services.agent_graph.planner import TaskGraphPlanner
from services.agent_graph.executor import GraphExecutor, TaskGraphExecutionContext
from services.agent_graph.schema import PlannerContext, TaskGraph, GraphNode
from services.data_query_service import DataQueryResult, QueryDataset


class _StubDataQueryService:
    def __init__(self, result: DataQueryResult):
        self.result = result
        self.calls = 0

    def query(self, *args, **kwargs):
        self.calls += 1
        return self.result


class _StubLLMClient:
    def __init__(self, payload: dict):
        self._response = json.dumps(payload, ensure_ascii=False)

    def chat(self, *args, **kwargs):
        return self._response


def _build_query_result(items):
    dataset = QueryDataset(
        route_id="demo.route",
        provider="demo",
        name="demo",
        generated_path="/demo",
        items=items,
        feed_title="demo feed",
        source="local",
    )
    return DataQueryResult(
        status="success",
        items=list(items),
        feed_title="demo feed",
        generated_path="/demo",
        source="local",
        datasets=[dataset],
    )


def test_task_graph_planner_detects_keyword_filter():
    llm_payload = {
        "reasoning": "需要先拉取投稿再过滤标题",
        "nodes": [
            {
                "id": "fetch",
                "type": "fetch_data",
                "tool": "fetch_public_data",
                "description": "获取影视飓风投稿",
                "params": {"query": "B站影视飓风投稿视频", "filter_datasource": "bilibili"},
                "input_refs": [],
                "expected_output": "DataQueryResult",
            },
            {
                "id": "filter",
                "type": "transform",
                "tool": "filter_data",
                "description": "只保留标题包含英雄联盟的视频",
                "params": {
                    "strategy": "keyword",
                    "target_field": "title",
                    "keywords": ["英雄联盟"],
                },
                "input_refs": ["fetch"],
                "expected_output": "DataQueryResult",
            },
        ],
        "metadata": {"output_node": "filter"},
    }
    planner = TaskGraphPlanner(llm_client=_StubLLMClient(llm_payload))
    query = 'B站影视飓风投稿视频中，标题包含"英雄联盟"的视频'
    plan = planner.plan(query, PlannerContext())

    assert len(plan.graph.nodes) == 2
    fetch_node, filter_node = plan.graph.nodes
    assert fetch_node.type == "fetch_data"
    assert filter_node.tool == "filter_data"
    assert "英雄联盟" in filter_node.params["keywords"]


def test_graph_executor_filters_dataset():
    items = [
        {"title": "英雄联盟周报"},
        {"title": "科技早报"},
        {"title": "英雄联盟赛事点评"},
    ]
    query_result = _build_query_result(items)
    data_service = _StubDataQueryService(query_result)
    executor = GraphExecutor(data_query_service=data_service)

    llm_payload = {
        "reasoning": "拉取一次投稿并过滤标题",
        "nodes": [
            {
                "id": "fetch",
                "type": "fetch_data",
                "tool": "fetch_public_data",
                "description": "获取投稿",
                "params": {"query": '标题包含"英雄联盟"', "filter_datasource": None},
                "input_refs": [],
                "expected_output": "DataQueryResult",
            },
            {
                "id": "filter",
                "type": "transform",
                "tool": "filter_data",
                "description": "过滤标题包含关键词",
                "params": {
                    "strategy": "keyword",
                    "target_field": "title",
                    "keywords": ["英雄联盟"],
                },
                "input_refs": ["fetch"],
                "expected_output": "DataQueryResult",
            },
        ],
        "metadata": {"output_node": "filter"},
    }
    planner = TaskGraphPlanner(llm_client=_StubLLMClient(llm_payload))
    plan = planner.plan('标题包含"英雄联盟"', PlannerContext())

    context = TaskGraphExecutionContext(
        user_query='标题包含"英雄联盟"',
        filter_datasource=None,
        use_cache=True,
        prefer_single_route=True,
        user_id=None,
    )
    exec_result = executor.execute(plan.graph, context)

    assert exec_result.success is True
    assert data_service.calls == 1
    filtered_result = exec_result.final_output
    assert isinstance(filtered_result, DataQueryResult)
    assert filtered_result.items == [
        {"title": "英雄联盟周报"},
        {"title": "英雄联盟赛事点评"},
    ]
    assert len(exec_result.node_results) == 2


def test_task_graph_detects_cyclic_dependency():
    """测试循环依赖检测。"""
    # 创建一个有循环依赖的图：A -> B -> C -> A
    nodes = [
        GraphNode(id="A", type="fetch_data", input_refs=["C"]),
        GraphNode(id="B", type="transform", input_refs=["A"]),
        GraphNode(id="C", type="transform", input_refs=["B"]),
    ]
    graph = TaskGraph(nodes=nodes)

    with pytest.raises(ValueError, match="循环依赖"):
        graph.topological_order()


def test_task_graph_empty_graph_execution():
    """测试空图执行。"""
    empty_graph = TaskGraph(nodes=[])
    data_service = _StubDataQueryService(_build_query_result([]))
    executor = GraphExecutor(data_query_service=data_service)

    context = TaskGraphExecutionContext(
        user_query="test",
        filter_datasource=None,
        use_cache=True,
        prefer_single_route=True,
        user_id=None,
    )
    result = executor.execute(empty_graph, context)

    # 空图执行应该成功但无输出
    assert result.success is False  # 没有节点产生输出
    assert result.final_output is None
    assert len(result.node_results) == 0


def test_planner_fallback_on_invalid_json():
    """测试 LLM 返回无效 JSON 时的降级处理。"""

    class _InvalidJsonLLMClient:
        def chat(self, *args, **kwargs):
            return "这不是有效的 JSON 响应"

    planner = TaskGraphPlanner(llm_client=_InvalidJsonLLMClient())
    plan = planner.plan("测试查询", PlannerContext())

    # 应该降级为单节点计划
    assert plan.complexity == "single_step"
    assert len(plan.graph.nodes) == 1
    assert plan.graph.nodes[0].type == "fetch_data"
    assert "fallback" in plan.llm_trace.get("mode", "")


def test_planner_fallback_without_llm_client():
    """测试没有 LLM 客户端时的降级处理。"""
    planner = TaskGraphPlanner(llm_client=None)
    plan = planner.plan("测试查询", PlannerContext())

    # 应该降级为单节点计划
    assert plan.complexity == "single_step"
    assert len(plan.graph.nodes) == 1
    assert plan.graph.nodes[0].type == "fetch_data"


def test_executor_handles_missing_input_ref():
    """测试执行器处理缺失输入引用的情况。

    当节点引用不存在的输入时，拓扑排序会检测到无法解决的依赖并报告错误。
    """
    nodes = [
        GraphNode(
            id="transform_node",
            type="transform",
            tool="filter_data",
            input_refs=["non_existent_node"],  # 引用不存在的节点
            params={"keywords": ["test"]},
        ),
    ]
    graph = TaskGraph(nodes=nodes)
    data_service = _StubDataQueryService(_build_query_result([]))
    executor = GraphExecutor(data_query_service=data_service)

    context = TaskGraphExecutionContext(
        user_query="test",
        filter_datasource=None,
        use_cache=True,
        prefer_single_route=True,
        user_id=None,
    )
    result = executor.execute(graph, context)

    # 应该失败（拓扑排序检测到无法解决的依赖）
    assert result.success is False
    assert result.error is not None
    # 由于拓扑排序失败，不会有节点执行记录
    assert len(result.node_results) == 0
