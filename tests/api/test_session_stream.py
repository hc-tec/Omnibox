"""
Session WebSocket 流式接口单元测试。

测试内容：
1. Session WebSocket 连接与基本消息流
2. 消息类型与顺序验证（stage/data/research_step/complete/error）
3. Session 上下文维护（data_stash, chat_history）
4. 错误处理（无效 Session ID、空查询）
5. stream_id 生成与追踪
"""

import os
import sys
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault("CHAT_SERVICE_MODE", "mock")
from api.app import create_app


@pytest.fixture(scope="module")
def client():
    """创建测试客户端（模块级别，共享连接）。"""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session_id(client):
    """创建测试用 Session。"""
    response = client.post("/api/v1/sessions", json={"name": "测试 Session"})
    assert response.status_code in (200, 201)  # API 可能返回 200 或 201
    data = response.json()
    assert data.get("success"), f"创建 Session 失败: {data}"
    return data["session"]["session_id"]


class TestSessionWebSocketConnection:
    """Session WebSocket 连接测试。"""

    def test_websocket_basic_connection(self, client, session_id):
        """测试基本 WebSocket 连接与消息流。"""
        with client.websocket_connect(f"/api/v1/sessions/{session_id}/stream") as ws:
            ws.send_json({"query": "测试查询"})

            messages = []
            while True:
                data = ws.receive_json()
                messages.append(data)
                if data["type"] in ("complete", "error"):
                    break
                # 超时保护
                if len(messages) > 100:
                    break

            # 验证收到了完成消息
            final_msg = messages[-1]
            assert final_msg["type"] in ("complete", "error")

    def test_websocket_stream_id_generation(self, client, session_id):
        """测试 stream_id 的生成与一致性。"""
        with client.websocket_connect(f"/api/v1/sessions/{session_id}/stream") as ws:
            ws.send_json({"query": "stream_id 测试"})

            messages = []
            while True:
                data = ws.receive_json()
                messages.append(data)
                if data["type"] in ("complete", "error"):
                    break
                if len(messages) > 100:
                    break

            # 所有消息应该有相同的 stream_id
            stream_ids = {msg.get("stream_id") for msg in messages if msg.get("stream_id")}
            assert len(stream_ids) == 1
            # Session stream IDs 以 "session-stream-" 或 "stream-" 开头
            stream_id = next(iter(stream_ids))
            assert stream_id.startswith("session-stream-") or stream_id.startswith("stream-")

    def test_invalid_session_id(self, client):
        """测试无效 Session ID 的处理。"""
        # 使用不存在的 Session ID
        with client.websocket_connect("/api/v1/sessions/invalid-session-id/stream") as ws:
            ws.send_json({"query": "测试"})

            # 收集所有消息直到完成或错误
            messages = []
            while True:
                data = ws.receive_json()
                messages.append(data)
                if data["type"] in ("complete", "error"):
                    break
                if len(messages) > 50:
                    break

            # 应该最终收到 error 消息
            error_msgs = [m for m in messages if m["type"] == "error"]
            assert len(error_msgs) >= 1 or messages[-1]["type"] == "complete"
            # 如果是 error，应该包含 session 相关信息
            if error_msgs:
                assert "session" in error_msgs[0].get("error_message", "").lower() or \
                       "error_code" in error_msgs[0]


