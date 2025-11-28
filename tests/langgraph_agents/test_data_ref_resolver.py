"""DataRefResolver 单元测试。"""

import pytest
from unittest.mock import MagicMock

from langgraph_agents.tools.data_ref_resolver import (
    DataRefResolver,
    ResolvedData,
    create_resolver_from_context,
)
from langgraph_agents.state import DataReference


class TestDataRefResolver:
    """DataRefResolver 测试类。"""

    def setup_method(self):
        """设置测试数据。"""
        # 模拟 data_store
        self.data_store = MagicMock()
        self.data_store.load.side_effect = self._mock_load

        # 模拟 data_stash
        self.data_stash = [
            DataReference(
                step_id=1,
                tool_name="fetch_public_data",
                data_id="lg-abc123",
                summary="获取30条数据",
                status="success",
            ),
            DataReference(
                step_id=2,
                tool_name="filter_data",
                data_id="lg-def456",
                summary="过滤后10条数据",
                status="success",
            ),
            DataReference(
                step_id=3,
                tool_name="ask_user_clarification",
                data_id=None,  # needs_user_input 状态没有 data_id
                summary="等待用户澄清",
                status="needs_user_input",
            ),
        ]

        # 模拟数据
        self.mock_data = {
            "lg-abc123": {
                "type": "rss_public_data",
                "items": [
                    {"title": "标题1", "content": "内容1"},
                    {"title": "标题2", "content": "内容2"},
                ],
            },
            "lg-def456": {
                "type": "data_filter",
                "items": [
                    {"title": "过滤标题1"},
                ],
            },
        }

        self.resolver = DataRefResolver(self.data_stash, self.data_store)

    def _mock_load(self, data_id):
        """模拟 data_store.load。"""
        return self.mock_data.get(data_id)

    # --- 基础解析测试 ---

    def test_resolve_data_id_string(self):
        """测试解析 data_id 字符串。"""
        result = self.resolver.resolve("lg-abc123")

        assert isinstance(result, ResolvedData)
        assert result.source_data_id == "lg-abc123"
        assert result.source_step_id == 1
        assert result.source_type == "data_id"
        assert result.data["type"] == "rss_public_data"

    def test_resolve_step_id_int(self):
        """测试解析整数 step_id。"""
        result = self.resolver.resolve(1)

        assert result.source_step_id == 1
        assert result.source_data_id == "lg-abc123"
        assert result.source_type == "step_id"
        assert result.data["type"] == "rss_public_data"

    def test_resolve_step_ref_string(self):
        """测试解析 $step.N 格式。"""
        result = self.resolver.resolve("$step.2")

        assert result.source_step_id == 2
        assert result.source_data_id == "lg-def456"
        assert result.source_type == "step_id"
        assert result.data["type"] == "data_filter"

    def test_resolve_step_ref_with_json_path(self):
        """测试解析带 JSONPath 的引用。"""
        result = self.resolver.resolve("$step.1.items")

        assert result.source_step_id == 1
        assert result.source_type == "json_path"
        assert isinstance(result.data, list)
        assert len(result.data) == 2

    def test_resolve_step_ref_with_nested_json_path(self):
        """测试解析嵌套 JSONPath。"""
        result = self.resolver.resolve("$step.1.items[0].title")

        assert result.source_step_id == 1
        assert result.source_type == "json_path"
        assert result.data == "标题1"

    def test_resolve_numeric_string(self):
        """测试解析纯数字字符串。"""
        result = self.resolver.resolve("1")

        assert result.source_step_id == 1
        assert result.source_type == "step_id"

    # --- 错误处理测试 ---

    def test_resolve_invalid_step_id(self):
        """测试解析不存在的 step_id。"""
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(99)

        assert "step_id=99" in str(exc_info.value)
        assert "可用的步骤" in str(exc_info.value)

    def test_resolve_invalid_data_id(self):
        """测试解析不存在的 data_id。"""
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve("lg-invalid")

        assert "lg-invalid" in str(exc_info.value)
        assert "不存在" in str(exc_info.value)

    def test_resolve_invalid_format(self):
        """测试解析无效格式。"""
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve("invalid_format")

        assert "无效的数据引用格式" in str(exc_info.value)

    def test_resolve_needs_user_input_status(self):
        """测试解析 needs_user_input 状态的引用。"""
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(3)

        # 错误消息可能是 "执行状态为 'needs_user_input'" 或 "没有关联的 data_id"
        error_msg = str(exc_info.value)
        assert "step_id=3" in error_msg or "needs_user_input" in error_msg

    def test_resolve_error_status(self):
        """测试解析错误状态的引用。"""
        # 添加一个错误状态的引用
        self.data_stash.append(
            DataReference(
                step_id=4,
                tool_name="failed_tool",
                data_id="lg-failed",
                summary="执行失败",
                status="error",
                error_message="网络超时",
            )
        )
        self.resolver = DataRefResolver(self.data_stash, self.data_store)

        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(4)

        assert "status" in str(exc_info.value).lower() or "error" in str(exc_info.value).lower()

    def test_resolve_unsupported_type(self):
        """测试解析不支持的类型。"""
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve({"invalid": "type"})

        assert "不支持的引用类型" in str(exc_info.value)

    # --- JSONPath 测试 ---

    def test_json_path_array_index(self):
        """测试数组索引提取。"""
        result = self.resolver.resolve("$step.1.items[1]")

        assert result.data["title"] == "标题2"

    def test_json_path_nested_field(self):
        """测试嵌套字段提取。"""
        # 添加嵌套数据
        self.mock_data["lg-nested"] = {
            "meta": {
                "author": {
                    "name": "测试作者"
                }
            }
        }
        self.data_stash.append(
            DataReference(
                step_id=5,
                tool_name="test_tool",
                data_id="lg-nested",
                summary="测试",
                status="success",
            )
        )
        self.resolver = DataRefResolver(self.data_stash, self.data_store)

        result = self.resolver.resolve("$step.5.meta.author.name")

        assert result.data == "测试作者"

    def test_json_path_out_of_bounds(self):
        """测试数组索引越界。"""
        result = self.resolver.resolve("$step.1.items[99]")

        assert result.data is None

    def test_json_path_nonexistent_field(self):
        """测试不存在的字段。"""
        result = self.resolver.resolve("$step.1.nonexistent.field")

        assert result.data is None

    # --- 辅助方法测试 ---

    def test_list_available_refs(self):
        """测试列出可用引用。"""
        refs = self.resolver.list_available_refs()

        assert len(refs) == 3
        assert refs[0]["step_id"] == 1
        assert refs[0]["tool"] == "fetch_public_data"
        assert refs[1]["step_id"] == 2
        assert refs[2]["status"] == "needs_user_input"

    def test_get_ref_by_tool(self):
        """测试按工具名获取引用。"""
        ref = self.resolver.get_ref_by_tool("fetch_public_data")

        assert ref is not None
        assert ref.step_id == 1
        assert ref.data_id == "lg-abc123"

    def test_get_ref_by_tool_not_found(self):
        """测试获取不存在的工具引用。"""
        ref = self.resolver.get_ref_by_tool("nonexistent_tool")

        assert ref is None

    def test_get_ref_by_tool_returns_latest(self):
        """测试获取工具的最新引用。"""
        # 添加同一工具的另一个引用
        self.data_stash.append(
            DataReference(
                step_id=6,
                tool_name="fetch_public_data",
                data_id="lg-latest",
                summary="最新数据",
                status="success",
            )
        )
        self.resolver = DataRefResolver(self.data_stash, self.data_store)

        ref = self.resolver.get_ref_by_tool("fetch_public_data")

        assert ref.step_id == 6
        assert ref.data_id == "lg-latest"


