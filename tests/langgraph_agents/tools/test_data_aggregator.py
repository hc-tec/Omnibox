"""aggregate_data 工具单元测试。"""

import pytest
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.tools.data_aggregator import register_data_aggregator_tool
from langgraph_agents.state import ToolCall
from langgraph_agents.runtime import ToolExecutionContext
from unittest.mock import MagicMock


@pytest.fixture
def registry():
    """创建测试用工具注册表。"""
    reg = ToolRegistry()
    register_data_aggregator_tool(reg)
    return reg


@pytest.fixture
def mock_data_store():
    """创建 mock data_store。"""
    store = MagicMock()
    # 模拟数据
    store.load.return_value = {
        "items": [
            {"author": "UP1", "view_count": 10000, "title": "Video 1"},
            {"author": "UP1", "view_count": 15000, "title": "Video 2"},
            {"author": "UP2", "view_count": 8000, "title": "Video 3"},
            {"author": "UP2", "view_count": 12000, "title": "Video 4"},
            {"author": "UP3", "view_count": 20000, "title": "Video 5"},
        ]
    }
    return store


def test_aggregate_simple_count(registry, mock_data_store):
    """测试简单计数聚合。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": mock_data_store}
    )

    call = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "metrics": [
                {"field": "author", "function": "count"}
            ]
        },
        step_id=1,
        description="计数测试"
    )

    result = registry.execute(call, context)

    assert result.status == "success"
    assert result.raw_output["type"] == "aggregation"
    assert result.raw_output["total_items"] == 5
    assert len(result.raw_output["groups"]) == 1
    assert result.raw_output["groups"][0]["metrics"]["count_author"] == 5


def test_aggregate_group_by(registry, mock_data_store):
    """测试分组聚合。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": mock_data_store}
    )

    call = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "group_by": ["author"],
            "metrics": [
                {"field": "author", "function": "count", "alias": "video_count"},
                {"field": "view_count", "function": "avg", "alias": "avg_views"}
            ]
        },
        step_id=1,
        description="分组聚合测试"
    )

    result = registry.execute(call, context)

    assert result.status == "success"
    assert result.raw_output["total_groups"] == 3  # UP1, UP2, UP3

    groups = result.raw_output["groups"]
    # 找到 UP1 的统计
    up1_group = next(g for g in groups if g["group_key"]["author"] == "UP1")
    assert up1_group["metrics"]["video_count"] == 2
    assert up1_group["metrics"]["avg_views"] == 12500  # (10000 + 15000) / 2


def test_aggregate_with_sort(registry, mock_data_store):
    """测试排序功能。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": mock_data_store}
    )

    call = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "group_by": ["author"],
            "metrics": [
                {"field": "view_count", "function": "avg", "alias": "avg_views"}
            ],
            "sort_by": "avg_views",
            "order": "desc"
        },
        step_id=1,
        description="排序测试"
    )

    result = registry.execute(call, context)

    assert result.status == "success"
    groups = result.raw_output["groups"]
    # 第一个应该是 UP3（avg_views = 20000）
    assert groups[0]["group_key"]["author"] == "UP3"


def test_aggregate_with_filters(registry, mock_data_store):
    """测试预过滤功能。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": mock_data_store}
    )

    call = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "filters": {
                "view_count": {"$gt": 10000}
            },
            "metrics": [
                {"field": "author", "function": "count"}
            ]
        },
        step_id=1,
        description="过滤测试"
    )

    result = registry.execute(call, context)

    assert result.status == "success"
    # 只有 3 条数据满足 view_count > 10000
    assert result.raw_output["total_items"] == 3


def test_aggregate_missing_source_ref(registry, mock_data_store):
    """测试缺少 source_ref 参数。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": mock_data_store}
    )

    call = ToolCall(
        plugin_id="aggregate_data",
        args={
            "metrics": [{"field": "author", "function": "count"}]
        },
        step_id=1,
        description="缺少参数测试"
    )

    result = registry.execute(call, context)

    assert result.status == "error"
    assert result.raw_output["error_code"] == "E101"


def test_aggregate_empty_data(registry):
    """测试空数据源。"""
    store = MagicMock()
    store.load.return_value = {"items": []}

    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": store}
    )

    call = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "empty-data",
            "metrics": [{"field": "author", "function": "count"}]
        },
        step_id=1,
        description="空数据测试"
    )

    result = registry.execute(call, context)

    assert result.status == "success"
    assert result.raw_output["total_groups"] == 0
    assert len(result.raw_output["groups"]) == 0


def test_tool_registration(registry):
    """测试工具注册。"""
    spec = registry.get("aggregate_data")
    assert spec is not None
    assert spec.plugin_id == "aggregate_data"
    assert spec.execution_mode == "full"
    assert spec.description == "对数据进行聚合统计（计数、求和、平均、分组）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
