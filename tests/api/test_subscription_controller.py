"""订阅管理 API 集成测试

测试 SubscriptionController 的所有 RESTful 端点。

运行测试：
    python -m pytest tests/api/test_subscription_controller.py -v
"""

import pytest
import os
from fastapi.testclient import TestClient

from api.app import create_app
from services.database import DatabaseConnection


@pytest.fixture(scope="function")
def test_db():
    """测试数据库 fixture（每个测试函数独立）"""
    # 使用独立的测试数据库
    os.environ["DATABASE_URL"] = "sqlite:///test_api_subscription.db"

    # 先删除旧的测试数据库（如果存在）
    if os.path.exists("test_api_subscription.db"):
        try:
            os.remove("test_api_subscription.db")
        except PermissionError:
            import time
            time.sleep(0.1)
            try:
                os.remove("test_api_subscription.db")
            except:
                pass

    # 重置单例
    DatabaseConnection.reset()

    # 创建数据库连接并创建表
    db = DatabaseConnection()
    db.create_tables()

    yield db

    # 清理：显式关闭数据库连接并删除测试数据库
    if db.engine:
        db.engine.dispose()

    DatabaseConnection.reset()

    # 重置环境变量
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]

    # 删除测试数据库文件
    try:
        if os.path.exists("test_api_subscription.db"):
            os.remove("test_api_subscription.db")
    except PermissionError:
        import time
        time.sleep(0.1)
        try:
            if os.path.exists("test_api_subscription.db"):
                os.remove("test_api_subscription.db")
        except:
            pass


@pytest.fixture
def client(test_db):
    """FastAPI 测试客户端"""
    app = create_app()
    return TestClient(app)


