"""测试 LangGraph 状态定义和数据模型"""
import pytest
from langgraph_agents.state import (
    ToolCall,
    ToolExecutionPayload,
    DataReference,
    Reflection,
    RouterDecision,
    GraphState,
)


class TestToolCall:
    """测试 ToolCall 模型"""

    def test_valid_tool_call(self):
        """测试创建有效的 ToolCall"""
        call = ToolCall(
            plugin_id="fetch_public_data",
            args={"query": "test"},
            step_id=1,
            description="测试调用",
        )
        assert call.plugin_id == "fetch_public_data"
        assert call.args == {"query": "test"}
        assert call.step_id == 1

    def test_tool_call_default_args(self):
        """测试 ToolCall 的默认参数"""
        call = ToolCall(plugin_id="test_tool", step_id=1, description="test")
        assert call.args == {}


class TestDataReference:
    """测试 DataReference 模型"""

    def test_success_data_reference(self):
        """测试成功的数据引用"""
        ref = DataReference(
            step_id=1,
            tool_name="fetch_public_data",
            data_id="test-id-123",
            summary="测试摘要",
            status="success",
        )
        assert ref.status == "success"
        assert ref.error_message is None

    def test_error_data_reference(self):
        """测试失败的数据引用"""
        ref = DataReference(
            step_id=1,
            tool_name="test_tool",
            data_id="err-id",
            summary="错误",
            status="error",
            error_message="测试错误",
        )
        assert ref.status == "error"
        assert ref.error_message == "测试错误"


class TestReflection:
    """测试 Reflection 模型"""

    def test_continue_decision(self):
        """测试 CONTINUE 决策"""
        refl = Reflection(decision="CONTINUE", reasoning="需要更多数据")
        assert refl.decision == "CONTINUE"

    def test_finish_decision(self):
        """测试 FINISH 决策"""
        refl = Reflection(decision="FINISH", reasoning="数据充分")
        assert refl.decision == "FINISH"

    def test_request_human_decision(self):
        """测试 REQUEST_HUMAN 决策"""
        refl = Reflection(decision="REQUEST_HUMAN", reasoning="需要澄清")
        assert refl.decision == "REQUEST_HUMAN"


class TestGraphState:
    """测试 GraphState"""

    def test_required_original_query(self):
        """测试 original_query 是必需字段"""
        # 创建包含 original_query 的状态
        state: GraphState = {"original_query": "测试查询"}
        assert state["original_query"] == "测试查询"

    def test_optional_fields(self):
        """测试可选字段"""
        state: GraphState = {
            "original_query": "test",
            "chat_history": ["msg1", "msg2"],
            "data_stash": [],
        }
        assert state.get("chat_history") == ["msg1", "msg2"]
        assert state.get("final_report") is None
