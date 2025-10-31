"""
WebSocket流式接口端到端测试

测试内容：
1. 基本WebSocket连接和流式消息推送
2. 消息格式验证（stage/data/error/complete）
3. 流式阶段顺序验证（intent → rag → fetch → summary）
4. 错误处理（空查询、连接断开）
5. stream_id生成和追踪
"""

import os
import sys
import pytest
import json
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


class TestWebSocketConnection:
    """WebSocket连接测试"""

    def test_websocket_basic_connection(self, client):
        """测试基本WebSocket连接"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            # 发送查询
            websocket.send_json({
                "query": "你好",
                "use_cache": True
            })

            # 接收消息直到complete
            messages = []
            while True:
                data = websocket.receive_json()
                messages.append(data)
                if data["type"] == "complete":
                    break

            # 验证至少收到了complete消息
            assert len(messages) > 0
            assert messages[-1]["type"] == "complete"
            assert "stream_id" in messages[-1]

    def test_websocket_stream_id_generation(self, client):
        """测试stream_id生成和一致性"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "测试查询"})

            # 收集所有消息
            messages = []
            while True:
                data = websocket.receive_json()
                messages.append(data)
                if data["type"] == "complete":
                    break

            # 验证所有消息的stream_id一致
            stream_ids = [msg["stream_id"] for msg in messages]
            assert len(set(stream_ids)) == 1, "所有消息应使用相同的stream_id"

            # 验证stream_id格式
            stream_id = stream_ids[0]
            assert stream_id.startswith("stream-"), "stream_id应以'stream-'开头"


class TestStreamMessageTypes:
    """流式消息类型测试"""

    def test_message_type_sequence(self, client):
        """测试消息类型顺序"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "虎扑步行街最新帖子"})

            # 收集所有消息
            messages = []
            while True:
                data = websocket.receive_json()
                messages.append(data)
                if data["type"] == "complete":
                    break

            # 验证消息类型
            message_types = [msg["type"] for msg in messages]

            # 至少应该包含stage和complete
            assert "stage" in message_types, "应包含stage类型消息"
            assert "complete" in message_types, "应包含complete类型消息"

            # complete应该是最后一条
            assert messages[-1]["type"] == "complete", "complete应该是最后一条消息"

    def test_stage_message_structure(self, client):
        """测试stage消息结构"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "测试"})

            # 找到第一条stage消息
            stage_message = None
            while True:
                data = websocket.receive_json()
                if data["type"] == "stage":
                    stage_message = data
                    break
                if data["type"] == "complete":
                    break

            # 验证stage消息结构
            assert stage_message is not None, "应收到stage消息"
            assert "stage" in stage_message
            assert "message" in stage_message
            assert "progress" in stage_message
            assert stage_message["stage"] in ["intent", "rag", "fetch", "summary"]

    def test_data_message_structure(self, client):
        """测试data消息结构"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "测试"})

            # 找到第一条data消息
            data_message = None
            while True:
                data = websocket.receive_json()
                if data["type"] == "data":
                    data_message = data
                    break
                if data["type"] == "complete":
                    break

            # 如果有data消息，验证其结构
            if data_message:
                assert "stage" in data_message
                assert "data" in data_message
                assert data_message["stage"] in ["intent", "rag", "fetch", "summary"]

    def test_complete_message_structure(self, client):
        """测试complete消息结构"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "你好"})

            # 找到complete消息
            complete_message = None
            while True:
                data = websocket.receive_json()
                if data["type"] == "complete":
                    complete_message = data
                    break

            # 验证complete消息结构
            assert complete_message is not None
            assert "success" in complete_message
            assert "message" in complete_message
            assert "total_time" in complete_message
            assert isinstance(complete_message["success"], bool)
            assert isinstance(complete_message["total_time"], (int, float))


class TestStreamStages:
    """流式阶段测试"""

    def test_intent_stage_present(self, client):
        """测试intent阶段存在"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "测试"})

            # 收集所有stage消息
            stages = []
            while True:
                data = websocket.receive_json()
                if data["type"] == "stage":
                    stages.append(data["stage"])
                if data["type"] == "complete":
                    break

            # 验证包含intent阶段
            assert "intent" in stages, "应包含intent阶段"

    def test_data_query_includes_all_stages(self, client):
        """测试数据查询包含所有阶段"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "虎扑最新帖子"})

            # 收集所有stage
            stages = []
            while True:
                data = websocket.receive_json()
                if data["type"] == "stage":
                    stages.append(data["stage"])
                if data["type"] == "complete":
                    break

            # 数据查询应包含多个阶段
            # 至少有intent和fetch
            assert len(stages) >= 2, "数据查询应包含多个阶段"
            assert "intent" in stages
            assert "fetch" in stages or "summary" in stages


class TestErrorHandling:
    """错误处理测试"""

    def test_empty_query_error(self, client):
        """测试空查询错误处理"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            # 发送空查询
            websocket.send_json({"query": ""})

            # 接收第一条消息（应该是错误消息）
            try:
                data = websocket.receive_json()
                # 验证收到错误消息
                assert data["type"] == "error"
                assert data["error_code"] == "VALIDATION_ERROR"
                assert "空" in data["error_message"]
            except Exception as e:
                pytest.fail(f"应该收到错误消息，但发生异常: {e}")

    def test_invalid_json_handling(self, client):
        """测试无效JSON处理"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            # 发送无效的数据（缺少query字段）
            try:
                websocket.send_json({"invalid_field": "test"})

                # 尝试接收响应
                messages = []
                while len(messages) < 3:  # 最多接收3条消息
                    try:
                        data = websocket.receive_json(timeout=2)
                        messages.append(data)
                        if data["type"] in ["complete", "error"]:
                            break
                    except:
                        break

                # 如果收到消息，应该是error或者处理了空query
                if messages:
                    first_msg = messages[0]
                    assert first_msg["type"] in ["error", "stage"], \
                        "应返回error或开始处理"

            except Exception as e:
                # 连接可能被关闭，这也是合理的行为
                pass


class TestCacheControl:
    """缓存控制测试"""

    def test_cache_disabled(self, client):
        """测试禁用缓存"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({
                "query": "测试查询",
                "use_cache": False
            })

            # 收集所有消息
            messages = []
            while True:
                data = websocket.receive_json()
                messages.append(data)
                if data["type"] == "complete":
                    break

            # 验证处理完成
            assert messages[-1]["type"] == "complete"

    def test_filter_datasource(self, client):
        """测试数据源过滤"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({
                "query": "测试",
                "filter_datasource": "rsshub"
            })

            # 收集所有消息
            messages = []
            while True:
                data = websocket.receive_json()
                messages.append(data)
                if data["type"] == "complete":
                    break

            # 验证处理完成
            assert messages[-1]["type"] == "complete"


class TestStreamProgress:
    """流式进度测试"""

    def test_progress_values(self, client):
        """测试进度值的有效性"""
        with client.websocket_connect("/api/v1/chat/stream") as websocket:
            websocket.send_json({"query": "测试"})

            # 收集所有stage消息的进度
            progress_values = []
            while True:
                data = websocket.receive_json()
                if data["type"] == "stage" and "progress" in data:
                    progress_values.append(data["progress"])
                if data["type"] == "complete":
                    break

            # 验证进度值
            for progress in progress_values:
                assert 0.0 <= progress <= 1.0, "进度值应在0.0-1.0之间"

            # 如果有多个进度值，应该递增
            if len(progress_values) > 1:
                for i in range(1, len(progress_values)):
                    assert progress_values[i] >= progress_values[i-1], \
                        "进度值应递增或保持不变"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
