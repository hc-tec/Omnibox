"""测试 compare_data 工具"""
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
from langgraph_agents.tools.data_compare import register_data_compare_tool
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.runtime import ToolExecutionContext
from langgraph_agents.state import ToolCall


class _StubDataStore:
    """模拟数据存储"""

    def __init__(self):
        self.data = {
            "bilibili-data": [
                {"title": "AI Agent 开发教程", "platform": "bilibili", "view_count": 100000},
                {"title": "大模型应用实战", "platform": "bilibili", "view_count": 80000},
            ],
            "xiaohongshu-data": [
                {"title": "AI Agent 使用体验", "platform": "xiaohongshu", "likes": 5000},
                {"title": "小红书 AI 工具推荐", "platform": "xiaohongshu", "likes": 3000},
            ],
            "youtube-data": [
                {"title": "AI Agent Tutorial", "platform": "youtube", "views": 50000},
            ],
        }

    def load(self, data_id):
        return self.data.get(data_id)


class _StubLLMClient:
    """模拟 LLM 客户端"""

    def generate(self, prompt, **kwargs):
        # 返回有效的 JSON 格式（修复静默失败问题）
        return """```json
{
  "common_themes": ["AI Agent 技术应用", "大模型应用"],
  "unique_themes": {
    "bilibili-data": ["技术教程", "开发实战"],
    "xiaohongshu-data": ["使用体验", "工具推荐"]
  },
  "gap_analysis": ["缺少企业级应用案例", "缺少性能对比"],
  "reasoning": "基于 LLM 语义分析的对比结果"
}
```"""


def _build_tool():
    registry = ToolRegistry()
    register_data_compare_tool(registry)
    return registry.get("compare_data")


def _build_context(use_llm=False):
    extras = {"data_store": _StubDataStore()}
    if use_llm:
        extras["planner_llm"] = _StubLLMClient()

    return ToolExecutionContext(
        data_query_service=None,
        note_backend=None,
        extras=extras,
    )


def test_compare_data_diff_mode():
    """测试差异对比模式"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="compare_data",
        args={
            "source_refs": ["bilibili-data", "xiaohongshu-data"],
            "comparison_type": "diff",
        },
        step_id=1,
        description="对比 B站 和小红书数据",
    )

    payload = tool.handler(call, context)

    assert payload.status == "success"
    assert "comparison_type" in payload.raw_output
    assert payload.raw_output["comparison_type"] == "diff"
    assert "common_themes" in payload.raw_output
    assert "unique_themes" in payload.raw_output


def test_compare_data_with_semantic():
    """测试语义对比"""
    tool = _build_tool()
    context = _build_context(use_llm=True)

    call = ToolCall(
        plugin_id="compare_data",
        args={
            "source_refs": ["bilibili-data", "xiaohongshu-data"],
            "comparison_type": "gap_analysis",
            "use_semantic": True,
        },
        step_id=1,
        description="语义对比分析",
    )

    payload = tool.handler(call, context)

    assert payload.status == "success"
    assert "comparison_type" in payload.raw_output
    assert payload.raw_output["comparison_type"] == "gap_analysis"
    # LLM 返回的字段可能包含 common_themes, unique_themes 或 gap_analysis
    assert "common_themes" in payload.raw_output or "reasoning" in payload.raw_output


def test_compare_data_multiple_sources():
    """测试对比多个数据源"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="compare_data",
        args={
            "source_refs": ["bilibili-data", "xiaohongshu-data", "youtube-data"],
            "comparison_type": "diff",  # 使用已实现的 diff 类型
        },
        step_id=1,
        description="对比三个平台",
    )

    payload = tool.handler(call, context)

    assert payload.status == "success"
    assert "comparison_type" in payload.raw_output
    assert payload.raw_output["comparison_type"] == "diff"
    # 验证对比了多个数据源（通过 common_themes 或其他字段）
    assert "common_themes" in payload.raw_output


def test_compare_data_missing_source_refs():
    """测试缺少 source_refs 参数"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="compare_data",
        args={"comparison_type": "diff"},  # 缺少 source_refs
        step_id=1,
        description="缺少参数",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E101"


def test_compare_data_too_few_sources():
    """测试数据源数量不足"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="compare_data",
        args={
            "source_refs": ["bilibili-data"],  # 只有 1 个，至少需要 2 个
            "comparison_type": "diff",
        },
        step_id=1,
        description="数据源不足",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E102"  # 参数无效


def test_compare_data_too_many_sources():
    """测试数据源数量超限"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="compare_data",
        args={
            "source_refs": ["s1", "s2", "s3", "s4", "s5", "s6"],  # 超过 5 个
            "comparison_type": "diff",
        },
        step_id=1,
        description="数据源过多",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E102"


def test_compare_data_source_not_found():
    """测试数据源不存在"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="compare_data",
        args={
            "source_refs": ["bilibili-data", "nonexistent-id"],
            "comparison_type": "diff",
        },
        step_id=1,
        description="数据源不存在",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E105"


def test_compare_data_semantic_without_llm():
    """测试语义对比但缺少 LLM"""
    tool = _build_tool()
    context = _build_context(use_llm=False)  # 没有 LLM

    call = ToolCall(
        plugin_id="compare_data",
        args={
            "source_refs": ["bilibili-data", "xiaohongshu-data"],
            "comparison_type": "gap_analysis",
            "use_semantic": True,
        },
        step_id=1,
        description="缺少 LLM",
    )

    payload = tool.handler(call, context)

    # V5.0 P0: 修复后应该返回错误
    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E501"


def test_compare_data_data_store_unavailable():
    """测试 data_store 不可用"""
    tool = _build_tool()
    context = ToolExecutionContext(
        data_query_service=None,
        note_backend=None,
        extras={},  # 缺少 data_store
    )

    call = ToolCall(
        plugin_id="compare_data",
        args={
            "source_refs": ["bilibili-data", "xiaohongshu-data"],
            "comparison_type": "diff",
        },
        step_id=1,
        description="data_store 不可用",
    )

    payload = tool.handler(call, context)

    # 应该返回 E501（data_store 不可用属于系统错误）
    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E501"


def test_tool_registration():
    """测试工具注册"""
    registry = ToolRegistry()
    register_data_compare_tool(registry)

    spec = registry.get("compare_data")
    assert spec.plugin_id == "compare_data"
    assert "对比分析多个数据源" in spec.description
    assert spec.schema is not None
    assert "source_refs" in spec.schema["properties"]
    assert "comparison_type" in spec.schema["properties"]
