"""测试 search_data_sources 工具"""
import sys
import types

# Stub for rag_system (required by tools)
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
from langgraph_agents.tools.source_discovery import register_source_discovery_tool
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.runtime import ToolExecutionContext
from langgraph_agents.state import ToolCall
from services.data_query_service import DataQueryResult


class _StubRAGInAction:
    """模拟 RAGInAction"""
    pass


class _StubDataQueryResult:
    """模拟 DataQueryService 返回结果"""
    def __init__(self, retrieved_tools):
        self.retrieved_tools = retrieved_tools


class _StubDataQueryService:
    """模拟 DataQueryService"""

    def __init__(self):
        self.rag_in_action = _StubRAGInAction()  # 必须有这个属性

    def query(self, user_query, filter_datasource=None, use_cache=True, prefer_single_route=False):
        # 模拟返回 RAG 检索结果
        if "bilibili" in user_query.lower():
            retrieved_tools = [
                {
                    "route_id": "bilibili_hot",
                    "provider": "bilibili",
                    "name": "B站热门视频",
                    "description": "获取B站热门视频列表",
                    "requires_auth": False,
                    "requires_params": False
                },
                {
                    "route_id": "bilibili_user",
                    "provider": "bilibili",
                    "name": "B站用户投稿",
                    "description": "获取B站用户的投稿视频",
                    "requires_auth": False,
                    "requires_params": True
                }
            ]
        else:
            retrieved_tools = [
                {
                    "route_id": "xhs_notes",
                    "provider": "xiaohongshu",
                    "name": "小红书笔记",
                    "description": "小红书笔记内容",
                    "requires_auth": False,
                    "requires_params": False
                },
                {
                    "route_id": "youtube_videos",
                    "provider": "youtube",
                    "name": "YouTube视频",
                    "description": "YouTube视频列表",
                    "requires_auth": False,
                    "requires_params": False
                }
            ]

        return _StubDataQueryResult(retrieved_tools=retrieved_tools)


def _build_tool():
    registry = ToolRegistry()
    register_source_discovery_tool(registry)
    return registry.get("search_data_sources")


def _build_context():
    return ToolExecutionContext(
        data_query_service=_StubDataQueryService(),
        note_backend=None,
        extras={},
    )


def test_search_data_sources_success():
    """测试成功搜索数据源"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="search_data_sources",
        args={"query": "AI Agent 相关内容"},
        step_id=1,
        description="搜索数据源",
    )

    payload = tool.handler(call, context)

    assert payload.status == "success"
    assert "public_sources" in payload.raw_output
    assert "private_sources" in payload.raw_output
    assert payload.raw_output["auth_required"] is False


def test_search_data_sources_with_platform_filter():
    """测试使用平台过滤器"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="search_data_sources",
        args={"query": "bilibili AI 视频", "platforms": ["bilibili"]},
        step_id=1,
        description="搜索 B站 数据源",
    )

    payload = tool.handler(call, context)

    assert payload.status == "success"
    assert len(payload.raw_output["public_sources"]) > 0


def test_search_data_sources_missing_query():
    """测试缺少 query 参数"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="search_data_sources",
        args={},  # 缺少 query
        step_id=1,
        description="搜索数据源",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E101"  # 参数缺失


def test_search_data_sources_service_unavailable():
    """测试 DataQueryService 不可用"""
    tool = _build_tool()
    context = ToolExecutionContext(
        data_query_service=None,  # 服务不可用
        note_backend=None,
        extras={},
    )

    call = ToolCall(
        plugin_id="search_data_sources",
        args={"query": "test"},
        step_id=1,
        description="搜索数据源",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E301"  # RAG 服务不可用


def test_tool_registration():
    """测试工具注册是否正确"""
    registry = ToolRegistry()
    register_source_discovery_tool(registry)

    spec = registry.get("search_data_sources")
    assert spec.plugin_id == "search_data_sources"
    assert "探索可用的数据源" in spec.description
    assert spec.schema is not None
    assert "query" in spec.schema["properties"]
