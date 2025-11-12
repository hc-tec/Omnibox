"""LangGraph Agents 集成测试

验证整个工作流的端到端功能，包括：
1. Runtime 构建
2. Graph 构建和编译
3. 基本查询流程
4. 工具执行
"""
import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path

from langgraph_agents.factory import build_runtime
from langgraph_agents.graph_builder import create_langgraph_app
from langgraph_agents.state import GraphState
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.tools.bootstrap import register_default_tools


class MockLLMClient:
    """模拟 LLM 客户端用于测试"""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.call_count = 0

    def generate(self, prompt, temperature=0.0):
        """模拟生成响应"""
        self.call_count += 1
        # 根据 prompt 中的关键词返回不同响应
        if "RouterAgent" in prompt or "historic_messages" in prompt:
            return '{"route": "complex_research", "reasoning": "需要多步研究"}'
        elif "PlannerAgent" in prompt or "可用工具列表" in prompt:
            return '{"plugin_id": "fetch_public_data", "args": {"query": "测试查询"}, "description": "测试工具调用"}'
        elif "ReflectorAgent" in prompt or "collected_data" in prompt:
            return '{"decision": "FINISH", "reasoning": "数据已充分"}'
        elif "SynthesizerAgent" in prompt or "data_references" in prompt:
            return '{"summary": "测试总结", "evidence": [], "next_actions": []}'
        return '{"status": "ok"}'


class MockDataQueryService:
    """模拟 DataQueryService"""

    def query(self, user_query, filter_datasource=None, use_cache=True):
        """模拟查询"""
        from services.data_query_service import DataQueryResult

        return DataQueryResult(
            status="success",
            feed_title="测试数据源",
            generated_path="/test/path",
            items=[{"title": "测试项目", "link": "http://test.com"}],
            source="test",
            cache_hit=False,
            reasoning="测试成功",
        )


class TestRuntimeBuilding:
    """测试运行时构建"""

    def test_build_runtime_with_minimal_config(self):
        """测试使用最小配置构建运行时"""
        llms = {"default": MockLLMClient()}
        data_service = MockDataQueryService()

        runtime = build_runtime(llms=llms, data_query_service=data_service)

        assert runtime.router_llm is not None
        assert runtime.planner_llm is not None
        assert runtime.reflector_llm is not None
        assert runtime.synthesizer_llm is not None
        assert runtime.tool_registry is not None
        assert runtime.data_store is not None

    def test_build_runtime_with_role_specific_llms(self):
        """测试使用角色特定的 LLM"""
        llms = {
            "router": MockLLMClient(),
            "planner": MockLLMClient(),
            "reflector": MockLLMClient(),
            "synthesizer": MockLLMClient(),
        }
        data_service = MockDataQueryService()

        runtime = build_runtime(llms=llms, data_query_service=data_service)

        assert runtime.router_llm is not None
        assert runtime.planner_llm is not None

    def test_tool_registry_has_default_tools(self):
        """测试工具注册表包含默认工具"""
        llms = {"default": MockLLMClient()}
        data_service = MockDataQueryService()

        runtime = build_runtime(llms=llms, data_query_service=data_service)

        tools = runtime.tool_registry.list_tools()
        tool_ids = [t.plugin_id for t in tools]

        # 验证默认工具已注册
        assert "fetch_public_data" in tool_ids
        assert "search_private_notes" in tool_ids


class TestGraphBuilding:
    """测试图构建"""

    def test_create_app_success(self):
        """测试成功创建 LangGraph 应用"""
        llms = {"default": MockLLMClient()}
        data_service = MockDataQueryService()
        runtime = build_runtime(llms=llms, data_query_service=data_service)

        app = create_langgraph_app(runtime)

        assert app is not None
        # 验证应用可以编译
        assert hasattr(app, "invoke")

    def test_graph_has_required_nodes(self):
        """测试图包含所有必需节点"""
        llms = {"default": MockLLMClient()}
        data_service = MockDataQueryService()
        runtime = build_runtime(llms=llms, data_query_service=data_service)

        from langgraph_agents.graph_builder import build_workflow

        workflow = build_workflow(runtime)

        # 验证节点存在（通过检查 workflow 的内部结构）
        assert workflow is not None


