"""上下文管理器单元测试。"""

import pytest
from unittest.mock import MagicMock

from langgraph_agents.context_manager import (
    MemoryLayer,
    ContextBudget,
    HierarchicalMemoryManager,
    ContextUsageMonitor,
    get_optimized_context,
)
from langgraph_agents.state import DataReference


class TestMemoryLayer:
    """测试单个记忆层。"""

    def test_create_layer(self):
        """测试创建记忆层。"""
        layer = MemoryLayer(
            name="测试层",
            priority=1,
            max_tokens=500,
        )

        assert layer.name == "测试层"
        assert layer.priority == 1
        assert layer.max_tokens == 500
        assert layer.content == ""
        assert layer.estimated_tokens == 0

    def test_update_content(self):
        """测试更新内容。"""
        layer = MemoryLayer(name="测试", priority=1, max_tokens=500)

        layer.update("这是测试内容", estimated_tokens=10)

        assert layer.content == "这是测试内容"
        assert layer.estimated_tokens == 10

    def test_estimate_tokens_chinese(self):
        """测试中文 token 估算。"""
        layer = MemoryLayer(name="测试", priority=1, max_tokens=500)

        # 中文：约 2 字符/token
        chinese_text = "这是一段中文测试文本"
        layer.update(chinese_text)

        # 10 个中文字符 -> 约 5 tokens + buffer
        assert layer.estimated_tokens > 0
        assert layer.estimated_tokens < 20

    def test_estimate_tokens_english(self):
        """测试英文 token 估算。"""
        layer = MemoryLayer(name="测试", priority=1, max_tokens=500)

        # 英文：约 4 字符/token
        english_text = "This is a test string"
        layer.update(english_text)

        # 21 个英文字符 -> 约 5 tokens + buffer
        assert layer.estimated_tokens > 0
        assert layer.estimated_tokens < 20


class TestContextBudget:
    """测试上下文预算。"""

    def test_default_budget(self):
        """测试默认预算配置。"""
        budget = ContextBudget()

        assert budget.total_budget == 8000
        assert budget.system_prompt_budget == 2000
        assert budget.tool_list_budget == 1000
        assert budget.response_buffer == 1500

    def test_available_for_memory(self):
        """测试可用于记忆的 token 数。"""
        budget = ContextBudget(
            total_budget=10000,
            system_prompt_budget=2000,
            tool_list_budget=1000,
            response_buffer=2000,
        )

        assert budget.available_for_memory == 5000

    def test_custom_budget(self):
        """测试自定义预算。"""
        budget = ContextBudget(
            total_budget=16000,
            system_prompt_budget=3000,
            tool_list_budget=2000,
            response_buffer=3000,
        )

        assert budget.available_for_memory == 8000


