"""
对话服务
职责：作为统一入口，整合意图识别、数据查询与智能数据面板输出。
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from uuid import uuid4

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

    def chat(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        use_cache: bool = True,
        layout_snapshot: Optional[List[Dict[str, Any]]] = None,
        mode: str = "auto",  # auto / simple / research / langgraph
        client_task_id: Optional[str] = None,
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

        Returns:
            ChatResponse 对象
        """
        logger.info("收到对话请求: %s (mode=%s)", user_query, mode)

        try:
            llm_logs: List[Dict[str, Any]] = []
            # 阶段0：如果显式指定 LangGraph 研究模式
            if mode == "langgraph":
                if not self.research_service:
                    logger.warning("LangGraph 模式被请求但 ResearchService 未初始化，回退到简单查询")
                else:
                    return self._handle_langgraph_research(
                        user_query=user_query,
                        filter_datasource=filter_datasource,
                        intent_confidence=1.0,
                        client_task_id=client_task_id,
                    )

            # 阶段0.5：如果显式指定简单查询或复杂研究
            if mode == "simple":
                return self._handle_simple_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=1.0,
                    layout_snapshot=layout_snapshot,
                    llm_logs=llm_logs,
                )

            if mode == "research":
                if not self.query_planner or not self.parallel_executor:
                    logger.warning("研究模式被请求但三层架构未初始化，回退到简单查询")
                    return self._handle_simple_query(
                        user_query=user_query,
                        filter_datasource=filter_datasource,
                        use_cache=use_cache,
                        intent_confidence=1.0,
                        layout_snapshot=layout_snapshot,
                        llm_logs=llm_logs,
                    )
                else:
                    return self._handle_complex_research(
                        user_query=user_query,
                        filter_datasource=filter_datasource,
                        use_cache=use_cache,
                        intent_confidence=1.0,
                        layout_snapshot=layout_snapshot,
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
                )

            elif intent_result.intent == "complex_research":
                # 检查三层架构组件是否可用
                if not self.query_planner or not self.parallel_executor:
                    logger.warning("复杂研究意图但三层架构未初始化，回退到简单查询")
                    return self._handle_simple_query(
                        user_query=user_query,
                        filter_datasource=filter_datasource,
                        use_cache=use_cache,
                        intent_confidence=intent_result.confidence,
                        layout_snapshot=layout_snapshot,
                        llm_logs=llm_logs,
                    )
                else:
                    return self._handle_complex_research(
                        user_query=user_query,
                        filter_datasource=filter_datasource,
                        use_cache=use_cache,
                        intent_confidence=intent_result.confidence,
                        layout_snapshot=layout_snapshot,
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
    ) -> ChatResponse:
        """处理简单查询意图（单次 RAG 调用）。"""
        logger.debug("处理简单查询意图")

        query_result = self.data_query_service.query(
            user_query=user_query,
            filter_datasource=filter_datasource,
            use_cache=use_cache,
             prefer_single_route=self._should_force_single_route(filter_datasource),
        )
        llm_debug = self._clone_llm_logs(llm_logs)

        if query_result.status == "success":
            datasets = query_result.datasets or []
            panel_result = self._build_panel(
                query_result=query_result,
                datasets=datasets,
                intent_confidence=intent_confidence,
                user_query=user_query,
                layout_snapshot=layout_snapshot,
            )

            message = self._format_success_message(
                datasets=datasets,
                fallback_feed=query_result.feed_title,
                fallback_source=query_result.source,
            )

            debug_info = self._compose_debug_payload(
                panel_result.debug,
                llm_debug,
                query_result.rag_trace or None,
            )

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
                "datasets": self._summarize_datasets(datasets, query_result),
                "retrieved_tools": self._format_retrieved_tools(query_result.retrieved_tools),
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

        formatted_tools = self._format_retrieved_tools(query_result.retrieved_tools)

        if query_result.status == "needs_clarification":
            debug_payload = self._compose_debug_payload(
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
            debug_payload = self._compose_debug_payload(
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

        debug_payload = self._compose_debug_payload(None, llm_debug, query_result.rag_trace or None)
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
                debug_payload = self._compose_debug_payload(
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

        debug_payload = self._compose_debug_payload(
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

    def _handle_complex_research(
        self,
        user_query: str,
        filter_datasource: Optional[str],
        use_cache: bool,
        intent_confidence: float,
        layout_snapshot: Optional[List[Dict[str, Any]]] = None,
        llm_logs: Optional[List[Dict[str, Any]]] = None,
    ) -> ChatResponse:
        """
        处理复杂研究意图（LLM 查询规划 + 并行执行）。

        流程：
        1. 使用 LLMQueryPlanner 分解查询为多个子查询
        2. 使用 ParallelQueryExecutor 并行执行所有子查询
        3. 聚合结果并生成面板

        Args:
            user_query: 用户查询
            filter_datasource: 过滤数据源（可选）
            use_cache: 是否使用缓存
            intent_confidence: 意图置信度
            layout_snapshot: 布局快照（可选）

        Returns:
            ChatResponse 对象
        """
        logger.info("处理复杂研究意图: %s", user_query)
        llm_debug = self._clone_llm_logs(llm_logs)

        try:
            # 第一步：LLM 查询规划（三层架构第二层）
            query_plan: QueryPlan = self.query_planner.plan(user_query)
            if query_plan.debug:
                llm_debug.append(dict(query_plan.debug))

            if not query_plan.sub_queries:
                logger.warning("查询规划未生成子查询，回退到简单查询")
                return self._handle_simple_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=intent_confidence,
                    layout_snapshot=layout_snapshot,
                    llm_logs=llm_debug,
                )

            logger.info(
                "查询规划完成: %d 个子查询 - %s",
                len(query_plan.sub_queries),
                query_plan.reasoning,
            )

            data_sub_queries = [sq for sq in query_plan.sub_queries if sq.task_type == "data_fetch"]
            if not data_sub_queries:
                logger.warning("查询规划未包含 data_fetch 子查询，回退到简单查询")
                return self._handle_simple_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=intent_confidence,
                    layout_snapshot=layout_snapshot,
                    llm_logs=llm_debug,
                )
            analysis_sub_queries = [
                sq for sq in query_plan.sub_queries if sq.task_type in {"analysis", "report"}
            ]

            # 第二步：并行执行数据子查询（三层架构第三层）
            sub_query_results: List[SubQueryResult] = self.parallel_executor.execute_parallel(
                sub_queries=data_sub_queries,
                use_cache=use_cache,
                prefer_single_route=True,
            )

            # 第三步：聚合结果
            success_results = [
                result for result in sub_query_results
                if result.result and result.result.status == "success"
            ]

            if not success_results:
                # 所有子查询都失败
                error_messages = [
                    f"- {result.sub_query.query}: {result.error}"
                    for result in sub_query_results
                    if result.error
                ]
                return ChatResponse(
                    success=False,
                    intent_type="complex_research",
                    message=f"复杂研究失败，所有子查询均未成功：\n" + "\n".join(error_messages),
                    metadata={
                        "query_plan": query_plan.reasoning,
                        "sub_query_count": len(query_plan.sub_queries),
                        "success_count": 0,
                        "intent_confidence": intent_confidence,
                        "debug": self._compose_debug_payload(
                            None,
                            llm_debug,
                            None,
                        ),
                    },
                )

            # 第四步：构建聚合数据集
            aggregated_datasets: List[QueryDataset] = []
            for result in success_results:
                query_result = result.result
                datasets = query_result.datasets or []
                if datasets:
                    aggregated_datasets.extend(datasets)
                else:
                    # 如果没有 datasets，从 result 构造一个
                    aggregated_datasets.append(self._dataset_from_result(query_result))

            # 第五步：生成面板（复用 _build_panel 逻辑）
            # 使用第一个成功的 query_result 作为主结果
            primary_result = success_results[0].result
            panel_result = self._build_panel(
                query_result=primary_result,
                datasets=aggregated_datasets,
                intent_confidence=intent_confidence,
                user_query=user_query,
                layout_snapshot=layout_snapshot,
            )

            # 第五步：执行分析子查询（LLM 总结）
            analysis_summaries = self._run_analysis_sub_queries(
                analysis_sub_queries,
                aggregated_datasets,
            )

            # 第六步：构造响应消息
            message_parts = []
            for result in success_results:
                query_result = result.result
                feed = query_result.feed_title or "数据"
                message_parts.append(f"{feed}（{len(query_result.items or [])} 条）")

            message = f"已完成复杂研究，获取 {len(success_results)} 组数据：" + "；".join(message_parts)
            if analysis_summaries:
                message += "\n分析总结：" + "；".join(item["summary"] for item in analysis_summaries)

            # 第七步：构造元数据
            rag_traces = [
                result.result.rag_trace
                for result in success_results
                if result.result and result.result.rag_trace
            ]
            if len(rag_traces) == 1:
                rag_debug = rag_traces[0]
            elif rag_traces:
                rag_debug = rag_traces
            else:
                rag_debug = None

            debug_info = self._compose_debug_payload(
                panel_result.debug,
                llm_debug,
                rag_debug,
            )

            metadata: Dict[str, Any] = {
                "generated_path": primary_result.generated_path,
                "source": primary_result.source,
                "cache_hit": primary_result.cache_hit,
                "intent_confidence": intent_confidence,
                "feed_title": primary_result.feed_title,
                "component_confidence": panel_result.component_confidence,
                "requested_components": panel_result.debug.get("requested_components"),
                "planner_reasons": panel_result.debug.get("planner_reasons"),
                "planner_engine": panel_result.debug.get("planner_engine"),
                "debug": debug_info,
                "datasets": self._summarize_datasets(aggregated_datasets, primary_result),
                "retrieved_tools": self._format_retrieved_tools(primary_result.retrieved_tools),
                # 复杂研究特有元数据
                "research_type": "complex_research",
                "query_plan": {
                    "reasoning": query_plan.reasoning,
                    "sub_query_count": len(query_plan.sub_queries),
                    "success_count": len(success_results),
                    "failure_count": len(sub_query_results) - len(success_results),
                    "estimated_time": query_plan.estimated_time,
                },
                "sub_queries": [
                    {
                        "query": result.sub_query.query,
                        "datasource": result.sub_query.datasource,
                        "status": "success" if result.result else "failed",
                        "error": result.error,
                        "execution_time": result.execution_time,
                        "item_count": len(result.result.items) if result.result else 0,
                        "task_type": result.sub_query.task_type,
                    }
                    for result in sub_query_results
                ],
            }
            if analysis_summaries:
                metadata["analysis"] = analysis_summaries
                metadata["sub_queries"].extend(
                    [
                        {
                            "query": entry["query"],
                            "datasource": "analysis",
                            "status": "analysis",
                            "error": None,
                            "execution_time": entry.get("execution_time"),
                            "item_count": entry.get("item_count"),
                            "analysis_summary": entry["summary"],
                            "task_type": entry.get("task_type", "analysis"),
                        }
                        for entry in analysis_summaries
                    ]
                )

            # 提取警告信息
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
                intent_type="complex_research",
                message=message,
                data=panel_result.payload,
                data_blocks=panel_result.data_blocks,
                metadata=metadata,
            )

        except Exception as exc:
            logger.error("复杂研究处理失败: %s", exc, exc_info=True)
            return ChatResponse(
                success=False,
                intent_type="complex_research",
                message=f"复杂研究失败：{exc}",
                metadata={
                    "error": str(exc),
                    "intent_confidence": intent_confidence,
                    "debug": self._compose_debug_payload(None, llm_debug, None),
                },
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
        normalized = datasets or [self._dataset_from_result(query_result)]
        block_inputs: List[PanelBlockInput] = []
        planner_reasons_acc: List[str] = []
        planner_engines: List[str] = []

        for index, dataset in enumerate(normalized, start=1):
            source_info = SourceInfo(
                datasource=self._guess_datasource(dataset.generated_path),
                route=dataset.generated_path or "",
                params={},
                fetched_at=None,
                request_id=None,
            )

            planned_components, planner_reasons, planner_engine = self._plan_components_for_source(
                source_info.route,
                user_query=user_query,
                layout_snapshot=layout_snapshot,
                item_count=self._infer_dataset_item_count(dataset),
            )
            planner_engines.append(planner_engine)
            planner_reasons_acc.extend([f"[dataset-{index}] {reason}" for reason in planner_reasons])

            block_input = PanelBlockInput(
                block_id=f"data_block_{uuid4().hex[:8]}",
                records=self._dataset_records(dataset),
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
        result.debug.setdefault("planner_engine", self._merge_planner_engines(planner_engines))
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

    @staticmethod
    def _dataset_from_result(query_result: DataQueryResult) -> QueryDataset:
        return QueryDataset(
            route_id=None,
            provider=None,
            name=query_result.feed_title,
            generated_path=query_result.generated_path,
            items=query_result.items,
            feed_title=query_result.feed_title,
            source=query_result.source,
            cache_hit=query_result.cache_hit,
            reasoning=query_result.reasoning,
            payload=query_result.payload,
        )

    @staticmethod
    def _dataset_records(dataset: QueryDataset) -> List[Dict[str, Any]]:
        if dataset.payload and isinstance(dataset.payload, dict):
            return [dataset.payload]
        return dataset.items or []

    @staticmethod
    def _infer_dataset_item_count(dataset: QueryDataset) -> int:
        records = ChatService._dataset_records(dataset)
        return len(records)

    @staticmethod
    def _merge_planner_engines(engines: List[str]) -> str:
        if not engines:
            return "rule"
        if len(set(engines)) == 1:
            return engines[0]
        if "llm" in engines:
            return "llm"
        if "error" in engines and "rule" in engines:
            return "mixed"
        return engines[0]

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

        dataset_summary, total_items = self._build_dataset_preview(datasets)
        if not dataset_summary or total_items == 0:
            return []

        summaries: List[Dict[str, Any]] = []
        for sub_query in analysis_sub_queries:
            prompt = self._build_analysis_prompt(sub_query.query, dataset_summary)
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

    @staticmethod
    def _build_analysis_prompt(analysis_query: str, dataset_summary: str) -> str:
        return (
            f"用户需要回答的问题是：{analysis_query}\n"
            "以下是最近抓取到的数据，请基于这些数据总结内容趋势、主题或方向。"
            "务必引用数据中的具体现象，输出要点式总结。\n"
            f"{dataset_summary}\n"
            "请给出不超过4条的分析结论。"
        )

    def _build_dataset_preview(self, datasets: List[QueryDataset], max_items: int = 20) -> Tuple[str, int]:
        """
        构建数据集预览文本，在多个数据集间均匀分配采样数量。

        Args:
            datasets: 数据集列表
            max_items: 最大采样数量

        Returns:
            (预览文本, 实际采样数量)
        """
        if not datasets:
            return "", 0

        lines: List[str] = []
        count = 0

        # 计算每个数据集的采样数量（均匀分配）
        items_per_dataset = max(1, max_items // len(datasets))

        for dataset in datasets:
            header = dataset.feed_title or dataset.generated_path or "数据集"
            lines.append(f"[{header}]")
            records = self._dataset_records(dataset)

            # 限制当前数据集的采样数量
            dataset_count = 0
            for record in records:
                if count >= max_items:
                    break
                if dataset_count >= items_per_dataset:
                    break

                title = record.get("title") or record.get("name") or record.get("keyword") or "未命名"
                desc = record.get("description") or record.get("summary") or ""
                lines.append(f"- {title}: {desc[:120]}")
                count += 1
                dataset_count += 1

        return "\n".join(lines), count

    @staticmethod
    def _clone_llm_logs(llm_logs: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        if not llm_logs:
            return []
        return [dict(entry) for entry in llm_logs]

    @staticmethod
    def _compose_debug_payload(
        panel_debug: Optional[Dict[str, Any]] = None,
        llm_logs: Optional[List[Dict[str, Any]]] = None,
        rag_trace: Optional[Any] = None,
    ) -> Dict[str, Any]:
        debug_info: Dict[str, Any] = {}
        if panel_debug:
            debug_info.update(panel_debug)
        if llm_logs:
            debug_info.setdefault("llm_calls", []).extend([
                dict(entry) for entry in llm_logs
            ])
        if rag_trace:
            debug_info["rag"] = rag_trace
        return debug_info

    @staticmethod
    def _guess_datasource(generated_path: Optional[str]) -> str:
        """通过生成的路径推测数据源标识。"""
        if not generated_path:
            return "unknown"
        stripped = generated_path.strip("/")
        if not stripped:
            return "unknown"
        return stripped.split("/")[0]

    def _format_success_message(
        self,
        datasets: List[QueryDataset],
        fallback_feed: Optional[str],
        fallback_source: Optional[str],
    ) -> str:
        if not datasets:
            if fallback_feed:
                return f"已获取 {fallback_feed} 的数据卡片"
            return "已获取数据卡片"

        if len(datasets) == 1:
            dataset = datasets[0]
            feed = dataset.feed_title or dataset.name or fallback_feed or "数据"
            source_hint = self._format_source_hint(dataset.source or fallback_source)
            return f"已获取 {feed}（{len(dataset.items or [])} 条{source_hint}）"

        parts = []
        for dataset in datasets:
            feed = dataset.feed_title or dataset.name or "数据"
            source_hint = self._format_source_hint(dataset.source)
            parts.append(f"{feed}（{len(dataset.items or [])} 条{source_hint}）")
        return f"已获取 {len(datasets)} 组数据：" + "；".join(parts)

    @staticmethod
    def _format_source_hint(source: Optional[str]) -> str:
        if source == "local":
            return "本地"
        if source == "fallback":
            return "公共"
        return "远程"

    def _summarize_datasets(self, datasets: List[QueryDataset], query_result: DataQueryResult) -> List[Dict[str, Any]]:
        summary: List[Dict[str, Any]] = []
        records = datasets or [self._dataset_from_result(query_result)]
        for dataset in records:
            summary.append(
                {
                    "route": dataset.generated_path,
                    "feed_title": dataset.feed_title,
                    "source": dataset.source,
                    "item_count": len(dataset.items or []),
                }
            )
        return summary

    @staticmethod
    def _format_retrieved_tools(retrieved_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        格式化 RAG 检索到的候选工具列表，用于前端展示。

        Args:
            retrieved_tools: RAG 检索返回的工具列表

        Returns:
            格式化后的工具列表，包含关键信息
        """
        if not retrieved_tools:
            return []

        formatted = []
        for tool in retrieved_tools:
            formatted.append({
                "route_id": tool.get("route_id"),
                "name": tool.get("name"),
                "provider": tool.get("datasource") or tool.get("provider_id"),
                "description": (tool.get("description") or "")[:120],
                "score": tool.get("score"),
                "route": ChatService._resolve_tool_route(tool),
                "example_path": tool.get("example_path"),
            })
        return formatted

    @staticmethod
    def _resolve_tool_route(tool: Dict[str, Any]) -> Optional[str]:
        if tool.get("route"):
            return tool["route"]

        path_template = tool.get("path_template")
        if isinstance(path_template, list) and path_template:
            return path_template[0]
        if isinstance(path_template, str):
            return path_template

        if tool.get("generated_path"):
            return tool.get("generated_path")

        if tool.get("example_path"):
            return tool.get("example_path")

        return None

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
