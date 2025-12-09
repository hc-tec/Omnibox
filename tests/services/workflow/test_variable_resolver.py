"""
VariableResolver 变量解析器测试
"""

import pytest

from services.workflow.variable_resolver import (
    VariableResolver,
    VariableValidationError,
)
from services.workflow.models import Variable, VariableType


@pytest.fixture
def resolver():
    """创建变量解析器"""
    return VariableResolver()


class TestVariableValidation:
    """变量验证测试"""

    def test_validate_required_variable(self, resolver):
        """测试必填变量验证"""
        variables = {
            "keyword": Variable(
                name="keyword",
                var_type=VariableType.STRING,
                required=True
            )
        }

        # 缺少必填变量
        errors = resolver.validate(variables, {})
        assert len(errors) == 1
        assert "缺少必填变量" in errors[0]

        # 提供必填变量
        errors = resolver.validate(variables, {"keyword": "测试"})
        assert errors == []

    def test_validate_optional_variable(self, resolver):
        """测试可选变量验证"""
        variables = {
            "limit": Variable(
                name="limit",
                var_type=VariableType.NUMBER,
                default=10,
                required=False
            )
        }

        # 不提供可选变量（有默认值）
        errors = resolver.validate(variables, {})
        assert errors == []

    def test_validate_type_string(self, resolver):
        """测试字符串类型验证"""
        variables = {
            "keyword": Variable(
                name="keyword",
                var_type=VariableType.STRING,
                required=True
            )
        }

        # 正确类型
        errors = resolver.validate(variables, {"keyword": "测试"})
        assert errors == []

        # 错误类型
        errors = resolver.validate(variables, {"keyword": 123})
        assert len(errors) == 1
        assert "应为字符串" in errors[0]

    def test_validate_type_number(self, resolver):
        """测试数字类型验证"""
        variables = {
            "limit": Variable(
                name="limit",
                var_type=VariableType.NUMBER,
                required=True
            )
        }

        # 整数
        errors = resolver.validate(variables, {"limit": 10})
        assert errors == []

        # 浮点数
        errors = resolver.validate(variables, {"limit": 10.5})
        assert errors == []

        # 错误类型
        errors = resolver.validate(variables, {"limit": "10"})
        assert len(errors) == 1
        assert "应为数字" in errors[0]

    def test_validate_type_list(self, resolver):
        """测试列表类型验证"""
        variables = {
            "platforms": Variable(
                name="platforms",
                var_type=VariableType.LIST,
                required=True
            )
        }

        # 正确类型
        errors = resolver.validate(variables, {"platforms": ["bilibili", "youtube"]})
        assert errors == []

        # 错误类型
        errors = resolver.validate(variables, {"platforms": "bilibili"})
        assert len(errors) == 1
        assert "应为列表" in errors[0]

    def test_validate_enum_values(self, resolver):
        """测试枚举值验证"""
        variables = {
            "platform": Variable(
                name="platform",
                var_type=VariableType.STRING,
                enum_values=["bilibili", "youtube", "douyin"],
                required=True
            )
        }

        # 有效枚举值
        errors = resolver.validate(variables, {"platform": "bilibili"})
        assert errors == []

        # 无效枚举值
        errors = resolver.validate(variables, {"platform": "weibo"})
        assert len(errors) == 1
        assert "不在允许列表中" in errors[0]


