"""
对话服务
职责：作为统一入口，整合意图识别、数据查询与智能数据面板输出。
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from uuid import uuid4

from typing import TYPE_CHECKING

from services.config import get_data_query_config
from services.llm_intent_classifier import LLMIntentClassifier, IntentClassification
from services.data_query_service import DataQueryService, DataQueryResult, QueryDataset
from api.schemas.panel import PanelPayload, DataBlock, SourceInfo
from langgraph_agents.sync_executor import (
    SyncLangGraphExecutor,
    LangGraphExecutionResult,
    create_sync_executor,
)
from services.chat.langgraph_handler import handle_langgraph_research

if TYPE_CHECKING:
    from api.schemas.llm_call_event import LLMCallTracker
from services.panel.panel_generator import (
    PanelGenerator,
    PanelBlockInput,
    PanelGenerationResult,
)
from services.panel.component_planner import (
    ComponentPlannerConfig,
    PlannerContext,
    plan_components_for_route,
)
from services.panel.llm_component_planner import LLMComponentPlanner
from services.panel.adapters import get_route_manifest
from query_processor.llm_client import create_llm_client

# 导入拆分的工具函数
from services.chat.utils import (
    merge_planner_engines,
    clone_llm_logs,
    compose_debug_payload,
    guess_datasource,
    format_retrieved_tools,
)
from services.chat.dataset_utils import (
    dataset_from_result,
    dataset_records,
    infer_dataset_item_count,
    build_dataset_preview,
    summarize_datasets,
    format_success_message,
)

logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    """
    对话响应数据结构。

    Attributes:
        success: 是否成功
        intent_type: 意图类型（data_query/chitchat/error）
        message: 响应消息
        data: 智能面板载荷（仅数据查询时返回）
        data_blocks: 数据块字典（id -> DataBlock）
        metadata: 元数据（路径、来源、缓存命中等）
    """

    success: bool
    intent_type: str
    message: str
    data: Optional[PanelPayload] = None
    data_blocks: Dict[str, DataBlock] = field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为便于序列化的字典。"""
        payload = asdict(self)
        if self.data:
            payload["data"] = self.data.model_dump()
        if self.data_blocks:
            payload["data_blocks"] = {
                key: block.model_dump() for key, block in self.data_blocks.items()
            }
        return payload


