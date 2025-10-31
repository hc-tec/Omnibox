"""
ChatController集成测试
测试内容：
1. POST /api/v1/chat - 对话接口
2. GET /api/v1/health - 健康检查
3. 异常处理和错误响应
4. 线程池策略验证
"""

import os
import sys
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


os.environ.setdefault("CHAT_SERVICE_MODE", "mock")
from api.app import create_app


@pytest.fixture(scope="module")
def client():
    """
    创建测试客户端

    使用module级别的fixture，在所有测试间共享客户端
    """
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


class TestRootEndpoint:
    """根路径测试"""

    def test_root_endpoint(self, client):
        """测试根路径返回API信息"""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "RSS聚合API"
        assert data["version"] == "1.0.0"
        assert "docs" in data
        assert "health" in data


class TestHealthCheck:
    """健康检查测试"""

    def test_health_check_success(self, client):
        """测试健康检查成功"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "services" in data

        # 检查服务状态
        services = data["services"]
        assert "chat_service" in services
        assert "rsshub" in services
        assert "rag" in services
        assert "cache" in services


class TestChatEndpoint:
    """对话接口测试"""

    def test_chat_basic_query(self, client):
        """测试基本对话查询"""
        response = client.post(
            "/api/v1/chat",
            json={
                "query": "你好",
                "use_cache": True,
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert "success" in data
        assert "message" in data
        assert "metadata" in data

        # 检查metadata存在且包含intent_type字段
        metadata = data["metadata"]
        assert metadata is not None
        assert "intent_type" in metadata
        # 如果intent_type有值，应该是chitchat
        if metadata["intent_type"]:
            assert metadata["intent_type"] in ["chitchat", "data_query"]

    def test_chat_with_cache_disabled(self, client):
        """测试禁用缓存的查询"""
        response = client.post(
            "/api/v1/chat",
            json={
                "query": "测试查询",
                "use_cache": False,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is not None

    def test_chat_validation_error_empty_query(self, client):
        """测试空查询参数验证错误"""
        response = client.post(
            "/api/v1/chat",
            json={
                "query": "",  # 空查询应该失败
                "use_cache": True,
            }
        )

        assert response.status_code == 422  # Unprocessable Entity

        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"
        assert "detail" in data

    def test_chat_validation_error_missing_query(self, client):
        """测试缺少query参数验证错误"""
        response = client.post(
            "/api/v1/chat",
            json={
                "use_cache": True,
            }
        )

        assert response.status_code == 422

        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"

    def test_chat_validation_error_invalid_type(self, client):
        """测试无效类型验证错误"""
        response = client.post(
            "/api/v1/chat",
            json={
                "query": 123,  # 应该是字符串
                "use_cache": True,
            }
        )

        assert response.status_code == 422

        data = response.json()
        assert data["success"] is False


class TestResponseFormat:
    """响应格式测试"""

    def test_response_has_required_fields(self, client):
        """测试响应包含必需字段"""
        response = client.post(
            "/api/v1/chat",
            json={"query": "测试"}
        )

        assert response.status_code == 200

        data = response.json()
        # 检查必需字段
        assert "success" in data
        assert "message" in data
        assert "data" in data
        assert "metadata" in data

    def test_response_metadata_structure(self, client):
        """测试响应元数据结构"""
        response = client.post(
            "/api/v1/chat",
            json={"query": "你好"}
        )

        assert response.status_code == 200

        metadata = response.json()["metadata"]
        # 检查元数据字段
        assert "intent_type" in metadata
        assert "intent_confidence" in metadata

    def test_response_has_process_time_header(self, client):
        """测试响应包含处理时间头"""
        response = client.post(
            "/api/v1/chat",
            json={"query": "测试"}
        )

        assert response.status_code == 200
        # 检查X-Process-Time头
        assert "X-Process-Time" in response.headers


class TestConcurrency:
    """并发测试"""

    def test_concurrent_requests(self, client):
        """测试并发请求处理"""
        import concurrent.futures

        def make_request(query_id):
            response = client.post(
                "/api/v1/chat",
                json={"query": f"测试查询{query_id}"}
            )
            return response.status_code == 200

        # 发起10个并发请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # 所有请求都应该成功
        assert all(results), "部分并发请求失败"


class TestErrorHandling:
    """错误处理测试"""

    def test_404_not_found(self, client):
        """测试404错误"""
        response = client.get("/nonexistent")
        assert response.status_code == 404

        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "HTTP_404"

    def test_405_method_not_allowed(self, client):
        """测试405错误（方法不允许）"""
        # /api/v1/health只接受GET
        response = client.post("/api/v1/health")
        assert response.status_code == 405

        data = response.json()
        assert data["success"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
