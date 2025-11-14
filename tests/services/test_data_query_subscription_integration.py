"""集成测试：DataQueryService 订阅预检与真实依赖

这些测试使用真实的 CacheService 和 DataExecutor，确保 API 集成正确。
"""

import pytest
from unittest.mock import Mock, patch
from services.data_query_service import DataQueryService
from integration.cache_service import CacheService, reset_cache_service
from integration.data_executor import DataExecutor, FetchResult
from orchestrator.rag_in_action import RAGInAction


class TestSubscriptionPrecheckIntegration:
    """集成测试：验证订阅预检与真实 CacheService/DataExecutor 的集成"""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """每个测试后重置缓存单例"""
        yield
        reset_cache_service()

    @pytest.fixture
    def cache_service(self):
        """真实的 CacheService"""
        cache = CacheService()
        return cache

    @pytest.fixture
    def data_executor(self):
        """真实的 DataExecutor（但 mock HTTP 调用）"""
        executor = DataExecutor()
        return executor

    @pytest.fixture
    def mock_rag(self):
        """Mock RAG（订阅预检测试不需要真实 RAG）"""
        rag = Mock()
        return rag

    @pytest.fixture
    def mock_subscription_resolver(self):
        """Mock SubscriptionResolver"""
        resolver = Mock()
        return resolver

    @pytest.fixture
    def service(self, mock_rag, cache_service, data_executor, mock_subscription_resolver):
        """创建使用真实 Cache 和 Executor 的 DataQueryService"""
        return DataQueryService(
            rag_in_action=mock_rag,
            cache_service=cache_service,
            data_executor=data_executor,
            subscription_resolver=mock_subscription_resolver,
        )

    def test_subscription_cache_uses_real_llm_cache(
        self, service, cache_service, mock_subscription_resolver
    ):
        """验证订阅解析使用真实的 LLM 缓存 API"""
        # Mock 订阅解析返回
        mock_subscription_resolver.resolve.return_value = {
            "subscription_id": 1,
            "path": "/bilibili/user/video/12345",
            "display_name": "科技美学",
            "similarity": 0.95,
        }

        user_query = "科技美学的投稿"
        user_id = 1

        # 第一次调用（应该调用 resolver）
        result1 = service._try_subscription_query(user_query, user_id, use_cache=True)
        assert result1 is not None
        assert result1["display_name"] == "科技美学"
        assert mock_subscription_resolver.resolve.call_count == 1

        # 第二次调用（应该命中缓存，不调用 resolver）
        result2 = service._try_subscription_query(user_query, user_id, use_cache=True)
        assert result2 is not None
        assert result2["display_name"] == "科技美学"
        # resolver 仍然只被调用了一次（证明缓存生效）
        assert mock_subscription_resolver.resolve.call_count == 1

        # 验证缓存键正确
        cached_value = cache_service.get_llm_cache(
            prompt=user_query,
            cache_type="subscription_resolve",
            user_id=user_id,
        )
        assert cached_value is not None
        assert cached_value["display_name"] == "科技美学"

    def test_subscription_data_uses_real_rss_cache(
        self, service, cache_service, data_executor, mock_subscription_resolver
    ):
        """验证订阅数据使用真实的 RSS 缓存和 DataExecutor API"""
        # Mock 订阅解析
        mock_subscription_resolver.resolve.return_value = {
            "subscription_id": 1,
            "path": "/bilibili/user/video/12345",
            "display_name": "科技美学",
            "similarity": 0.95,
        }

        # Mock DataExecutor 的 fetch_rss 方法（返回 FetchResult）
        mock_fetch_result = FetchResult(
            status="success",
            items=[{"title": "视频1"}, {"title": "视频2"}],
            source="local",
            feed_title="科技美学的投稿",
        )

        with patch.object(data_executor, 'fetch_rss', return_value=mock_fetch_result):
            # 第一次构建订阅结果（应该调用 fetch_rss）
            subscription_data = {
                "subscription_id": 1,
                "path": "/bilibili/user/video/12345",
                "display_name": "科技美学",
                "confidence": 0.95,
            }

            result1 = service._build_subscription_result(
                subscription_data,
                use_cache=True,
            )

            assert result1.status == "success"
            assert len(result1.items) == 2
            assert result1.items[0]["title"] == "视频1"
            assert data_executor.fetch_rss.call_count == 1

            # 第二次构建（应该命中 RSS 缓存，不调用 fetch_rss）
            result2 = service._build_subscription_result(
                subscription_data,
                use_cache=True,
            )

            assert result2.status == "success"
            assert len(result2.items) == 2
            # fetch_rss 仍然只被调用了一次（证明 RSS 缓存生效）
            assert data_executor.fetch_rss.call_count == 1
            # 验证缓存状态
            assert result2.cache_hit == "rss_cache"

    def test_subscription_precheck_with_real_cache_flow(
        self, service, cache_service, data_executor, mock_subscription_resolver, mock_rag
    ):
        """端到端测试：订阅预检 + 真实缓存流程"""
        # Mock 订阅解析
        mock_subscription_resolver.resolve.return_value = {
            "subscription_id": 1,
            "path": "/bilibili/user/video/12345",
            "display_name": "科技美学",
            "similarity": 0.95,
        }

        # Mock DataExecutor
        mock_fetch_result = FetchResult(
            status="success",
            items=[{"title": "视频1"}],
            source="local",
            feed_title="科技美学的投稿",
        )

        with patch.object(data_executor, 'fetch_rss', return_value=mock_fetch_result):
            # 第一次完整查询
            result1 = service.query("科技美学的投稿", user_id=1, use_cache=True)

            assert result1.status == "success"
            assert result1.source == "subscription"
            assert mock_subscription_resolver.resolve.call_count == 1
            assert data_executor.fetch_rss.call_count == 1

            # 第二次查询（两层缓存都应该命中）
            result2 = service.query("科技美学的投稿", user_id=1, use_cache=True)

            assert result2.status == "success"
            assert result2.source == "subscription"
            # 订阅解析缓存命中，不应再调用 resolver
            assert mock_subscription_resolver.resolve.call_count == 1
            # RSS 缓存命中，不应再调用 fetch_rss
            assert data_executor.fetch_rss.call_count == 1

    def test_fetch_rss_error_handling(
        self, service, data_executor, mock_subscription_resolver
    ):
        """测试 DataExecutor 返回错误时的处理"""
        # Mock 订阅解析
        mock_subscription_resolver.resolve.return_value = {
            "subscription_id": 1,
            "path": "/bilibili/user/video/12345",
            "display_name": "科技美学",
            "similarity": 0.95,
        }

        # Mock DataExecutor 返回错误
        mock_fetch_result = FetchResult(
            status="error",
            items=[],
            source="local",
            error_message="RSSHub API 错误",
        )

        with patch.object(data_executor, 'fetch_rss', return_value=mock_fetch_result):
            subscription_data = {
                "subscription_id": 1,
                "path": "/bilibili/user/video/12345",
                "display_name": "科技美学",
                "confidence": 0.95,
            }

            result = service._build_subscription_result(
                subscription_data,
                use_cache=True,
            )

            # 应该返回错误状态
            assert result.status == "error"
            assert "订阅数据获取失败" in result.reasoning
            assert "RSSHub API 错误" in result.reasoning
