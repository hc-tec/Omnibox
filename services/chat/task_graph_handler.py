"""
Task Graph 处理模块

从 ChatService 拆分出来，负责 Task Graph 的执行和元数据构建。
"""

import logging
from typing import Any, Dict, Optional, Tuple

from services.agent_graph import (
    TaskGraphPlanner,
    GraphExecutor,
    TaskGraphExecutionContext,
    TaskGraphPlan,
    PlannerContext as TaskPlannerContext,
    GraphExecutionResult,
)

logger = logging.getLogger(__name__)


def execute_task_graph(
    planner: Optional[TaskGraphPlanner],
    executor: Optional[GraphExecutor],
    user_query: str,
    filter_datasource: Optional[str],
    use_cache: bool,
    prefer_single_route: bool,
    user_id: Optional[int],
) -> Tuple[Optional[TaskGraphPlan], Optional[GraphExecutionResult]]:
    """
    执行 Task Graph，失败时返回 (None, None)。

    Args:
        planner: Task Graph 规划器
        executor: Task Graph 执行器
        user_query: 用户查询
        filter_datasource: 过滤数据源（可选）
        use_cache: 是否使用缓存
        prefer_single_route: 是否优先单路由
        user_id: 用户 ID（可选）

    Returns:
        (TaskGraphPlan, GraphExecutionResult) 或 (None, None)
    """
    if not planner or not executor:
        return None, None

    try:
        planner_context = TaskPlannerContext(
            filter_datasource=filter_datasource,
            user_id=user_id,
        )
        plan = planner.plan(user_query=user_query, context=planner_context)

        exec_context = TaskGraphExecutionContext(
            user_query=user_query,
            filter_datasource=filter_datasource,
            use_cache=use_cache,
            prefer_single_route=prefer_single_route,
            user_id=user_id,
        )
        graph_result = executor.execute(plan.graph, exec_context)
        return plan, graph_result

    except (ValueError, RuntimeError) as exc:
        # 捕获明确的执行错误
        logger.error("Task Graph 执行失败，将回退至传统流程: %s", exc, exc_info=True)
        return None, None
    except Exception as exc:
        # 其他未预期的错误
        logger.error("Task Graph 执行发生未知异常，将回退至传统流程: %s", exc, exc_info=True)
        return None, None


def build_task_graph_metadata(
    plan: Optional[TaskGraphPlan],
    graph_result: Optional[GraphExecutionResult],
) -> Optional[Dict[str, Any]]:
    """
    构建 Task Graph 的调试元数据。

    Args:
        plan: Task Graph 计划
        graph_result: Task Graph 执行结果

    Returns:
        调试元数据字典，如果没有有效数据则返回 None
    """
    if not plan or not graph_result:
        return None

    debug_payload = graph_result.to_debug_payload()
    return {
        "reasoning": plan.reasoning,
        "complexity": plan.complexity,
        "requires_research": plan.requires_research,
        "node_count": len(plan.graph.nodes),
        "llm_trace": plan.llm_trace,
        "graph": [node.to_dict() for node in plan.graph.nodes],
        **debug_payload,
    }
