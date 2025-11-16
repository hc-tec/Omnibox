"""V5.0 Phase 4 - ExecutionPlan 和 ExecutionEngine 测试。"""

import pytest
from langgraph_agents.state import (
    ExecutionPlan,
    ToolCall,
    StashReference,
    DataReference,
    GraphState
)
from langgraph_agents.execution_engine import ExecutionEngine
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.runtime import ToolExecutionContext
from unittest.mock import MagicMock


class TestExecutionPlan:
    """测试 ExecutionPlan 数据结构。"""

    def test_simple_plan_no_dependencies(self):
        """测试简单计划（无依赖）。"""
        plan = ExecutionPlan(
            steps=[
                ToolCall(plugin_id="tool_a", args={}, step_id=1, description="Step 1"),
                ToolCall(plugin_id="tool_b", args={}, step_id=2, description="Step 2"),
            ],
            dependencies={},
            reasoning="简单的两步计划"
        )

        # 初始状态：无已完成步骤
        ready = plan.get_ready_steps([])
        assert len(ready) == 2  # 两个步骤都就绪

        # 完成 step 1
        ready = plan.get_ready_steps([1])
        assert len(ready) == 1
        assert ready[0].step_id == 2

        # 全部完成
        assert not plan.is_complete([])
        assert not plan.is_complete([1])
        assert plan.is_complete([1, 2])

    def test_plan_with_dependencies(self):
        """测试带依赖的计划。"""
        plan = ExecutionPlan(
            steps=[
                ToolCall(plugin_id="fetch_data", args={}, step_id=1, description="获取数据"),
                ToolCall(plugin_id="filter_data", args={}, step_id=2, description="过滤数据"),
                ToolCall(plugin_id="aggregate_data", args={}, step_id=3, description="聚合数据"),
            ],
            dependencies={
                2: [1],  # step 2 依赖 step 1
                3: [2],  # step 3 依赖 step 2
            },
            reasoning="依赖链：fetch → filter → aggregate"
        )

        # 初始：只有 step 1 就绪
        ready = plan.get_ready_steps([])
        assert len(ready) == 1
        assert ready[0].step_id == 1

        # 完成 step 1 后：step 2 就绪
        ready = plan.get_ready_steps([1])
        assert len(ready) == 1
        assert ready[0].step_id == 2

        # 完成 step 1, 2 后：step 3 就绪
        ready = plan.get_ready_steps([1, 2])
        assert len(ready) == 1
        assert ready[0].step_id == 3

        # 全部完成
        assert plan.is_complete([1, 2, 3])

    def test_plan_with_parallel_steps(self):
        """测试并行步骤（无依赖冲突）。"""
        plan = ExecutionPlan(
            steps=[
                ToolCall(plugin_id="fetch_bilibili", args={}, step_id=1, description="获取B站数据"),
                ToolCall(plugin_id="fetch_xiaohongshu", args={}, step_id=2, description="获取小红书数据"),
                ToolCall(plugin_id="compare_data", args={}, step_id=3, description="对比数据"),
            ],
            dependencies={
                3: [1, 2],  # step 3 依赖 step 1 和 step 2
            },
            reasoning="并行获取数据，然后对比"
        )

        # 初始：step 1 和 step 2 都就绪（可并行）
        ready = plan.get_ready_steps([])
        assert len(ready) == 2
        assert {s.step_id for s in ready} == {1, 2}

        # 完成 step 1：step 2 仍就绪，step 3 不就绪
        ready = plan.get_ready_steps([1])
        assert len(ready) == 1
        assert ready[0].step_id == 2

        # 完成 step 1, 2：step 3 就绪
        ready = plan.get_ready_steps([1, 2])
        assert len(ready) == 1
        assert ready[0].step_id == 3


