"""aggregate_data 工具边界情况测试。"""

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
def mock_data_store_with_mixed_types():
    """创建包含混合类型数据的 mock data_store。"""
    store = MagicMock()
    store.load.return_value = {
        "items": [
            {"author": "UP1", "view_count": 10000, "title": "Video 1"},
            {"author": "UP2", "view_count": "not_a_number", "title": "Video 2"},  # 字符串
            {"author": "UP3", "view_count": None, "title": "Video 3"},  # None
            {"author": "UP4", "view_count": True, "title": "Video 4"},  # bool
            {"author": "UP5", "view_count": 20000, "title": "Video 5"},
        ]
    }
    return store


def test_aggregate_with_non_numeric_fields(registry, mock_data_store_with_mixed_types):
    """测试聚合非数值字段时的类型过滤。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": mock_data_store_with_mixed_types}
    )

    call = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "metrics": [
                {"field": "view_count", "function": "sum"},
                {"field": "view_count", "function": "avg"},
                {"field": "view_count", "function": "min"},
                {"field": "view_count", "function": "max"},
            ]
        },
        step_id=1,
        description="非数值字段聚合测试"
    )

    result = registry.execute(call, context)

    assert result.status == "success"
    metrics = result.raw_output["groups"][0]["metrics"]

    # 应该只统计有效的数值（10000 和 20000）
    assert metrics["sum_view_count"] == 30000
    assert metrics["avg_view_count"] == 15000
    assert metrics["min_view_count"] == 10000
    assert metrics["max_view_count"] == 20000


def test_aggregate_with_all_non_numeric_fields(registry):
    """测试字段全部为非数值时的处理。"""
    store = MagicMock()
    store.load.return_value = {
        "items": [
            {"author": "UP1", "view_count": "abc"},
            {"author": "UP2", "view_count": "def"},
            {"author": "UP3", "view_count": "ghi"},
        ]
    }

    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": store}
    )

    call = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "metrics": [
                {"field": "view_count", "function": "sum"},
                {"field": "view_count", "function": "avg"},
            ]
        },
        step_id=1,
        description="全非数值字段测试"
    )

    result = registry.execute(call, context)

    assert result.status == "success"
    metrics = result.raw_output["groups"][0]["metrics"]

    # 无有效数值，sum/avg 应返回 0
    assert metrics["sum_view_count"] == 0
    assert metrics["avg_view_count"] == 0


def test_aggregate_with_new_filter_operators(registry):
    """测试新增的过滤操作符（$ne, $in, $between, $regex）。"""
    store = MagicMock()
    store.load.return_value = {
        "items": [
            {"author": "UP1", "view_count": 10000, "category": "tech"},
            {"author": "UP2", "view_count": 15000, "category": "gaming"},
            {"author": "UP3", "view_count": 20000, "category": "tech"},
            {"author": "UP4", "view_count": 25000, "category": "music"},
            {"author": "UP5", "view_count": 30000, "category": "tech"},
        ]
    }

    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": store}
    )

    # 测试 $ne
    call_ne = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "filters": {"category": {"$ne": "gaming"}},
            "metrics": [{"field": "author", "function": "count"}]
        },
        step_id=1,
        description="$ne 测试"
    )

    result_ne = registry.execute(call_ne, context)
    assert result_ne.status == "success"
    assert result_ne.raw_output["total_items"] == 4  # 排除 gaming

    # 测试 $in
    call_in = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "filters": {"category": {"$in": ["tech", "music"]}},
            "metrics": [{"field": "author", "function": "count"}]
        },
        step_id=2,
        description="$in 测试"
    )

    result_in = registry.execute(call_in, context)
    assert result_in.status == "success"
    assert result_in.raw_output["total_items"] == 4

    # 测试 $between
    call_between = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "filters": {"view_count": {"$between": [15000, 25000]}},
            "metrics": [{"field": "author", "function": "count"}]
        },
        step_id=3,
        description="$between 测试"
    )

    result_between = registry.execute(call_between, context)
    assert result_between.status == "success"
    assert result_between.raw_output["total_items"] == 3  # 15000, 20000, 25000

    # 测试 $regex
    call_regex = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "filters": {"category": {"$regex": "^te"}},  # 以 te 开头
            "metrics": [{"field": "author", "function": "count"}]
        },
        step_id=4,
        description="$regex 测试"
    )

    result_regex = registry.execute(call_regex, context)
    assert result_regex.status == "success"
    assert result_regex.raw_output["total_items"] == 3  # tech


def test_aggregate_with_non_dict_data_package(registry):
    """测试 data_store 返回非 dict 数据结构。"""
    # 测试直接返回列表
    store_list = MagicMock()
    store_list.load.return_value = [
        {"author": "UP1", "view_count": 10000},
        {"author": "UP2", "view_count": 15000},
    ]

    context_list = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": store_list}
    )

    call = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "metrics": [{"field": "author", "function": "count"}]
        },
        step_id=1,
        description="列表数据测试"
    )

    result_list = registry.execute(call, context_list)
    assert result_list.status == "success"
    assert result_list.raw_output["total_items"] == 2

    # 测试 dict with "data" key
    store_data = MagicMock()
    store_data.load.return_value = {
        "data": [
            {"author": "UP1", "view_count": 10000},
            {"author": "UP2", "view_count": 15000},
        ]
    }

    context_data = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": store_data}
    )

    result_data = registry.execute(call, context_data)
    assert result_data.status == "success"
    assert result_data.raw_output["total_items"] == 2


def test_aggregate_with_invalid_data_structure(registry):
    """测试完全无法提取 items 的数据结构。"""
    store = MagicMock()
    store.load.return_value = {"unexpected_key": "value"}  # 没有 items/data/results

    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": store}
    )

    call = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "metrics": [{"field": "author", "function": "count"}]
        },
        step_id=1,
        description="无效数据结构测试"
    )

    result = registry.execute(call, context)

    # 应该返回空结果而不是崩溃
    assert result.status == "success"
    assert result.raw_output["total_items"] == 0
    assert result.raw_output["total_groups"] == 0


def test_aggregate_distinct_count_with_unhashable_types(registry):
    """测试 distinct_count 处理不可哈希类型（如 dict）。"""
    store = MagicMock()
    store.load.return_value = {
        "items": [
            {"author": "UP1", "metadata": {"views": 100}},
            {"author": "UP2", "metadata": {"views": 200}},
            {"author": "UP3", "metadata": {"views": 100}},  # 重复
        ]
    }

    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={"data_store": store}
    )

    call = ToolCall(
        plugin_id="aggregate_data",
        args={
            "source_ref": "test-data",
            "metrics": [{"field": "metadata", "function": "distinct_count"}]
        },
        step_id=1,
        description="不可哈希类型测试"
    )

    result = registry.execute(call, context)

    # 应该降级到去重列表逻辑，不抛出异常
    assert result.status == "success"
    # 两个不同的 dict
    assert result.raw_output["groups"][0]["metrics"]["distinct_count_metadata"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
