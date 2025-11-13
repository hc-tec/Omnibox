"""订阅管理服务测试

测试 SubscriptionService 的 CRUD 操作和 ID 映射功能。

运行测试：
    python -m pytest tests/services/test_subscription_service.py -v
"""

import pytest
import os
from services.database import (
    DatabaseConnection,
    SubscriptionService,
    Subscription
)


@pytest.fixture(scope="function")
def test_db():
    """测试数据库 fixture（每个测试函数独立）"""
    # 使用独立的测试数据库
    os.environ["DATABASE_URL"] = "sqlite:///test_subscription.db"

    # 重置单例
    DatabaseConnection.reset()

    # 创建数据库连接并创建表
    db = DatabaseConnection()
    db.create_tables()

    yield db

    # 清理：显式关闭数据库连接并删除测试数据库
    if db.engine:
        db.engine.dispose()  # 关闭所有连接

    DatabaseConnection.reset()

    # 重置环境变量
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]

    # 删除测试数据库文件
    try:
        if os.path.exists("test_subscription.db"):
            os.remove("test_subscription.db")
    except PermissionError:
        # Windows 下可能需要延迟
        import time
        time.sleep(0.1)
        if os.path.exists("test_subscription.db"):
            os.remove("test_subscription.db")


@pytest.fixture
def subscription_service(test_db):
    """订阅管理服务 fixture"""
    return SubscriptionService()


class TestSubscriptionService:
    """订阅管理服务测试套件"""

    def test_create_subscription(self, subscription_service):
        """测试创建订阅"""
        subscription = subscription_service.create_subscription(
            display_name="科技美学",
            platform="bilibili",
            entity_type="user",
            identifiers={"uid": "12345"},
            description="数码测评UP主",
            aliases=["科技美学", "科技美学Official"],
            tags=["数码", "科技"]
        )

        assert subscription.id is not None
        assert subscription.display_name == "科技美学"
        assert subscription.platform == "bilibili"
        assert subscription.entity_type == "user"
        assert subscription.is_active is True

        # 验证 JSON 字段
        import json
        identifiers = json.loads(subscription.identifiers)
        assert identifiers["uid"] == "12345"

        aliases = json.loads(subscription.aliases)
        assert "科技美学" in aliases
        assert "科技美学Official" in aliases

        tags = json.loads(subscription.tags)
        assert "数码" in tags
        assert "科技" in tags

        # 验证支持的动作自动获取
        supported_actions = json.loads(subscription.supported_actions)
        assert isinstance(supported_actions, list)
        print(f"支持的动作: {supported_actions}")

    def test_list_subscriptions(self, subscription_service):
        """测试列出订阅"""
        # 创建多个订阅
        subscription_service.create_subscription(
            display_name="科技美学",
            platform="bilibili",
            entity_type="user",
            identifiers={"uid": "12345"}
        )
        subscription_service.create_subscription(
            display_name="少数派",
            platform="zhihu",
            entity_type="column",
            identifiers={"column_id": "sspai"}
        )

        # 列出所有订阅
        subscriptions = subscription_service.list_subscriptions()
        assert len(subscriptions) == 2

        # 按平台过滤
        bilibili_subs = subscription_service.list_subscriptions(platform="bilibili")
        assert len(bilibili_subs) == 1
        assert bilibili_subs[0].display_name == "科技美学"

    def test_get_subscription(self, subscription_service):
        """测试获取订阅详情"""
        # 创建订阅
        created = subscription_service.create_subscription(
            display_name="科技美学",
            platform="bilibili",
            entity_type="user",
            identifiers={"uid": "12345"}
        )

        # 获取订阅
        subscription = subscription_service.get_subscription(created.id)
        assert subscription is not None
        assert subscription.display_name == "科技美学"

        # 测试不存在的订阅
        none_sub = subscription_service.get_subscription(9999)
        assert none_sub is None

    def test_update_subscription(self, subscription_service):
        """测试更新订阅"""
        # 创建订阅
        created = subscription_service.create_subscription(
            display_name="科技美学",
            platform="bilibili",
            entity_type="user",
            identifiers={"uid": "12345"}
        )

        # 更新订阅
        updated = subscription_service.update_subscription(
            created.id,
            description="更新后的描述",
            tags=["数码", "科技", "测评"]
        )

        assert updated is not None
        assert updated.description == "更新后的描述"

        import json
        tags = json.loads(updated.tags)
        assert len(tags) == 3
        assert "测评" in tags

    def test_delete_subscription(self, subscription_service):
        """测试删除订阅"""
        # 创建订阅
        created = subscription_service.create_subscription(
            display_name="科技美学",
            platform="bilibili",
            entity_type="user",
            identifiers={"uid": "12345"}
        )

        # 删除订阅
        success = subscription_service.delete_subscription(created.id)
        assert success is True

        # 验证已删除
        subscription = subscription_service.get_subscription(created.id)
        assert subscription is None

        # 测试删除不存在的订阅
        success = subscription_service.delete_subscription(9999)
        assert success is False

    def test_search_subscriptions_fuzzy(self, subscription_service):
        """测试模糊搜索订阅"""
        # 创建订阅
        subscription_service.create_subscription(
            display_name="科技美学",
            platform="bilibili",
            entity_type="user",
            identifiers={"uid": "12345"},
            aliases=["科技美学", "科技美学Official"],
            description="数码测评UP主"
        )
        subscription_service.create_subscription(
            display_name="少数派",
            platform="zhihu",
            entity_type="column",
            identifiers={"column_id": "sspai"}
        )

        # 搜索 "科技"
        results = subscription_service.search_subscriptions("科技")
        assert len(results) >= 1
        assert any(sub.display_name == "科技美学" for sub in results)

        # 搜索 "少数派"
        results = subscription_service.search_subscriptions("少数派")
        assert len(results) >= 1
        assert any(sub.display_name == "少数派" for sub in results)

    def test_resolve_entity(self, subscription_service):
        """测试解析实体标识符（核心功能）"""
        # 创建订阅
        subscription_service.create_subscription(
            display_name="科技美学",
            platform="bilibili",
            entity_type="user",
            identifiers={"uid": "12345"}
        )

        # 解析实体
        identifiers = subscription_service.resolve_entity(
            entity_name="科技美学",
            platform="bilibili",
            entity_type="user"
        )

        assert identifiers is not None
        assert identifiers["uid"] == "12345"

    def test_resolve_entity_by_alias(self, subscription_service):
        """测试通过别名解析实体"""
        # 创建订阅
        subscription_service.create_subscription(
            display_name="科技美学",
            platform="bilibili",
            entity_type="user",
            identifiers={"uid": "12345"},
            aliases=["科技美学", "科技美学Official", "那岩"]
        )

        # 通过别名解析
        identifiers = subscription_service.resolve_entity(
            entity_name="那岩",
            platform="bilibili",
            entity_type="user"
        )

        assert identifiers is not None
        assert identifiers["uid"] == "12345"

    def test_resolve_entity_not_found(self, subscription_service):
        """测试解析不存在的实体"""
        identifiers = subscription_service.resolve_entity(
            entity_name="不存在的UP主",
            platform="bilibili",
            entity_type="user"
        )

        assert identifiers is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
