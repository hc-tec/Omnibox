"""V6.0 ResearchAgent 单元测试

验证单Agent架构的核心功能：
1. Agent 决策逻辑（CONTINUE/FINISH/REQUEST_CLARIFICATION）
2. 工具调用生成
3. 最终报告生成
4. 错误处理
"""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch

from langgraph_agents.agents.research_agent import (
    create_research_agent_node,
    _format_data_stash,
    _format_working_memory,
    _extract_executed_tools,
    _process_agent_decision,
)
from langgraph_agents.state import GraphState, DataReference, ToolCall
from langgraph_agents.runtime import LangGraphRuntime


class MockLLMClient:
    """模拟 LLM 客户端"""

    def __init__(self, response: str):
        self.response = response
        self.call_count = 0
        self.last_prompt = None
        self.tracker = None
        self.tracker_role = None

    def generate(self, prompt, temperature=0.0, role=None):
        self.call_count += 1
        self.last_prompt = prompt
        return self.response

    def set_tracker(self, tracker, role=None):
        self.tracker = tracker
        self.tracker_role = role


class MockToolRegistry:
    """模拟工具注册表"""

    def list_tools(self):
        return [
            Mock(
                plugin_id="fetch_public_data",
                description="获取公共数据",
                schema={"properties": {"query": {}}},
            ),
            Mock(
                plugin_id="filter_data",
                description="过滤数据",
                schema={"properties": {"source_ref": {}, "conditions": {}}},
            ),
        ]

    def get(self, plugin_id):
        return Mock(execution_mode="full")


class MockDataStore:
    """模拟数据存储"""

    def save(self, data):
        return "lg-test-123"

    def load(self, data_id):
        return {"items": [{"title": "测试"}]}


class TestFormatHelpers:
    """测试格式化辅助函数"""

    def test_format_data_stash_empty(self):
        """测试空数据stash"""
        result = _format_data_stash([])
        assert result == "暂无数据"

    def test_format_data_stash_with_items(self):
        """测试有数据的stash"""
        data_stash = [
            DataReference(
                step_id=1,
                tool_name="fetch_public_data",
                data_id="lg-abc123",
                summary="获取了 30 条数据",
                status="success",
            ),
            DataReference(
                step_id=2,
                tool_name="filter_data",
                data_id="lg-def456",
                summary="筛选后剩余 5 条",
                status="success",
            ),
        ]
        result = _format_data_stash(data_stash)
        assert "[Step 1] fetch_public_data (✓)" in result
        assert "[Step 2] filter_data (✓)" in result
        assert "lg-abc123" in result
        assert "lg-def456" in result

    def test_format_data_stash_with_error(self):
        """测试包含错误的stash"""
        data_stash = [
            DataReference(
                step_id=1,
                tool_name="fetch_public_data",
                summary="获取失败",
                status="error",
                error_message="网络错误",
            ),
        ]
        result = _format_data_stash(data_stash)
        assert "[Step 1] fetch_public_data (✗)" in result

    def test_format_working_memory_empty(self):
        """测试空工作记忆"""
        result = _format_working_memory({})
        assert result == "暂无"

    def test_format_working_memory_with_items(self):
        """测试有内容的工作记忆"""
        working_memory = {
            "search_data_sources": {
                "step_id": 1,
                "status": "success",
                "description": "探索数据源",
            }
        }
        result = _format_working_memory(working_memory)
        assert "[Step 1] search_data_sources (success)" in result

    def test_format_working_memory_skips_filter_datasource(self):
        """测试跳过内部标记"""
        working_memory = {
            "filter_datasource": "bilibili",  # 应该被跳过
            "search_data_sources": {
                "step_id": 1,
                "status": "success",
                "description": "探索数据源",
            },
        }
        result = _format_working_memory(working_memory)
        assert "filter_datasource" not in result
        assert "search_data_sources" in result

    def test_format_working_memory_component_contracts(self):
        """测试组件契约格式化"""
        working_memory = {
            "component_contracts": {
                "contracts": {
                    "StatisticCard-contract-v2": {
                        "component_id": "StatisticCard",
                        "contract_id": "StatisticCard-contract-v2",
                        "status": "planned",
                        "targets": ["$step.2"],
                        "description": "统计B站热搜数量",
                    }
                }
            }
        }
        result = _format_working_memory(working_memory)
        assert "组件契约登记" in result
        assert "StatisticCard" in result
        assert "$step.2" in result

    def test_extract_executed_tools_empty(self):
        """测试空执行记录"""
        result = _extract_executed_tools([])
        assert result == "暂无"

    def test_extract_executed_tools_with_items(self):
        """测试有执行记录"""
        data_stash = [
            DataReference(step_id=1, tool_name="fetch_public_data", summary="", status="success"),
            DataReference(step_id=2, tool_name="filter_data", summary="", status="success"),
        ]
        result = _extract_executed_tools(data_stash)
        assert "fetch_public_data(success)" in result
        assert "filter_data(success)" in result
        assert "→" in result


