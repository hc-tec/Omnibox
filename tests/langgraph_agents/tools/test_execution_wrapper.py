"""执行包装器单元测试。"""

import time
import pytest
from unittest.mock import MagicMock

from langgraph_agents.tools.execution_wrapper import (
    ToolExecutionWrapper,
    ToolTimeoutError,
    ToolRetryExhaustedError,
    with_timeout,
    with_retry,
    is_tool_retriable_error,
    execute_with_protection,
)
from langgraph_agents.state import ToolCall, ToolExecutionPayload


class TestIsToolRetriableError:
    """测试可重试错误判断。"""

    def test_connection_error_is_retriable(self):
        """ConnectionError 应该可重试。"""
        assert is_tool_retriable_error(ConnectionError("连接失败"))

    def test_timeout_error_is_retriable(self):
        """TimeoutError 应该可重试。"""
        assert is_tool_retriable_error(TimeoutError("超时"))

    def test_tool_timeout_error_is_retriable(self):
        """ToolTimeoutError 应该可重试。"""
        assert is_tool_retriable_error(ToolTimeoutError("test_tool", 30.0))

    def test_value_error_not_retriable(self):
        """ValueError 不应该可重试。"""
        assert not is_tool_retriable_error(ValueError("无效参数"))

    def test_error_with_timeout_keyword_is_retriable(self):
        """包含 timeout 关键词的错误应该可重试。"""
        assert is_tool_retriable_error(Exception("Request timeout"))

    def test_error_with_connection_keyword_is_retriable(self):
        """包含 connection 关键词的错误应该可重试。"""
        assert is_tool_retriable_error(Exception("Connection refused"))

    def test_503_error_is_retriable(self):
        """503 错误应该可重试。"""
        assert is_tool_retriable_error(Exception("HTTP 503 Service Unavailable"))


class TestWithTimeout:
    """测试超时装饰器。"""

    def test_fast_function_succeeds(self):
        """快速函数应该成功执行。"""
        @with_timeout(5.0, "test_tool")
        def fast_func():
            return "success"

        result = fast_func()
        assert result == "success"

    def test_slow_function_times_out(self):
        """慢速函数应该超时。"""
        @with_timeout(0.1, "slow_tool")
        def slow_func():
            time.sleep(1.0)
            return "never reached"

        with pytest.raises(ToolTimeoutError) as exc_info:
            slow_func()

        assert exc_info.value.plugin_id == "slow_tool"
        assert exc_info.value.timeout == 0.1

    def test_timeout_preserves_function_args(self):
        """超时装饰器应该保留函数参数。"""
        @with_timeout(5.0, "test_tool")
        def func_with_args(a, b, c=None):
            return (a, b, c)

        result = func_with_args(1, 2, c=3)
        assert result == (1, 2, 3)


class TestWithRetry:
    """测试重试装饰器。"""

    def test_successful_first_attempt(self):
        """首次尝试成功不应重试。"""
        call_count = [0]

        @with_retry(max_retries=2, plugin_id="test_tool")
        def always_succeeds():
            call_count[0] += 1
            return "success"

        result = always_succeeds()
        assert result == "success"
        assert call_count[0] == 1

    def test_retry_on_retriable_error(self):
        """可重试错误应该触发重试。"""
        call_count = [0]

        @with_retry(max_retries=2, initial_delay=0.01, plugin_id="test_tool")
        def fails_then_succeeds():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("模拟连接错误")
            return "success"

        result = fails_then_succeeds()
        assert result == "success"
        assert call_count[0] == 2

    def test_no_retry_on_non_retriable_error(self):
        """不可重试错误不应触发重试。"""
        call_count = [0]

        @with_retry(max_retries=2, plugin_id="test_tool")
        def raises_value_error():
            call_count[0] += 1
            raise ValueError("参数错误")

        with pytest.raises(ValueError):
            raises_value_error()

        assert call_count[0] == 1  # 只调用一次

    def test_exhausted_retries(self):
        """重试耗尽应抛出 ToolRetryExhaustedError。"""
        call_count = [0]

        @with_retry(max_retries=2, initial_delay=0.01, plugin_id="test_tool")
        def always_fails():
            call_count[0] += 1
            raise ConnectionError("持续失败")

        with pytest.raises(ToolRetryExhaustedError) as exc_info:
            always_fails()

        assert exc_info.value.plugin_id == "test_tool"
        assert exc_info.value.attempts == 3  # 1 + 2 retries
        assert call_count[0] == 3


