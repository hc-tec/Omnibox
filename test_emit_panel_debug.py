"""
测试脚本：触发持续调用 emit_panel_preview 的问题场景

场景：
1. 查询"B站热搜前三条"
2. 再请求"用表格展示数据"
3. 观察是否会重复调用 emit_panel_preview

目标：
- 抓取每次 LLM 调用的完整提示词
- 查看提示词中是否包含 data_stash 历史
- 对比 data_stash 实际状态和提示词中的内容
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("test_emit_panel_debug.log", encoding="utf-8", mode="w"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.session.runtime_manager import SessionRuntimeManager
from services.session.store import get_session_store
from langgraph_agents.sync_executor import SyncLangGraphExecutor


def save_llm_calls(calls, filename="llm_calls.json"):
    """保存 LLM 调用记录到文件"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(calls, f, ensure_ascii=False, indent=2)
    logger.info(f"LLM 调用记录已保存到 {filename}")


async def test_emit_panel_scenario():
    """测试场景"""
    logger.info("=" * 80)
    logger.info("开始测试场景：持续调用 emit_panel_preview 问题")
    logger.info("=" * 80)

    # 初始化 SessionRuntimeManager
    session_store = get_session_store()
    manager = SessionRuntimeManager(session_store)

    # 创建一个测试 session
    session = manager.create_session("测试用户", "测试持续调用 emit_panel_preview")
    session_id = session.session_id
    logger.info(f"创建测试 session: {session_id}")

    # 收集所有 LLM 调用
    all_llm_calls = []

    def collect_llm_call(event):
        """收集 LLM 调用事件"""
        call_data = event.to_dict()
        all_llm_calls.append(call_data)
        logger.info("=" * 80)
        logger.info(f"LLM 调用 #{len(all_llm_calls)}: {call_data['role']} (step {call_data['step_id']})")
        logger.info(f"Status: {call_data['status']}")
        logger.info(f"Model: {call_data['model']}")
        logger.info(f"Duration: {call_data['duration_ms']}ms")
        if call_data.get("prompt_tokens"):
            logger.info(
                f"Tokens: {call_data['prompt_tokens']} + {call_data['completion_tokens']} = {call_data['total_tokens']}"
            )
        logger.info("-" * 80)
        if call_data.get("full_prompt"):
            logger.info("FULL PROMPT:")
            logger.info(call_data["full_prompt"])
        logger.info("-" * 80)
        if call_data.get("full_response"):
            logger.info("FULL RESPONSE:")
            logger.info(call_data["full_response"])
        logger.info("=" * 80)

    # 第一轮查询：获取B站热搜
    logger.info("\n" + "=" * 80)
    logger.info("第一轮查询：B站热搜前三条")
    logger.info("=" * 80)

    try:
        result1 = manager.execute_in_session(
            session_id=session_id,
            query="B站热搜前三条",
        )
        logger.info(f"第一轮查询完成，状态: {result1.status}")
        logger.info(f"Data stash: {len(result1.data_stash)} 条记录")
        for i, ref in enumerate(result1.data_stash):
            logger.info(f"  [{i}] Step {ref.step_id}: {ref.tool_name} ({ref.status}) - {ref.summary[:100]}...")

    except Exception as e:
        logger.error(f"第一轮查询失败: {e}", exc_info=True)
        save_llm_calls(all_llm_calls, "llm_calls_error_round1.json")
        return

    # 第二轮查询：用表格展示
    logger.info("\n" + "=" * 80)
    logger.info("第二轮查询：用表格展示数据")
    logger.info("=" * 80)

    try:
        result2 = manager.execute_in_session(
            session_id=session_id,
            query="用表格展示数据",
        )
        logger.info(f"第二轮查询完成，状态: {result2.status}")
        logger.info(f"Data stash: {len(result2.data_stash)} 条记录")
        for i, ref in enumerate(result2.data_stash):
            logger.info(f"  [{i}] Step {ref.step_id}: {ref.tool_name} ({ref.status}) - {ref.summary[:100]}...")

    except Exception as e:
        logger.error(f"第二轮查询失败: {e}", exc_info=True)
        save_llm_calls(all_llm_calls, "llm_calls_error_round2.json")
        return

    # 保存所有 LLM 调用记录
    save_llm_calls(all_llm_calls, "llm_calls_full.json")

    # 统计分析
    logger.info("\n" + "=" * 80)
    logger.info("统计分析")
    logger.info("=" * 80)
    logger.info(f"总共 LLM 调用次数: {len(all_llm_calls)}")

    # 按 role 统计
    role_count = {}
    for call in all_llm_calls:
        role = call["role"]
        role_count[role] = role_count.get(role, 0) + 1

    logger.info("按角色统计:")
    for role, count in role_count.items():
        logger.info(f"  {role}: {count} 次")

    # 检查 data_stash 在提示词中的出现
    logger.info("\n检查 data_stash 在提示词中的出现情况:")
    for i, call in enumerate(all_llm_calls):
        if call.get("full_prompt"):
            prompt = call["full_prompt"]
            if "已获取的数据（data_stash）" in prompt or "data_stash" in prompt:
                # 提取 data_stash 部分
                if "已获取的数据（data_stash）" in prompt:
                    start = prompt.find("已获取的数据（data_stash）")
                    end = prompt.find("\n## ", start + 1)
                    if end == -1:
                        end = len(prompt)
                    data_stash_section = prompt[start:end]
                    logger.info(f"LLM 调用 #{i+1} ({call['role']}, step {call['step_id']}) 包含 data_stash:")
                    logger.info(data_stash_section)
                    logger.info("-" * 40)
            else:
                logger.info(f"LLM 调用 #{i+1} ({call['role']}, step {call['step_id']}) 不包含 data_stash")

    logger.info("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(test_emit_panel_scenario())