class TestVariableResolution:
    """变量解析测试"""

    def test_resolve_simple_variable(self, resolver):
        """测试简单变量解析"""
        variables = {
            "keyword": Variable(
                name="keyword",
                var_type=VariableType.STRING,
                required=True
            )
        }
        values = {"keyword": "AI Agent"}

        template = {"query": "${keyword}"}
        result = resolver.resolve(template, variables, values)

        assert result["query"] == "AI Agent"

    def test_resolve_variable_in_string(self, resolver):
        """测试字符串中的变量"""
        variables = {
            "name": Variable(
                name="name",
                var_type=VariableType.STRING,
                required=True
            )
        }
        values = {"name": "影视飓风"}

        template = {"query": "B站 ${name} 最新视频"}
        result = resolver.resolve(template, variables, values)

        assert result["query"] == "B站 影视飓风 最新视频"

    def test_resolve_multiple_variables(self, resolver):
        """测试多变量解析"""
        variables = {
            "platform": Variable(name="platform", var_type=VariableType.STRING, required=True),
            "keyword": Variable(name="keyword", var_type=VariableType.STRING, required=True),
        }
        values = {"platform": "B站", "keyword": "科技测评"}

        template = {"query": "${platform} ${keyword} 热门视频"}
        result = resolver.resolve(template, variables, values)

        assert result["query"] == "B站 科技测评 热门视频"

    def test_resolve_with_default_value(self, resolver):
        """测试默认值"""
        variables = {
            "limit": Variable(
                name="limit",
                var_type=VariableType.NUMBER,
                default=20,
                required=False
            )
        }
        values = {}  # 不提供值

        template = {"limit": "${limit}"}
        result = resolver.resolve(template, variables, values)

        assert result["limit"] == 20

    def test_resolve_nested_structure(self, resolver):
        """测试嵌套结构"""
        variables = {
            "keyword": Variable(name="keyword", var_type=VariableType.STRING, required=True),
            "limit": Variable(name="limit", var_type=VariableType.NUMBER, default=10, required=False),
        }
        values = {"keyword": "测试"}

        template = {
            "params": {
                "query": "${keyword}",
                "options": {
                    "limit": "${limit}"
                }
            }
        }
        result = resolver.resolve(template, variables, values)

        assert result["params"]["query"] == "测试"
        assert result["params"]["options"]["limit"] == 10

    def test_resolve_list_variable(self, resolver):
        """测试列表变量"""
        variables = {
            "platforms": Variable(
                name="platforms",
                var_type=VariableType.LIST,
                required=True
            )
        }
        values = {"platforms": ["bilibili", "youtube"]}

        template = {"platforms": "${platforms}"}
        result = resolver.resolve(template, variables, values)

        # 完整变量引用保持原始类型
        assert result["platforms"] == ["bilibili", "youtube"]

    def test_resolve_preserves_non_variable_content(self, resolver):
        """测试保留非变量内容"""
        variables = {}
        values = {}

        template = {
            "static": "固定值",
            "number": 42,
            "nested": {"key": "value"}
        }
        result = resolver.resolve(template, variables, values)

        assert result["static"] == "固定值"
        assert result["number"] == 42
        assert result["nested"]["key"] == "value"

    def test_resolve_object_path(self, resolver):
        """测试对象路径访问"""
        variables = {
            "config": Variable(
                name="config",
                var_type=VariableType.DATASOURCE,
                required=True
            )
        }
        values = {"config": {"host": "localhost", "port": 8080}}

        template = {"host": "${config.host}", "port": "${config.port}"}
        result = resolver.resolve(template, variables, values)

        assert result["host"] == "localhost"
        assert result["port"] == 8080

    def test_resolve_array_index(self, resolver):
        """测试数组索引访问"""
        variables = {
            "items": Variable(
                name="items",
                var_type=VariableType.LIST,
                required=True
            )
        }
        values = {"items": ["first", "second", "third"]}

        template = {"first": "${items[0]}", "second": "${items[1]}"}
        result = resolver.resolve(template, variables, values)

        assert result["first"] == "first"
        assert result["second"] == "second"

    def test_resolve_validation_error(self, resolver):
        """测试验证失败抛出异常"""
        variables = {
            "keyword": Variable(
                name="keyword",
                var_type=VariableType.STRING,
                required=True
            )
        }
        values = {}  # 缺少必填变量

        with pytest.raises(VariableValidationError) as exc_info:
            resolver.resolve({"query": "${keyword}"}, variables, values)

        assert "缺少必填变量" in str(exc_info.value)


class TestExtractVariables:
    """提取变量测试"""

    def test_extract_simple_variables(self, resolver):
        """测试提取简单变量"""
        template = {"query": "${keyword}", "limit": "${limit}"}
        variables = resolver.extract_variables(template)

        assert set(variables) == {"keyword", "limit"}

    def test_extract_nested_variables(self, resolver):
        """测试提取嵌套变量"""
        template = {
            "params": {
                "query": "${keyword}",
                "options": {
                    "limit": "${limit}"
                }
            },
            "items": ["${item1}", "${item2}"]
        }
        variables = resolver.extract_variables(template)

        assert set(variables) == {"keyword", "limit", "item1", "item2"}

    def test_extract_path_variables(self, resolver):
        """测试提取路径变量（只提取根变量名）"""
        template = {"host": "${config.host}", "first": "${items[0]}"}
        variables = resolver.extract_variables(template)

        # 只提取根变量名
        assert set(variables) == {"config", "items"}

    def test_extract_no_variables(self, resolver):
        """测试无变量模板"""
        template = {"static": "value", "number": 42}
        variables = resolver.extract_variables(template)

        assert variables == []