class TestStashReference:
    """测试 StashReference 依赖解析。"""

    def test_resolve_simple_reference(self):
        """测试简单引用（无 JSONPath）。"""
        # Mock data_stash
        data_stash = [
            DataReference(
                step_id=1,
                tool_name="fetch_data",
                data_id="data-123",
                summary="获取了10条数据",
                status="success"
            )
        ]

        # Mock data_store
        data_store = MagicMock()
        data_store.load.return_value = {"items": [1, 2, 3]}

        # 创建引用并解析
        ref = StashReference(step_id=1)
        result = ref.resolve(data_stash, data_store)

        assert result == {"items": [1, 2, 3]}
        data_store.load.assert_called_once_with("data-123")

    def test_resolve_with_json_path(self):
        """测试 JSONPath 提取字段。"""
        data_stash = [
            DataReference(
                step_id=1,
                tool_name="fetch_data",
                data_id="data-456",
                summary="数据",
                status="success"
            )
        ]

        data_store = MagicMock()
        data_store.load.return_value = {
            "data": {
                "id": "lg-result-1",
                "count": 100
            }
        }

        # 提取 data.id
        ref = StashReference(step_id=1, json_path="data.id")
        result = ref.resolve(data_stash, data_store)

        assert result == "lg-result-1"

    def test_resolve_missing_step(self):
        """测试引用不存在的步骤。"""
        data_stash = []
        data_store = MagicMock()

        ref = StashReference(step_id=99)

        with pytest.raises(ValueError, match="未找到 step_id=99"):
            ref.resolve(data_stash, data_store)

    def test_resolve_failed_step(self):
        """测试引用失败的步骤。"""
        data_stash = [
            DataReference(
                step_id=1,
                tool_name="fetch_data",
                data_id=None,
                summary="执行失败",
                status="error",
                error_message="网络错误"
            )
        ]
        data_store = MagicMock()

        ref = StashReference(step_id=1)

        with pytest.raises(ValueError, match="step_id=1 的执行失败"):
            ref.resolve(data_stash, data_store)


class TestExecutionEngine:
    """测试 ExecutionEngine 调度器。"""

    @pytest.fixture
    def mock_registry(self):
        """创建 mock ToolRegistry。"""
        registry = MagicMock(spec=ToolRegistry)
        return registry

    @pytest.fixture
    def mock_data_store(self):
        """创建 mock DataStore。"""
        store = MagicMock()
        store.save.return_value = "data-123"
        store.load.return_value = {"result": "success"}
        return store

    @pytest.fixture
    def mock_context(self, mock_data_store):
        """创建 mock ToolExecutionContext。"""
        context = MagicMock(spec=ToolExecutionContext)
        context.extras = {"data_store": mock_data_store}
        return context

    def test_execute_simple_plan(self, mock_registry, mock_data_store, mock_context):
        """测试执行简单计划（无依赖）。"""
        # 创建计划
        plan = ExecutionPlan(
            steps=[
                ToolCall(plugin_id="tool_a", args={"param": "value"}, step_id=1, description="Step 1"),
            ],
            dependencies={},
            reasoning="单步计划"
        )

        # Mock 工具执行结果
        from langgraph_agents.state import ToolExecutionPayload
        mock_result = ToolExecutionPayload(
            call=plan.steps[0],
            raw_output={"result": "success"},
            status="success"
        )
        mock_registry.execute.return_value = mock_result

        # 创建引擎并执行
        engine = ExecutionEngine(
            registry=mock_registry,
            data_store=mock_data_store
        )
        state = GraphState(
            original_query="test",
            completed_step_ids=[]
        )

        updated_state = engine.execute_plan(plan, state, mock_context)

        # 验证
        assert updated_state["completed_step_ids"] == [1]
        assert updated_state["last_tool_result"] == mock_result
        # 验证数据已保存
        assert len(updated_state["data_stash"]) == 1
        assert updated_state["data_stash"][0].step_id == 1
        assert updated_state["data_stash"][0].data_id == "data-123"
        mock_registry.execute.assert_called_once()
        mock_data_store.save.assert_called_once()

    def test_execute_plan_with_dependencies(self, mock_registry, mock_data_store, mock_context):
        """测试执行带依赖的计划。"""
        plan = ExecutionPlan(
            steps=[
                ToolCall(plugin_id="step1", args={}, step_id=1, description="Step 1"),
                ToolCall(plugin_id="step2", args={}, step_id=2, description="Step 2"),
            ],
            dependencies={
                2: [1],  # step 2 依赖 step 1
            },
            reasoning="依赖计划"
        )

        # Mock 工具执行
        from langgraph_agents.state import ToolExecutionPayload

        def mock_execute(call, context):
            return ToolExecutionPayload(
                call=call,
                raw_output={"step": call.step_id},
                status="success"
            )

        mock_registry.execute.side_effect = mock_execute

        # 执行
        engine = ExecutionEngine(
            registry=mock_registry,
            data_store=mock_data_store
        )
        state = GraphState(
            original_query="test",
            completed_step_ids=[]
        )

        updated_state = engine.execute_plan(plan, state, mock_context)

        # 验证：两个步骤都执行了
        assert updated_state["completed_step_ids"] == [1, 2]
        assert mock_registry.execute.call_count == 2
        # 验证两个步骤都保存了数据
        assert len(updated_state["data_stash"]) == 2
        assert mock_data_store.save.call_count == 2

    def test_execute_plan_with_error(self, mock_registry, mock_data_store, mock_context):
        """测试执行计划时遇到错误。"""
        plan = ExecutionPlan(
            steps=[
                ToolCall(plugin_id="failing_tool", args={}, step_id=1, description="Failing Step"),
            ],
            dependencies={},
            reasoning="错误测试"
        )

        # Mock 工具执行失败
        from langgraph_agents.state import ToolExecutionPayload
        mock_result = ToolExecutionPayload(
            call=plan.steps[0],
            raw_output={"error": "failed"},
            status="error",
            error_message="工具执行失败"
        )
        mock_registry.execute.return_value = mock_result

        # 执行
        engine = ExecutionEngine(
            registry=mock_registry,
            data_store=mock_data_store
        )
        state = GraphState(
            original_query="test",
            completed_step_ids=[]
        )

        updated_state = engine.execute_plan(plan, state, mock_context)

        # 验证：步骤标记为完成（避免死循环），但有错误记录
        assert updated_state["completed_step_ids"] == [1]
        assert updated_state["last_error"] == "工具执行失败"
        # 验证错误状态也保存到 data_stash
        assert len(updated_state["data_stash"]) == 1
        assert updated_state["data_stash"][0].status == "error"
        mock_data_store.save.assert_called_once()


