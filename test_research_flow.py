"""
测试研究模式完整流程

用法：
    python test_research_flow.py
"""
import asyncio
import json
import logging
import sys
import websockets
from urllib.parse import urlencode

import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
API_BASE = "http://localhost:8005/api/v1"
WS_BASE = "ws://localhost:8005/api/v1"
TEST_QUERY = "我想看看bilibili中，up主行业101的视频投稿，同时呢，帮我分析一下这个up主最近做的视频方向是什么"


def test_rest_api():
    """测试 REST API 是否返回 requires_streaming"""
    logger.info("=" * 80)
    logger.info("步骤1：测试 REST API /api/v1/chat")
    logger.info("=" * 80)

    url = f"{API_BASE}/chat"
    payload = {
        "query": TEST_QUERY,
        "mode": "auto"
    }

    logger.info(f"发送请求到: {url}")
    logger.info(f"请求参数: {json.dumps(payload, ensure_ascii=False)}")

    try:
        response = requests.post(url, json=payload, timeout=30)
        logger.info(f"响应状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            logger.info(f"响应数据: {json.dumps(data, ensure_ascii=False, indent=2)}")

            # 检查关键字段
            requires_streaming = data.get("metadata", {}).get("requires_streaming")
            intent_type = data.get("intent_type")

            logger.info("")
            logger.info("=" * 80)
            logger.info("验证结果:")
            logger.info("=" * 80)
            logger.info(f"intent_type: {intent_type}")
            logger.info(f"metadata.requires_streaming: {requires_streaming}")

            if requires_streaming:
                logger.info("✅ REST API 正确返回 requires_streaming: True")
                return True, data
            else:
                logger.error("❌ REST API 未返回 requires_streaming: True")
                return False, data
        else:
            logger.error(f"❌ REST API 返回错误状态码: {response.status_code}")
            logger.error(f"响应内容: {response.text}")
            return False, None

    except Exception as e:
        logger.error(f"❌ REST API 请求失败: {e}", exc_info=True)
        return False, None


async def test_websocket():
    """测试 WebSocket 连接和消息接收"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("步骤2：测试 WebSocket /api/v1/chat/stream")
    logger.info("=" * 80)

    ws_url = f"{WS_BASE}/chat/stream"
    logger.info(f"连接到: {ws_url}")

    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info("✅ WebSocket 连接成功")

            # 发送研究查询
            message = {
                "query": TEST_QUERY,
                "mode": "research",
                "task_id": "test-task-001",
                "use_cache": True
            }

            logger.info(f"发送消息: {json.dumps(message, ensure_ascii=False)}")
            await websocket.send(json.dumps(message))
            logger.info("消息已发送，等待响应...")

            # 接收消息（设置超时）
            message_count = 0
            try:
                while True:
                    msg_str = await asyncio.wait_for(websocket.recv(), timeout=60)
                    message_count += 1
                    msg = json.loads(msg_str)
                    msg_type = msg.get("type", "unknown")

                    logger.info(f"收到消息 #{message_count}: type={msg_type}")
                    logger.debug(f"完整消息: {json.dumps(msg, ensure_ascii=False, indent=2)}")

                    # 如果是完成消息，退出
                    if msg_type in ("research_complete", "complete"):
                        logger.info("✅ 收到完成消息")
                        break
                    elif msg_type in ("research_error", "error"):
                        logger.error(f"❌ 收到错误消息: {msg.get('error_message')}")
                        break

            except asyncio.TimeoutError:
                logger.warning(f"⚠️  接收超时，已收到 {message_count} 条消息")

            logger.info("")
            logger.info("=" * 80)
            logger.info("验证结果:")
            logger.info("=" * 80)
            if message_count > 0:
                logger.info(f"✅ WebSocket 正常工作，共收到 {message_count} 条消息")
                return True
            else:
                logger.error("❌ WebSocket 没有收到任何消息")
                return False

    except Exception as e:
        logger.error(f"❌ WebSocket 测试失败: {e}", exc_info=True)
        return False


async def main():
    """主测试流程"""
    logger.info("开始测试研究模式完整流程")
    logger.info("")

    # 步骤1：测试 REST API
    rest_ok, rest_data = test_rest_api()

    if not rest_ok:
        logger.error("")
        logger.error("=" * 80)
        logger.error("测试失败：REST API 未正确返回 requires_streaming")
        logger.error("=" * 80)
        logger.error("可能的原因：")
        logger.error("1. 后端没有识别为 complex_research 意图")
        logger.error("2. _create_streaming_required_response 方法未被调用")
        logger.error("3. 返回的 JSON 缺少 metadata.requires_streaming 字段")
        return 1

    # 步骤2：测试 WebSocket
    ws_ok = await test_websocket()

    if not ws_ok:
        logger.error("")
        logger.error("=" * 80)
        logger.error("测试失败：WebSocket 连接或消息接收失败")
        logger.error("=" * 80)
        logger.error("可能的原因：")
        logger.error("1. WebSocket 连接失败（检查端口和防火墙）")
        logger.error("2. 后端没有发送消息（检查 _handle_complex_research_streaming）")
        logger.error("3. 消息格式不正确（检查 StreamMessage 定义）")
        return 1

    # 全部通过
    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ 所有测试通过！研究模式流程正常工作")
    logger.info("=" * 80)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