class TestToolExecutionWrapper:
    """测试工具执行包装器。"""

    def setup_method(self):
        """设置测试数据。"""
        self.wrapper = ToolExecutionWrapper(
            default_timeout=30.0,
            default_retries=1,
        )
        self.call = ToolCall(
            plugin_id="test_tool",
            args={"key": "value"},
            step_id=1,
            description="测试工具",
        )
        self.context = MagicMock()

    def test_successful_execution(self):
        """成功执行应返回正常 payload。"""
        def handler(call, context):
            return ToolExecutionPayload(
                call=call,
                raw_output={"result": "success"},
                status="success",
            )

        result = self.wrapper.execute(handler, self.call, self.context)

        assert result.status == "success"
        assert result.raw_output["result"] == "success"

    def test_timeout_returns_error_payload(self):
        """超时应返回错误 payload。"""
        # 使用更短的超时
        wrapper = ToolExecutionWrapper(default_timeout=0.1, default_retries=0)

        def slow_handler(call, context):
            time.sleep(1.0)
            return ToolExecutionPayload(
                call=call,
                raw_output={},
                status="success",
            )

        result = wrapper.execute(slow_handler, self.call, self.context)

        assert result.status == "error"
        assert "E601" in str(result.raw_output.get("error_code", ""))
        assert "timeout" in result.raw_output.get("error_type", "")

    def test_retry_exhausted_returns_error_payload(self):
        """重试耗尽应返回错误 payload。"""
        wrapper = ToolExecutionWrapper(default_timeout=30.0, default_retries=1)

        def failing_handler(call, context):
            raise ConnectionError("持续失败")

        result = wrapper.execute(failing_handler, self.call, self.context)

        assert result.status == "error"
        assert "E602" in str(result.raw_output.get("error_code", ""))

    def test_unexpected_error_returns_error_payload(self):
        """意外错误应返回错误 payload。"""
        wrapper = ToolExecutionWrapper(default_timeout=30.0, default_retries=0)

        def error_handler(call, context):
            raise ValueError("不可重试的错误")

        result = wrapper.execute(error_handler, self.call, self.context)

        assert result.status == "error"
        assert "E699" in str(result.raw_output.get("error_code", ""))

    def test_tool_specific_timeout(self):
        """工具特定超时配置应生效。"""
        # fetch_public_data 有更长的超时
        assert self.wrapper.get_timeout("fetch_public_data") == 60.0
        assert self.wrapper.get_timeout("ask_user_clarification") == 5.0
        assert self.wrapper.get_timeout("unknown_tool") == 30.0  # 默认值

    def test_tool_specific_retries(self):
        """工具特定重试配置应生效。"""
        assert self.wrapper.get_retries("fetch_public_data") == 3
        assert self.wrapper.get_retries("filter_data") == 0  # 不重试
        assert self.wrapper.get_retries("unknown_tool") == 1  # 默认值


class TestExecuteWithProtection:
    """测试便捷函数。"""

    def test_execute_with_protection_uses_default_wrapper(self):
        """execute_with_protection 应使用默认包装器。"""
        call = ToolCall(
            plugin_id="test_tool",
            args={},
            step_id=1,
            description="测试",
        )
        context = MagicMock()

        def handler(call, context):
            return ToolExecutionPayload(
                call=call,
                raw_output={"test": True},
                status="success",
            )

        result = execute_with_protection(handler, call, context)

        assert result.status == "success"
        assert result.raw_output["test"] is True


class TestIntegrationWithRegistry:
    """测试与 ToolRegistry 的集成。"""

    def test_registry_uses_protection_by_default(self):
        """Registry.execute 默认应使用保护。"""
        from langgraph_agents.tools.registry import ToolRegistry

        registry = ToolRegistry()
        call_count = [0]

        def test_handler(call, context):
            call_count[0] += 1
            return ToolExecutionPayload(
                call=call,
                raw_output={"count": call_count[0]},
                status="success",
            )

        registry.register(
            plugin_id="test_tool",
            handler=test_handler,
            description="测试工具",
        )

        call = ToolCall(
            plugin_id="test_tool",
            args={},
            step_id=1,
            description="测试",
        )
        context = MagicMock()

        result = registry.execute(call, context, use_protection=True)

        assert result.status == "success"

    def test_registry_can_skip_protection(self):
        """Registry.execute 可以跳过保护。"""
        from langgraph_agents.tools.registry import ToolRegistry

        registry = ToolRegistry()

        def test_handler(call, context):
            return ToolExecutionPayload(
                call=call,
                raw_output={"direct": True},
                status="success",
            )

        registry.register(
            plugin_id="direct_tool",
            handler=test_handler,
            description="直接执行工具",
        )

        call = ToolCall(
            plugin_id="direct_tool",
            args={},
            step_id=1,
            description="测试",
        )
        context = MagicMock()

        result = registry.execute(call, context, use_protection=False)

        assert result.status == "success"
        assert result.raw_output["direct"] is True
