"""
SyncLangGraphExecutor 单元测试。

测试 V5.0 LangGraph 同步执行适配层。
"""

import pytest
from unittest.mock import MagicMock, patch

from services.data_query_service import DataQueryResult
from langgraph_agents.sync_executor import (
    SyncLangGraphExecutor,
    LangGraphExecutionResult,
    create_sync_executor,
)


def _make_success_result(items=None, feed_title="Test Feed"):
    """创建成功的 DataQueryResult。"""
    if items is None:
        items = [{"title": "item-1"}, {"title": "item-2"}]
    return DataQueryResult(
        status="success",
        items=items,
        feed_title=feed_title,
        generated_path="/test/route",
        source="rsshub",
        cache_hit="none",
    )


class _MockDataQueryService:
    """Mock 数据查询服务。"""

    def __init__(self, result=None):
        self._result = result or _make_success_result()
        self.query_calls = []

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return self._result


class _MockLLMClient:
    """Mock LLM 客户端。"""

    def __init__(self):
        self.generate_calls = []

    def generate(self, prompt, **kwargs):
        self.generate_calls.append({"prompt": prompt, **kwargs})
        # 返回简单响应，让 Router 走 simple_tool_call 路径
        return '{"route": "simple_tool_call", "reasoning": "简单查询"}'

    def chat(self, messages, **kwargs):
        return self.generate(messages[-1]["content"] if messages else "", **kwargs)


class TestSyncLangGraphExecutorInit:
    """初始化测试。"""

    def test_init_creates_runtime_and_app(self):
        """测试初始化创建 Runtime 和 App。"""
        llm_client = _MockLLMClient()
        data_service = _MockDataQueryService()

        executor = SyncLangGraphExecutor(
            llm_client=llm_client,
            data_query_service=data_service,
        )

        assert executor.runtime is not None
        assert executor.app is not None
        assert len(executor.runtime.tool_registry.list_tools()) > 0


class TestSyncLangGraphExecutorExecution:
    """执行测试。"""

    def test_execute_returns_result(self):
        """测试执行返回结果。"""
        llm_client = _MockLLMClient()
        data_service = _MockDataQueryService()

        executor = SyncLangGraphExecutor(
            llm_client=llm_client,
            data_query_service=data_service,
        )

        result = executor.execute("测试查询")

        assert isinstance(result, LangGraphExecutionResult)
        # Router 应该被调用
        assert len(llm_client.generate_calls) > 0

    def test_execute_with_filter_datasource(self):
        """测试带 filter_datasource 的执行。"""
        llm_client = _MockLLMClient()
        data_service = _MockDataQueryService()

        executor = SyncLangGraphExecutor(
            llm_client=llm_client,
            data_query_service=data_service,
        )

        result = executor.execute(
            "B站热门视频",
            filter_datasource="bilibili",
        )

        assert isinstance(result, LangGraphExecutionResult)


class TestCreateSyncExecutor:
    """工厂函数测试。"""

    def test_create_sync_executor(self):
        """测试工厂函数。"""
        llm_client = _MockLLMClient()
        data_service = _MockDataQueryService()

        executor = create_sync_executor(
            llm_client=llm_client,
            data_query_service=data_service,
        )

        assert isinstance(executor, SyncLangGraphExecutor)


class TestLangGraphExecutionResult:
    """执行结果测试。"""

    def test_result_dataclass(self):
        """测试结果数据类。"""
        result = LangGraphExecutionResult(
            success=True,
            final_report="测试报告",
            data_stash=[],
            router_decision="simple_tool_call",
            execution_steps=[],
        )

        assert result.success is True
        assert result.final_report == "测试报告"
        assert result.error is None
