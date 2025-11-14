"""
entity_resolver_helper 单元测试

测试基于 schema 的参数验证和订阅解析逻辑。
"""

import pytest
from unittest.mock import Mock, patch
from services.subscription.entity_resolver_helper import (
    should_resolve_param,
    resolve_entity_from_schema,
    validate_and_resolve_params
)


class TestShouldResolveParam:
    """测试 should_resolve_param 函数"""

    def test_schema_based_entity_ref(self):
        """测试：schema 明确标记为 entity_ref"""
        tool_schema = {
            "parameters": {
                "uid": {"parameter_type": "entity_ref"}
            }
        }
        result = should_resolve_param("uid", "行业101", tool_schema)
        assert result is True

    def test_schema_based_literal(self):
        """测试：schema 标记为 literal"""
        tool_schema = {
            "parameters": {
                "embed": {"parameter_type": "literal"}
            }
        }
        result = should_resolve_param("embed", "true", tool_schema)
        assert result is False

    def test_schema_based_enum(self):
        """测试：schema 标记为 enum"""
        tool_schema = {
            "parameters": {
                "category": {"parameter_type": "enum"}
            }
        }
        result = should_resolve_param("category", "tech", tool_schema)
        assert result is False

    def test_heuristic_fallback_digit(self):
        """测试：schema 缺失，参数值全数字（启发式兜底）"""
        tool_schema = {"parameters": {}}  # 缺少 parameter_type
        result = should_resolve_param("uid", "1566847", tool_schema)
        assert result is False  # 全数字假设为有效ID

    def test_heuristic_fallback_chinese(self):
        """测试：schema 缺失，参数值包含中文（启发式兜底）"""
        tool_schema = {"parameters": {}}  # 缺少 parameter_type
        result = should_resolve_param("uid", "行业101", tool_schema)
        assert result is True  # 包含中文假设为名字

    def test_heuristic_fallback_default(self):
        """测试：schema 缺失，无明显特征（启发式兜底）"""
        tool_schema = {"parameters": {}}  # 缺少 parameter_type
        result = should_resolve_param("owner", "langchain", tool_schema)
        assert result is True  # 默认尝试解析（保守策略）


class TestResolveEntityFromSchema:
    """测试 resolve_entity_from_schema 函数"""

    @patch('services.database.subscription_service.SubscriptionService')
    def test_resolve_success(self, mock_service_class):
        """测试：订阅解析成功"""
        # Mock SubscriptionService
        mock_service = Mock()
        mock_service.resolve_entity.return_value = {"uid": "1566847"}
        mock_service_class.return_value = mock_service

        tool_schema = {
            "platform": "bilibili",
            "entity_type": "user",
            "parameters": {"uid": {"parameter_type": "entity_ref"}}
        }

        result = resolve_entity_from_schema(
            entity_name="行业101",
            tool_schema=tool_schema,
            extracted_params={"uid": "行业101"},
            target_params=["uid"]
        )

        assert result == {"uid": "1566847"}
        mock_service.resolve_entity.assert_called_once_with(
            entity_name="行业101",
            platform="bilibili",
            entity_type="user",
            user_id=None,
            is_active=True
        )

    @patch('services.database.subscription_service.SubscriptionService')
    def test_resolve_not_found(self, mock_service_class):
        """测试：订阅未找到"""
        # Mock SubscriptionService
        mock_service = Mock()
        mock_service.resolve_entity.return_value = None
        mock_service_class.return_value = mock_service

        tool_schema = {
            "platform": "bilibili",
            "entity_type": "user"
        }

        result = resolve_entity_from_schema(
            entity_name="不存在的UP主",
            tool_schema=tool_schema,
            extracted_params={"uid": "不存在的UP主"},
            target_params=["uid"]
        )

        assert result is None

    def test_schema_incomplete(self):
        """测试：schema 缺少必要字段"""
        tool_schema = {
            # 缺少 platform 和 entity_type
            "parameters": {"uid": {"parameter_type": "entity_ref"}}
        }

        result = resolve_entity_from_schema(
            entity_name="行业101",
            tool_schema=tool_schema,
            extracted_params={"uid": "行业101"},
            target_params=["uid"]
        )

        assert result is None  # schema 不完整，无法解析


class TestValidateAndResolveParams:
    """测试 validate_and_resolve_params 函数"""

    @patch('services.subscription.entity_resolver_helper.resolve_entity_from_schema')
    @patch('services.subscription.entity_resolver_helper.should_resolve_param')
    def test_resolve_success(
        self,
        mock_should_resolve,
        mock_resolve_entity
    ):
        """测试：完整流程，解析成功"""
        # Mock should_resolve_param
        def should_resolve_side_effect(param_name, param_value, tool_schema):
            if param_name == "uid":
                return True  # uid 需要解析
            return False  # 其他参数无需解析

        mock_should_resolve.side_effect = should_resolve_side_effect

        # Mock resolve_entity_from_schema
        mock_resolve_entity.return_value = {"uid": "1566847"}

        tool_schema = {
            "platform": "bilibili",
            "entity_type": "user",
            "parameters": {
                "uid": {"parameter_type": "entity_ref"},
                "embed": {"parameter_type": "literal"}
            }
        }

        params = {"uid": "行业101", "embed": "true"}
        result = validate_and_resolve_params(
            params=params,
            tool_schema=tool_schema,
            user_query="我想看看行业101的投稿视频"
        )

        assert result == {"uid": "1566847", "embed": "true"}
        mock_resolve_entity.assert_called_once()

    @patch('services.subscription.entity_resolver_helper.resolve_entity_from_schema')
    @patch('services.subscription.entity_resolver_helper.should_resolve_param')
    def test_resolve_fallback_to_original(
        self,
        mock_should_resolve,
        mock_resolve_entity
    ):
        """测试：解析失败，降级使用原值"""
        # Mock should_resolve_param
        mock_should_resolve.side_effect = lambda p, v, s: p == "uid"

        # Mock resolve_entity_from_schema（返回 None）
        mock_resolve_entity.return_value = None

        tool_schema = {
            "platform": "bilibili",
            "entity_type": "user",
            "parameters": {"uid": {"parameter_type": "entity_ref"}}
        }

        params = {"uid": "未订阅的UP主"}
        result = validate_and_resolve_params(
            params=params,
            tool_schema=tool_schema,
            user_query="查询未订阅的UP主"
        )

        # 降级处理，使用原值
        assert result == {"uid": "未订阅的UP主"}

    @patch('services.subscription.entity_resolver_helper.should_resolve_param')
    def test_no_params_need_resolution(self, mock_should_resolve):
        """测试：所有参数都无需解析"""
        # Mock should_resolve_param（全部返回 False）
        mock_should_resolve.return_value = False

        tool_schema = {
            "platform": "bilibili",
            "parameters": {
                "kw": {"parameter_type": "literal"},
                "order": {"parameter_type": "enum"}
            }
        }

        params = {"kw": "RSSHub", "order": "pubdate"}
        result = validate_and_resolve_params(
            params=params,
            tool_schema=tool_schema,
            user_query="搜索RSSHub视频"
        )

        # 直接返回原参数
        assert result == params
