"""
对话服务
职责：作为统一入口，整合意图识别、数据查询与智能数据面板输出。
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple, Generator
from dataclasses import dataclass, field, asdict
from uuid import uuid4
from datetime import datetime

from services.config import get_data_query_config
from services.llm_intent_classifier import LLMIntentClassifier, IntentClassification
from services.llm_query_planner import LLMQueryPlanner, QueryPlan, SubQuery
from services.parallel_query_executor import ParallelQueryExecutor, SubQueryResult
from services.data_query_service import DataQueryService, DataQueryResult, QueryDataset
from api.schemas.panel import PanelPayload, DataBlock, SourceInfo
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
    format_source_hint,
    format_retrieved_tools,
    resolve_tool_route,
)
from services.chat.dataset_utils import (
    dataset_from_result,
    dataset_records,
    infer_dataset_item_count,
    build_dataset_preview,
    summarize_datasets,
    format_success_message,
    build_analysis_prompt,
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
    对话服务（同步实现）。

    统一入口，负责：
    1. 三层智能意图识别（chitchat / simple_query / complex_research）
    2. 简单查询：单次 RAG 调用
    3. 复杂研究：LLM 查询规划 + 并行执行多个 RAG 查询
    4. 生成智能数据面板结构
    """

    def __init__(
        self,
        data_query_service: DataQueryService,
        llm_client=None,  # LLM 客户端，用于意图分类和查询规划
        research_service=None,  # 研究服务（可选，用于 LangGraph 工作流）
        manage_data_service: bool = False,
        component_planner_config: Optional[ComponentPlannerConfig] = None,
        max_parallel_queries: int = 3,  # 并行查询最大数量
        query_timeout: int = 30,  # 单个查询超时时间（秒）
        force_single_route: Optional[bool] = None,
    ):
        """
        初始化对话服务。

        Args:
            data_query_service: 数据查询服务实例
            llm_client: LLM 客户端实例（用于意图分类和查询规划，可选）
            research_service: 研究服务实例（可选，用于 LangGraph 复杂研究工作流）
            manage_data_service: 是否由 ChatService 负责关闭 data_query_service
            component_planner_config: 组件规划器配置（可选）
            max_parallel_queries: 并行查询的最大工作线程数（默认 3）
            query_timeout: 每个查询的超时时间，秒（默认 30）
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

        # 初始化三层架构组件
        self.intent_classifier = None
        self.query_planner = None
        self.parallel_executor = None
        self._llm_client = llm_client

        if llm_client:
            try:
                # Layer 1: 意图分类器
                self.intent_classifier = LLMIntentClassifier(llm_client)
                logger.info("LLM 意图分类器初始化完成")

                # Layer 2: 查询规划器
                self.query_planner = LLMQueryPlanner(llm_client)
                logger.info("LLM 查询规划器初始化完成")

                # Layer 3: 并行查询执行器
                self.parallel_executor = ParallelQueryExecutor(
                    data_query_service=data_query_service,
                    max_workers=max_parallel_queries,
                    timeout_per_query=query_timeout,
                )
                logger.info(
                    "并行查询执行器初始化完成 (max_workers=%d, timeout=%ds)",
                    max_parallel_queries,
                    query_timeout,
                )
            except Exception as exc:
                logger.warning(f"三层架构组件初始化失败: {exc}")
                self.intent_classifier = None
                self.query_planner = None
                self.parallel_executor = None

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

        Returns:
            ChatResponse 对象
        """
        logger.info("收到对话请求: %s (mode=%s, user_id=%s)", user_query, mode, user_id)

        try:
            llm_logs: List[Dict[str, Any]] = []

            # ==================== 统一的复杂研究检测 ====================
            # 无论是 mode="research" 还是 LLM 判断为 complex_research
            # 都应该返回统一的"需要流式接口"响应

            is_research_mode = False
            research_reasoning = ""
            research_confidence = 1.0

            # 情况1：用户显式选择研究模式
            if mode == "research":
                is_research_mode = True
                research_reasoning = "用户显式选择研究模式"
                research_confidence = 1.0
                logger.info("用户显式选择研究模式")

            # 情况2：LangGraph 模式（特殊的研究模式）
            elif mode == "langgraph":
                if not self.research_service:
                    logger.warning("LangGraph 模式被请求但 ResearchService 未初始化，回退到简单查询")
                    return self._handle_simple_query(
                        user_query=user_query,
                        filter_datasource=filter_datasource,
                        use_cache=use_cache,
                        intent_confidence=0.5,
                        layout_snapshot=layout_snapshot,
                        llm_logs=llm_logs,
                        user_id=user_id,
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
                return self._handle_simple_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=1.0,
                    layout_snapshot=layout_snapshot,
                    llm_logs=llm_logs,
                    user_id=user_id,
                )

            # 如果已经确定是研究模式，直接返回流式提示
            if is_research_mode:
                return self._create_streaming_required_response(
                    reasoning=research_reasoning,
                    confidence=research_confidence,
                    llm_logs=llm_logs,
                )

            # 阶段1：LLM 意图分类（三层架构第一层）
            if not self.intent_classifier:
                # 降级：如果 LLM 意图分类器不可用，默认为简单查询
                logger.warning("LLM 意图分类器不可用，默认使用简单查询模式")
                return self._handle_simple_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=0.5,
                    layout_snapshot=layout_snapshot,
                    llm_logs=llm_logs,
                    user_id=user_id,
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
                return self._handle_simple_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=intent_result.confidence,
                    layout_snapshot=layout_snapshot,
                    llm_logs=llm_logs,
                    user_id=user_id,
                )

            elif intent_result.intent == "complex_research":
                # ⚠️ 重要：LLM 识别为复杂研究，需要使用流式接口
                logger.info("LLM 识别为复杂研究意图，引导前端使用流式接口")

                return self._create_streaming_required_response(
                    reasoning=intent_result.reasoning,
                    confidence=intent_result.confidence,
                    llm_logs=llm_logs,
                )

            else:
                # 未知意图，降级为简单查询
                logger.warning(f"未知意图类型: {intent_result.intent}，降级为简单查询")
                return self._handle_simple_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=intent_result.confidence,
                    layout_snapshot=layout_snapshot,
                    llm_logs=llm_logs,
                    user_id=user_id,
                )

        except Exception as exc:
            logger.error("对话处理失败: %s", exc, exc_info=True)
            return ChatResponse(
                success=False,
                intent_type="error",
                message=f"抱歉，处理您的请求时发生了错误：{exc}",
                metadata={"error": str(exc)},
            )

    def _handle_simple_query(
        self,
        user_query: str,
        filter_datasource: Optional[str],
        use_cache: bool,
        intent_confidence: float,
        layout_snapshot: Optional[List[Dict[str, Any]]] = None,
        llm_logs: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[int] = None,  # Phase 2: 用户 ID
    ) -> ChatResponse:
        """处理简单查询意图（单次 RAG 调用）。"""
        logger.debug("处理简单查询意图 (user_id=%s)", user_id)

        query_result = self.data_query_service.query(
            user_query=user_query,
            filter_datasource=filter_datasource,
            use_cache=use_cache,
            prefer_single_route=self._should_force_single_route(filter_datasource),
            user_id=user_id,  # Phase 2: 传递 user_id
        )
        llm_debug = clone_llm_logs(llm_logs)

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
            }

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

            return ChatResponse(
                success=True,
                intent_type="data_query",
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
            return ChatResponse(
                success=False,
                intent_type="data_query",
                message=query_result.clarification_question or "需要更多信息以继续处理。",
                metadata={
                    "status": "needs_clarification",
                    "reasoning": query_result.reasoning,
                    "intent_confidence": intent_confidence,
                    "retrieved_tools": formatted_tools,
                    "debug": debug_payload,
                },
            )

        if query_result.status == "not_found":
            debug_payload = compose_debug_payload(
                None,
                llm_debug,
                query_result.rag_trace or None,
            )
            return ChatResponse(
                success=False,
                intent_type="data_query",
                message=query_result.clarification_question or "抱歉，没有找到相关能力。",
                metadata={
                    "status": "not_found",
                    "reasoning": query_result.reasoning,
                    "intent_confidence": intent_confidence,
                    "retrieved_tools": formatted_tools,
                    "debug": debug_payload,
                },
            )

        debug_payload = compose_debug_payload(None, llm_debug, query_result.rag_trace or None)
        return ChatResponse(
            success=False,
            intent_type="data_query",
            message=f"查询失败：{query_result.reasoning}",
            metadata={
                "status": "error",
                "reasoning": query_result.reasoning,
                "intent_confidence": intent_confidence,
                "generated_path": query_result.generated_path,
                "retrieved_tools": formatted_tools,
                "debug": debug_payload,
            },
        )

    def _create_streaming_required_response(
        self,
        reasoning: str,
        confidence: float,
        llm_logs: Optional[List[Dict[str, Any]]] = None,
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
                    self._clone_llm_logs(llm_logs),
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
            self._clone_llm_logs(llm_logs),
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

    def _handle_complex_research_streaming(
        self,
        task_id: str,
        user_query: str,
        filter_datasource: Optional[str] = None,
        use_cache: bool = True,
        intent_confidence: float = 0.95,
        layout_snapshot: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[int] = None,  # Phase 2: 用户 ID
    ) -> Generator[Dict[str, Any], None, None]:
        """
        处理复杂研究意图（流式版本）。

        通过 Generator 逐步 yield 研究进度消息，支持 WebSocket 实时推送。

        流程：
        1. LLM 查询规划 → yield ResearchStartMessage
        2. 并行执行数据子查询 → 每个子查询 yield step/panel 消息
        3. 执行分析子查询 → 每个分析 yield analysis 消息
        4. 完成 → yield ResearchCompleteMessage

        Args:
            task_id: 研究任务 ID
            user_query: 用户查询
            filter_datasource: 过滤数据源（可选）
            use_cache: 是否使用缓存
            intent_confidence: 意图置信度
            layout_snapshot: 布局快照（可选）

        Yields:
            Dict[str, Any]: 研究消息（ResearchStartMessage / ResearchStepMessage /
                           ResearchPanelMessage / ResearchAnalysisMessage /
                           ResearchCompleteMessage / ResearchErrorMessage）
        """
        stream_id = f"stream-{uuid4().hex[:16]}"
        start_time = time.time()

        logger.info("开始流式研究任务 (task_id=%s, stream_id=%s): %s", task_id, stream_id, user_query)

        # P0 修复：检查 LLM 组件是否可用
        if not self.query_planner:
            logger.error("研究任务失败: query_planner 未初始化或不可用")
            yield {
                "type": "research_error",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": "initialization",
                "error_code": "COMPONENT_UNAVAILABLE",
                "error_message": "LLM 组件未初始化，无法执行复杂研究任务。请检查环境配置或稍后重试。",
                "timestamp": datetime.now().isoformat(),
            }
            yield {
                "type": "research_complete",
                "stream_id": stream_id,
                "task_id": task_id,
                "success": False,
                "message": "研究失败：LLM 组件不可用",
                "total_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat(),
            }
            return

        try:
            # ========== 第一步：LLM 查询规划 ==========
            yield {
                "type": "research_step",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": "planning",
                "step_type": "planning",
                "action": "LLM 正在规划研究方案...",
                "status": "processing",
                "timestamp": datetime.now().isoformat(),
            }

            query_plan: QueryPlan = self.query_planner.plan(user_query)

            if not query_plan.sub_queries:
                yield {
                    "type": "research_error",
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "step_id": "planning",
                    "error_code": "PLANNING_ERROR",
                    "error_message": "查询规划未生成子查询，无法继续研究",
                    "timestamp": datetime.now().isoformat(),
                }
                yield {
                    "type": "research_complete",
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "success": False,
                    "message": "研究失败：查询规划未生成子查询",
                    "total_time": time.time() - start_time,
                    "timestamp": datetime.now().isoformat(),
                }
                return

            # 分类子查询
            data_sub_queries = [sq for sq in query_plan.sub_queries if sq.task_type == "data_fetch"]
            analysis_sub_queries = [
                sq for sq in query_plan.sub_queries if sq.task_type in {"analysis", "report"}
            ]

            if not data_sub_queries:
                yield {
                    "type": "research_error",
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "step_id": "planning",
                    "error_code": "PLANNING_ERROR",
                    "error_message": "查询规划未包含数据获取任务",
                    "timestamp": datetime.now().isoformat(),
                }
                yield {
                    "type": "research_complete",
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "success": False,
                    "message": "研究失败：查询规划未包含数据获取任务",
                    "total_time": time.time() - start_time,
                    "timestamp": datetime.now().isoformat(),
                }
                return

            # 规划完成，推送开始消息
            yield {
                "type": "research_start",
                "stream_id": stream_id,
                "task_id": task_id,
                "query": user_query,
                "plan": {
                    "reasoning": query_plan.reasoning,
                    "sub_queries": [
                        {
                            "query": sq.query,
                            "task_type": sq.task_type,
                            "datasource": sq.datasource,
                        }
                        for sq in query_plan.sub_queries
                    ],
                    "estimated_time": query_plan.estimated_time,
                },
                "timestamp": datetime.now().isoformat(),
            }

            yield {
                "type": "research_step",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": "planning",
                "step_type": "planning",
                "action": f"规划完成：{len(data_sub_queries)} 个数据任务，{len(analysis_sub_queries)} 个分析任务",
                "status": "success",
                "details": {
                    "data_task_count": len(data_sub_queries),
                    "analysis_task_count": len(analysis_sub_queries),
                },
                "timestamp": datetime.now().isoformat(),
            }

            # ========== 第二步：并行执行数据子查询 ==========
            aggregated_datasets: List[QueryDataset] = []
            success_count = 0

            for idx, sub_query in enumerate(data_sub_queries):
                step_id = f"data_fetch_{idx}"

                # 开始执行
                yield {
                    "type": "research_step",
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "step_type": "data_fetch",
                    "action": f"正在获取数据：{sub_query.query}",
                    "status": "processing",
                    "timestamp": datetime.now().isoformat(),
                }

                try:
                    # 执行查询
                    effective_datasource = filter_datasource or sub_query.datasource
                    prefer_single_route = self._should_force_single_route(effective_datasource)
                    query_result = self.data_query_service.query(
                        user_query=sub_query.query,
                        filter_datasource=effective_datasource,
                        use_cache=use_cache,
                        prefer_single_route=prefer_single_route,
                        user_id=user_id,  # Phase 2: 传递 user_id
                    )

                    if query_result.status == "success":
                        # 聚合数据集
                        datasets = query_result.datasets or []
                        if datasets:
                            aggregated_datasets.extend(datasets)
                        else:
                            aggregated_datasets.append(dataset_from_result(query_result))

                        # 生成面板
                        panel_result = self._build_panel(
                            query_result=query_result,
                            datasets=datasets or [dataset_from_result(query_result)],
                            intent_confidence=intent_confidence,
                            user_query=sub_query.query,
                            layout_snapshot=layout_snapshot,
                        )

                        # 推送面板消息
                        yield {
                            "type": "research_panel",
                            "stream_id": stream_id,
                            "task_id": task_id,
                            "step_id": step_id,
                            "step_index": idx + 1,
                            "panel_payload": panel_result.payload.model_dump(),
                            "panel_data_blocks": {
                                key: block.model_dump()
                                for key, block in (panel_result.data_blocks or {}).items()
                            },
                            "source_query": sub_query.query,
                            "timestamp": datetime.now().isoformat(),
                        }

                        # 步骤成功
                        yield {
                            "type": "research_step",
                            "stream_id": stream_id,
                            "task_id": task_id,
                            "step_id": step_id,
                            "step_type": "data_fetch",
                            "action": f"数据获取成功：{query_result.feed_title or '数据'}",
                            "status": "success",
                            "details": {
                                "item_count": len(query_result.items or []),
                                "feed_title": query_result.feed_title,
                            },
                            "timestamp": datetime.now().isoformat(),
                        }

                        success_count += 1

                    else:
                        # 查询失败
                        yield {
                            "type": "research_step",
                            "stream_id": stream_id,
                            "task_id": task_id,
                            "step_id": step_id,
                            "step_type": "data_fetch",
                            "action": f"数据获取失败：{query_result.reasoning or '未知错误'}",
                            "status": "error",
                            "details": {
                                "error": query_result.reasoning,
                            },
                            "timestamp": datetime.now().isoformat(),
                        }

                except Exception as exc:
                    logger.error("数据子查询执行异常: %s - %s", sub_query.query, exc, exc_info=True)
                    yield {
                        "type": "research_step",
                        "stream_id": stream_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "step_type": "data_fetch",
                        "action": f"数据获取异常：{exc}",
                        "status": "error",
                        "details": {
                            "error": str(exc),
                        },
                        "timestamp": datetime.now().isoformat(),
                    }

            # 检查是否有成功的数据查询
            if success_count == 0:
                yield {
                    "type": "research_error",
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "step_id": None,
                    "error_code": "ALL_DATA_FETCH_FAILED",
                    "error_message": "所有数据获取任务均失败",
                    "timestamp": datetime.now().isoformat(),
                }
                yield {
                    "type": "research_complete",
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "success": False,
                    "message": "研究失败：所有数据获取任务均失败",
                    "total_time": time.time() - start_time,
                    "timestamp": datetime.now().isoformat(),
                }
                return

            # ========== 第三步：执行分析子查询 ==========
            if analysis_sub_queries and aggregated_datasets and self._llm_client:
                dataset_summary, total_items = build_dataset_preview(aggregated_datasets)

                if dataset_summary and total_items > 0:
                    for idx, sub_query in enumerate(analysis_sub_queries):
                        step_id = f"analysis_{idx}"

                        # 开始分析
                        yield {
                            "type": "research_step",
                            "stream_id": stream_id,
                            "task_id": task_id,
                            "step_id": step_id,
                            "step_type": "analysis",
                            "action": f"正在分析：{sub_query.query}",
                            "status": "processing",
                            "timestamp": datetime.now().isoformat(),
                        }

                        try:
                            prompt = build_analysis_prompt(sub_query.query, dataset_summary)
                            response = self._llm_client.chat(
                                messages=[
                                    {"role": "system", "content": "你是一名资深的数据分析师，擅长归纳总结。"},
                                    {"role": "user", "content": prompt},
                                ],
                                temperature=0.2,
                            )

                            # 空值检查
                            if response is None or not response.strip():
                                raise ValueError("LLM 返回空响应")

                            # 推送分析结果
                            yield {
                                "type": "research_analysis",
                                "stream_id": stream_id,
                                "task_id": task_id,
                                "step_id": step_id,
                                "step_index": idx + 1,
                                "analysis_text": response.strip(),
                                "is_complete": True,
                                "timestamp": datetime.now().isoformat(),
                            }

                            # 分析成功
                            yield {
                                "type": "research_step",
                                "stream_id": stream_id,
                                "task_id": task_id,
                                "step_id": step_id,
                                "step_type": "analysis",
                                "action": "分析完成",
                                "status": "success",
                                "details": {
                                    "item_count": total_items,
                                },
                                "timestamp": datetime.now().isoformat(),
                            }

                        except Exception as exc:
                            logger.warning("分析子查询失败: %s - %s", sub_query.query, exc)
                            yield {
                                "type": "research_step",
                                "stream_id": stream_id,
                                "task_id": task_id,
                                "step_id": step_id,
                                "step_type": "analysis",
                                "action": f"分析失败：{exc}",
                                "status": "error",
                                "details": {
                                    "error": str(exc),
                                },
                                "timestamp": datetime.now().isoformat(),
                            }

            # ========== 第四步：研究完成 ==========
            total_time = time.time() - start_time
            yield {
                "type": "research_complete",
                "stream_id": stream_id,
                "task_id": task_id,
                "success": True,
                "message": f"研究完成，共获取 {success_count} 组数据",
                "total_time": total_time,
                "summary": None,  # 可选：未来可以添加总结
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                "流式研究任务完成 (task_id=%s, success_count=%d, total_time=%.2fs)",
                task_id,
                success_count,
                total_time
            )

        except Exception as exc:
            logger.error("流式研究任务异常 (task_id=%s): %s", task_id, exc, exc_info=True)
            yield {
                "type": "research_error",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": None,
                "error_code": "RESEARCH_ERROR",
                "error_message": str(exc),
                "timestamp": datetime.now().isoformat(),
            }
            yield {
                "type": "research_complete",
                "stream_id": stream_id,
                "task_id": task_id,
                "success": False,
                "message": f"研究失败：{exc}",
                "total_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat(),
            }

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
            source_info = SourceInfo(
                datasource=guess_datasource(dataset.generated_path),
                route=dataset.generated_path or "",
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

            block_input = PanelBlockInput(
                block_id=f"data_block_{uuid4().hex[:8]}",
                records=dataset_records(dataset),
                source_info=source_info,
                title=dataset.feed_title,
                stats={"intent_confidence": intent_confidence, "dataset_index": index},
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

    def _run_analysis_sub_queries(
        self,
        analysis_sub_queries: List[SubQuery],
        datasets: List[QueryDataset],
    ) -> List[Dict[str, Any]]:
        """
        执行分析类子查询，对已有数据进行LLM总结。

        Args:
            analysis_sub_queries: 分析类子查询列表
            datasets: 数据集列表

        Returns:
            分析总结列表
        """
        if not analysis_sub_queries or not datasets or not self._llm_client:
            return []

        dataset_summary, total_items = build_dataset_preview(datasets)
        if not dataset_summary or total_items == 0:
            return []

        summaries: List[Dict[str, Any]] = []
        for sub_query in analysis_sub_queries:
            prompt = build_analysis_prompt(sub_query.query, dataset_summary)
            try:
                response = self._llm_client.chat(
                    messages=[
                        {"role": "system", "content": "你是一名资深的数据分析师，擅长归纳总结。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )

                # 添加空值检查，确保LLM返回有效响应
                if response is None or not response.strip():
                    raise ValueError("LLM 返回空响应")

                summaries.append({
                    "query": sub_query.query,
                    "summary": response.strip(),
                    "item_count": total_items,
                    "task_type": sub_query.task_type or "analysis",
                })
            except Exception as exc:
                logger.warning("分析子查询失败: %s", exc)
                summaries.append({
                    "query": sub_query.query,
                    "summary": f"分析失败：{exc}",
                    "task_type": sub_query.task_type or "analysis",
                })
        return summaries

    def _handle_langgraph_research(
        self,
        user_query: str,
        filter_datasource: Optional[str],
        intent_confidence: float,
        client_task_id: Optional[str] = None,
    ) -> ChatResponse:
        """
        处理 LangGraph 研究工作流（多轮动态研究）。

        Args:
            user_query: 用户查询
            filter_datasource: 过滤数据源（可选）
            intent_confidence: 意图置信度
            client_task_id: 客户端任务 ID（可选）

        Returns:
            ChatResponse 对象
        """
        logger.debug("处理 LangGraph 研究工作流")

        if not self.research_service:
            return ChatResponse(
                success=False,
                intent_type="error",
                message="研究服务未启用，请使用简单查询模式",
                metadata={"error": "research_service_not_available"},
            )

        task_id = client_task_id or f"task-{uuid4().hex}"

        try:
            # 调用 ResearchService 执行研究
            research_result = self.research_service.research(
                user_query=user_query,
                filter_datasource=filter_datasource,
                task_id=task_id,
            )

            if research_result.success:
                # 格式化执行步骤
                execution_steps = [
                    {
                        "step_id": step.step_id,
                        "node": step.node_name,
                        "action": step.action,
                        "status": step.status,
                        "timestamp": step.timestamp,
                    }
                    for step in research_result.execution_steps
                ]

                metadata = {
                    "mode": "research",
                    "intent_confidence": intent_confidence,
                    "total_steps": len(research_result.execution_steps),
                    "execution_steps": execution_steps,
                    "data_stash_count": len(research_result.data_stash),
                }
                if research_result.metadata:
                    metadata.update(research_result.metadata)
                metadata.setdefault("task_id", task_id)

                return ChatResponse(
                    success=True,
                    intent_type="research",
                    message=research_result.final_report,
                    metadata=metadata,
                )
            else:
                return ChatResponse(
                    success=False,
                    intent_type="research",
                    message=f"研究任务失败：{research_result.error}",
                    metadata={
                        "mode": "research",
                        "error": research_result.error,
                        "intent_confidence": intent_confidence,
                        "task_id": task_id,
                    },
                )

        except Exception as exc:
            logger.error(f"研究任务执行失败: {exc}", exc_info=True)
            return ChatResponse(
                success=False,
                intent_type="research",
                message=f"研究任务执行失败：{exc}",
                metadata={
                    "mode": "research",
                    "error": str(exc),
                    "task_id": task_id,
                },
            )

    def close(self):
        """关闭服务并释放资源。"""
        if self._manage_data_service and self.data_query_service:
            self.data_query_service.close()
            logger.info("ChatService 已关闭（管理 DataQueryService 资源）")

        if self.parallel_executor:
            try:
                self.parallel_executor.shutdown()
                logger.info("ParallelQueryExecutor 已关闭")
            except Exception as exc:  # pragma: no cover
                logger.warning("ParallelQueryExecutor 关闭失败: %s", exc)

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