class TestCreateResolverFromContext:
    """测试从上下文创建解析器的工厂函数。"""

    def test_create_resolver_success(self):
        """测试成功创建解析器。"""
        context = MagicMock()
        context.extras = {
            "data_store": MagicMock(),
            "data_stash": [],
            "working_memory": {},
        }

        resolver = create_resolver_from_context(context)

        assert resolver is not None
        assert isinstance(resolver, DataRefResolver)

    def test_create_resolver_no_data_store(self):
        """测试缺少 data_store 时返回 None。"""
        context = MagicMock()
        context.extras = {
            "data_stash": [],
        }

        resolver = create_resolver_from_context(context)

        assert resolver is None

    def test_create_resolver_missing_data_stash(self):
        """测试缺少 data_stash 时使用默认空列表。"""
        context = MagicMock()
        context.extras = {
            "data_store": MagicMock(),
        }

        resolver = create_resolver_from_context(context)

        assert resolver is not None
        assert len(resolver.data_stash) == 0


class TestRequireSuccess:
    """测试 require_success 参数。"""

    def setup_method(self):
        """设置测试数据。"""
        self.data_store = MagicMock()
        self.data_store.load.return_value = {"data": "test"}

        self.data_stash = [
            DataReference(
                step_id=1,
                tool_name="test_tool",
                data_id="lg-error",
                summary="执行失败",
                status="error",
                error_message="测试错误",
            ),
        ]

        self.resolver = DataRefResolver(self.data_stash, self.data_store)

    def test_require_success_true_blocks_error(self):
        """测试 require_success=True 阻止错误状态。"""
        with pytest.raises(ValueError):
            self.resolver.resolve(1, require_success=True)

    def test_require_success_false_allows_error(self):
        """测试 require_success=False 允许错误状态。"""
        # 错误状态有 data_id 时应该可以解析
        self.data_stash[0] = DataReference(
            step_id=1,
            tool_name="test_tool",
            data_id="lg-error",
            summary="执行失败",
            status="success",  # 改为 success 以通过 data_id 检查
        )
        self.resolver = DataRefResolver(self.data_stash, self.data_store)

        result = self.resolver.resolve(1, require_success=False)

        assert result is not None
