"""测试 filter_data 工具"""
import sys
import types

# Stub for rag_system
if "rag_system" not in sys.modules:
    rag_system_stub = types.ModuleType("rag_system")
    rag_system_stub.__path__ = []
    sys.modules["rag_system"] = rag_system_stub

if "rag_system.rag_pipeline" not in sys.modules:
    rag_pipeline_stub = types.ModuleType("rag_system.rag_pipeline")

    class _StubRAGPipeline:
        def search(self, *args, **kwargs):
            return []

    rag_pipeline_stub.RAGPipeline = _StubRAGPipeline
    sys.modules["rag_system.rag_pipeline"] = rag_pipeline_stub

import pytest
from langgraph_agents.tools.data_filter import register_data_filter_tool
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.runtime import ToolExecutionContext
from langgraph_agents.state import ToolCall
from langgraph_agents.storage import InMemoryResearchDataStore


class _StubDataStore:
    """模拟数据存储"""

    def __init__(self):
        self.data = {
            "data-001": [
                {"title": "高播放视频", "view_count": 1000000, "category": "AI"},
                {"title": "中播放视频", "view_count": 500000, "category": "AI"},
                {"title": "低播放视频", "view_count": 10000, "category": "Tech"},
                {"title": "极低播放视频", "view_count": 1000, "category": "Other"},
            ]
        }

    def load(self, data_id):
        return self.data.get(data_id)


def _build_tool():
    registry = ToolRegistry()
    register_data_filter_tool(registry)
    return registry.get("filter_data")


def _build_context(data_store=None):
    return ToolExecutionContext(
        data_query_service=None,
        note_backend=None,
        extras={"data_store": data_store or _StubDataStore()},
    )


def test_filter_data_gt_operator():
    """测试 $gt (大于) 操作符"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="filter_data",
        args={
            "source_ref": "data-001",
            "conditions": {"view_count": {"$gt": 500000}},
        },
        step_id=1,
        description="筛选高播放量视频",
    )

    payload = tool.handler(call, context)

    assert payload.status == "success"
    assert len(payload.raw_output["items"]) == 1
    assert payload.raw_output["items"][0]["title"] == "高播放视频"
    assert payload.raw_output["total_after_filter"] == 1


def test_filter_data_contains_operator():
    """测试 $contains (包含) 操作符"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="filter_data",
        args={
            "source_ref": "data-001",
            "conditions": {"category": {"$contains": "ai"}},  # 不区分大小写
        },
        step_id=1,
        description="筛选 AI 类别",
    )

    payload = tool.handler(call, context)

    assert payload.status == "success"
    assert len(payload.raw_output["items"]) == 2
    assert all(item["category"] == "AI" for item in payload.raw_output["items"])


def test_filter_data_multiple_conditions():
    """测试多个条件组合"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="filter_data",
        args={
            "source_ref": "data-001",
            "conditions": {
                "view_count": {"$gte": 10000},
                "category": {"$eq": "AI"},
            },
        },
        step_id=1,
        description="筛选 AI 类别且播放量 >= 10000",
    )

    payload = tool.handler(call, context)

    assert payload.status == "success"
    assert len(payload.raw_output["items"]) == 2


def test_filter_data_with_limit():
    """测试 limit 参数"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="filter_data",
        args={
            "source_ref": "data-001",
            "conditions": {"view_count": {"$gt": 0}},
            "limit": 2,
        },
        step_id=1,
        description="限制返回 2 条",
    )

    payload = tool.handler(call, context)

    assert payload.status == "success"
    assert len(payload.raw_output["items"]) == 2
    assert payload.raw_output["total_before_filter"] == 4  # 过滤前总数


def test_filter_data_with_pagination():
    """测试分页参数"""
    tool = _build_tool()
    context = _build_context()

    # 第一页
    call1 = ToolCall(
        plugin_id="filter_data",
        args={
            "source_ref": "data-001",
            "conditions": {},
            "limit": 2,
            "offset": 0,
        },
        step_id=1,
        description="获取第一页",
    )

    payload1 = tool.handler(call1, context)
    assert len(payload1.raw_output["items"]) == 2

    # 第二页
    call2 = ToolCall(
        plugin_id="filter_data",
        args={
            "source_ref": "data-001",
            "conditions": {},
            "limit": 2,
            "offset": 2,
        },
        step_id=2,
        description="获取第二页",
    )

    payload2 = tool.handler(call2, context)
    assert len(payload2.raw_output["items"]) == 2

    # 确保两页数据不同
    assert payload1.raw_output["items"][0] != payload2.raw_output["items"][0]


def test_filter_data_missing_source_ref():
    """测试缺少 source_ref 参数"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="filter_data",
        args={"conditions": {}},  # 缺少 source_ref
        step_id=1,
        description="缺少参数",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E101"


def test_filter_data_source_not_found():
    """测试数据源不存在"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="filter_data",
        args={
            "source_ref": "nonexistent-id",
            "conditions": {},
        },
        step_id=1,
        description="不存在的数据源",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E105"  # 数据源未找到


def test_filter_data_data_store_unavailable():
    """测试 data_store 不可用"""
    tool = _build_tool()
    context = ToolExecutionContext(
        data_query_service=None,
        note_backend=None,
        extras={},  # 缺少 data_store
    )

    call = ToolCall(
        plugin_id="filter_data",
        args={"source_ref": "data-001", "conditions": {}},
        step_id=1,
        description="data_store 不可用",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E501"


def test_tool_registration():
    """测试工具注册"""
    registry = ToolRegistry()
    register_data_filter_tool(registry)

    spec = registry.get("filter_data")
    assert spec.plugin_id == "filter_data"
    assert "过滤" in spec.description or "筛选" in spec.description
    assert spec.schema is not None
    assert "source_ref" in spec.schema["properties"]
    assert "conditions" in spec.schema["properties"]
