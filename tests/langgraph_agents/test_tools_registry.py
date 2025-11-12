"""测试工具注册表"""
import pytest
from langgraph_agents.tools.registry import ToolRegistry, ToolSpec, tool
from langgraph_agents.state import ToolCall, ToolExecutionPayload
from langgraph_agents.runtime import ToolExecutionContext


class TestToolRegistry:
    """测试 ToolRegistry"""

    def test_register_tool(self):
        """测试注册工具"""
        registry = ToolRegistry()

        def dummy_handler(call, context):
            return ToolExecutionPayload(call=call, raw_output="test")

        registry.register(
            plugin_id="test_tool",
            handler=dummy_handler,
            description="测试工具",
        )

        spec = registry.get("test_tool")
        assert spec.plugin_id == "test_tool"
        assert spec.description == "测试工具"

    def test_register_duplicate_raises_error(self):
        """测试注册重复工具抛出异常"""
        registry = ToolRegistry()

        def dummy_handler(call, context):
            return ToolExecutionPayload(call=call)

        registry.register("tool1", dummy_handler, "desc1")

        with pytest.raises(ValueError, match="已注册"):
            registry.register("tool1", dummy_handler, "desc2")

    def test_get_nonexistent_tool_raises_error(self):
        """测试获取不存在的工具抛出异常"""
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="未找到工具"):
            registry.get("nonexistent")

    def test_list_tools(self):
        """测试列出所有工具"""
        registry = ToolRegistry()

        def handler(call, context):
            return ToolExecutionPayload(call=call)

        registry.register("tool1", handler, "desc1")
        registry.register("tool2", handler, "desc2")

        tools = registry.list_tools()
        assert len(tools) == 2
        tool_ids = [t.plugin_id for t in tools]
        assert "tool1" in tool_ids
        assert "tool2" in tool_ids

    def test_execute_tool(self):
        """测试执行工具"""
        registry = ToolRegistry()

        def test_handler(call, context):
            return ToolExecutionPayload(
                call=call,
                raw_output=f"Processed: {call.args.get('query')}",
                status="success",
            )

        registry.register("test_exec", test_handler, "test")

        call = ToolCall(
            plugin_id="test_exec",
            args={"query": "test query"},
            step_id=1,
            description="test",
        )
        context = ToolExecutionContext()

        result = registry.execute(call, context)
        assert result.status == "success"
        assert "test query" in result.raw_output


class TestToolDecorator:
    """测试 @tool 装饰器"""

    def test_tool_decorator(self):
        """测试使用装饰器注册工具"""
        registry = ToolRegistry()

        @tool(registry, plugin_id="decorated_tool", description="装饰器测试")
        def my_tool(call, context):
            return ToolExecutionPayload(call=call, raw_output="decorated")

        spec = registry.get("decorated_tool")
        assert spec.plugin_id == "decorated_tool"
        assert spec.description == "装饰器测试"

        # 验证函数仍然可以直接调用
        call = ToolCall(plugin_id="decorated_tool", step_id=1, description="test")
        result = my_tool(call, ToolExecutionContext())
        assert result.raw_output == "decorated"