class TestNestedDependencyResolution:
    """测试嵌套依赖解析（修复后的功能）。"""

    @pytest.fixture
    def mock_data_store(self):
        """创建 mock DataStore。"""
        store = MagicMock()
        # 模拟保存和加载数据
        saved_data = {}

        def save(data):
            data_id = f"data-{len(saved_data)}"
            saved_data[data_id] = data
            return data_id

        def load(data_id):
            return saved_data.get(data_id)

        store.save.side_effect = save
        store.load.side_effect = load
        return store

    @pytest.fixture
    def mock_registry(self):
        """创建 mock ToolRegistry。"""
        registry = MagicMock(spec=ToolRegistry)

        def execute(call, context):
            from langgraph_agents.state import ToolExecutionPayload
            # 根据不同工具返回不同数据
            if call.plugin_id == "fetch_data":
                return ToolExecutionPayload(
                    call=call,
                    raw_output={
                        "items": [
                            {"id": "item-1", "name": "Item 1", "value": 100},
                            {"id": "item-2", "name": "Item 2", "value": 200}
                        ]
                    },
                    status="success"
                )
            elif call.plugin_id == "filter_data":
                # 使用引用的数据
                return ToolExecutionPayload(
                    call=call,
                    raw_output={"filtered_count": 1},
                    status="success"
                )
            else:
                return ToolExecutionPayload(
                    call=call,
                    raw_output={"result": "ok"},
                    status="success"
                )

        registry.execute.side_effect = execute
        return registry

    @pytest.fixture
    def mock_context(self, mock_data_store):
        """创建 mock ToolExecutionContext。"""
        context = MagicMock(spec=ToolExecutionContext)
        context.extras = {"data_store": mock_data_store}
        return context

    def test_nested_ref_in_dict(self, mock_registry, mock_data_store, mock_context):
        """测试嵌套在 dict 中的引用。"""
        plan = ExecutionPlan(
            steps=[
                ToolCall(plugin_id="fetch_data", args={}, step_id=1, description="获取数据"),
                ToolCall(
                    plugin_id="filter_data",
                    args={
                        "source_ref": {"$ref": {"step_id": 1}},
                        "conditions": {
                            "field": "id",
                            "value": {"$ref": {"step_id": 1, "json_path": "items.0.id"}}
                        }
                    },
                    step_id=2,
                    description="过滤数据"
                ),
            ],
            dependencies={2: [1]},
            reasoning="测试嵌套引用"
        )

        engine = ExecutionEngine(
            registry=mock_registry,
            data_store=mock_data_store
        )
        state = GraphState(
            original_query="test nested ref",
            completed_step_ids=[]
        )

        updated_state = engine.execute_plan(plan, state, mock_context)

        # 验证执行完成
        assert updated_state["completed_step_ids"] == [1, 2]
        assert len(updated_state["data_stash"]) == 2

        # 验证第二步的调用参数（检查引用是否被解析）
        second_call = mock_registry.execute.call_args_list[1][0][0]
        # source_ref 应该被解析为实际数据
        assert "items" in second_call.args["source_ref"]
        # 嵌套的 value 引用应该被解析为 "item-1"
        assert second_call.args["conditions"]["value"] == "item-1"

    def test_nested_ref_in_list(self, mock_registry, mock_data_store, mock_context):
        """测试嵌套在 list 中的引用（如 source_refs）。"""
        plan = ExecutionPlan(
            steps=[
                ToolCall(plugin_id="fetch_data", args={}, step_id=1, description="获取数据1"),
                ToolCall(plugin_id="fetch_data", args={}, step_id=2, description="获取数据2"),
                ToolCall(
                    plugin_id="compare_data",
                    args={
                        "source_refs": [
                            {"$ref": {"step_id": 1}},
                            {"$ref": {"step_id": 2}}
                        ]
                    },
                    step_id=3,
                    description="对比数据"
                ),
            ],
            dependencies={3: [1, 2]},
            reasoning="测试数组中的引用"
        )

        engine = ExecutionEngine(
            registry=mock_registry,
            data_store=mock_data_store
        )
        state = GraphState(
            original_query="test list ref",
            completed_step_ids=[]
        )

        updated_state = engine.execute_plan(plan, state, mock_context)

        # 验证执行完成
        assert updated_state["completed_step_ids"] == [1, 2, 3]
        assert len(updated_state["data_stash"]) == 3

        # 验证第三步的调用参数
        third_call = mock_registry.execute.call_args_list[2][0][0]
        # source_refs 数组应该被解析为实际数据
        assert isinstance(third_call.args["source_refs"], list)
        assert len(third_call.args["source_refs"]) == 2
        assert "items" in third_call.args["source_refs"][0]
        assert "items" in third_call.args["source_refs"][1]

    def test_deeply_nested_ref(self, mock_registry, mock_data_store, mock_context):
        """测试深层嵌套的引用。"""
        plan = ExecutionPlan(
            steps=[
                ToolCall(plugin_id="fetch_data", args={}, step_id=1, description="获取数据"),
                ToolCall(
                    plugin_id="complex_tool",
                    args={
                        "config": {
                            "filters": [
                                {
                                    "field": "id",
                                    "operator": "eq",
                                    "value": {"$ref": {"step_id": 1, "json_path": "items.0.id"}}
                                }
                            ]
                        }
                    },
                    step_id=2,
                    description="复杂工具"
                ),
            ],
            dependencies={2: [1]},
            reasoning="测试深层嵌套引用"
        )

        engine = ExecutionEngine(
            registry=mock_registry,
            data_store=mock_data_store
        )
        state = GraphState(
            original_query="test deeply nested ref",
            completed_step_ids=[]
        )

        updated_state = engine.execute_plan(plan, state, mock_context)

        # 验证执行完成
        assert updated_state["completed_step_ids"] == [1, 2]

        # 验证第二步的调用参数
        second_call = mock_registry.execute.call_args_list[1][0][0]
        # 深层嵌套的 value 引用应该被解析
        assert second_call.args["config"]["filters"][0]["value"] == "item-1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
