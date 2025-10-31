"""
WebSocket 流式接口端到端测试。

测试内容：
1. 基本 WebSocket 连接与流式消息推送
2. 消息类型与顺序验证（stage/data/error/complete）
3. 结果载荷结构校验（智能面板 + 数据块）
4. 错误处理（空查询、非法请求）
5. stream_id 生成与追踪
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
    创建测试客户端（模块级别，共享连接）。
    """
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


class TestWebSocketConnection:
    """WebSocket 连接测试。"""

    def test_websocket_basic_connection(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "你好", "use_cache": True})

            messages = []
            while True:
                data = websocket.receive_json()
                messages.append(data)
                if data["type"] == "complete":
                    break

            assert messages[-1]["type"] == "complete"
            assert "stream_id" in messages[-1]

    def test_websocket_stream_id_generation(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "测试查询"})

            messages = []
            while True:
                data = websocket.receive_json()
                messages.append(data)
                if data["type"] == "complete":
                    break

            stream_ids = {msg["stream_id"] for msg in messages}
            assert len(stream_ids) == 1
            assert next(iter(stream_ids)).startswith("stream-")


class TestStreamMessageTypes:
    """流式消息类型测试。"""

    def test_message_type_sequence(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "虎扑步行街最新帖子"})

            messages = []
            while True:
                data = websocket.receive_json()
                messages.append(data)
                if data["type"] == "complete":
                    break

            types = [msg["type"] for msg in messages]
            assert "stage" in types
            assert "complete" in types
            assert messages[-1]["type"] == "complete"

    def test_stage_message_structure(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "测试"})

            while True:
                data = websocket.receive_json()
                if data["type"] == "stage":
                    assert "stage" in data
                    assert data["stage"] in {"intent", "rag", "fetch", "summary"}
                    assert "message" in data
                    break
                if data["type"] == "complete":
                    pytest.fail("未收到 stage 消息")

    def test_data_message_structure(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "测试"})

            while True:
                data = websocket.receive_json()
                if data["type"] == "data" and data["stage"] == "summary":
                    payload = data["data"]
                    assert "data" in payload
                    assert "data_blocks" in payload
                    assert isinstance(payload["data"], (dict, type(None)))
                    assert isinstance(payload["data_blocks"], dict)
                    if payload["data"]:
                        nodes = payload["data"]["layout"]["nodes"]
                        assert nodes, "布局节点不能为空"
                        first_props = nodes[0].get("props", {})
                        assert first_props.get("span") is not None
                        assert first_props.get("min_height") is not None
                    break
                if data["type"] == "complete":
                    pytest.fail("未收到 summary 数据消息")

    def test_complete_message_structure(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "你好"})

            while True:
                data = websocket.receive_json()
                if data["type"] == "complete":
                    assert isinstance(data["success"], bool)
                    assert "message" in data
                    assert "total_time" in data
                    break


class TestStreamStages:
    """阶段覆盖测试。"""

    def test_intent_stage_present(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "测试"})

            stages = []
            while True:
                data = websocket.receive_json()
                if data["type"] == "stage":
                    stages.append(data["stage"])
                if data["type"] == "complete":
                    break

            assert "intent" in stages

    def test_data_query_includes_fetch(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "虎扑最新帖子"})

            stages = []
            while True:
                data = websocket.receive_json()
                if data["type"] == "stage":
                    stages.append(data["stage"])
                if data["type"] == "complete":
                    break

            assert "intent" in stages
            assert any(stage in {"fetch", "summary"} for stage in stages)


class TestErrorHandling:
    """错误处理测试。"""

    def test_empty_query_error(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": ""})

            data = websocket.receive_json()
            assert data["type"] == "error"
            assert data["error_code"] == "VALIDATION_ERROR"

    def test_invalid_payload(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"invalid": "payload"})

            data = websocket.receive_json()
            assert data["type"] in {"error", "stage"}


class TestCacheControl:
    """缓存控制测试。"""

    def test_cache_disabled(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "测试查询", "use_cache": False})

            messages = []
            while True:
                data = websocket.receive_json()
                messages.append(data)
                if data["type"] == "complete":
                    break

            assert messages[-1]["type"] == "complete"

    def test_filter_datasource(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "测试", "filter_datasource": "rsshub"})

            messages = []
            while True:
                data = websocket.receive_json()
                messages.append(data)
                if data["type"] == "complete":
                    break

            assert messages[-1]["type"] == "complete"


class TestStreamProgress:
    """进度值测试。"""

    def test_progress_values(self, client):
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "测试"})

            progress_values = []
            while True:
                data = websocket.receive_json()
                if data["type"] == "stage" and "progress" in data:
                    progress_values.append(data["progress"])
                if data["type"] == "complete":
                    break

            for value in progress_values:
                assert 0.0 <= value <= 1.0

            for left, right in zip(progress_values, progress_values[1:]):
                assert right >= left


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