class TestProcessAgentDecision:
    """测试Agent决策处理"""

    def test_process_finish_decision(self):
        """测试FINISH决策"""
        data = {
            "decision": "FINISH",
            "reasoning": "任务已完成",
            "final_report": {
                "summary": "核心发现",
                "evidence": [{"source": "test", "insight": "测试洞察"}],
                "next_actions": [],
            },
        }
        state: GraphState = {"original_query": "测试查询", "data_stash": []}
        result = _process_agent_decision(data, 1, state)

        assert result["agent_decision"] == "FINISH"
        assert result["next_tool_call"] is None
        assert "核心发现" in result["final_report"]

    def test_process_continue_decision_with_tool_call(self):
        """测试CONTINUE决策带工具调用"""
        data = {
            "decision": "CONTINUE",
            "reasoning": "需要获取数据",
            "tool_call": {
                "plugin_id": "fetch_public_data",
                "args": {"query": "测试查询"},
                "description": "获取测试数据",
            },
        }
        state: GraphState = {"original_query": "测试查询", "data_stash": []}
        result = _process_agent_decision(data, 1, state)

        assert result["agent_decision"] == "CONTINUE"
        assert result["next_tool_call"] is not None
        assert result["next_tool_call"].plugin_id == "fetch_public_data"
        assert result["next_tool_call"].step_id == 1

    def test_process_continue_decision_without_tool_call(self):
        """测试CONTINUE决策但无工具调用（应强制FINISH）"""
        data = {
            "decision": "CONTINUE",
            "reasoning": "继续",
            "tool_call": {},  # 空工具调用
        }
        state: GraphState = {"original_query": "测试查询", "data_stash": []}
        result = _process_agent_decision(data, 1, state)

        # 应该强制转为FINISH
        assert result["agent_decision"] == "FINISH"
        assert result["next_tool_call"] is None

    def test_process_request_clarification_decision(self):
        """测试REQUEST_CLARIFICATION决策"""
        data = {
            "decision": "REQUEST_CLARIFICATION",
            "reasoning": "需要用户选择平台",
            "clarification": {
                "question": "您想查询哪个平台？",
                "options": ["B站", "小红书"],
            },
        }
        state: GraphState = {"original_query": "测试查询", "data_stash": []}
        result = _process_agent_decision(data, 1, state)

        assert result["agent_decision"] == "REQUEST_CLARIFICATION"
        assert result["next_tool_call"] is not None
        assert result["next_tool_call"].plugin_id == "ask_user_clarification"

    def test_process_continue_updates_component_contracts(self):
        """记录组件契约时应写入 working_memory"""
        data = {
            "decision": "CONTINUE",
            "reasoning": "统计指标卡",
            "tool_call": {
                "plugin_id": "data_operator",
                "args": {"source_ref": "$step.1", "instruction": "统计数量"},
                "description": "统计热搜数量",
            },
            "component_contract": {
                "component_id": "StatisticCard",
                "contract_id": "StatisticCard-contract-v2",
                "status": "planned",
                "description": "输出数字卡片",
            },
        }
        state: GraphState = {"original_query": "测试", "data_stash": [], "working_memory": {}}
        result = _process_agent_decision(data, 1, state)

        working_memory = result.get("working_memory")
        assert working_memory is not None
        contracts = working_memory["component_contracts"]["contracts"]
        assert "StatisticCard-contract-v2" in contracts
        assert contracts["StatisticCard-contract-v2"]["targets"] == ["$step.1"]


