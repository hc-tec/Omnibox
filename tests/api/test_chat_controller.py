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
        assert "data_blocks" in data
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
        assert data["data"] is not None
        assert isinstance(data["data_blocks"], dict)

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
        assert "data_blocks" in data
        assert "metadata" in data

        panel = data["data"]
        assert panel is not None
        assert panel["mode"] in {"append", "replace", "insert"}
        assert "layout" in panel
        assert "blocks" in panel
        assert isinstance(panel["blocks"], list) and len(panel["blocks"]) >= 1
        assert isinstance(data["data_blocks"], dict)

        layout_nodes = panel["layout"]["nodes"]
        assert layout_nodes, "布局节点不能为空"
        first_props = layout_nodes[0].get("props", {})
        assert first_props.get("span") is not None, "布局节点应包含span信息"
        assert first_props.get("min_height") is not None, "布局节点应包含min_height信息"

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


# Phase 3: 快速刷新功能集成测试


class TestRefreshEndpoint:
    """快速刷新接口测试"""

    def test_refresh_with_valid_metadata(self, client):
        """测试使用有效 refresh_metadata 进行快速刷新"""
        # 先执行一次正常查询以获取 refresh_metadata
        chat_response = client.post(
            "/api/v1/chat",
            json={
                "query": "测试查询",
                "use_cache": True,
            }
        )
        assert chat_response.status_code == 200

        chat_data = chat_response.json()
        refresh_metadata = chat_data.get("metadata", {}).get("refresh_metadata")

        # 如果有 refresh_metadata，测试快速刷新
        if refresh_metadata and refresh_metadata.get("generated_path"):
            refresh_response = client.post(
                "/api/v1/refresh",
                json={
                    "refresh_metadata": refresh_metadata,
                }
            )

            assert refresh_response.status_code == 200

            data = refresh_response.json()
            assert data["success"] is True
            assert "刷新成功" in data["message"]
            assert "data" in data
            assert "metadata" in data

            # 验证元数据包含 is_refresh 标记
            metadata = data["metadata"]
            assert metadata is not None
            assert metadata.get("is_refresh") is True
            assert "refresh_metadata" in metadata

    def test_refresh_missing_metadata(self, client):
        """测试缺少 refresh_metadata 的验证错误"""
        response = client.post(
            "/api/v1/refresh",
            json={
                # 缺少 refresh_metadata
            }
        )

        assert response.status_code == 422  # Validation error

        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"

    def test_refresh_missing_generated_path(self, client):
        """测试 refresh_metadata 缺少 generated_path"""
        response = client.post(
            "/api/v1/refresh",
            json={
                "refresh_metadata": {
                    "route_id": "demo/hot",
                    # 缺少 generated_path
                }
            }
        )

        # 应该返回业务错误（200状态码，success=false）
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is False
        assert "缺少 generated_path" in data["message"]

    def test_refresh_with_layout_snapshot(self, client):
        """测试携带 layout_snapshot 的快速刷新"""
        # 构造一个最小的 refresh_metadata
        refresh_metadata = {
            "route_id": "demo/hot",
            "generated_path": "/demo/hot",
        }

        layout_snapshot = [
            {
                "block_id": "block-1",
                "component": "FeedList",
                "x": 0,
                "y": 0,
                "w": 12,
                "h": 4,
            }
        ]

        response = client.post(
            "/api/v1/refresh",
            json={
                "refresh_metadata": refresh_metadata,
                "layout_snapshot": layout_snapshot,
            }
        )

        # 根据 mock 模式，可能返回成功或失败
        assert response.status_code == 200

        data = response.json()
        # 至少应该有响应结构
        assert "success" in data
        assert "message" in data

    def test_refresh_response_format(self, client):
        """测试快速刷新响应格式"""
        refresh_metadata = {
            "route_id": "demo/test",
            "generated_path": "/demo/test",
        }

        response = client.post(
            "/api/v1/refresh",
            json={
                "refresh_metadata": refresh_metadata,
            }
        )

        assert response.status_code == 200

        data = response.json()
        # 检查必需字段
        assert "success" in data
        assert "message" in data
        assert "data" in data
        assert "data_blocks" in data
        assert "metadata" in data

    def test_refresh_concurrent_requests(self, client):
        """测试快速刷新并发请求"""
        import concurrent.futures

        refresh_metadata = {
            "route_id": "demo/concurrent",
            "generated_path": "/demo/concurrent",
        }

        def make_refresh_request(request_id):
            response = client.post(
                "/api/v1/refresh",
                json={"refresh_metadata": refresh_metadata}
            )
            return response.status_code == 200

        # 发起5个并发刷新请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_refresh_request, i) for i in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # 所有请求都应该成功
        assert all(results), "部分并发刷新请求失败"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
