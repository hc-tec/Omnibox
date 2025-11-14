"""测试 DataQueryService 的订阅预检功能

验证订阅预检逻辑的正确性：
1. 高置信度订阅直接返回
2. 中等置信度订阅作为 RAG 兜底
3. user_id 正确传递
4. 缓存机制
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from services.data_query_service import DataQueryService, DataQueryResult
from integration.cache_service import CacheService


class TestDataQuerySubscriptionPrecheck:
    """测试 DataQueryService 订阅预检功能"""

    @pytest.fixture
    def mock_rag(self):
        """创建 Mock RAG"""
        rag = Mock()
        return rag

    @pytest.fixture
    def mock_cache(self):
        """创建 Mock CacheService"""
        cache = Mock()
        cache.get = Mock(return_value=None)  # 默认缓存未命中
        cache.set = Mock()
        return cache

    @pytest.fixture
    def mock_subscription_resolver(self):
        """创建 Mock SubscriptionResolver"""
        resolver = Mock()
        return resolver

    @pytest.fixture
    def service(self, mock_rag, mock_cache, mock_subscription_resolver):
        """创建 DataQueryService 实例"""
        return DataQueryService(
            rag_in_action=mock_rag,
            cache_service=mock_cache,
            subscription_resolver=mock_subscription_resolver,
        )

    def test_high_confidence_subscription_skips_rag(
        self, service, mock_subscription_resolver, mock_rag, mock_cache
    ):
        """测试高置信度订阅跳过 RAG"""
        # Mock 订阅解析返回高置信度结果
        mock_subscription_resolver.resolve.return_value = {
            "subscription_id": 1,
            "path": "/user/video-all/12345",
            "display_name": "科技美学",
            "action_display_name": "用户所有视频",
            "similarity": 0.95,  # 高置信度
        }

        # Mock RSSHub 数据
        mock_cache.get.side_effect = lambda key: None  # 缓存未命中
        with patch.object(service, 'data_executor') as mock_executor:
            mock_executor.fetch_rsshub.return_value = {
                "items": [{"title": "视频1"}],
            }

            # 执行查询
            result = service.query("科技美学的投稿", user_id=1)

            # 验证结果
            assert result.status == "success"
            assert result.source == "subscription"
            assert result.feed_title == "科技美学"
            assert "订阅命中" in result.reasoning

            # 验证 RAG 未被调用（跳过了）
            mock_rag.process.assert_not_called()

            # 验证订阅解析被调用
            mock_subscription_resolver.resolve.assert_called_once()
            call_kwargs = mock_subscription_resolver.resolve.call_args.kwargs
            assert call_kwargs["user_id"] == 1
            assert call_kwargs["min_similarity"] == 0.6

    def test_medium_confidence_subscription_as_fallback(
        self, service, mock_subscription_resolver, mock_rag, mock_cache
    ):
        """测试中等置信度订阅作为 RAG 失败后的兜底"""
        # Mock 订阅解析返回中等置信度结果
        mock_subscription_resolver.resolve.return_value = {
            "subscription_id": 1,
            "path": "/user/video-all/12345",
            "display_name": "科技美学",
            "action_display_name": "用户所有视频",
            "similarity": 0.65,  # 中等置信度
        }

        # Mock RAG 失败
        mock_rag.process.return_value = Mock(
            status="not_found",
            reasoning="未找到相关工具",
            retrieved_tools=[],
            datasets=[],
            rag_trace={},
        )

        # Mock RSSHub 数据
        with patch.object(service, 'data_executor') as mock_executor:
            mock_executor.fetch_rsshub.return_value = {
                "items": [{"title": "视频1"}],
            }

            # 执行查询
            result = service.query("科技美学的投稿", user_id=1)

            # 验证结果
            assert result.status == "success"
            assert result.source == "subscription"
            assert "RAG not_found" in result.reasoning

            # 验证 RAG 被调用了（因为置信度不够高）
            mock_rag.process.assert_called_once()

    def test_low_confidence_subscription_ignored(
        self, service, mock_subscription_resolver, mock_rag
    ):
        """测试低置信度订阅被忽略"""
        # Mock 订阅解析返回低置信度结果
        mock_subscription_resolver.resolve.return_value = {
            "subscription_id": 1,
            "path": "/user/video-all/12345",
            "display_name": "科技美学",
            "similarity": 0.5,  # 低于阈值 0.6
        }

        # 但实际上，resolve 应该直接返回 None（因为 min_similarity=0.6）
        mock_subscription_resolver.resolve.return_value = None

        # Mock RAG 成功
        mock_rag.process.return_value = Mock(
            status="success",
            reasoning="RAG 成功",
            feed_title="B站热搜",
            items=[{"title": "item1"}],
            generated_path="/bilibili/hot",
            source="rsshub",
            cache_hit=False,
            datasets=[],
            retrieved_tools=[],
        )

        # 执行查询
        result = service.query("科技美学的投稿", user_id=1)

        # 验证使用了 RAG 结果
        assert result.status == "success"
        assert result.feed_title == "B站热搜"

        # 验证订阅解析被调用
        mock_subscription_resolver.resolve.assert_called_once()

    def test_no_subscription_found_uses_rag(
        self, service, mock_subscription_resolver, mock_rag
    ):
        """测试未找到订阅时使用 RAG"""
        # Mock 订阅解析未找到
        mock_subscription_resolver.resolve.return_value = None

        # Mock RAG 成功
        def mock_rag_process(query, *args, **kwargs):
            return Mock(
                status="success",
                reasoning="RAG 成功",
                feed_title="B站热搜",
                items=[{"title": "item1"}],
                generated_path="/bilibili/hot",
                source="rsshub",
                cache_hit=False,
                datasets=[],
                retrieved_tools=[],
                rag_trace={},
            )

        mock_rag.process = mock_rag_process

        # 执行查询
        result = service.query("B站热搜", user_id=1)

        # 验证使用了 RAG 结果
        assert result.status == "success"
        assert result.feed_title == "B站热搜"

    def test_guest_mode_user_id_none(
        self, service, mock_subscription_resolver, mock_rag
    ):
        """测试游客模式（user_id=None）"""
        # Mock 订阅解析
        mock_subscription_resolver.resolve.return_value = None

        # Mock RAG 成功
        mock_rag.process.return_value = Mock(
            status="success",
            reasoning="RAG 成功",
            feed_title="B站热搜",
            items=[{"title": "item1"}],
            generated_path="/bilibili/hot",
            source="rsshub",
            cache_hit=False,
            datasets=[],
            retrieved_tools=[],
        )

        # 执行查询（user_id=None）
        result = service.query("B站热搜", user_id=None)

        # 验证订阅解析被调用时 user_id=None
        mock_subscription_resolver.resolve.assert_called_once()
        call_kwargs = mock_subscription_resolver.resolve.call_args.kwargs
        assert call_kwargs["user_id"] is None

    def test_filter_datasource_skips_subscription(
        self, service, mock_subscription_resolver, mock_rag
    ):
        """测试 filter_datasource 存在时跳过订阅预检"""
        # Mock RAG 成功
        mock_rag.process.return_value = Mock(
            status="success",
            reasoning="RAG 成功",
            feed_title="GitHub 热门",
            items=[{"title": "repo1"}],
            generated_path="/github/trending",
            source="rsshub",
            cache_hit=False,
            datasets=[],
            retrieved_tools=[],
        )

        # 执行查询（指定 filter_datasource）
        result = service.query("GitHub 热门", filter_datasource="github", user_id=1)

        # 验证订阅解析未被调用
        mock_subscription_resolver.resolve.assert_not_called()

    def test_subscription_cache_hit(
        self, service, mock_subscription_resolver, mock_cache
    ):
        """测试订阅解析缓存命中"""
        # Mock 缓存命中
        cached_subscription = {
            "subscription_id": 1,
            "path": "/user/video-all/12345",
            "display_name": "科技美学",
            "action_display_name": "用户所有视频",
            "confidence": 0.95,
        }

        def cache_get_side_effect(key):
            if "sub_resolve:" in key:
                return cached_subscription
            return None

        mock_cache.get.side_effect = cache_get_side_effect

        # Mock RSSHub 数据
        with patch.object(service, 'data_executor') as mock_executor:
            mock_executor.fetch_rsshub.return_value = {
                "items": [{"title": "视频1"}],
            }

            # 执行查询
            result = service.query("科技美学的投稿", user_id=1)

            # 验证结果
            assert result.status == "success"
            assert result.source == "subscription"

            # 验证订阅解析未被调用（因为缓存命中）
            mock_subscription_resolver.resolve.assert_not_called()

    def test_subscription_data_cache_hit(
        self, service, mock_subscription_resolver, mock_cache
    ):
        """测试订阅数据缓存命中"""
        # Mock 订阅解析返回高置信度结果
        mock_subscription_resolver.resolve.return_value = {
            "subscription_id": 1,
            "path": "/user/video-all/12345",
            "display_name": "科技美学",
            "similarity": 0.95,
        }

        # Mock 数据缓存命中
        cached_data = {
            "items": [{"title": "视频1（缓存）"}],
        }

        def cache_get_side_effect(key):
            if "rsshub:" in key:
                return cached_data
            return None

        mock_cache.get.side_effect = cache_get_side_effect

        # 执行查询
        result = service.query("科技美学的投稿", user_id=1, use_cache=True)

        # 验证结果
        assert result.status == "success"
        assert result.source == "subscription"
        assert result.cache_hit == "data_cache"
        assert result.items[0]["title"] == "视频1（缓存）"

    def test_subscription_resolver_exception(
        self, service, mock_subscription_resolver, mock_rag
    ):
        """测试订阅解析异常处理"""
        # Mock 订阅解析抛出异常
        mock_subscription_resolver.resolve.side_effect = Exception("LLM 错误")

        # Mock RAG 成功
        mock_rag.process.return_value = Mock(
            status="success",
            reasoning="RAG 成功",
            feed_title="B站热搜",
            items=[{"title": "item1"}],
            generated_path="/bilibili/hot",
            source="rsshub",
            cache_hit=False,
            datasets=[],
            retrieved_tools=[],
        )

        # 执行查询（应该降级到 RAG）
        result = service.query("科技美学的投稿", user_id=1)

        # 验证使用了 RAG 结果（订阅失败后降级）
        assert result.status == "success"
        assert result.feed_title == "B站热搜"

    def test_no_subscription_resolver(self, mock_rag, mock_cache):
        """测试未注入 SubscriptionResolver 时的行为"""
        # 创建没有订阅解析器的服务
        service = DataQueryService(
            rag_in_action=mock_rag,
            cache_service=mock_cache,
            subscription_resolver=None,
        )

        # Mock RAG 成功
        mock_rag.process.return_value = Mock(
            status="success",
            reasoning="RAG 成功",
            feed_title="B站热搜",
            items=[{"title": "item1"}],
            generated_path="/bilibili/hot",
            source="rsshub",
            cache_hit=False,
            datasets=[],
            retrieved_tools=[],
        )

        # 执行查询
        result = service.query("科技美学的投稿", user_id=1)

        # 验证直接使用 RAG（跳过订阅预检）
        assert result.status == "success"
        assert result.feed_title == "B站热搜"