class TestResearchAgentNode:
    """测试ResearchAgent节点"""

    def _create_mock_runtime(self, llm_response: str):
        """创建模拟运行时"""
        runtime = Mock(spec=LangGraphRuntime)
        runtime.planner_llm = MockLLMClient(llm_response)
        runtime.tool_registry = MockToolRegistry()
        runtime.data_store = MockDataStore()
        return runtime

    def test_agent_node_continue_decision(self):
        """测试Agent节点返回CONTINUE"""
        llm_response = json.dumps({
            "decision": "CONTINUE",
            "reasoning": "需要获取数据",
            "tool_call": {
                "plugin_id": "fetch_public_data",
                "args": {"query": "B站视频"},
                "description": "获取B站视频数据",
            },
        })
        runtime = self._create_mock_runtime(llm_response)

        node = create_research_agent_node(runtime)
        state: GraphState = {
            "original_query": "查询B站视频",
            "data_stash": [],
            "working_memory": {},
        }

        result = node(state)

        assert result["agent_decision"] == "CONTINUE"
        assert result["next_tool_call"].plugin_id == "fetch_public_data"
        # Prompt 应包含组件契约提示
        prompt = runtime.planner_llm.last_prompt
        assert "组件契约参考" in prompt
        assert "StatisticCard-contract-v2" in prompt

    def test_agent_node_finish_decision(self):
        """测试Agent节点返回FINISH"""
        llm_response = json.dumps({
            "decision": "FINISH",
            "reasoning": "数据已获取完成",
            "final_report": {
                "summary": "成功获取了30条视频数据",
                "evidence": [],
                "next_actions": [],
            },
        })
        runtime = self._create_mock_runtime(llm_response)

        node = create_research_agent_node(runtime)
        state: GraphState = {
            "original_query": "查询B站视频",
            "data_stash": [
                DataReference(
                    step_id=1,
                    tool_name="fetch_public_data",
                    data_id="lg-abc",
                    summary="获取了30条视频",
                    status="success",
                ),
            ],
            "working_memory": {},
        }

        result = node(state)

        assert result["agent_decision"] == "FINISH"
        assert result["next_tool_call"] is None
        assert "成功获取" in result["final_report"]

    def test_agent_node_with_tool_status_check(self):
        """测试Agent检查工具状态"""
        llm_response = json.dumps({
            "decision": "REQUEST_CLARIFICATION",
            "reasoning": "工具请求用户输入",
            "clarification": {
                "question": "请选择平台",
                "options": ["B站", "小红书"],
            },
        })
        runtime = self._create_mock_runtime(llm_response)

        node = create_research_agent_node(runtime)

        # 模拟上一步工具返回 needs_user_input
        last_tool_result = Mock()
        last_tool_result.status = "needs_user_input"

        state: GraphState = {
            "original_query": "查询视频",
            "data_stash": [],
            "working_memory": {},
            "last_tool_result": last_tool_result,
        }

        result = node(state)

        # 应该包含工具状态提示
        assert "needs_user_input" in runtime.planner_llm.last_prompt

    def test_agent_node_empty_query_raises_error(self):
        """测试空查询抛出错误"""
        runtime = self._create_mock_runtime("{}")

        node = create_research_agent_node(runtime)
        state: GraphState = {
            "original_query": "",
            "data_stash": [],
            "working_memory": {},
        }

        with pytest.raises(ValueError, match="original_query 为空"):
            node(state)

    def test_agent_node_llm_parse_error_fallback(self):
        """测试LLM解析错误时的降级处理"""
        # 返回无效JSON
        runtime = self._create_mock_runtime("这不是有效的JSON")

        node = create_research_agent_node(runtime)
        state: GraphState = {
            "original_query": "测试查询",
            "data_stash": [],
            "working_memory": {},
        }

        result = node(state)

        # 应该返回错误报告
        assert "final_report" in result
        assert "error" in result["final_report"].lower() or "错误" in result["final_report"]