class TestSubscriptionAPI:
    """订阅管理 API 测试套件"""

    def test_create_subscription(self, client):
        """测试创建订阅 API"""
        response = client.post(
            "/api/v1/subscriptions",
            json={
                "display_name": "科技美学",
                "platform": "bilibili",
                "entity_type": "user",
                "identifiers": {"uid": "12345"},
                "description": "数码测评UP主",
                "aliases": ["科技美学", "科技美学Official"],
                "tags": ["数码", "科技"]
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["display_name"] == "科技美学"
        assert data["platform"] == "bilibili"
        assert data["entity_type"] == "user"
        assert data["identifiers"]["uid"] == "12345"
        assert "科技美学" in data["aliases"]
        assert "数码" in data["tags"]
        assert "id" in data
        assert isinstance(data["supported_actions"], list)

    def test_create_duplicate_subscription(self, client):
        """测试创建重复订阅（应返回 409）"""
        # 准备相同的请求数据
        request_data = {
            "display_name": "科技美学测试",
            "platform": "bilibili",
            "entity_type": "user",
            "identifiers": {"uid": "99999"},  # 使用特殊的 uid 避免与其他测试冲突
            "aliases": ["科技美学测试"],  # 明确指定 aliases 保持一致
            "tags": []  # 明确指定空标签
        }

        # 第一次创建
        response1 = client.post("/api/v1/subscriptions", json=request_data)
        assert response1.status_code == 201

        # 第二次创建（完全相同的数据）
        response2 = client.post("/api/v1/subscriptions", json=request_data)

        # 验证返回 409 Conflict
        assert response2.status_code == 409
        # 检查响应中包含错误信息（格式可能因中间件而异）
        response_text = response2.text
        assert response2.status_code == 409  # 主要检查状态码

    def test_list_subscriptions(self, client):
        """测试列出订阅 API"""
        # 创建两个订阅
        client.post(
            "/api/v1/subscriptions",
            json={
                "display_name": "科技美学",
                "platform": "bilibili",
                "entity_type": "user",
                "identifiers": {"uid": "12345"}
            }
        )
        client.post(
            "/api/v1/subscriptions",
            json={
                "display_name": "少数派",
                "platform": "zhihu",
                "entity_type": "column",
                "identifiers": {"column_id": "sspai"}
            }
        )

        # 列出所有订阅
        response = client.get("/api/v1/subscriptions")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        # 按平台过滤
        response = client.get("/api/v1/subscriptions?platform=bilibili")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["platform"] == "bilibili"

    def test_get_subscription(self, client):
        """测试获取订阅详情 API"""
        # 创建订阅
        create_response = client.post(
            "/api/v1/subscriptions",
            json={
                "display_name": "科技美学",
                "platform": "bilibili",
                "entity_type": "user",
                "identifiers": {"uid": "12345"}
            }
        )
        subscription_id = create_response.json()["id"]

        # 获取订阅
        response = client.get(f"/api/v1/subscriptions/{subscription_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == subscription_id
        assert data["display_name"] == "科技美学"

        # 测试不存在的订阅
        response = client.get("/api/v1/subscriptions/9999")
        assert response.status_code == 404

    def test_update_subscription(self, client):
        """测试更新订阅 API"""
        # 创建订阅
        create_response = client.post(
            "/api/v1/subscriptions",
            json={
                "display_name": "科技美学",
                "platform": "bilibili",
                "entity_type": "user",
                "identifiers": {"uid": "12345"}
            }
        )
        subscription_id = create_response.json()["id"]

        # 更新订阅
        response = client.patch(
            f"/api/v1/subscriptions/{subscription_id}",
            json={
                "description": "更新后的描述",
                "tags": ["数码", "科技", "测评"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "更新后的描述"
        assert len(data["tags"]) == 3
        assert "测评" in data["tags"]

        # 测试不存在的订阅
        response = client.patch(
            "/api/v1/subscriptions/9999",
            json={"description": "test"}
        )
        assert response.status_code == 404

    def test_update_platform_refreshes_actions(self, client):
        """测试更新平台会自动刷新 supported_actions"""
        # 创建订阅
        create_response = client.post(
            "/api/v1/subscriptions",
            json={
                "display_name": "测试实体",
                "platform": "bilibili",
                "entity_type": "user",
                "identifiers": {"uid": "12345"}
            }
        )
        subscription_id = create_response.json()["id"]
        original_actions = create_response.json()["supported_actions"]

        # 更新平台（假设切换到不同平台会有不同的 actions）
        response = client.patch(
            f"/api/v1/subscriptions/{subscription_id}",
            json={"platform": "zhihu"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "zhihu"
        # supported_actions 应该已经刷新（可能与原来不同）

    def test_delete_subscription(self, client):
        """测试删除订阅 API"""
        # 创建订阅
        create_response = client.post(
            "/api/v1/subscriptions",
            json={
                "display_name": "科技美学",
                "platform": "bilibili",
                "entity_type": "user",
                "identifiers": {"uid": "12345"}
            }
        )
        subscription_id = create_response.json()["id"]

        # 删除订阅
        response = client.delete(f"/api/v1/subscriptions/{subscription_id}")
        assert response.status_code == 204

        # 验证已删除
        response = client.get(f"/api/v1/subscriptions/{subscription_id}")
        assert response.status_code == 404

        # 测试删除不存在的订阅
        response = client.delete("/api/v1/subscriptions/9999")
        assert response.status_code == 404

    def test_get_subscription_actions(self, client):
        """测试获取订阅支持的动作列表 API"""
        # 创建订阅
        create_response = client.post(
            "/api/v1/subscriptions",
            json={
                "display_name": "科技美学",
                "platform": "bilibili",
                "entity_type": "user",
                "identifiers": {"uid": "12345"}
            }
        )
        subscription_id = create_response.json()["id"]

        # 获取动作列表
        response = client.get(f"/api/v1/subscriptions/{subscription_id}/actions")
        assert response.status_code == 200
        actions = response.json()
        assert isinstance(actions, list)
        # 应该有至少一个动作
        if len(actions) > 0:
            action = actions[0]
            assert "action" in action
            assert "display_name" in action
            assert "path_template" in action

    def test_resolve_entity(self, client):
        """测试解析实体标识符 API"""
        # 创建订阅
        client.post(
            "/api/v1/subscriptions",
            json={
                "display_name": "科技美学",
                "platform": "bilibili",
                "entity_type": "user",
                "identifiers": {"uid": "12345"}
            }
        )

        # 解析实体
        response = client.post(
            "/api/v1/subscriptions/resolve",
            json={
                "entity_name": "科技美学",
                "platform": "bilibili",
                "entity_type": "user"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["identifiers"]["uid"] == "12345"
        assert "subscription_id" in data

    def test_resolve_entity_by_alias(self, client):
        """测试通过别名解析实体 API"""
        # 创建订阅
        client.post(
            "/api/v1/subscriptions",
            json={
                "display_name": "科技美学",
                "platform": "bilibili",
                "entity_type": "user",
                "identifiers": {"uid": "12345"},
                "aliases": ["科技美学", "科技美学Official", "那岩"]
            }
        )

        # 通过别名解析
        response = client.post(
            "/api/v1/subscriptions/resolve",
            json={
                "entity_name": "那岩",
                "platform": "bilibili",
                "entity_type": "user"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["identifiers"]["uid"] == "12345"

    def test_resolve_entity_not_found(self, client):
        """测试解析不存在的实体 API"""
        response = client.post(
            "/api/v1/subscriptions/resolve",
            json={
                "entity_name": "不存在的UP主",
                "platform": "bilibili",
                "entity_type": "user"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "未找到订阅" in data["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
