"""测试 ask_user_clarification 工具"""
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
from langgraph_agents.tools.user_interaction import register_user_interaction_tool
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.runtime import ToolExecutionContext
from langgraph_agents.state import ToolCall


def _build_tool():
    registry = ToolRegistry()
    register_user_interaction_tool(registry)
    return registry.get("ask_user_clarification")


def _build_context():
    return ToolExecutionContext(
        data_query_service=None,
        note_backend=None,
        extras={},
    )


def test_ask_user_clarification_success():
    """测试成功请求用户澄清"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="ask_user_clarification",
        args={
            "question": "您想查询哪个平台的数据？",
            "options": ["B站", "小红书", "两个都要"],
        },
        step_id=1,
        description="请求用户选择平台",
    )

    payload = tool.handler(call, context)

    # V5.0 P0: 应该返回 needs_user_input 状态
    assert payload.status == "needs_user_input"
    assert "clarification_id" in payload.raw_output
    assert payload.raw_output["question"] == "您想查询哪个平台的数据？"
    assert len(payload.raw_output["options"]) == 3
    assert payload.raw_output["allow_other"] is True  # 默认值


def test_ask_user_clarification_with_allow_other_false():
    """测试不允许用户自定义输入"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="ask_user_clarification",
        args={
            "question": "选择时间范围",
            "options": ["最近一周", "最近一月"],
            "allow_other": False,
        },
        step_id=1,
        description="请求用户选择时间范围",
    )

    payload = tool.handler(call, context)

    assert payload.status == "needs_user_input"
    assert payload.raw_output["allow_other"] is False


def test_ask_user_clarification_missing_question():
    """测试缺少 question 参数"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="ask_user_clarification",
        args={
            "options": ["选项1", "选项2"],  # 缺少 question
        },
        step_id=1,
        description="缺少参数",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E101"  # 参数缺失


def test_ask_user_clarification_missing_options():
    """测试缺少 options 参数"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="ask_user_clarification",
        args={
            "question": "测试问题？",  # 缺少 options
        },
        step_id=1,
        description="缺少参数",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E101"


def test_ask_user_clarification_too_few_options():
    """测试选项数量不足"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="ask_user_clarification",
        args={
            "question": "测试问题？",
            "options": ["只有一个选项"],  # 至少需要 2 个
        },
        step_id=1,
        description="选项不足",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E102"  # 参数无效


def test_ask_user_clarification_too_many_options():
    """测试选项数量超限"""
    tool = _build_tool()
    context = _build_context()

    call = ToolCall(
        plugin_id="ask_user_clarification",
        args={
            "question": "测试问题？",
            "options": ["选项1", "选项2", "选项3", "选项4", "选项5", "选项6"],  # 超过 5 个
        },
        step_id=1,
        description="选项过多",
    )

    payload = tool.handler(call, context)

    assert payload.status == "error"
    assert payload.raw_output["error_code"] == "E102"


def test_ask_user_clarification_clarification_id_unique():
    """测试 clarification_id 的唯一性"""
    tool = _build_tool()
    context = _build_context()

    call1 = ToolCall(
        plugin_id="ask_user_clarification",
        args={
            "question": "问题1？",
            "options": ["A", "B"],
        },
        step_id=1,
        description="第一个澄清请求",
    )

    call2 = ToolCall(
        plugin_id="ask_user_clarification",
        args={
            "question": "问题2？",
            "options": ["C", "D"],
        },
        step_id=2,
        description="第二个澄清请求",
    )

    payload1 = tool.handler(call1, context)
    payload2 = tool.handler(call2, context)

    # 两次调用应该生成不同的 clarification_id
    assert payload1.raw_output["clarification_id"] != payload2.raw_output["clarification_id"]


def test_tool_registration():
    """测试工具注册"""
    registry = ToolRegistry()
    register_user_interaction_tool(registry)

    spec = registry.get("ask_user_clarification")
    assert spec.plugin_id == "ask_user_clarification"
    assert "请求用户澄清" in spec.description
    assert spec.schema is not None
    assert "question" in spec.schema["properties"]
    assert "options" in spec.schema["properties"]
    assert "allow_other" in spec.schema["properties"]