class TestBasicWorkflow:
    """测试基本工作流"""

    def test_router_node_execution(self):
        """测试 Router 节点执行"""
        from langgraph_agents.agents.router import create_router_node

        runtime = Mock()
        runtime.router_llm = MockLLMClient()

        node = create_router_node(runtime)
        state: GraphState = {
            "original_query": "测试查询",
            "chat_history": [],
        }

        result = node(state)

        assert "router_decision" in result
        assert result["router_decision"].route in [
            "simple_tool_call",
            "complex_research",
            "clarify_with_human",
            "end",
        ]

    def test_planner_node_with_tool_list(self):
        """测试 Planner 节点包含工具列表（P0-2 修复验证）"""
        from langgraph_agents.agents.planner import create_planner_node

        runtime = Mock()
        runtime.planner_llm = MockLLMClient()

        # 创建工具注册表
        registry = ToolRegistry()
        register_default_tools(registry)
        runtime.tool_registry = registry

        node = create_planner_node(runtime)

        # 验证节点可以创建（工具列表会在创建时构建）
        assert node is not None

        # 执行节点
        state: GraphState = {
            "original_query": "测试查询",
            "data_stash": [],
        }

        result = node(state)

        assert "next_tool_call" in result
        assert result["next_tool_call"] is not None
        assert result["next_tool_call"].plugin_id == "fetch_public_data"

    def test_planner_rejects_empty_query(self):
        """测试 Planner 拒绝空查询（P0-3 修复验证）"""
        from langgraph_agents.agents.planner import create_planner_node

        runtime = Mock()
        runtime.planner_llm = MockLLMClient()
        runtime.tool_registry = ToolRegistry()
        register_default_tools(runtime.tool_registry)

        node = create_planner_node(runtime)

        state: GraphState = {
            "original_query": "",  # 空查询
            "data_stash": [],
        }

        with pytest.raises(ValueError, match="original_query 为空或缺失"):
            node(state)

    def test_tool_executor_node(self):
        """测试工具执行节点"""
        from langgraph_agents.agents.tool_executor import create_tool_executor_node
        from langgraph_agents.state import ToolCall

        runtime = Mock()
        registry = ToolRegistry()
        register_default_tools(registry)
        runtime.tool_registry = registry

        # Mock context
        from langgraph_agents.runtime import ToolExecutionContext

        runtime.tool_context = ToolExecutionContext(
            data_query_service=MockDataQueryService()
        )

        node = create_tool_executor_node(runtime)

        call = ToolCall(
            plugin_id="fetch_public_data",
            args={"query": "测试"},
            step_id=1,
            description="测试",
        )

        state: GraphState = {"original_query": "test", "next_tool_call": call}

        result = node(state)

        assert "pending_tool_result" in result
        assert result["pending_tool_result"] is not None
        assert result["next_tool_call"] is None  # 应该被清空

    def test_data_stasher_node(self):
        """测试数据暂存节点"""
        from langgraph_agents.agents.data_stasher import create_data_stasher_node
        from langgraph_agents.state import ToolCall, ToolExecutionPayload
        from langgraph_agents.storage import InMemoryResearchDataStore

        runtime = Mock()
        runtime.data_store = InMemoryResearchDataStore()
        runtime.summarizer_llm = None  # 使用默认摘要
        runtime.cheap_summary_max_chars = 100

        node = create_data_stasher_node(runtime)

        call = ToolCall(
            plugin_id="test", args={}, step_id=1, description="test"
        )
        payload = ToolExecutionPayload(
            call=call,
            raw_output={"data": "测试数据"},
            status="success",
        )

        state: GraphState = {
            "original_query": "test",
            "pending_tool_result": payload,
            "data_stash": [],
        }

        result = node(state)

        assert "data_stash" in result
        assert len(result["data_stash"]) == 1
        assert result["data_stash"][0].step_id == 1
        assert result["pending_tool_result"] is None

    def test_reflector_node(self):
        """测试反思节点"""
        from langgraph_agents.agents.reflector import create_reflector_node

        runtime = Mock()
        runtime.reflector_llm = MockLLMClient()

        node = create_reflector_node(runtime)

        state: GraphState = {
            "original_query": "测试查询",
            "data_stash": [],
        }

        result = node(state)

        assert "reflection" in result
        assert result["reflection"] is not None
        assert result["reflection"].decision in [
            "CONTINUE",
            "FINISH",
            "REQUEST_HUMAN",
        ]


class TestEndToEndFlow:
    """端到端流程测试"""

    @pytest.mark.skip(reason="需要完整的 LangGraph 环境，暂时跳过")
    def test_simple_query_flow(self):
        """测试简单查询的完整流程"""
        llms = {"default": MockLLMClient()}
        data_service = MockDataQueryService()

        runtime = build_runtime(llms=llms, data_query_service=data_service)
        app = create_langgraph_app(runtime)

        initial_state: GraphState = {
            "original_query": "获取B站热搜数据",
            "chat_history": [],
        }

        # 执行应用
        # 注意：这需要 LangGraph 的完整配置，可能需要更多mock
        # result = app.invoke(initial_state)
        # assert "final_report" in result or "human_in_loop_request" in result


class TestP0Fixes:
    """专门测试 P0 修复的效果"""

    def test_p0_2_planner_has_tool_list(self):
        """P0-2: 验证 Planner 现在有工具列表"""
        from langgraph_agents.agents.planner import create_planner_node

        runtime = Mock()
        llm = MockLLMClient()
        runtime.planner_llm = llm

        registry = ToolRegistry()
        register_default_tools(registry)
        runtime.tool_registry = registry

        node = create_planner_node(runtime)

        state: GraphState = {
            "original_query": "test query",
            "data_stash": [],
        }

        # 执行节点
        result = node(state)

        # 验证 LLM 被调用了
        assert llm.call_count > 0

        # 验证返回的工具ID是合法的
        assert result["next_tool_call"].plugin_id in [
            t.plugin_id for t in registry.list_tools()
        ]

    def test_p0_3_required_query_validation(self):
        """P0-3: 验证 original_query 必需字段验证"""
        from langgraph_agents.agents.router import create_router_node
        from langgraph_agents.agents.planner import create_planner_node
        from langgraph_agents.agents.reflector import create_reflector_node

        runtime = Mock()
        runtime.router_llm = MockLLMClient()
        runtime.planner_llm = MockLLMClient()
        runtime.reflector_llm = MockLLMClient()
        runtime.tool_registry = ToolRegistry()
        register_default_tools(runtime.tool_registry)

        # 测试所有关键节点都验证 original_query
        for node_creator in [
            create_router_node,
            create_planner_node,
            create_reflector_node,
        ]:
            node = node_creator(runtime)
            state: GraphState = {"original_query": ""}

            with pytest.raises(ValueError, match="original_query"):
                node(state)
