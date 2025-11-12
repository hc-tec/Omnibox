from __future__ import annotations

"""LangGraph 构建入口。"""

from typing import Literal, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .agents import (
    data_stasher,
    human,
    planner,
    reflector,
    router,
    simple_chat,
    synthesizer,
    tool_executor,
)
from .runtime import LangGraphRuntime
from .state import GraphState


def _router_edge(state: GraphState) -> Literal["to_simple", "to_planner", "to_human", "to_end"]:
    """
    Router 决策边。

    根据 RouterAgent 的决策路由到不同节点：
    - simple_tool_call: 简单查询 → simple_chat 节点
    - complex_research: 复杂研究 → planner 节点
    - clarify_with_human: 需要澄清 → wait_for_human 节点
    - end: 无需处理 → END
    """
    decision = state.get("router_decision")
    if not decision:
        return "to_planner"

    if decision.route == "simple_tool_call":
        return "to_simple"  # 新增：快速响应路由
    elif decision.route == "complex_research":
        return "to_planner"
    elif decision.route == "clarify_with_human":
        return "to_human"
    else:  # end
        return "to_end"


def _reflection_edge(
    state: GraphState,
) -> Literal["to_planner", "to_synthesizer", "to_human"]:
    reflection = state.get("reflection")
    if reflection is None:
        return "to_planner"

    if reflection.decision == "CONTINUE":
        return "to_planner"
    if reflection.decision == "FINISH":
        return "to_synthesizer"
    return "to_human"


def build_workflow(runtime: LangGraphRuntime) -> StateGraph:
    """
    构建 LangGraph 工作流。

    节点：
    - router: 入口路由决策
    - simple_chat: 简单查询快速响应（P2新增）
    - planner: 复杂研究规划
    - tool_executor: 工具执行
    - data_stasher: 数据暂存和摘要
    - reflector: 反思决策
    - synthesizer: 最终报告生成
    - wait_for_human: 人机交互
    """
    workflow = StateGraph(GraphState)

    # 添加所有节点
    workflow.add_node("router", router.create_router_node(runtime))
    workflow.add_node("simple_chat", simple_chat.create_simple_chat_node())  # P2新增
    workflow.add_node("planner", planner.create_planner_node(runtime))
    workflow.add_node("tool_executor", tool_executor.create_tool_executor_node(runtime))
    workflow.add_node("data_stasher", data_stasher.create_data_stasher_node(runtime))
    workflow.add_node("reflector", reflector.create_reflector_node(runtime))
    workflow.add_node("synthesizer", synthesizer.create_synthesizer_node(runtime))
    workflow.add_node("wait_for_human", human.create_wait_for_human_node())

    # 从 START 到 router
    workflow.add_edge(START, "router")

    # router 的条件分支（P2更新：新增 simple_chat 路由）
    workflow.add_conditional_edges(
        "router",
        _router_edge,
        {
            "to_simple": "simple_chat",  # P2新增：快速响应
            "to_planner": "planner",
            "to_human": "wait_for_human",
            "to_end": END,
        },
    )

    # 复杂研究循环
    workflow.add_edge("planner", "tool_executor")
    workflow.add_edge("tool_executor", "data_stasher")
    workflow.add_edge("data_stasher", "reflector")
    workflow.add_conditional_edges(
        "reflector",
        _reflection_edge,
        {
            "to_planner": "planner",
            "to_synthesizer": "synthesizer",
            "to_human": "wait_for_human",
        },
    )

    # 终止节点
    workflow.add_edge("simple_chat", END)  # P2新增
    workflow.add_edge("synthesizer", END)
    workflow.add_edge("wait_for_human", END)

    return workflow


def create_langgraph_app(
    runtime: LangGraphRuntime,
    *,
    checkpointer: Optional[MemorySaver] = None,
):
    workflow = build_workflow(runtime)
    memory = checkpointer or MemorySaver()
    return workflow.compile(checkpointer=memory)

