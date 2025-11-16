"""fetch_private_data 工具边界情况测试。"""

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


def test_fetch_private_data_with_authorization(registry):
    """测试已授权场景下返回模拟数据。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={
            "platform_tokens": {
                "bilibili": "mock_token_bilibili",
                "github": "mock_token_github"
            },
            "user_id": "test_user_123"
        }
    )

    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "platform": "bilibili",
            "data_type": "favorites",
            "limit": 10
        },
        step_id=1,
        description="已授权获取 B站收藏夹"
    )

    result = registry.execute(call, context)

    # 应该返回成功状态和模拟数据
    assert result.status == "success"
    assert result.raw_output["type"] == "private_data"
    assert result.raw_output["platform"] == "bilibili"
    assert result.raw_output["data_type"] == "favorites"
    assert result.raw_output["is_mock"] is True
    assert "items" in result.raw_output
    assert len(result.raw_output["items"]) == 10
    assert result.raw_output["total_count"] == 10

    # 验证模拟数据结构
    first_item = result.raw_output["items"][0]
    assert "id" in first_item
    assert "title" in first_item
    assert "author" in first_item
    assert "bvid" in first_item
    assert "view_count" in first_item


def test_fetch_private_data_github_starred_with_auth(registry):
    """测试已授权获取 GitHub Starred。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={
            "platform_tokens": {"github": "ghp_mock_token"},
            "user_id": "github_user"
        }
    )

    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "platform": "github",
            "data_type": "starred",
            "limit": 15
        },
        step_id=1,
        description="已授权获取 GitHub Starred"
    )

    result = registry.execute(call, context)

    assert result.status == "success"
    assert result.raw_output["platform"] == "github"
    assert result.raw_output["data_type"] == "starred"
    assert len(result.raw_output["items"]) == 15

    # 验证 GitHub 特定字段
    first_repo = result.raw_output["items"][0]
    assert "name" in first_repo
    assert "full_name" in first_repo
    assert "description" in first_repo
    assert "stars" in first_repo
    assert "language" in first_repo


def test_fetch_private_data_without_authorization(registry):
    """测试未授权场景下返回 E201。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={}  # 没有 platform_tokens
    )

    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "platform": "bilibili",
            "data_type": "favorites"
        },
        step_id=1,
        description="未授权访问"
    )

    result = registry.execute(call, context)

    assert result.status == "error"
    assert result.raw_output["error_code"] == "E201"
    assert result.raw_output["auth_required"] is True
    assert "auth_url" in result.raw_output
    assert "scopes_needed" in result.raw_output


def test_fetch_private_data_partial_authorization(registry):
    """测试部分授权场景（有其他平台的 token，但没有目标平台的）。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={
            "platform_tokens": {
                "github": "ghp_token"  # 只有 GitHub token
            }
        }
    )

    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "platform": "bilibili",  # 请求 B站数据
            "data_type": "favorites"
        },
        step_id=1,
        description="部分授权测试"
    )

    result = registry.execute(call, context)

    # 应该返回 E201，因为没有 bilibili token
    assert result.status == "error"
    assert result.raw_output["error_code"] == "E201"


def test_fetch_private_data_empty_token(registry):
    """测试 token 为空字符串的情况。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={
            "platform_tokens": {
                "bilibili": ""  # 空 token
            }
        }
    )

    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "platform": "bilibili",
            "data_type": "favorites"
        },
        step_id=1,
        description="空 token 测试"
    )

    result = registry.execute(call, context)

    # 空 token 应被视为未授权
    assert result.status == "error"
    assert result.raw_output["error_code"] == "E201"


def test_fetch_private_data_limit_capping(registry):
    """测试 limit 参数的上限限制。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={
            "platform_tokens": {"bilibili": "token"},
            "user_id": "user123"
        }
    )

    # 请求超过上限的数据（上限为 20）
    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "platform": "bilibili",
            "data_type": "favorites",
            "limit": 100  # 超过上限
        },
        step_id=1,
        description="limit 上限测试"
    )

    result = registry.execute(call, context)

    assert result.status == "success"
    # 应该被限制在 20 以内
    assert len(result.raw_output["items"]) <= 20


def test_fetch_private_data_unsupported_platform_generic_template(registry):
    """测试未定义模板的平台使用通用模板。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={
            "platform_tokens": {"yuque": "token"},
            "user_id": "user123"
        }
    )

    call = ToolCall(
        plugin_id="fetch_private_data",
        args={
            "platform": "yuque",
            "data_type": "watching"
        },
        step_id=1,
        description="通用模板测试"
    )

    result = registry.execute(call, context)

    assert result.status == "success"
    assert len(result.raw_output["items"]) > 0

    # 通用模板应包含基础字段
    first_item = result.raw_output["items"][0]
    assert "id" in first_item
    assert "title" in first_item
    assert "created_at" in first_item


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
