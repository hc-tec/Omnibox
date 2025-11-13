"""测试 fetch_subscription_data 工具"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from langgraph_agents.tools.subscription_data import register_subscription_data_tool
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.state import ToolCall
from langgraph_agents.runtime import ToolExecutionContext
from services.data_query_service import DataQueryResult


class TestFetchSubscriptionDataTool:
    """fetch_subscription_data 工具测试套件"""

    @pytest.fixture
    def registry(self):
        """创建工具注册表"""
        return ToolRegistry()

    @pytest.fixture
    def mock_context(self):
        """创建 Mock ToolExecutionContext"""
        context = Mock(spec=ToolExecutionContext)

        # Mock DataQueryService
        mock_dq = Mock()
        context.data_query_service = mock_dq

        # 添加 extras 字段，包括 mock llm_client
        mock_llm_client = Mock()
        context.extras = {"llm_client": mock_llm_client}

        return context

    @pytest.fixture
    def tool_function(self, registry):
        """注册工具并返回工具函数"""
        register_subscription_data_tool(registry)
        tool_spec = registry.get("fetch_subscription_data")
        assert tool_spec is not None
        return tool_spec.handler

    def test_tool_registration(self, registry):
        """测试工具注册"""
        register_subscription_data_tool(registry)

        tool_spec = registry.get("fetch_subscription_data")
        assert tool_spec is not None
        assert tool_spec.plugin_id == "fetch_subscription_data"
        assert "订阅" in tool_spec.description
        assert "query" in tool_spec.schema["properties"]

    def test_fetch_subscription_data_success(self, tool_function, mock_context):
        """测试成功获取订阅数据"""
        # Mock SubscriptionResolver.resolve
        mock_resolve_result = {
            "subscription_id": 1,
            "path": "/user/video-all/12345",
            "display_name": "科技美学",
            "action_display_name": "用户所有视频",
            "similarity": 0.95
        }

        # Mock DataQueryService.query
        mock_feed_result = DataQueryResult(
            status="success",
            feed_title="科技美学的视频",
            generated_path="/user/video-all/12345",
            items=[
                {"title": "视频1", "link": "https://example.com/1"},
                {"title": "视频2", "link": "https://example.com/2"}
            ],
            source="rsshub",
            cache_hit=False,
            reasoning="成功获取数据"
        )
        mock_context.data_query_service.query.return_value = mock_feed_result

        # 创建 ToolCall
        call = ToolCall(
            plugin_id="fetch_subscription_data",
            args={"query": "科技美学的投稿"},
            step_id=1,
            description="查询科技美学的投稿"
        )

        # Mock SubscriptionResolver
        with patch('services.subscription.subscription_resolver.SubscriptionResolver') as MockResolver:
            mock_resolver = MockResolver.return_value
            mock_resolver.resolve.return_value = mock_resolve_result

            # 执行工具
            result = tool_function(call, mock_context)

            # 验证结果
            assert result.status == "success"
            assert result.raw_output["type"] == "subscription_data"
            assert result.raw_output["subscription_id"] == 1
            assert result.raw_output["display_name"] == "科技美学"
            assert result.raw_output["similarity"] == 0.95
            assert len(result.raw_output["items"]) == 2

    def test_fetch_subscription_data_not_found(self, tool_function, mock_context):
        """测试订阅未找到的情况"""
        call = ToolCall(
            plugin_id="fetch_subscription_data",
            args={"query": "不存在的UP主"},
            step_id=1,
            description="查询不存在的UP主"
        )

        # Mock SubscriptionResolver 返回 None
        with patch('services.subscription.subscription_resolver.SubscriptionResolver') as MockResolver:
            mock_resolver = MockResolver.return_value
            mock_resolver.resolve.return_value = None

            # 执行工具
            result = tool_function(call, mock_context)

            # 验证结果
            assert result.status == "error"
            assert result.raw_output["status"] == "not_found"
            assert "未找到匹配的订阅" in result.error_message

    def test_fetch_subscription_data_feed_error(self, tool_function, mock_context):
        """测试数据获取失败的情况"""
        # Mock SubscriptionResolver.resolve
        mock_resolve_result = {
            "subscription_id": 1,
            "path": "/user/video-all/12345",
            "display_name": "科技美学",
            "action_display_name": "用户所有视频",
            "similarity": 0.95
        }

        # Mock DataQueryService.query 返回失败
        mock_feed_result = DataQueryResult(
            status="error",
            feed_title="",
            generated_path="",
            items=[],
            source="rsshub",
            cache_hit=False,
            reasoning="RSSHub API 错误"
        )
        mock_context.data_query_service.query.return_value = mock_feed_result

        call = ToolCall(
            plugin_id="fetch_subscription_data",
            args={"query": "科技美学的投稿"},
            step_id=1,
            description="查询科技美学的投稿"
        )

        with patch('services.subscription.subscription_resolver.SubscriptionResolver') as MockResolver:
            mock_resolver = MockResolver.return_value
            mock_resolver.resolve.return_value = mock_resolve_result

            # 执行工具
            result = tool_function(call, mock_context)

            # 验证结果
            assert result.status == "error"
            assert "数据获取失败" in result.error_message

    def test_fetch_subscription_data_missing_query(self, tool_function, mock_context):
        """测试缺少 query 参数的情况"""
        call = ToolCall(
            plugin_id="fetch_subscription_data",
            args={},  # 缺少 query
            step_id=1,
            description="测试缺少参数"
        )

        # 应该抛出 ValueError
        with pytest.raises(ValueError, match="需要 query 参数"):
            tool_function(call, mock_context)

    def test_fetch_subscription_data_with_subscription_name(self, tool_function, mock_context):
        """测试使用 subscription_name 参数"""
        mock_resolve_result = {
            "subscription_id": 1,
            "path": "/user/video-all/12345",
            "display_name": "科技美学",
            "action_display_name": "用户所有视频",
            "similarity": 1.0  # 精确匹配
        }

        mock_feed_result = DataQueryResult(
            status="success",
            feed_title="科技美学的视频",
            generated_path="/user/video-all/12345",
            items=[{"title": "视频1"}],
            source="rsshub",
            cache_hit=True,
            reasoning=""
        )
        mock_context.data_query_service.query.return_value = mock_feed_result

        call = ToolCall(
            plugin_id="fetch_subscription_data",
            args={
                "query": "科技美学的投稿",
                "subscription_name": "科技美学"
            },
            step_id=1,
            description="使用subscription_name查询"
        )

        with patch('services.subscription.subscription_resolver.SubscriptionResolver') as MockResolver:
            mock_resolver = MockResolver.return_value
            mock_resolver.resolve.return_value = mock_resolve_result

            # 执行工具
            result = tool_function(call, mock_context)

            # 验证结果
            assert result.status == "success"
            assert result.raw_output["display_name"] == "科技美学"

    def test_fetch_subscription_data_exception_handling(self, tool_function, mock_context):
        """测试异常处理"""
        call = ToolCall(
            plugin_id="fetch_subscription_data",
            args={"query": "科技美学的投稿"},
            step_id=1,
            description="测试异常处理"
        )

        # Mock SubscriptionResolver 抛出异常
        with patch('services.subscription.subscription_resolver.SubscriptionResolver') as MockResolver:
            MockResolver.side_effect = Exception("LLM 服务不可用")

            # 执行工具
            result = tool_function(call, mock_context)

            # 验证结果
            assert result.status == "error"
            assert "订阅查询失败" in result.error_message

    def test_fetch_subscription_data_no_data_query_service(self, tool_function):
        """测试 DataQueryService 未注入的情况"""
        # 创建没有 data_query_service 的 context
        mock_context = Mock(spec=ToolExecutionContext)
        mock_context.data_query_service = None

        mock_resolve_result = {
            "subscription_id": 1,
            "path": "/user/video-all/12345",
            "display_name": "科技美学",
            "action_display_name": "用户所有视频",
            "similarity": 0.95
        }

        call = ToolCall(
            plugin_id="fetch_subscription_data",
            args={"query": "科技美学的投稿"},
            step_id=1,
            description="测试无DataQueryService"
        )

        # 添加 extras 字段（需要 llm_client）
        mock_llm_client = Mock()
        mock_context.extras = {"llm_client": mock_llm_client}

        with patch('services.subscription.subscription_resolver.SubscriptionResolver') as MockResolver:
            mock_resolver = MockResolver.return_value
            mock_resolver.resolve.return_value = mock_resolve_result

            # 执行工具
            result = tool_function(call, mock_context)

            # 应该返回错误
            assert result.status == "error"
            assert "DataQueryService" in result.error_message

    def test_fetch_subscription_data_guest_mode(self, tool_function, mock_context):
        """测试游客模式（context.extras 中没有 user_id）"""
        # Mock SubscriptionResolver.resolve
        mock_resolve_result = {
            "subscription_id": 1,
            "path": "/user/video-all/12345",
            "display_name": "科技美学",
            "action_display_name": "用户所有视频",
            "similarity": 0.95
        }

        # Mock DataQueryService.query
        mock_feed_result = DataQueryResult(
            status="success",
            feed_title="科技美学的视频",
            generated_path="/user/video-all/12345",
            items=[
                {"title": "视频1", "link": "https://example.com/1"}
            ],
            source="rsshub",
            cache_hit=False,
            reasoning=""
        )
        mock_context.data_query_service.query.return_value = mock_feed_result

        # 创建 ToolCall（游客模式）
        call = ToolCall(
            plugin_id="fetch_subscription_data",
            args={"query": "科技美学的投稿"},
            step_id=1,
            description="游客模式查询"
        )

        # Mock SubscriptionResolver（验证传入 user_id=None）
        with patch('services.subscription.subscription_resolver.SubscriptionResolver') as MockResolver:
            mock_resolver = MockResolver.return_value
            mock_resolver.resolve.return_value = mock_resolve_result

            # 执行工具
            result = tool_function(call, mock_context)

            # 验证 resolve 被调用时 user_id=None（游客模式）
            mock_resolver.resolve.assert_called_once()
            call_args = mock_resolver.resolve.call_args
            # user_id 是第二个位置参数
            assert call_args[0][1] is None  # 验证 user_id=None

            # 验证结果
            assert result.status == "success"
            assert result.raw_output["display_name"] == "科技美学"