class TestResearchAgentIntegration:
    """ResearchAgent集成测试"""

    def test_multi_step_workflow(self):
        """测试多步工作流"""
        # 第一次调用：CONTINUE，调用fetch_public_data
        response1 = json.dumps({
            "decision": "CONTINUE",
            "reasoning": "需要先获取数据",
            "tool_call": {
                "plugin_id": "fetch_public_data",
                "args": {"query": "影视飓风视频"},
                "description": "获取影视飓风投稿视频",
            },
        })

        # 第二次调用：CONTINUE，调用filter_data
        response2 = json.dumps({
            "decision": "CONTINUE",
            "reasoning": "需要筛选包含英雄联盟的视频",
            "tool_call": {
                "plugin_id": "filter_data",
                "args": {
                    "source_ref": "lg-abc123",
                    "conditions": {"title": {"$contains": "英雄联盟"}},
                },
                "description": "筛选标题包含英雄联盟的视频",
            },
        })

        # 第三次调用：FINISH
        response3 = json.dumps({
            "decision": "FINISH",
            "reasoning": "筛选完成",
            "final_report": {
                "summary": "找到3条包含英雄联盟的视频",
                "evidence": [{"source": "lg-filtered", "insight": "筛选结果"}],
                "next_actions": [],
            },
        })

        responses = [response1, response2, response3]
        call_index = [0]

        class MultiResponseLLM:
            def generate(self, prompt, temperature=0.0, role=None):
                response = responses[call_index[0]]
                call_index[0] += 1
                return response

        runtime = Mock(spec=LangGraphRuntime)
        runtime.planner_llm = MultiResponseLLM()
        runtime.tool_registry = MockToolRegistry()
        runtime.data_store = MockDataStore()

        node = create_research_agent_node(runtime)

        # 第一步
        state1: GraphState = {
            "original_query": "影视飓风视频中包含英雄联盟的",
            "data_stash": [],
            "working_memory": {},
        }
        result1 = node(state1)
        assert result1["agent_decision"] == "CONTINUE"
        assert result1["next_tool_call"].plugin_id == "fetch_public_data"

        # 第二步（假设工具已执行）
        state2: GraphState = {
            "original_query": "影视飓风视频中包含英雄联盟的",
            "data_stash": [
                DataReference(
                    step_id=1,
                    tool_name="fetch_public_data",
                    data_id="lg-abc123",
                    summary="获取了30条视频",
                    status="success",
                ),
            ],
            "working_memory": {},
        }
        result2 = node(state2)
        assert result2["agent_decision"] == "CONTINUE"
        assert result2["next_tool_call"].plugin_id == "filter_data"

        # 第三步（筛选完成）
        state3: GraphState = {
            "original_query": "影视飓风视频中包含英雄联盟的",
            "data_stash": [
                DataReference(
                    step_id=1,
                    tool_name="fetch_public_data",
                    data_id="lg-abc123",
                    summary="获取了30条视频",
                    status="success",
                ),
                DataReference(
                    step_id=2,
                    tool_name="filter_data",
                    data_id="lg-filtered",
                    summary="筛选后剩余3条",
                    status="success",
                ),
            ],
            "working_memory": {},
        }
        result3 = node(state3)
        assert result3["agent_decision"] == "FINISH"
        assert "3条" in result3["final_report"] or "找到" in result3["final_report"]