class ChatService:
    """
    对话服务（V5.0 Task Graph 架构）。

    统一入口，负责：
    1. 意图识别（chitchat / data_query）
    2. 所有数据查询通过 Task Graph 规划和执行
    3. 生成智能数据面板结构
    """

    def __init__(
        self,
        data_query_service: DataQueryService,
        llm_client=None,  # LLM 客户端，用于意图分类和 Task Graph 规划
        research_service=None,  # 研究服务（可选，用于 LangGraph 深度研究）
        manage_data_service: bool = False,
        component_planner_config: Optional[ComponentPlannerConfig] = None,
        force_single_route: Optional[bool] = None,
    ):
        """
        初始化对话服务。

        Args:
            data_query_service: 数据查询服务实例
            llm_client: LLM 客户端实例（用于意图分类和 Task Graph 规划，可选）
            research_service: 研究服务实例（可选，用于 LangGraph 深度研究工作流）
            manage_data_service: 是否由 ChatService 负责关闭 data_query_service
            component_planner_config: 组件规划器配置（可选）
            force_single_route: 是否强制单路由模式
        """
        self.data_query_service = data_query_service
        self.research_service = research_service
        self._manage_data_service = manage_data_service
        self.panel_generator = PanelGenerator()
        self.component_planner_config = component_planner_config or ComponentPlannerConfig()

        # 使用统一配置管理
        self.config = get_data_query_config()
        if force_single_route is None:
            force_single_route = self.config.single_route_default
        self._force_single_route = force_single_route

        # 初始化 LLM 客户端（如果未提供，则创建默认客户端）
        if llm_client is None:
            try:
                llm_client = create_llm_client()
                logger.info("使用默认 LLM 客户端")
            except Exception as exc:
                logger.warning(f"LLM 客户端创建失败: {exc}")
                llm_client = None

        self._llm_client = llm_client
        self.intent_classifier = None
        self.langgraph_executor = None  # V5.0 LangGraph 执行器

        # 初始化意图分类器
        if llm_client:
            try:
                self.intent_classifier = LLMIntentClassifier(llm_client)
                logger.info("LLM 意图分类器初始化完成")
            except Exception as exc:
                logger.warning(f"意图分类器初始化失败: {exc}")
                self.intent_classifier = None

        # 初始化 V5.0 LangGraph 执行器（单步迭代规划）
        if llm_client:
            try:
                self.langgraph_executor = create_sync_executor(
                    llm_client=llm_client,
                    data_query_service=data_query_service,
                )
                logger.info(
                    "V5.0 LangGraph 执行器初始化完成（%d 个工具）",
                    len(self.langgraph_executor.runtime.tool_registry.list_tools())
                )
            except Exception as exc:
                logger.warning("V5.0 LangGraph 执行器初始化失败: %s", exc)
                self.langgraph_executor = None

        # 初始化 LLM 组件规划器（作为规则引擎的备选方案）
        try:
            self.llm_component_planner = LLMComponentPlanner()
        except Exception as exc:
            logger.warning(f"LLM 组件规划器初始化失败，将仅使用规则引擎: {exc}")
            self.llm_component_planner = None

        logger.info("ChatService 初始化完成")

    def quick_refresh(
        self,
        refresh_metadata: Dict[str, Any],
        layout_snapshot: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[int] = None,
    ) -> ChatResponse:
        """
        快速刷新：跳过 RAG/LLM 推理，直接使用 refresh_metadata 重新获取数据。

        Phase 3: 快速刷新功能
        - 跳过意图识别
        - 跳过 RAG 检索
        - 直接使用 route_id 和 generated_path 调用数据 API
        - 生成面板并返回

        Args:
            refresh_metadata: 刷新元数据，包含 route_id、generated_path
            layout_snapshot: 当前面板布局快照（可选）
            user_id: 用户 ID（Phase 2，游客模式可为 None）

        Returns:
            ChatResponse 对象
        """
        generated_path = refresh_metadata.get("generated_path")
        route_id = refresh_metadata.get("route_id")

        if not generated_path:
            return ChatResponse(
                success=False,
                intent_type="error",
                message="刷新失败：缺少 generated_path",
                metadata={"error": "missing_generated_path"},
            )

        logger.info("快速刷新数据: route_id=%s, generated_path=%s", route_id, generated_path)

        try:
            # 直接调用数据查询（使用 generated_path）
            query_result = self.data_query_service.fetch_data_directly(
                route_id=route_id,
                generated_path=generated_path,
                use_cache=False,  # 刷新时不使用缓存
            )

            if query_result.status != "success":
                return ChatResponse(
                    success=False,
                    intent_type="data_query",
                    message=f"刷新失败：{query_result.reasoning}",
                    metadata={
                        "status": query_result.status,
                        "reasoning": query_result.reasoning,
                    },
                )

            # 构建面板
            datasets = query_result.datasets or []
            panel_result = self._build_panel(
                query_result=query_result,
                datasets=datasets,
                intent_confidence=1.0,  # 刷新时置信度为 1.0
                user_query="[快速刷新]",
                layout_snapshot=layout_snapshot,
            )

            # 构建新的 refresh_metadata
            new_refresh_metadata = {
                "route_id": route_id,
                "generated_path": query_result.generated_path or generated_path,
                "retrieved_tools": refresh_metadata.get("retrieved_tools", []),
            }

            metadata = {
                "generated_path": query_result.generated_path,
                "source": query_result.source,
                "cache_hit": query_result.cache_hit,
                "feed_title": query_result.feed_title,
                "component_confidence": panel_result.component_confidence,
                "refresh_metadata": new_refresh_metadata,
                "is_refresh": True,  # 标记为刷新请求
            }

            return ChatResponse(
                success=True,
                intent_type="data_query",
                message=f"刷新成功，获取 {len(datasets)} 个数据集",
                data=panel_result.payload,
                data_blocks=panel_result.data_blocks,
                metadata=metadata,
            )

        except Exception as exc:
            logger.error(f"快速刷新失败: {exc}", exc_info=True)
            return ChatResponse(
                success=False,
                intent_type="error",
                message=f"刷新失败：{exc}",
                metadata={"error": str(exc)},
            )

    def chat(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        use_cache: bool = True,
        layout_snapshot: Optional[List[Dict[str, Any]]] = None,
        mode: str = "auto",  # auto / simple / research / langgraph
        client_task_id: Optional[str] = None,
        user_id: Optional[int] = None,  # Phase 2: 用户 ID（游客模式可为 None）
        force_execute: bool = False,  # 强制执行（流式接口使用）
        llm_tracker: Optional["LLMCallTracker"] = None,  # V5.0 LLM 调用追踪器
    ) -> ChatResponse:
        """
        处理用户查询（三层智能路由）。

        Args:
            user_query: 用户输入的自然语言查询
            filter_datasource: 过滤特定数据源（可选）
            use_cache: 是否使用缓存
            layout_snapshot: 当前面板布局快照（可选）
            mode: 查询模式
                - auto: 自动智能路由（使用 LLM 意图分类）
                - simple: 强制简单查询（单次 RAG）
                - research: 强制复杂研究（查询规划 + 并行执行）
                - langgraph: 强制使用 LangGraph 工作流
            client_task_id: 客户端任务 ID（可选）
            user_id: 用户 ID（Phase 2，游客模式可为 None）
            force_execute: 强制执行复杂查询（流式接口使用，跳过 requires_streaming 提示）
            llm_tracker: LLM 调用追踪器（V5.0 可观测性，流式接口使用）

        Returns:
            ChatResponse 对象
        """
        logger.info("收到对话请求: %s (mode=%s, user_id=%s)", user_query, mode, user_id)

        try:
            llm_logs: List[Dict[str, Any]] = []

            # ==================== V5.0 统一数据查询架构 ====================
            # 所有数据查询（simple_query / complex_research / mode=research）
            # 统一通过 Task Graph 处理

            # 情况1：用户显式选择研究模式 → 使用 Task Graph
            if mode == "research":
                if self.research_service:
                    logger.info("用户显式选择研究模式，使用 ResearchService 推进多轮研究流程")
                    return self._handle_langgraph_research(
                        user_query=user_query,
                        filter_datasource=filter_datasource,
                        intent_confidence=1.0,
                        client_task_id=client_task_id,
                    )
                logger.warning("研究模式被请求但 ResearchService 未初始化，回退到 Task Graph")
                return self._handle_data_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=1.0,
                    layout_snapshot=layout_snapshot,
                    llm_logs=llm_logs,
                    user_id=user_id,
                    is_complex=True,
                    llm_tracker=llm_tracker,
                )

            # 情况2：LangGraph 模式（特殊的研究模式）
            elif mode == "langgraph":
                if not self.research_service:
                    logger.warning("LangGraph 模式被请求但 ResearchService 未初始化，回退到数据查询")
                    return self._handle_data_query(
                        user_query=user_query,
                        filter_datasource=filter_datasource,
                        use_cache=use_cache,
                        intent_confidence=0.5,
                        layout_snapshot=layout_snapshot,
                        llm_logs=llm_logs,
                        user_id=user_id,
                        llm_tracker=llm_tracker,
                    )
                else:
                    return self._handle_langgraph_research(
                        user_query=user_query,
                        filter_datasource=filter_datasource,
                        intent_confidence=1.0,
                        client_task_id=client_task_id,
                    )

            # 情况3：显式指定简单查询
            elif mode == "simple":
                return self._handle_data_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=1.0,
                    layout_snapshot=layout_snapshot,
                    llm_logs=llm_logs,
                    user_id=user_id,
                    llm_tracker=llm_tracker,
                )

            # 阶段1：LLM 意图分类（三层架构第一层）
            if not self.intent_classifier:
                # 降级：如果 LLM 意图分类器不可用，默认为数据查询
                logger.warning("LLM 意图分类器不可用，默认使用数据查询模式")
                return self._handle_data_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=0.5,
                    layout_snapshot=layout_snapshot,
                    llm_logs=llm_logs,
                    user_id=user_id,
                    llm_tracker=llm_tracker,
                )

            intent_result: IntentClassification = self.intent_classifier.classify(user_query)
            if intent_result.debug:
                llm_logs.append(dict(intent_result.debug))
            logger.info(
                "意图分类结果: %s (置信度 %.2f) - %s",
                intent_result.intent,
                intent_result.confidence,
                intent_result.reasoning,
            )

            # 阶段2：根据意图路由
            if intent_result.intent == "chitchat":
                return self._handle_chitchat(
                    user_query=user_query,
                    intent_confidence=intent_result.confidence,
                    llm_logs=llm_logs,
                )

            elif intent_result.intent == "simple_query":
                return self._handle_data_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=intent_result.confidence,
                    layout_snapshot=layout_snapshot,
                    llm_logs=llm_logs,
                    user_id=user_id,
                    llm_tracker=llm_tracker,
                )

            elif intent_result.intent == "complex_research":
                if force_execute:
                    # 流式接口：直接执行 Task Graph
                    logger.info("LLM 识别为复杂研究意图，流式模式直接执行 Task Graph")
                    return self._handle_data_query(
                        user_query=user_query,
                        filter_datasource=filter_datasource,
                        use_cache=use_cache,
                        intent_confidence=intent_result.confidence,
                        layout_snapshot=layout_snapshot,
                        llm_logs=llm_logs,
                        user_id=user_id,
                        is_complex=True,
                        llm_tracker=llm_tracker,
                    )
                else:
                    # 非流式接口：返回提示，让前端切换到 WebSocket 流式
                    logger.info("LLM 识别为复杂研究意图，返回流式接口提示")
                    return self._create_streaming_required_response(
                        reasoning=intent_result.reasoning,
                        confidence=intent_result.confidence,
                        llm_logs=llm_logs,
                        client_task_id=client_task_id,
                    )

            else:
                # 未知意图，降级为数据查询
                logger.warning(f"未知意图类型: {intent_result.intent}，降级为数据查询")
                return self._handle_data_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=intent_result.confidence,
                    layout_snapshot=layout_snapshot,
                    llm_logs=llm_logs,
                    user_id=user_id,
                    llm_tracker=llm_tracker,
                )

        except Exception as exc:
            logger.error("对话处理失败: %s", exc, exc_info=True)
            return ChatResponse(
                success=False,
                intent_type="error",
                message=f"抱歉，处理您的请求时发生了错误：{exc}",
                metadata={"error": str(exc)},
            )

    def _handle_data_query(
        self,
        user_query: str,
        filter_datasource: Optional[str],
        use_cache: bool,
        intent_confidence: float,
        layout_snapshot: Optional[List[Dict[str, Any]]] = None,
        llm_logs: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[int] = None,
        is_complex: bool = False,  # V5.0：标记是否为复杂查询
        llm_tracker: Optional["LLMCallTracker"] = None,  # V5.0 LLM 调用追踪器
    ) -> ChatResponse:
        """
        统一处理数据查询意图（V5.0 LangGraph 架构）。

        V5.0 采用单步迭代规划（类似 Claude Code 的工作方式）：
        - Router → 判断意图
        - Planner → 规划下一步（有前序步骤的上下文）
        - ToolExecutor → 执行工具
        - Reflector → 决定是否继续
        - 循环直到完成

        这种设计确保每一步规划都有充足的上下文信息。
        """
        logger.debug("处理数据查询意图 (user_id=%s, is_complex=%s)", user_id, is_complex)

        langgraph_result: Optional[LangGraphExecutionResult] = None
        query_result: Optional[DataQueryResult] = None
        panel_events: List[Dict[str, Any]] = []

        def capture_panel(payload: Dict[str, Any]) -> None:
            panel_events.append(payload)

        # 优先使用 V5.0 LangGraph 执行器
        if self.langgraph_executor or llm_tracker:
            try:
                # V5.0 可观测性：如果提供了 tracker，创建临时带追踪器的 executor
                executor = self.langgraph_executor
                if llm_tracker and self._llm_client:
                    executor = create_sync_executor(
                        llm_client=self._llm_client,
                        data_query_service=self.data_query_service,
                        llm_tracker=llm_tracker,
                    )
                    logger.debug("创建带 LLM 追踪器的临时执行器")

                if executor:
                    try:
                        langgraph_result = executor.execute(
                            user_query=user_query,
                            filter_datasource=filter_datasource,
                            panel_callback=capture_panel,
                        )
                    except TypeError as exc:
                        if "panel_callback" in str(exc):
                            langgraph_result = executor.execute(
                                user_query=user_query,
                                filter_datasource=filter_datasource,
                            )
                        else:
                            raise

                    # 提取最终数据（如果成功）
                    if langgraph_result and langgraph_result.success:
                        query_result = executor.get_final_data(langgraph_result)

                # V5.0 修复：处理需要澄清的情况，不回退到直接查询
                if langgraph_result and langgraph_result.needs_clarification:
                    logger.info("LangGraph 需要用户澄清: %s", langgraph_result.clarification_question)
                    llm_debug = clone_llm_logs(llm_logs)
                    langgraph_debug = self._build_langgraph_metadata(langgraph_result)
                    debug_payload = compose_debug_payload(None, llm_debug, None)
                    metadata = {
                        "status": "needs_clarification",
                        "reasoning": langgraph_result.clarification_question,
                        "intent_confidence": intent_confidence,
                        "debug": debug_payload,
                    }
                    if langgraph_debug:
                        metadata["langgraph"] = langgraph_debug
                    return ChatResponse(
                        success=False,
                        intent_type="data_query",
                        message=langgraph_result.clarification_question or "需要更多信息以继续处理。",
                        metadata=metadata,
                    )

            except Exception as exc:
                logger.warning("V5.0 LangGraph 执行失败，回退到直接查询: %s", exc)

        # 降级：直接使用 DataQueryService（仅当 LangGraph 未成功且未请求澄清时）
        if query_result is None:
            query_result = self.data_query_service.query(
                user_query=user_query,
                filter_datasource=filter_datasource,
                use_cache=use_cache,
                prefer_single_route=self._should_force_single_route(filter_datasource),
                user_id=user_id,
            )

        llm_debug = clone_llm_logs(llm_logs)
        langgraph_debug = self._build_langgraph_metadata(langgraph_result)

        if query_result.status == "success":
            datasets = query_result.datasets or []
            panel_result = self._build_panel(
                query_result=query_result,
                datasets=datasets,
                intent_confidence=intent_confidence,
                user_query=user_query,
                layout_snapshot=layout_snapshot,
            )

            message = format_success_message(
                datasets=datasets,
                fallback_feed=query_result.feed_title,
                fallback_source=query_result.source,
            )

            debug_info = compose_debug_payload(
                panel_result.debug,
                llm_debug,
                query_result.rag_trace or None,
            )

            # Phase 3: 构建 refresh_metadata（用于快速刷新）
            # 从数据集或 retrieved_tools 中提取 route_id
            route_id = ""
            if datasets and datasets[0].route_id:
                route_id = datasets[0].route_id
            elif query_result.retrieved_tools:
                # 从 RAG 检索到的第一个工具中获取 route_id
                route_id = query_result.retrieved_tools[0].get("route_id", "")

            refresh_metadata = {
                "route_id": route_id,
                "generated_path": query_result.generated_path or "",
                "retrieved_tools": format_retrieved_tools(query_result.retrieved_tools),
            }

            metadata: Dict[str, Any] = {
                "generated_path": query_result.generated_path,
                "source": query_result.source,
                "cache_hit": query_result.cache_hit,
                "intent_confidence": intent_confidence,
                "feed_title": query_result.feed_title,
                "component_confidence": panel_result.component_confidence,
                "requested_components": panel_result.debug.get("requested_components"),
                "planner_reasons": panel_result.debug.get("planner_reasons"),
                "planner_engine": panel_result.debug.get("planner_engine"),
                "debug": debug_info,
                "datasets": summarize_datasets(datasets, query_result),
                "retrieved_tools": format_retrieved_tools(query_result.retrieved_tools),
                "refresh_metadata": refresh_metadata,  # Phase 2: 快速刷新元数据
                "is_complex": is_complex,  # V5.0: 标记是否为复杂研究
            }
            if panel_events:
                metadata["panel_preview_events"] = panel_events

            # 提取并暴露适配器/渲染警告信息到顶层 metadata
            blocks_debug = debug_info.get("blocks", [])
            warnings = []
            for block in blocks_debug:
                if block.get("using_default_adapter"):
                    warnings.append({
                        "type": "missing_adapter",
                        "message": block.get("adapter_warning", "No adapter registered"),
                        "block_id": block.get("data_block_id"),
                    })
                if block.get("using_fallback"):
                    warnings.append({
                        "type": "fallback_rendering",
                        "message": block.get("fallback_reason", "Using fallback component"),
                        "block_id": block.get("data_block_id"),
                    })
                if block.get("skipped"):
                    warnings.append({
                        "type": "component_skipped",
                        "message": block.get("skip_reason", "Component generation skipped"),
                        "block_id": block.get("data_block_id"),
                    })

            if warnings:
                metadata["warnings"] = warnings

            if langgraph_debug:
                metadata["langgraph"] = langgraph_debug

            # 根据查询复杂度设置正确的 intent_type
            result_intent_type = "complex_research" if is_complex else "data_query"

            return ChatResponse(
                success=True,
                intent_type=result_intent_type,
                message=message,
                data=panel_result.payload,
                data_blocks=panel_result.data_blocks,
                metadata=metadata,
            )

        formatted_tools = format_retrieved_tools(query_result.retrieved_tools)

        if query_result.status == "needs_clarification":
            debug_payload = compose_debug_payload(
                None,
                llm_debug,
                query_result.rag_trace or None,
            )
            metadata = {
                "status": "needs_clarification",
                "reasoning": query_result.reasoning,
                "intent_confidence": intent_confidence,
                "retrieved_tools": formatted_tools,
                "debug": debug_payload,
            }
            if langgraph_debug:
                metadata["langgraph"] = langgraph_debug
            return ChatResponse(
                success=False,
                intent_type="data_query",
                message=query_result.clarification_question or "需要更多信息以继续处理。",
                metadata=metadata,
            )

        if query_result.status == "not_found":
            debug_payload = compose_debug_payload(
                None,
                llm_debug,
                query_result.rag_trace or None,
            )
            metadata = {
                "status": "not_found",
                "reasoning": query_result.reasoning,
                "intent_confidence": intent_confidence,
                "retrieved_tools": formatted_tools,
                "debug": debug_payload,
            }
            if langgraph_debug:
                metadata["langgraph"] = langgraph_debug
            return ChatResponse(
                success=False,
                intent_type="data_query",
                message=query_result.clarification_question or "抱歉，没有找到相关能力。",
                metadata=metadata,
            )

        debug_payload = compose_debug_payload(None, llm_debug, query_result.rag_trace or None)
        metadata = {
            "status": "error",
            "reasoning": query_result.reasoning,
            "intent_confidence": intent_confidence,
            "generated_path": query_result.generated_path,
            "retrieved_tools": formatted_tools,
            "debug": debug_payload,
        }
        if langgraph_debug:
            metadata["langgraph"] = langgraph_debug
        return ChatResponse(
            success=False,
            intent_type="data_query",
            message=f"查询失败：{query_result.reasoning}",
            metadata=metadata,
        )

    def _build_langgraph_metadata(
        self,
        result: Optional[LangGraphExecutionResult],
    ) -> Optional[Dict[str, Any]]:
        """
        构建 LangGraph 执行的调试元数据。

        Args:
            result: LangGraph 执行结果

        Returns:
            调试元数据字典，如果没有有效数据则返回 None
        """
        if not result:
            return None

        return {
            "success": result.success,
            "router_decision": result.router_decision,
            "final_report": result.final_report,
            "execution_steps": result.execution_steps,
            "error": result.error,
        }

    def _create_streaming_required_response(
        self,
        reasoning: str,
        confidence: float,
        llm_logs: Optional[List[Dict[str, Any]]] = None,
        client_task_id: Optional[str] = None,
    ) -> ChatResponse:
        """
        创建"需要流式接口"的统一响应

        ⚠️ 核心原则：复杂研究的唯一真理 = WebSocket 流式接口
        无论是 mode="research" 还是 LLM 识别为 complex_research，
        都应该通过这个方法返回统一的响应。

        Args:
            reasoning: 判断为复杂研究的理由
            confidence: 置信度
            llm_logs: LLM 调用日志

        Returns:
            ChatResponse 对象，包含 requires_streaming=True 标记
        """
        logger.info("返回流式研究提示: %s (置信度 %.2f)", reasoning, confidence)

        task_id = client_task_id or f"task-{uuid4().hex}"

        return ChatResponse(
            success=True,
            intent_type="complex_research",
            message="这是一个复杂研究任务，正在为您准备深度研究流程...",
            metadata={
                "intent_confidence": confidence,
                "reasoning": reasoning,
                "requires_streaming": True,  # ← 核心标记
                "websocket_endpoint": "/api/v1/chat/stream",
                "suggested_action": "使用 WebSocket 连接获取流式研究进度",
                "task_id": task_id,
                "debug": compose_debug_payload(None, llm_logs, None),
            }
        )

    def _handle_chitchat(
        self,
        user_query: str,
        intent_confidence: float,
        llm_logs: Optional[List[Dict[str, Any]]] = None,
    ) -> ChatResponse:
        """处理闲聊意图。"""
        logger.debug("处理闲聊意图")

        chitchat_responses = {
            "你好": "你好！我是RSS数据聚合助手，可以帮你获取各种平台的最新动态。",
            "您好": "您好！有什么我可以帮助您的吗？",
            "hi": "Hi! 我可以帮你查询各种RSS数据源。",
            "hello": "Hello! 需要查询什么数据吗？",
            "谢谢": "不客气！有其他需要随时告诉我。",
            "感谢": "不用谢！很高兴能帮到你。",
            "再见": "再见！期待下次为您服务。",
            "拜拜": "拜拜！",
        }

        user_query_lower = user_query.lower().strip()
        for keyword, response in chitchat_responses.items():
            if keyword.lower() in user_query_lower:
                debug_payload = compose_debug_payload(
                    None,
                    clone_llm_logs(llm_logs),
                    None,
                )
                metadata = {"intent_confidence": intent_confidence}
                if debug_payload:
                    metadata["debug"] = debug_payload
                return ChatResponse(
                    success=True,
                    intent_type="chitchat",
                    message=response,
                    metadata=metadata,
                )

        debug_payload = compose_debug_payload(
            None,
            clone_llm_logs(llm_logs),
            None,
        )
        metadata = {"intent_confidence": intent_confidence}
        if debug_payload:
            metadata["debug"] = debug_payload

        return ChatResponse(
            success=True,
            intent_type="chitchat",
            message='我是RSS数据聚合助手。您可以问我关于各种平台数据的问题，比如"虎扑步行街最新帖子"、"B站热门视频"等。',
            metadata=metadata,
        )

    def _build_panel(
        self,
        query_result: DataQueryResult,
        datasets: List[QueryDataset],
        intent_confidence: float,
        user_query: str,
        layout_snapshot: Optional[List[Dict[str, Any]]] = None,
    ) -> PanelGenerationResult:
        """将数据查询结果（可含多数据集）转换为 PanelPayload。"""
        # datasets 为空列表或 None 时，使用 query_result 构造单个数据集
        normalized = datasets or [dataset_from_result(query_result)]
        block_inputs: List[PanelBlockInput] = []
        planner_reasons_acc: List[str] = []
        planner_engines: List[str] = []

        for index, dataset in enumerate(normalized, start=1):
            route = self._resolve_dataset_route(dataset, query_result, dataset_index=index)
            datasource = dataset.source or (guess_datasource(route) if route else (query_result.source or "rsshub"))
            logger.debug(
                "panel.build_block dataset_index=%s route=%s datasource=%s feed_title=%s",
                index,
                route,
                datasource,
                dataset.feed_title,
            )
            source_info = SourceInfo(
                datasource=datasource,
                route=route or "",
                params={},
                fetched_at=None,
                request_id=None,
            )

            planned_components, planner_reasons, planner_engine = self._plan_components_for_source(
                source_info.route,
                user_query=user_query,
                layout_snapshot=layout_snapshot,
                item_count=infer_dataset_item_count(dataset),
            )
            planner_engines.append(planner_engine)
            planner_reasons_acc.extend([f"[dataset-{index}] {reason}" for reason in planner_reasons])

            if planner_engine == "error":
                logger.warning(
                    "panel.component_planner route=%s dataset_index=%s reasons=%s",
                    route,
                    index,
                    planner_reasons,
                )

            block_input = PanelBlockInput(
                block_id=f"data_block_{uuid4().hex[:8]}",
                records=dataset_records(dataset),
                source_info=source_info,
                title=dataset.feed_title,
                stats={
                    "intent_confidence": intent_confidence,
                    "dataset_index": index,
                    "generated_path": route,
                },
                requested_components=planned_components,
            )
            block_inputs.append(block_input)

        result = self.panel_generator.generate(
            mode="append",
            block_inputs=block_inputs,
            history_token=None,
        )
        result.debug.setdefault("planner_reasons", planner_reasons_acc)
        result.debug.setdefault("planner_engine", merge_planner_engines(planner_engines))
        result.debug.setdefault(
            "requested_components",
            [block_input.requested_components for block_input in block_inputs],
        )
        if layout_snapshot:
            result.debug.setdefault("layout_snapshot", layout_snapshot)

        logger.debug(
            "panel.generate route_count=%s planner_engine=%s reasons=%s",
            len(normalized),
            result.debug.get("planner_engine"),
            result.debug.get("planner_reasons"),
        )
        return result

    def _plan_components_for_source(
        self,
        route: str,
        user_query: str,
        layout_snapshot: Optional[List[Dict[str, Any]]],
        item_count: int,
    ) -> Tuple[Optional[List[str]], List[str], str]:
        planner_engine = "rule"
        planner_reasons: List[str] = []
        planned_components: Optional[List[str]] = None

        if not route:
            planner_engine = "error"
            planner_reasons.append("route_missing: 无法确定路由，跳过组件规划")
            logger.error("panel.component_planner route_missing user_query=%s", user_query)
            return None, planner_reasons, planner_engine

        try:
            planner_context = PlannerContext(
                item_count=item_count,
                user_preferences=(),
                raw_query=user_query,
                layout_mode=None,
                layout_snapshot=layout_snapshot,
            )
            manifest = get_route_manifest(route)
            decision = None
            if self.llm_component_planner and self.llm_component_planner.is_available():
                decision = self.llm_component_planner.plan(
                    route=route,
                    manifest=manifest,
                    context=planner_context,
                    config=self.component_planner_config,
                )
                if decision:
                    planner_engine = "llm"
            if decision is None:
                decision = plan_components_for_route(
                    route,
                    config=self.component_planner_config,
                    context=planner_context,
                    manifest=manifest,
                )
            if decision:
                planner_reasons = decision.reasons
                planned_components = decision.components
                if planned_components is not None and len(planned_components) == 0:
                    planned_components = None
        except Exception as exc:
            logger.warning("组件规划失败，使用默认策略: %s", exc)
            planner_reasons = [f"planner_error: {exc}"]
            planned_components = None
            planner_engine = "error"

        return planned_components, planner_reasons, planner_engine

    def _should_force_single_route(self, filter_datasource: Optional[str]) -> bool:
        if filter_datasource:
            return True
        return self._force_single_route

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

    @staticmethod
    def _normalize_route(route: str) -> str:
        cleaned = route.strip()
        if not cleaned.startswith("/"):
            cleaned = f"/{cleaned}"
        if cleaned != "/" and cleaned.endswith("/"):
            cleaned = cleaned.rstrip("/")
        return cleaned

    def _resolve_dataset_route(
        self,
        dataset: QueryDataset,
        query_result: Optional[DataQueryResult],
        dataset_index: Optional[int] = None,
    ) -> Optional[str]:
        payload_meta: Dict[str, Any] = {}
        payload_root: Dict[str, Any] = {}
        if isinstance(dataset.payload, dict):
            payload_root = dataset.payload
            metadata = payload_root.get("metadata")
            if isinstance(metadata, dict):
                payload_meta = metadata

        query_payload: Dict[str, Any] = {}
        query_payload_meta: Dict[str, Any] = {}
        if query_result and isinstance(query_result.payload, dict):
            query_payload = query_result.payload
            qp_meta = query_payload.get("metadata")
            if isinstance(qp_meta, dict):
                query_payload_meta = qp_meta

        candidate = self._select_non_empty(
            dataset.generated_path,
            payload_root.get("generated_path"),
            payload_root.get("route"),
            payload_meta.get("generated_path"),
            payload_meta.get("route"),
            payload_meta.get("source_route"),
            dataset.route_id,
            query_payload.get("generated_path"),
            query_payload_meta.get("generated_path"),
            query_payload_meta.get("route"),
            query_payload_meta.get("source_route"),
            query_result.generated_path if query_result else None,
        )
        logger.debug(
            "panel.resolve_route dataset_index=%s dataset_path=%s payload_route=%s metadata_route=%s route_id=%s fallback=%s resolved=%s",
            dataset_index,
            dataset.generated_path,
            payload_root.get("generated_path") or payload_root.get("route"),
            payload_meta.get("generated_path") or payload_meta.get("route"),
            dataset.route_id,
            query_result.generated_path if query_result else None,
            candidate,
        )
        if not candidate:
            logger.warning("panel.resolve_route_failed feed_title=%s dataset_index=%s", dataset.feed_title, dataset_index)
            return None
        return self._normalize_route(candidate)

    def _build_dataset_preview(
        self,
        datasets: List[QueryDataset],
        max_items: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """封装 build_dataset_preview，便于测试覆盖。"""
        limit = max_items if max_items is not None else self.config.analysis_preview_max_items
        return build_dataset_preview(datasets, max_items=limit)

    def _handle_langgraph_research(
        self,
        user_query: str,
        filter_datasource: Optional[str],
        intent_confidence: float,
        client_task_id: Optional[str] = None,
    ) -> ChatResponse:
        """
        处理 LangGraph 研究工作流（多轮动态研究）。
        具体实现已拆分到 services.chat.langgraph_handler 模块。
        """
        return handle_langgraph_research(
            research_service=self.research_service,
            user_query=user_query,
            filter_datasource=filter_datasource,
            intent_confidence=intent_confidence,
            client_task_id=client_task_id,
            chat_response_class=ChatResponse,
        )

    def close(self):
        """关闭服务并释放资源。"""
        if self._manage_data_service and self.data_query_service:
            self.data_query_service.close()
            logger.info("ChatService 已关闭（管理 DataQueryService 资源）")

        if self.research_service and hasattr(self.research_service, "close"):
            try:
                self.research_service.close()
                logger.info("ResearchService 已关闭")
            except Exception as exc:  # pragma: no cover
                logger.warning("ResearchService 关闭失败: %s", exc)

    def __enter__(self):
        """上下文管理器入口。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出时自动释放资源。"""
        self.close()
