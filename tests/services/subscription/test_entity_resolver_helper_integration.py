"""
entity_resolver_helper 集成测试（使用真实 schema 结构）

⚠️ P1 修复验证：测试列表形式的 parameters 和缺失元数据的回退逻辑
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch
from services.subscription.entity_resolver_helper import (
    should_resolve_param,
    resolve_entity_from_schema,
    validate_and_resolve_params
)


@pytest.fixture
def real_bilibili_schema():
    """真实的 bilibili_video schema（来自 datasource_definitions_enriched.json）"""
    return {
        "route_id": "bilibili_video",
        "path_template": ["/user/video/:uid/:embed?"],
        "name": "UP 主投稿",
        "platform": "bilibili",  # ✅ 有 platform
        "entity_type": "user",    # ✅ 有 entity_type
        "parameters": [  # ⚠️ 注意：是列表
            {
                "name": "uid",
                "type": "string",
                "description": "用户 id",
                "required": True,
                "parameter_type": "entity_ref",  # ✅ 明确标记
                "entity_field": "uid"
            },
            {
                "name": "embed",
                "type": "string",
                "required": False,
                "parameter_type": "literal"  # ✅ 明确标记
            }
        ],
        "required_identifiers": ["uid"]
    }


@pytest.fixture
def incomplete_schema():
    """缺少元数据的 schema（92.1% 的路由都是这样）"""
    return {
        "route_id": "some_incomplete_route",
        "path_template": ["/github/:owner/:repo/commits"],
        # ❌ 缺少 platform
        # ❌ 缺少 entity_type
        "parameters": [
            {
                "name": "owner",
                "type": "string",
                "description": "仓库所有者",
                "required": True
                # ❌ 缺少 parameter_type
            },
            {
                "name": "repo",
                "type": "string",
                "description": "仓库名称",
                "required": True
                # ❌ 缺少 parameter_type
            }
        ]
    }


class TestRealSchemaStructure:
    """测试真实的 schema 结构（列表形式的 parameters）"""

    def test_should_resolve_param_with_real_schema(self, real_bilibili_schema):
        """P0 修复验证：处理列表形式的 parameters"""
        # uid 被标记为 entity_ref
        result = should_resolve_param(
            "uid", "行业101", real_bilibili_schema
        )
        assert result is True

        # embed 被标记为 literal
        result = should_resolve_param(
            "embed", "true", real_bilibili_schema
        )
        assert result is False

    @patch('services.database.subscription_service.SubscriptionService')
    def test_resolve_entity_with_real_schema(
        self,
        mock_service_class,
        real_bilibili_schema
    ):
        """P1 修复验证：完整元数据的情况"""
        # Mock SubscriptionService
        mock_service = Mock()
        mock_service.resolve_entity.return_value = {"uid": "1566847"}
        mock_service_class.return_value = mock_service

        result = resolve_entity_from_schema(
            entity_name="行业101",
            tool_schema=real_bilibili_schema,
            extracted_params={"uid": "行业101"},
            target_params=["uid"]
        )

        assert result == {"uid": "1566847"}
        mock_service.resolve_entity.assert_called_once_with(
            entity_name="行业101",
            platform="bilibili",  # ✅ 从 schema 获取
            entity_type="user",    # ✅ 从 schema 获取
            user_id=None,
            is_active=True
        )


class TestIncompleteSchemaFallback:
    """测试缺失元数据的回退逻辑"""

    def test_should_resolve_param_without_parameter_type(
        self,
        incomplete_schema
    ):
        """启发式兜底：缺少 parameter_type 时使用启发式判断"""
        # 包含中文 → 需要解析
        result = should_resolve_param(
            "owner", "langchain-ai", incomplete_schema
        )
        assert result is True  # 默认保守策略

        # 全数字 → 无需解析
        result = should_resolve_param(
            "owner", "12345", incomplete_schema
        )
        assert result is False

    @patch('services.database.subscription_service.SubscriptionService')
    def test_resolve_entity_with_missing_platform(
        self,
        mock_service_class,
        incomplete_schema
    ):
        """P1 修复验证：缺少 platform 时从路径推断"""
        mock_service = Mock()
        mock_service.resolve_entity.return_value = {"owner": "langchain-ai", "repo": "langchain"}
        mock_service_class.return_value = mock_service

        result = resolve_entity_from_schema(
            entity_name="langchain-ai",
            tool_schema=incomplete_schema,
            extracted_params={"owner": "langchain-ai"},
            target_params=["owner"]
        )

        assert result == {"owner": "langchain-ai", "repo": "langchain"}

        # 验证回退逻辑正确推断了 platform 和 entity_type
        mock_service.resolve_entity.assert_called_once()
        call_args = mock_service.resolve_entity.call_args[1]
        assert call_args["platform"] == "github"  # ⚠️ 从路径推断
        # ⚠️ 注意：回退逻辑将 "owner" 推断为 "repo" entity_type
        # 这是启发式的局限性示例（"owner" 在 repo 相关参数列表中）
        assert call_args["entity_type"] == "repo"

    def test_resolve_entity_fallback_complete_failure(self):
        """回退失败的情况"""
        # 极端情况：既无元数据，也无法推断
        broken_schema = {
            "route_id": "broken",
            "path_template": [""],  # 空路径
            "parameters": []  # 空参数列表
        }

        result = resolve_entity_from_schema(
            entity_name="unknown",
            tool_schema=broken_schema,
            extracted_params={},
            target_params=[]
        )

        assert result is None  # 应该放弃解析


class TestBackwardCompatibility:
    """测试向后兼容性（字典形式的 parameters）"""

    def test_should_resolve_param_with_dict_parameters(self):
        """P0 修复验证：仍然支持字典形式（向后兼容）"""
        schema_with_dict = {
            "parameters": {  # 字典形式（旧格式）
                "uid": {"parameter_type": "entity_ref"}
            }
        }

        result = should_resolve_param("uid", "行业101", schema_with_dict)
        assert result is True


class TestEdgeCases:
    """边缘情况测试"""

    def test_empty_parameters_list(self):
        """空参数列表"""
        schema = {"parameters": []}
        result = should_resolve_param("uid", "123", schema)
        # 启发式兜底：全数字，无需解析
        assert result is False

    def test_missing_parameters_field(self):
        """完全缺少 parameters 字段"""
        schema = {"route_id": "test"}
        result = should_resolve_param("uid", "行业101", schema)
        # 启发式兜底：包含中文，需要解析
        assert result is True

    @patch('services.database.subscription_service.SubscriptionService')
    def test_resolve_with_multiple_entity_params(
        self,
        mock_service_class
    ):
        """多个实体参数（如 GitHub 的 owner + repo）"""
        mock_service = Mock()
        mock_service.resolve_entity.return_value = {
            "owner": "langchain-ai",
            "repo": "langchain"
        }
        mock_service_class.return_value = mock_service

        schema = {
            "platform": "github",
            "entity_type": "repo",
            "parameters": [
                {"name": "owner", "parameter_type": "entity_ref"},
                {"name": "repo", "parameter_type": "entity_ref"}
            ]
        }

        result = resolve_entity_from_schema(
            entity_name="langchain",
            tool_schema=schema,
            extracted_params={"owner": "langchain-ai", "repo": "langchain"},
            target_params=["owner", "repo"]
        )

        assert result is not None
        assert "owner" in result
        assert "repo" in result


@pytest.mark.skipif(
    not Path("route_process/datasource_definitions_enriched.json").exists(),
    reason="需要真实的 datasource_definitions_enriched.json"
)
class TestWithRealData:
    """使用真实数据文件的集成测试"""

    def test_load_and_validate_real_schema(self):
        """加载真实的 schema 并验证结构"""
        data_file = Path("route_process/datasource_definitions_enriched.json")
        with open(data_file, 'r', encoding='utf-8') as f:
            providers = json.load(f)

        # 找到 bilibili_video
        bilibili_video = None
        for provider in providers:
            for route in provider.get("routes", []):
                if route.get("route_id") == "bilibili_video":
                    bilibili_video = route
                    break

        assert bilibili_video is not None
        assert isinstance(bilibili_video["parameters"], list)  # ✅ 确认是列表
        assert bilibili_video["platform"] == "bilibili"
        assert bilibili_video["entity_type"] == "user"

        # 测试 should_resolve_param 能正常工作
        result = should_resolve_param(
            "uid", "行业101", bilibili_video
        )
        assert result is True
