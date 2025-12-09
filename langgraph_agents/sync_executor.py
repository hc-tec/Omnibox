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
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4

from query_processor.llm_client import LLMClient
from services.data_query_service import DataQueryService, DataQueryResult, QueryDataset

from .config import LangGraphConfig
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
        config: Optional[LangGraphConfig] = None,
        recursion_limit: Optional[int] = None,
    ):
        """
        初始化同步执行器。

        Args:
            llm_client: LLM 客户端（用于所有 Agent 节点）
            data_query_service: 数据查询服务
            llm_tracker: LLM 调用追踪器（可选，用于前端可视化）
            config: LangGraph 运行时配置（可选）
            recursion_limit: 自定义递归上限（可选，优先级高于 config）
        """
        self.llm_client = llm_client
        self.data_query_service = data_query_service
        self.llm_tracker = llm_tracker
        self.config = config or LangGraphConfig.default()
        configured_limit = recursion_limit or self.config.execution.recursion_limit
        self.recursion_limit = max(1, int(configured_limit))

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
            "SyncLangGraphExecutor 初始化完成（%d 个工具，recursion_limit=%d%s）",
            len(self.runtime.tool_registry.list_tools()),
            self.recursion_limit,
            "，已启用 LLM 追踪" if llm_tracker else ""
        )

    def execute(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        thread_id: Optional[str] = None,
        panel_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
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
        normalized_thread_id = thread_id or f"sync-{uuid4().hex}"
        recursion_limit = getattr(self, "recursion_limit", None)
        if recursion_limit is None:
            config_obj = getattr(self, "config", None)
            recursion_limit = getattr(getattr(config_obj, "execution", None), "recursion_limit", 10)
        config = {
            "recursion_limit": recursion_limit,
            "configurable": {"thread_id": normalized_thread_id},
        }

        logger.info("开始执行 LangGraph 工作流: %s", user_query[:50])

        tool_context = getattr(self.runtime, "tool_context", None)
        extras = getattr(tool_context, "extras", None)
        old_callback = extras.get("emit_panel_preview") if extras else None
        if panel_callback and extras is not None:
            extras["emit_panel_preview"] = panel_callback

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
        finally:
            if panel_callback and extras is not None:
                if old_callback is None:
                    extras.pop("emit_panel_preview", None)
                else:
                    extras["emit_panel_preview"] = old_callback

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
                # human_in_loop 可能是 dict 或 string
                if isinstance(human_in_loop, dict):
                    clarification_question = human_in_loop.get("question", "需要更多信息")
                elif isinstance(human_in_loop, str):
                    clarification_question = human_in_loop
                else:
                    clarification_question = "需要更多信息"

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

    DATA_RESULT_TOOLS = {
        "fetch_public_data",
        "fetch_private_data",
        "data_operator",
        "filter_data",
        "compare_data",
        "aggregate_data",
        "extract_insights",
    }

    def get_final_data(self, result: LangGraphExecutionResult) -> Optional[DataQueryResult]:
        """
        从执行结果中提取最终数据（DataQueryResult）。

        用于 ChatService 构建面板。
        """
        if not result.data_stash:
            return None

        def _load_data(ref: DataReference) -> Optional[DataQueryResult]:
            if not ref.data_id:
                return None
            data = self.runtime.data_store.load(ref.data_id)
            if not data:
                logger.debug("langgraph.get_final_data skip empty data_id=%s tool=%s", ref.data_id, ref.tool_name)
                return None
            return self._dict_to_query_result(data)

        # 优先选择可渲染数据的工具结果
        for ref in reversed(result.data_stash):
            if ref.status == "success" and ref.tool_name in self.DATA_RESULT_TOOLS:
                loaded = _load_data(ref)
                if loaded:
                    logger.debug(
                        "langgraph.get_final_data resolved tool=%s data_id=%s",
                        ref.tool_name,
                        ref.data_id,
                    )
                    return loaded

        # 兜底：若没有匹配的工具，退回到最后一个成功结果
        logger.warning(
            "langgraph.get_final_data: 未找到可用数据工具，使用最后一个成功结果（总计=%s）",
            len(result.data_stash),
        )
        for ref in reversed(result.data_stash):
            if ref.status == "success":
                loaded = _load_data(ref)
                if loaded:
                    return loaded

        return None

    @staticmethod
    def _select_non_empty(*values: Optional[str]) -> Optional[str]:
        for value in values:
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    return stripped
            elif value:
                return value
        return None

    def _dict_to_query_result(self, data: Dict[str, Any]) -> DataQueryResult:
        """将字典转换为 DataQueryResult。"""
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        logger.debug(
            "langgraph.dict_to_query_result raw_keys=%s metadata_keys=%s",
            list(data.keys()),
            list(metadata.keys()),
        )
        generated_path = self._select_non_empty(
            data.get("generated_path"),
            metadata.get("generated_path"),
            metadata.get("source_route"),
            metadata.get("route"),
        )
        source = self._select_non_empty(
            data.get("source"),
            metadata.get("source"),
            metadata.get("datasource"),
            metadata.get("source_datasource"),
        )
        feed_title = self._select_non_empty(
            data.get("feed_title"),
            metadata.get("feed_title"),
            metadata.get("source_feed_title"),
        )
        cache_hit = data.get("cache_hit") or metadata.get("cache_hit") or "none"
        items = data.get("items")
        if not isinstance(items, list):
            items = []

        dataset = QueryDataset(
            route_id=None,
            provider=None,
            name=feed_title,
            generated_path=generated_path,
            items=items,
            feed_title=feed_title,
            source=source,
            cache_hit=cache_hit,
            reasoning=data.get("reasoning", ""),
            payload=data if isinstance(data, dict) else None,
        )

        return DataQueryResult(
            status=data.get("status") or "success",
            items=items,
            feed_title=feed_title,
            generated_path=generated_path,
            source=source,
            cache_hit=cache_hit,
            reasoning=data.get("reasoning", ""),
            payload=data if isinstance(data, dict) else None,
            datasets=[dataset],
        )


def create_sync_executor(
    llm_client: LLMClient,
    data_query_service: DataQueryService,
    llm_tracker: Optional["LLMCallTracker"] = None,  # V5.0 可观测性
    config: Optional[LangGraphConfig] = None,
    recursion_limit: Optional[int] = None,
) -> SyncLangGraphExecutor:
    """
    创建同步执行器的便捷工厂函数。

    Args:
        llm_client: LLM 客户端
        data_query_service: 数据查询服务
        llm_tracker: LLM 调用追踪器（可选，用于前端可视化）
        config: LangGraph 配置（可选）
        recursion_limit: 自定义递归上限（可选）

    Returns:
        SyncLangGraphExecutor 实例
    """
    return SyncLangGraphExecutor(
        llm_client=llm_client,
        llm_tracker=llm_tracker,  # V5.0 可观测性
        data_query_service=data_query_service,
        config=config,
        recursion_limit=recursion_limit,
    )
