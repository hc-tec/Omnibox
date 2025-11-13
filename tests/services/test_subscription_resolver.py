"""测试 SubscriptionResolver（订阅解析器）

测试从自然语言查询到 RSSHub 路径的完整解析流程。
"""

import pytest
import json
from unittest.mock import Mock, patch
from services.subscription.subscription_resolver import SubscriptionResolver
from services.subscription.query_parser import ParsedQuery
from services.database.models import Subscription


class TestSubscriptionResolver:
    """SubscriptionResolver 测试套件"""

    @pytest.fixture
    def mock_llm_client(self):
        """创建 Mock LLM 客户端"""
        client = Mock()
        return client

    @pytest.fixture
    def mock_subscription(self):
        """创建 Mock 订阅对象"""
        subscription = Mock(spec=Subscription)
        subscription.id = 1
        subscription.user_id = 1
        subscription.display_name = "科技美学"
        subscription.platform = "bilibili"
        subscription.entity_type = "user"
        subscription.identifiers = json.dumps({"uid": "12345"})
        subscription.supported_actions = json.dumps(["videos", "dynamic", "following"])
        subscription.is_active = True
        subscription._similarity = 0.95
        return subscription

    @pytest.fixture
    def resolver(self, mock_llm_client):
        """创建 SubscriptionResolver 实例"""
        return SubscriptionResolver(mock_llm_client)

    def test_resolve_bilibili_video_query(
        self,
        resolver,
        mock_llm_client,
        mock_subscription
    ):
        """测试解析 B站投稿视频查询"""
        # 模拟 LLM 解析响应
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "科技美学",
            "action": "视频",  # 使用更简单的关键词
            "platform": "bilibili",
            "confidence": 0.9
        })

        # 模拟订阅搜索
        with patch.object(
            resolver.subscription_service,
            'search_subscriptions',
            return_value=[mock_subscription]
        ):
            # 执行解析
            result = resolver.resolve("科技美学的最新投稿", user_id=1)

            # 验证结果
            assert result is not None
            assert result["subscription_id"] == 1
            assert result["path"] == "/user/video-all/12345"  # 实际的路径模板
            assert result["display_name"] == "科技美学"
            assert result["action"] == "videos"
            assert result["similarity"] == 0.95

    def test_resolve_with_default_action(
        self,
        resolver,
        mock_llm_client,
        mock_subscription
    ):
        """测试未指定动作时使用默认动作"""
        # 模拟 LLM 解析响应（无动作）
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "科技美学",
            "action": None,
            "platform": "bilibili",
            "confidence": 0.8
        })

        with patch.object(
            resolver.subscription_service,
            'search_subscriptions',
            return_value=[mock_subscription]
        ):
            result = resolver.resolve("科技美学", user_id=1)

            # 应该使用默认动作（第一个支持的动作）
            assert result is not None
            assert result["action"] == "videos"  # 默认动作

    def test_resolve_no_matching_subscription(
        self,
        resolver,
        mock_llm_client
    ):
        """测试找不到匹配订阅的情况"""
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "不存在的UP主",
            "action": "投稿视频",
            "platform": "bilibili",
            "confidence": 0.9
        })

        # 模拟搜索无结果
        with patch.object(
            resolver.subscription_service,
            'search_subscriptions',
            return_value=[]
        ):
            result = resolver.resolve("不存在的UP主的视频", user_id=1)

            assert result is None

    def test_resolve_low_similarity(
        self,
        resolver,
        mock_llm_client,
        mock_subscription
    ):
        """测试相似度低于阈值的情况"""
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "科技美学",
            "action": "投稿视频",
            "platform": "bilibili",
            "confidence": 0.9
        })

        # 设置低相似度
        mock_subscription._similarity = 0.5

        with patch.object(
            resolver.subscription_service,
            'search_subscriptions',
            return_value=[]  # 相似度过低，搜索无结果
        ):
            result = resolver.resolve("科技美学", user_id=1, min_similarity=0.7)

            assert result is None

    def test_resolve_action_matching(self, resolver, mock_subscription):
        """测试动作匹配逻辑"""
        # 修改 mock 订阅的支持动作为实际存在的动作
        # bilibili user 支持的动作：videos, dynamics, followings_list 等
        mock_subscription.supported_actions = json.dumps(["videos", "dynamics", "followings_list"])

        # 测试包含匹配（"用户所有视频" 包含 "视频"）
        action = resolver._resolve_action("视频", mock_subscription)
        assert action == "videos"

        # 测试动态（"UP 主动态" 包含 "动态"）
        action = resolver._resolve_action("动态", mock_subscription)
        assert action == "dynamics"

        # 测试关注列表（"UP 主关注用户" 包含 "关注"）
        action = resolver._resolve_action("关注", mock_subscription)
        assert action == "followings_list"

        # 测试精确匹配动作名称
        action = resolver._resolve_action("videos", mock_subscription)
        assert action == "videos"

    def test_resolve_action_no_match(self, resolver, mock_subscription):
        """测试无法匹配动作的情况"""
        action = resolver._resolve_action("不支持的动作", mock_subscription)
        assert action is None

    def test_resolve_action_none(self, resolver, mock_subscription):
        """测试动作为 None 的情况"""
        action = resolver._resolve_action(None, mock_subscription)
        assert action is None

    def test_resolve_with_platform_filter(
        self,
        resolver,
        mock_llm_client,
        mock_subscription
    ):
        """测试平台过滤"""
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "科技美学",
            "action": "投稿视频",
            "platform": "bilibili",
            "confidence": 0.9
        })

        with patch.object(
            resolver.subscription_service,
            'search_subscriptions',
            return_value=[mock_subscription]
        ) as mock_search:
            result = resolver.resolve("科技美学的投稿", user_id=1)

            # 验证调用参数
            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["platform"] == "bilibili"

    def test_resolve_unsupported_action(
        self,
        resolver,
        mock_llm_client,
        mock_subscription
    ):
        """测试订阅不支持的动作"""
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "科技美学",
            "action": "收藏",  # 订阅不支持此动作
            "platform": "bilibili",
            "confidence": 0.9
        })

        with patch.object(
            resolver.subscription_service,
            'search_subscriptions',
            return_value=[mock_subscription]
        ):
            result = resolver.resolve("科技美学的收藏", user_id=1)

            # 应该回退到默认动作
            assert result is not None
            assert result["action"] == "videos"  # 默认动作

    def test_batch_resolve(
        self,
        resolver,
        mock_llm_client,
        mock_subscription
    ):
        """测试批量解析"""
        queries = [
            "科技美学的投稿",
            "不存在的UP主",
            "科技美学的动态"
        ]

        # 模拟 LLM 响应
        def mock_chat(messages, **kwargs):
            query = messages[-1]["content"]
            if "科技美学" in query:
                if "动态" in query:
                    action = "动态"
                else:
                    action = "投稿视频"
                return json.dumps({
                    "entity_name": "科技美学",
                    "action": action,
                    "platform": "bilibili",
                    "confidence": 0.9
                })
            else:
                return json.dumps({
                    "entity_name": "不存在的UP主",
                    "action": "投稿视频",
                    "platform": "bilibili",
                    "confidence": 0.8
                })

        mock_llm_client.chat.side_effect = mock_chat

        # 模拟订阅搜索
        def mock_search(query, **kwargs):
            if "科技美学" in query:
                return [mock_subscription]
            else:
                return []

        with patch.object(
            resolver.subscription_service,
            'search_subscriptions',
            side_effect=mock_search
        ):
            results = resolver.batch_resolve(queries, user_id=1)

            # 验证结果
            assert len(results) == 3
            assert results[0] is not None  # 科技美学的投稿
            assert results[1] is None  # 不存在的UP主
            assert results[2] is not None  # 科技美学的动态

    def test_resolve_exception_handling(
        self,
        resolver,
        mock_llm_client
    ):
        """测试异常处理"""
        # 模拟 LLM 抛出异常
        mock_llm_client.chat.side_effect = Exception("LLM 错误")

        result = resolver.resolve("科技美学的投稿", user_id=1)

        # 应该捕获异常并返回 None
        assert result is None

    def test_resolve_github_repo(
        self,
        resolver,
        mock_llm_client
    ):
        """测试 GitHub 仓库查询"""
        # 创建 GitHub 订阅 Mock
        github_subscription = Mock(spec=Subscription)
        github_subscription.id = 2
        github_subscription.user_id = 1
        github_subscription.display_name = "langchain-ai/langchain"
        github_subscription.platform = "github"
        github_subscription.entity_type = "repo"
        github_subscription.identifiers = json.dumps({"user": "langchain-ai", "repo": "langchain"})
        github_subscription.supported_actions = json.dumps(["issues", "pull_requests", "stars"])
        github_subscription.is_active = True
        github_subscription._similarity = 0.9

        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "langchain",
            "action": "issues",
            "platform": "github",
            "confidence": 0.85
        })

        with patch.object(
            resolver.subscription_service,
            'search_subscriptions',
            return_value=[github_subscription]
        ):
            result = resolver.resolve("langchain的issues", user_id=1)

            assert result is not None
            assert result["path"] == "/issue/langchain-ai/langchain"
            assert result["action"] == "issues"

    def test_resolve_zhihu_user(
        self,
        resolver,
        mock_llm_client
    ):
        """测试知乎用户查询"""
        # 创建知乎订阅 Mock
        zhihu_subscription = Mock(spec=Subscription)
        zhihu_subscription.id = 3
        zhihu_subscription.user_id = 1
        zhihu_subscription.display_name = "张三"
        zhihu_subscription.platform = "zhihu"
        zhihu_subscription.entity_type = "user"
        zhihu_subscription.identifiers = json.dumps({"id": "zhang-san"})
        zhihu_subscription.supported_actions = json.dumps(["answers", "activities", "pins"])
        zhihu_subscription.is_active = True
        zhihu_subscription._similarity = 0.92

        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "张三",
            "action": "回答",
            "platform": "zhihu",
            "confidence": 0.9
        })

        with patch.object(
            resolver.subscription_service,
            'search_subscriptions',
            return_value=[zhihu_subscription]
        ):
            result = resolver.resolve("张三的最新回答", user_id=1)

            assert result is not None
            assert result["path"] == "/people/answers/zhang-san"
            assert result["action"] == "answers"

    def test_resolve_guest_mode(
        self,
        resolver,
        mock_llm_client,
        mock_subscription
    ):
        """测试游客模式（user_id=None）"""
        # 模拟 LLM 解析响应
        mock_llm_client.chat.return_value = json.dumps({
            "entity_name": "科技美学",
            "action": "投稿",
            "platform": "bilibili",
            "confidence": 0.9
        })

        # 模拟订阅搜索（游客模式应该查询到公共订阅）
        with patch.object(
            resolver.subscription_service,
            'search_subscriptions',
            return_value=[mock_subscription]
        ) as mock_search:
            # 执行解析（user_id=None 表示游客模式）
            result = resolver.resolve("科技美学的投稿", user_id=None)

            # 验证 search_subscriptions 被调用时 user_id=None
            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args.kwargs
            assert call_kwargs["user_id"] is None

            # 验证结果
            assert result is not None
            assert result["subscription_id"] == 1
            assert result["path"] == "/user/video-all/12345"
            assert result["display_name"] == "科技美学"
