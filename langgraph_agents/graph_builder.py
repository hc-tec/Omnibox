"""
LangGraph V6.0 构建入口。

V6.0 架构：单Agent + 复杂工具层
- Router 保留作为前置分流（减少简单查询的开销）
- ResearchAgent 融合 Planner + Reflector + Synthesizer
- 工具层保持不变
"""

from __future__ import annotations

from typing import Literal, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .agents import (
    data_stasher,
    human,
    research_agent,
    router,
    simple_chat,
    tool_executor,
)
from .runtime import LangGraphRuntime
from .state import GraphState


def _router_edge(state: GraphState) -> Literal["to_simple", "to_research", "to_human", "to_end"]:
    """
    Router 决策边。

    根据 RouterAgent 的决策路由到不同节点：
    - simple_tool_call: 简单查询 → simple_chat 节点
    - complex_research: 复杂研究 → research_agent 节点
    - clarify_with_human: 需要澄清 → wait_for_human 节点
    - end: 无需处理 → END
    """
    decision = state.get("router_decision")
    if not decision:
        return "to_research"

    if decision.route == "simple_tool_call":
        return "to_simple"
    elif decision.route == "complex_research":
        return "to_research"
    elif decision.route == "clarify_with_human":
        return "to_human"
    else:  # end
        return "to_end"


def _research_agent_edge(
    state: GraphState,
) -> Literal["to_tool_executor", "to_end", "to_human"]:
    """
    ResearchAgent 决策边。

    根据 Agent 的决策路由：
    - CONTINUE + 有 tool_call → tool_executor
    - FINISH → END
    - REQUEST_CLARIFICATION → wait_for_human
    """
    agent_decision = state.get("agent_decision")
    next_tool_call = state.get("next_tool_call")

    if agent_decision == "FINISH":
        return "to_end"

    if agent_decision == "REQUEST_CLARIFICATION":
        # 如果有 tool_call（ask_user_clarification），执行它
        if next_tool_call:
            return "to_tool_executor"
        return "to_human"

    # CONTINUE 或无决策
    if next_tool_call:
        return "to_tool_executor"

    # 没有工具调用，结束
    return "to_end"


def _create_after_tool_execution_edge(runtime: LangGraphRuntime):
    """
    创建工具执行后的条件路由函数。

    使用闭包捕获 runtime，以便在条件边中访问工具注册表。
    """
    def edge_fn(state: GraphState) -> Literal["to_research_lightweight", "to_data_stasher"]:
        """
        根据工具的 execution_mode 决定流程：
        - lightweight: 直接返回 ResearchAgent（跳过 DataStasher）
        - full: 进入 DataStasher（完整流程）
        """
        pending = state.get("pending_tool_result")
        if not pending or not pending.call:
            return "to_data_stasher"

        try:
            tool_spec = runtime.tool_registry.get(pending.call.plugin_id)
            if tool_spec.execution_mode == "lightweight":
                return "to_research_lightweight"
            else:
                return "to_data_stasher"
        except KeyError:
            return "to_data_stasher"

    return edge_fn


def build_workflow(runtime: LangGraphRuntime) -> StateGraph:
    """
    构建 LangGraph V6.0 工作流。

    节点：
    - router: 入口路由决策（保留）
    - simple_chat: 简单查询快速响应
    - research_agent: 单Agent研究节点（融合 Planner + Reflector + Synthesizer）
    - tool_executor: 工具执行
    - data_stasher: 数据暂存和摘要
    - wait_for_human: 人机交互
    """
    workflow = StateGraph(GraphState)

    # 添加所有节点
    workflow.add_node("router", router.create_router_node(runtime))
    workflow.add_node("simple_chat", simple_chat.create_simple_chat_node())
    workflow.add_node("research_agent", research_agent.create_research_agent_node(runtime))
    workflow.add_node("tool_executor", tool_executor.create_tool_executor_node(runtime))
    workflow.add_node("data_stasher", data_stasher.create_data_stasher_node(runtime))
    workflow.add_node("wait_for_human", human.create_wait_for_human_node())

    # 轻量模式处理节点
    def lightweight_result_handler(state: GraphState) -> dict:
        """处理轻量工具结果：将结果添加到 working_memory。"""
        pending_result = state.get("pending_tool_result")
        if not pending_result:
            return {}

        working_memory = dict(state.get("working_memory", {}))

        if pending_result.call:
            working_memory[pending_result.call.plugin_id] = {
                "step_id": pending_result.call.step_id,
                "result": pending_result.raw_output,
                "status": pending_result.status,
                "description": pending_result.call.description,
            }

        return {
            "working_memory": working_memory,
            "pending_tool_result": None,
            "last_tool_result": pending_result,  # 保留给 ResearchAgent 检查
        }

    workflow.add_node("lightweight_handler", lightweight_result_handler)

    # 从 START 到 router
    workflow.add_edge(START, "router")

    # Router 的条件分支
    workflow.add_conditional_edges(
        "router",
        _router_edge,
        {
            "to_simple": "simple_chat",
            "to_research": "research_agent",
            "to_human": "wait_for_human",
            "to_end": END,
        },
    )

    # ResearchAgent 的条件分支
    workflow.add_conditional_edges(
        "research_agent",
        _research_agent_edge,
        {
            "to_tool_executor": "tool_executor",
            "to_end": END,
            "to_human": "wait_for_human",
        },
    )

    # 工具执行后的条件路由
    workflow.add_conditional_edges(
        "tool_executor",
        _create_after_tool_execution_edge(runtime),
        {
            "to_research_lightweight": "lightweight_handler",
            "to_data_stasher": "data_stasher",
        },
    )

    # 轻量模式循环回 ResearchAgent
    workflow.add_edge("lightweight_handler", "research_agent")

    # 完整模式：DataStasher 后回到 ResearchAgent
    workflow.add_edge("data_stasher", "research_agent")

    # 终止节点
    workflow.add_edge("simple_chat", END)
    workflow.add_edge("wait_for_human", END)

    return workflow


def create_langgraph_app(
    runtime: LangGraphRuntime,
    *,
    checkpointer: Optional[MemorySaver] = None,
):
    """创建 LangGraph 应用。"""
    workflow = build_workflow(runtime)
    memory = checkpointer or MemorySaver()
    return workflow.compile(checkpointer=memory)