class TestHierarchicalMemoryManager:
    """测试分层记忆管理器。"""

    def setup_method(self):
        """设置测试环境。"""
        self.manager = HierarchicalMemoryManager()

    def test_initialization(self):
        """测试初始化。"""
        assert "L1_working" in self.manager.layers
        assert "L2_session" in self.manager.layers
        assert "L3_conversation" in self.manager.layers
        assert "L4_longterm" in self.manager.layers

    def test_layer_priorities(self):
        """测试层优先级。"""
        assert self.manager.layers["L1_working"].priority == 1
        assert self.manager.layers["L2_session"].priority == 2
        assert self.manager.layers["L3_conversation"].priority == 3
        assert self.manager.layers["L4_longterm"].priority == 4

    def test_update_from_empty_state(self):
        """测试从空状态更新。"""
        state = {"original_query": "测试查询"}

        self.manager.update_from_state(state)

        # 所有层应该为空
        for layer in self.manager.layers.values():
            assert layer.content == "" or layer.estimated_tokens == 0

    def test_update_from_state_with_data_stash(self):
        """测试从包含 data_stash 的状态更新。"""
        state = {
            "original_query": "测试查询",
            "data_stash": [
                DataReference(
                    step_id=1,
                    tool_name="fetch_public_data",
                    data_id="lg-abc123",
                    summary="获取30条数据",
                    status="success",
                ),
            ],
        }

        self.manager.update_from_state(state)

        l2 = self.manager.layers["L2_session"]
        assert l2.content != ""
        assert "fetch_public_data" in l2.content
        assert "lg-abc123" in l2.content

    def test_update_from_state_with_working_memory(self):
        """测试从包含 working_memory 的状态更新。"""
        state = {
            "original_query": "测试查询",
            "working_memory": {
                "discover_sources": {
                    "status": "success",
                    "description": "发现5个数据源",
                    "step_id": 1,
                },
            },
        }

        self.manager.update_from_state(state)

        l1 = self.manager.layers["L1_working"]
        assert l1.content != ""
        assert "discover_sources" in l1.content

    def test_get_context_string(self):
        """测试获取上下文字符串。"""
        state = {
            "original_query": "测试查询",
            "data_stash": [
                DataReference(
                    step_id=1,
                    tool_name="test_tool",
                    data_id="lg-123",
                    summary="测试摘要",
                    status="success",
                ),
            ],
        }

        self.manager.update_from_state(state)
        context = self.manager.get_context_string()

        assert "会话记忆" in context
        assert "test_tool" in context

    def test_get_usage_stats(self):
        """测试获取使用统计。"""
        state = {
            "original_query": "测试",
            "data_stash": [
                DataReference(
                    step_id=1,
                    tool_name="test",
                    data_id="lg-1",
                    summary="测试",
                    status="success",
                ),
            ],
        }

        self.manager.update_from_state(state)
        stats = self.manager.get_usage_stats()

        assert "total_updates" in stats
        assert stats["total_updates"] == 1
        assert "layers" in stats
        assert "L1_working" in stats["layers"]
        assert "L2_session" in stats["layers"]

    def test_context_with_token_limit(self):
        """测试带 token 限制的上下文获取。"""
        # 添加大量内容
        state = {
            "original_query": "测试",
            "chat_history": ["对话1", "对话2", "对话3", "对话4", "对话5"],
            "data_stash": [
                DataReference(
                    step_id=i,
                    tool_name=f"tool_{i}",
                    data_id=f"lg-{i}",
                    summary=f"摘要内容{i}" * 50,
                    status="success",
                )
                for i in range(10)
            ],
        }

        self.manager.update_from_state(state)

        # 使用非常小的限制
        context = self.manager.get_context_string(max_tokens=100)

        # 应该被压缩
        assert len(context) < 5000


class TestContextUsageMonitor:
    """测试上下文使用监控器。"""

    def setup_method(self):
        """设置测试环境。"""
        self.monitor = ContextUsageMonitor()

    def test_record_stats(self):
        """测试记录统计。"""
        stats = {
            "total_estimated_tokens": 1000,
            "budget_available": 5000,
        }

        self.monitor.record(stats)

        summary = self.monitor.get_summary()
        assert summary["total_records"] == 1

    def test_high_utilization_alert(self):
        """测试高使用率告警。"""
        # 记录高使用率
        stats = {
            "total_estimated_tokens": 4600,  # 92% utilization
            "budget_available": 5000,
        }

        self.monitor.record(stats)

        summary = self.monitor.get_summary()
        assert summary["alerts_count"] > 0

    def test_clear_alerts(self):
        """测试清除告警。"""
        stats = {
            "total_estimated_tokens": 4600,
            "budget_available": 5000,
        }
        self.monitor.record(stats)

        self.monitor.clear_alerts()

        summary = self.monitor.get_summary()
        assert summary["alerts_count"] == 0

    def test_empty_summary(self):
        """测试空监控摘要。"""
        summary = self.monitor.get_summary()

        assert summary["status"] == "no_data"


class TestGetOptimizedContext:
    """测试便捷函数。"""

    def test_get_optimized_context(self):
        """测试获取优化上下文。"""
        state = {
            "original_query": "测试查询",
            "data_stash": [
                DataReference(
                    step_id=1,
                    tool_name="test_tool",
                    data_id="lg-123",
                    summary="测试摘要",
                    status="success",
                ),
            ],
        }

        context = get_optimized_context(state)

        assert isinstance(context, str)
        assert "test_tool" in context


class TestCustomConfiguration:
    """测试自定义配置。"""

    def test_custom_budget(self):
        """测试自定义预算。"""
        budget = ContextBudget(total_budget=16000)
        manager = HierarchicalMemoryManager(budget=budget)

        assert manager.budget.total_budget == 16000

    def test_custom_layer_ratios(self):
        """测试自定义层比例。"""
        custom_ratios = {
            "L1_working": 0.20,
            "L2_session": 0.50,
            "L3_conversation": 0.25,
            "L4_longterm": 0.05,
        }
        manager = HierarchicalMemoryManager(layer_ratios=custom_ratios)

        # 验证比例被应用
        available = manager.budget.available_for_memory
        assert manager.layers["L1_working"].max_tokens == int(available * 0.20)
        assert manager.layers["L2_session"].max_tokens == int(available * 0.50)