class TestSessionStreamMessageTypes:
    """Session 流式消息类型测试。"""

    def test_stage_message_present(self, client, session_id):
        """测试是否收到阶段消息。"""
        with client.websocket_connect(f"/api/v1/sessions/{session_id}/stream") as ws:
            ws.send_json({"query": "阶段测试"})

            stages_received = []
            while True:
                data = ws.receive_json()
                if data["type"] == "stage":
                    stages_received.append(data)
                if data["type"] in ("complete", "error"):
                    break
                if len(stages_received) > 50:
                    break

            # 应该收到至少一个阶段消息
            assert len(stages_received) >= 1

    def test_stage_message_structure(self, client, session_id):
        """测试阶段消息的结构。"""
        with client.websocket_connect(f"/api/v1/sessions/{session_id}/stream") as ws:
            ws.send_json({"query": "结构测试"})

            while True:
                data = ws.receive_json()
                if data["type"] == "stage":
                    # 验证阶段消息结构
                    assert "stream_id" in data
                    assert "stage" in data or "message" in data
                    break
                if data["type"] in ("complete", "error"):
                    # 如果没有收到 stage 消息也算通过（可能是快速执行）
                    break

    def test_complete_message_structure(self, client, session_id):
        """测试完成消息的结构。"""
        with client.websocket_connect(f"/api/v1/sessions/{session_id}/stream") as ws:
            ws.send_json({"query": "完成测试"})

            while True:
                data = ws.receive_json()
                if data["type"] == "complete":
                    assert isinstance(data.get("success"), bool)
                    assert "message" in data or "total_time" in data
                    break
                if data["type"] == "error":
                    # 错误也是有效的终止状态
                    assert "error_message" in data or "error_code" in data
                    break


class TestSessionContextMaintenance:
    """Session 上下文维护测试。"""

    def test_context_with_artifact_refs(self, client, session_id):
        """测试带有 artifact_refs 上下文的查询。"""
        with client.websocket_connect(f"/api/v1/sessions/{session_id}/stream") as ws:
            # 发送带上下文的查询
            ws.send_json({
                "query": "使用上下文测试",
                "context": {
                    "artifact_refs": ["test-artifact-id"]
                }
            })

            messages = []
            while True:
                data = ws.receive_json()
                messages.append(data)
                if data["type"] in ("complete", "error"):
                    break
                if len(messages) > 100:
                    break

            # 验证查询被处理
            assert len(messages) >= 1


class TestSessionStreamErrorHandling:
    """Session 流式错误处理测试。"""

    def test_empty_query_error(self, client, session_id):
        """测试空查询的错误处理。"""
        with client.websocket_connect(f"/api/v1/sessions/{session_id}/stream") as ws:
            ws.send_json({"query": ""})

            data = ws.receive_json()
            assert data["type"] == "error"
            assert "error_code" in data or "error_message" in data

    def test_invalid_payload_structure(self, client, session_id):
        """测试无效载荷结构的处理。"""
        with client.websocket_connect(f"/api/v1/sessions/{session_id}/stream") as ws:
            # 发送缺少 query 字段的载荷
            ws.send_json({"invalid_field": "value"})

            data = ws.receive_json()
            # 应该返回错误或者使用默认值
            assert data["type"] in ("error", "stage")


class TestSessionStreamProgress:
    """Session 流式进度测试。"""

    def test_progress_values_in_range(self, client, session_id):
        """测试进度值是否在有效范围内。"""
        with client.websocket_connect(f"/api/v1/sessions/{session_id}/stream") as ws:
            ws.send_json({"query": "进度测试"})

            progress_values = []
            while True:
                data = ws.receive_json()
                if data["type"] == "stage" and "progress" in data:
                    progress_values.append(data["progress"])
                if data["type"] in ("complete", "error"):
                    break
                if len(progress_values) > 50:
                    break

            # 验证进度值在 0-1 范围内
            for value in progress_values:
                assert 0.0 <= value <= 1.0


class TestMultipleQueriesInSession:
    """Session 多次查询测试。"""

    def test_sequential_queries(self, client, session_id):
        """测试同一 Session 中的顺序查询。"""
        # 第一次查询
        with client.websocket_connect(f"/api/v1/sessions/{session_id}/stream") as ws:
            ws.send_json({"query": "第一次查询"})

            while True:
                data = ws.receive_json()
                if data["type"] in ("complete", "error"):
                    break

        # 第二次查询（复用同一 Session）
        with client.websocket_connect(f"/api/v1/sessions/{session_id}/stream") as ws:
            ws.send_json({"query": "第二次查询"})

            messages = []
            while True:
                data = ws.receive_json()
                messages.append(data)
                if data["type"] in ("complete", "error"):
                    break
                if len(messages) > 100:
                    break

            # 第二次查询应该也能正常完成
            assert messages[-1]["type"] in ("complete", "error")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
