"""
V5.0 Phase 2: 轻量模式集成测试。

测试场景：
1. 轻量工具（search_data_sources）不触发 DataStasher
2. working_memory 正确维护
3. Planner 能读取 working_memory
"""
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
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.tools.source_discovery import register_source_discovery_tool
from langgraph_agents.tools.data_filter import register_data_filter_tool
from langgraph_agents.state import ToolCall, ToolExecutionPayload
from langgraph_agents.runtime import ToolExecutionContext


def test_tool_execution_mode_registration():
    """测试工具注册时正确设置执行模式"""
    from langgraph_agents.tools.user_interaction import register_user_interaction_tool

    registry = ToolRegistry()

    # 注册轻量工具
    register_source_discovery_tool(registry)

    # 注册完整工具
    register_data_filter_tool(registry)
    register_user_interaction_tool(registry)

    # 验证执行模式
    search_spec = registry.get("search_data_sources")
    assert search_spec.execution_mode == "lightweight"

    filter_spec = registry.get("filter_data")
    assert filter_spec.execution_mode == "full"

    # 修复：ask_user_clarification 应该是完整模式（需要触发 Reflector）
    user_spec = registry.get("ask_user_clarification")
    assert user_spec.execution_mode == "full"


def test_lightweight_tool_workflow():
    """
    测试轻量工具的完整工作流。

    场景：
    1. 调用 search_data_sources（轻量工具）
    2. 结果应该路由到 lightweight_handler
    3. working_memory 应该被写入
    """
    from langgraph_agents.graph_builder import _create_after_tool_execution_edge
    from langgraph_agents.runtime import LangGraphRuntime
    from unittest.mock import MagicMock

    # 创建 mock runtime
    runtime = MagicMock(spec=LangGraphRuntime)
    registry = ToolRegistry()
    register_source_discovery_tool(registry)
    runtime.tool_registry = registry

    # 修复：使用 pending_tool_result 而不是 next_tool_call
    # 模拟 tool_executor 执行后的状态
    tool_call = ToolCall(
        plugin_id="search_data_sources",
        args={"query": "AI Agent"},
        step_id=1,
        description="探索数据源",
    )

    state = {
        "pending_tool_result": ToolExecutionPayload(
            call=tool_call,
            raw_output={"type": "source_discovery", "public_sources": []},
            status="success",
        ),
        "working_memory": {},
        "data_stash": [],
    }

    # 测试条件路由
    edge_fn = _create_after_tool_execution_edge(runtime)
    result = edge_fn(state)

    # 验证轻量工具路由到 lightweight_handler
    assert result == "to_planner_lightweight"


def test_working_memory_format():
    """
    测试 working_memory 的格式化输出。

    验证 Planner 能正确读取 working_memory 内容。
    """
    from langgraph_agents.agents.planner import _format_working_memory

    # 模拟 search_data_sources 的结果
    working_memory = {
        "search_data_sources": {
            "step_id": 1,
            "result": {
                "type": "source_discovery",
                "public_sources": [
                    {"route_id": "bilibili/search", "name": "B站搜索"},
                    {"route_id": "xiaohongshu/search", "name": "小红书搜索"},
                ],
                "private_sources": [],
                "auth_required": False,
            },
            "status": "success",
            "description": "探索 AI Agent 数据源",
        }
    }

    formatted = _format_working_memory(working_memory)

    # 验证格式化输出包含关键信息
    assert "Step 1" in formatted
    assert "search_data_sources" in formatted
    assert "找到 2 个数据源" in formatted


def test_working_memory_in_state():
    """
    测试 GraphState 中的 working_memory 字段。
    """
    from langgraph_agents.state import GraphState

    # 创建状态
    state: GraphState = {
        "original_query": "test query",
        "working_memory": {
            "search_data_sources": {
                "result": {"public_sources": []},
                "status": "success",
            }
        },
    }

    # 验证 working_memory 可访问
    assert "working_memory" in state
    assert "search_data_sources" in state["working_memory"]


def test_full_mode_tool_workflow():
    """
    测试完整模式工具的工作流。

    场景：
    1. 调用 filter_data（完整工具）
    2. 路由应该指向 data_stasher
    """
    from langgraph_agents.graph_builder import _create_after_tool_execution_edge
    from langgraph_agents.runtime import LangGraphRuntime
    from unittest.mock import MagicMock

    # 创建 mock runtime
    runtime = MagicMock(spec=LangGraphRuntime)
    registry = ToolRegistry()
    register_data_filter_tool(registry)
    runtime.tool_registry = registry

    # 修复：使用 pending_tool_result 而不是 next_tool_call
    tool_call = ToolCall(
        plugin_id="filter_data",
        args={"source_ref": "data-001", "conditions": {}},
        step_id=1,
        description="过滤数据",
    )

    state = {
        "pending_tool_result": ToolExecutionPayload(
            call=tool_call,
            raw_output={"items": []},
            status="success",
        ),
    }

    # 测试条件路由
    edge_fn = _create_after_tool_execution_edge(runtime)
    result = edge_fn(state)

    # 验证完整工具路由到 data_stasher
    assert result == "to_data_stasher"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
