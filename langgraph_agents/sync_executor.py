"""
同步执行适配层 - ChatService 接入 V5.0 LangGraph 的桥梁。

V5.0 LangGraph 采用单步迭代规划（类似 Claude Code 的工作方式）：
1. Router → 判断意图
2. Planner → 规划下一步（有前序步骤的上下文）
3. ToolExecutor → 执行工具
4. Reflector → 决定是否继续
5. 循环直到完成

这种设计确保每一步规划都有充足的上下文信息。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from query_processor.llm_client import LLMClient
from services.data_query_service import DataQueryService, DataQueryResult

from .factory import build_runtime
from .graph_builder import create_langgraph_app
from .runtime import LangGraphRuntime
from .state import GraphState, DataReference

if TYPE_CHECKING:
    from api.schemas.llm_call_event import LLMCallTracker

logger = logging.getLogger(__name__)


@dataclass
class LangGraphExecutionResult:
    """LangGraph 执行结果。"""
    success: bool
    final_report: Optional[str]
    data_stash: List[DataReference]
    router_decision: Optional[str]
    execution_steps: List[Dict[str, Any]]
    error: Optional[str] = None
    needs_clarification: bool = False
    clarification_question: Optional[str] = None


class SyncLangGraphExecutor:
    """
    同步 LangGraph 执行器。

    封装 V5.0 LangGraph 状态机，提供同步执行接口供 ChatService 使用。
    """

    def __init__(
        self,
        llm_client: LLMClient,
        data_query_service: DataQueryService,
        llm_tracker: Optional["LLMCallTracker"] = None,  # V5.0 可观测性
    ):
        """
        初始化同步执行器。

        Args:
            llm_client: LLM 客户端（用于所有 Agent 节点）
            data_query_service: 数据查询服务
            llm_tracker: LLM 调用追踪器（可选，用于前端可视化）
        """
        self.llm_client = llm_client
        self.data_query_service = data_query_service
        self.llm_tracker = llm_tracker

        # 构建 V5.0 Runtime（注入追踪器）
        self.runtime = build_runtime(
            llms={
                "default": llm_client,
                "router": llm_client,
                "planner": llm_client,
                "reflector": llm_client,
                "synthesizer": llm_client,
            },
            data_query_service=data_query_service,
            llm_tracker=llm_tracker,  # V5.0 可观测性
        )

        # 创建 LangGraph App
        self.app = create_langgraph_app(self.runtime)

        logger.info(
            "SyncLangGraphExecutor 初始化完成（%d 个工具%s）",
            len(self.runtime.tool_registry.list_tools()),
            "，已启用 LLM 追踪" if llm_tracker else ""
        )

    def execute(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> LangGraphExecutionResult:
        """
        同步执行 LangGraph 工作流。

        Args:
            user_query: 用户查询
            filter_datasource: 过滤数据源（可选）
            thread_id: 会话 ID（可选，用于多轮对话）

        Returns:
            LangGraphExecutionResult
        """
        # 构建初始状态
        initial_state: GraphState = {
            "original_query": user_query,
            "chat_history": [],
            "next_tool_call": None,
            "data_stash": [],
            "reflection": None,
            "final_report": None,
            "human_in_loop_request": None,
            "router_decision": None,
            "pending_tool_result": None,
            "last_tool_result": None,
            "working_memory": {},
            "last_error": None,
            "execution_plan": None,
            "completed_step_ids": [],
            "knowledge_graph": None,
        }

        # 如果有 filter_datasource，添加到 working_memory 供工具使用
        if filter_datasource:
            initial_state["working_memory"]["filter_datasource"] = filter_datasource

        # 配置
        config = {"configurable": {"thread_id": thread_id or "default"}}

        logger.info("开始执行 LangGraph 工作流: %s", user_query[:50])

        try:
            # 同步调用 LangGraph
            final_state = self.app.invoke(initial_state, config)

            # 提取结果
            return self._extract_result(final_state)

        except Exception as exc:
            logger.error("LangGraph 执行失败: %s", exc, exc_info=True)
            return LangGraphExecutionResult(
                success=False,
                final_report=None,
                data_stash=[],
                router_decision=None,
                execution_steps=[],
                error=str(exc),
            )

    def _extract_result(self, state: GraphState) -> LangGraphExecutionResult:
        """从最终状态提取结果。"""
        data_stash: List[DataReference] = state.get("data_stash", [])
        router_decision = state.get("router_decision")
        final_report = state.get("final_report")
        last_error = state.get("last_error")

        # 构建执行步骤摘要
        execution_steps = []
        needs_clarification = False
        clarification_question = None

        for ref in data_stash:
            execution_steps.append({
                "step_id": ref.step_id,
                "tool_name": ref.tool_name,
                "status": ref.status,
                "summary": ref.summary,
                "error": ref.error_message,
            })
            # 检测 needs_user_input 状态
            if ref.status == "needs_user_input":
                needs_clarification = True
                # 从 summary 提取澄清问题
                if ref.summary and ref.summary.startswith("等待用户澄清:"):
                    clarification_question = ref.summary.replace("等待用户澄清: ", "")
                else:
                    clarification_question = ref.summary

        # 检查 human_in_loop_request（V5.0 状态字段）
        human_in_loop = state.get("human_in_loop_request")
        if human_in_loop:
            needs_clarification = True
            if not clarification_question:
                clarification_question = human_in_loop.get("question", "需要更多信息")

        # 判断成功与否：需要澄清不算成功
        has_successful_data = any(ref.status == "success" for ref in data_stash)
        success = (
            last_error is None
            and not needs_clarification
            and (final_report is not None or has_successful_data)
        )

        return LangGraphExecutionResult(
            success=success,
            final_report=final_report,
            data_stash=data_stash,
            router_decision=router_decision.route if router_decision else None,
            execution_steps=execution_steps,
            error=last_error,
            needs_clarification=needs_clarification,
            clarification_question=clarification_question,
        )

    def get_final_data(self, result: LangGraphExecutionResult) -> Optional[DataQueryResult]:
        """
        从执行结果中提取最终数据（DataQueryResult）。

        用于 ChatService 构建面板。
        """
        if not result.data_stash:
            return None

        # 找到最后一个成功的 fetch_public_data 或 filter_data 结果
        for ref in reversed(result.data_stash):
            if ref.status == "success" and ref.data_id:
                data = self.runtime.data_store.load(ref.data_id)
                if data:
                    return self._dict_to_query_result(data)

        return None

    @staticmethod
    def _dict_to_query_result(data: Dict[str, Any]) -> DataQueryResult:
        """将字典转换为 DataQueryResult。"""
        return DataQueryResult(
            status="success",
            items=data.get("items", []),
            feed_title=data.get("feed_title"),
            generated_path=data.get("generated_path"),
            source=data.get("source"),
            cache_hit=data.get("cache_hit"),
            reasoning=data.get("reasoning"),
        )


def create_sync_executor(
    llm_client: LLMClient,
    data_query_service: DataQueryService,
    llm_tracker: Optional["LLMCallTracker"] = None,  # V5.0 可观测性
) -> SyncLangGraphExecutor:
    """
    创建同步执行器的便捷工厂函数。

    Args:
        llm_client: LLM 客户端
        data_query_service: 数据查询服务
        llm_tracker: LLM 调用追踪器（可选，用于前端可视化）

    Returns:
        SyncLangGraphExecutor 实例
    """
    return SyncLangGraphExecutor(
        llm_client=llm_client,
        llm_tracker=llm_tracker,  # V5.0 可观测性
        data_query_service=data_query_service,
    )
