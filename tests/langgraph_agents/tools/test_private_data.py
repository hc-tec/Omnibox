"""fetch_private_data 工具单元测试。"""

import pytest
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.tools.private_data import register_private_data_tool
from langgraph_agents.state import ToolCall
from langgraph_agents.runtime import ToolExecutionContext
from unittest.mock import MagicMock


@pytest.fixture
def registry():
    """创建测试用工具注册表。"""
    reg = ToolRegistry()
    register_private_data_tool(reg)
    return reg


def test_fetch_private_data_returns_e201(registry):
    """测试返回 E201 未授权错误（当前实现）。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={}
    )

    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "platform": "bilibili",
            "data_type": "favorites",
            "limit": 20
        },
        step_id=1,
        description="获取 B站收藏夹"
    )

    result = registry.execute(call, context)

    assert result.status == "error"
    assert result.error_message and "E201" in result.error_message
    assert "auth_required" in result.raw_output
    assert result.raw_output["auth_required"] is True
    assert result.raw_output["platform"] == "bilibili"
    assert result.raw_output["data_type"] == "favorites"


def test_fetch_private_data_github_starred(registry):
    """测试 GitHub Starred 请求。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={}
    )

    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "platform": "github",
            "data_type": "starred"
        },
        step_id=1,
        description="获取 GitHub Starred"
    )

    result = registry.execute(call, context)

    assert result.status == "error"
    assert result.error_message and "E201" in result.error_message
    assert "GitHub Starred 仓库" in result.raw_output["data_source_name"]
    assert "user:read" in result.raw_output["scopes_needed"]


def test_fetch_private_data_missing_platform(registry):
    """测试缺少 platform 参数。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={}
    )

    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "data_type": "favorites"
        },
        step_id=1,
        description="缺少参数测试"
    )

    result = registry.execute(call, context)

    assert result.status == "error"
    assert result.raw_output["error_code"] == "E101"


def test_fetch_private_data_unsupported_combination(registry):
    """测试不支持的平台+数据类型组合。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={}
    )

    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "platform": "bilibili",
            "data_type": "starred"  # B站不支持 starred
        },
        step_id=1,
        description="不支持的组合测试"
    )

    result = registry.execute(call, context)

    assert result.status == "error"
    assert result.raw_output["error_code"] == "E102"


def test_fetch_private_data_auth_url_format(registry):
    """测试授权 URL 格式。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={}
    )

    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "platform": "xiaohongshu",
            "data_type": "likes"
        },
        step_id=1,
        description="授权 URL 测试"
    )

    result = registry.execute(call, context)

    assert "auth_url" in result.raw_output
    assert "xiaohongshu" in result.raw_output["auth_url"]
    assert result.raw_output["auth_url"].startswith("https://")


def test_fetch_private_data_user_friendly_message(registry):
    """测试用户友好消息。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={}
    )

    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "platform": "yuque",
            "data_type": "watching"
        },
        step_id=1,
        description="用户消息测试"
    )

    result = registry.execute(call, context)

    assert "user_friendly_message" in result.raw_output
    message = result.raw_output["user_friendly_message"]
    assert "语雀关注的知识库" in message
    assert ("OAuth 授权" in message or "Phase 3" in message)  # 新版本消息


def test_tool_registration(registry):
    """测试工具注册。"""
    spec = registry.get("fetch_private_data")
    assert spec is not None
    assert spec.plugin_id == "fetch_private_data"
    assert spec.execution_mode == "full"
    assert spec.description == "获取用户的私有数据（收藏、历史、关注等）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
