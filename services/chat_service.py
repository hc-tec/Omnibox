"""
对话服务
职责：作为统一入口，整合意图识别、数据查询与智能数据面板输出。
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from uuid import uuid4

from services.intent_service import IntentService, get_intent_service
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
    1. 意图识别（数据查询 / 闲聊）
    2. 调度数据查询服务
    3. 生成智能数据面板结构
    """

    def __init__(
        self,
        data_query_service: DataQueryService,
        intent_service: Optional[IntentService] = None,
        research_service=None,  # 新增：研究服务（可选）
        manage_data_service: bool = False,
        component_planner_config: Optional[ComponentPlannerConfig] = None,
    ):
        """
        初始化对话服务。

        Args:
            data_query_service: 数据查询服务实例
            intent_service: 意图识别服务（可选，默认使用全局单例）
            research_service: 研究服务实例（可选，用于复杂研究任务）
            manage_data_service: 是否由ChatService负责关闭 data_query_service
            component_planner_config: 组件规划器配置（可选）
        """
        self.data_query_service = data_query_service
        self.intent_service = intent_service or get_intent_service()
        self.research_service = research_service  # 新增
        self._manage_data_service = manage_data_service
        self.panel_generator = PanelGenerator()
        self.component_planner_config = component_planner_config or ComponentPlannerConfig()

        # 初始化 LLM 组件规划器（作为规则引擎的备选方案）
        try:
            self.llm_planner = LLMComponentPlanner()
        except Exception as exc:
            logger.warning(f"LLM 组件规划器初始化失败，将仅使用规则引擎: {exc}")
            self.llm_planner = None

        logger.info("ChatService 初始化完成")

    def chat(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        use_cache: bool = True,
        layout_snapshot: Optional[List[Dict[str, Any]]] = None,
        mode: str = "auto",  # 新增：auto / simple / research
        client_task_id: Optional[str] = None,
    ) -> ChatResponse:
        """
        处理用户查询。

        Args:
            user_query: 用户输入的自然语言查询
            filter_datasource: 过滤特定数据源（可选）
            use_cache: 是否使用缓存
            layout_snapshot: 当前面板布局快照（可选）
            mode: 查询模式 - auto(自动)/simple(简单查询)/research(复杂研究)

        Returns:
            ChatResponse 对象
        """
        logger.info("收到对话请求: %s (mode=%s)", user_query, mode)

        try:
            # 阶段0：如果显式指定研究模式
            if mode == "research":
                if not self.research_service:
                    logger.warning("研究模式被请求但 ResearchService 未初始化，回退到简单查询")
                else:
                    return self._handle_research(
                        user_query=user_query,
                        filter_datasource=filter_datasource,
                        intent_confidence=1.0,
                        client_task_id=client_task_id,
                    )

            # 阶段1：意图识别
            intent_result = self.intent_service.recognize(user_query)
            logger.debug(
                "意图识别结果: %s (置信度 %.2f)",
                intent_result.intent_type,
                intent_result.confidence,
            )

            # 阶段2：根据意图路由
            if intent_result.intent_type == "data_query":
                return self._handle_data_query(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    use_cache=use_cache,
                    intent_confidence=intent_result.confidence,
                    layout_snapshot=layout_snapshot,
                )

            return self._handle_chitchat(
                user_query=user_query,
                intent_confidence=intent_result.confidence,
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
    ) -> ChatResponse:
        """处理数据查询意图。"""
        logger.debug("处理数据查询意图")

        query_result = self.data_query_service.query(
            user_query=user_query,
            filter_datasource=filter_datasource,
            use_cache=use_cache,
        )

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
                "debug": panel_result.debug,
                "datasets": self._summarize_datasets(datasets, query_result),
            }

            # 提取并暴露适配器/渲染警告信息到顶层 metadata
            blocks_debug = panel_result.debug.get("blocks", [])
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

        if query_result.status == "needs_clarification":
            return ChatResponse(
                success=False,
                intent_type="data_query",
                message=query_result.clarification_question or "需要更多信息以继续处理。",
                metadata={
                    "status": "needs_clarification",
                    "reasoning": query_result.reasoning,
                    "intent_confidence": intent_confidence,
                },
            )

        if query_result.status == "not_found":
            return ChatResponse(
                success=False,
                intent_type="data_query",
                message=query_result.clarification_question or "抱歉，没有找到相关能力。",
                metadata={
                    "status": "not_found",
                    "reasoning": query_result.reasoning,
                    "intent_confidence": intent_confidence,
                },
            )

        return ChatResponse(
            success=False,
            intent_type="data_query",
            message=f"查询失败：{query_result.reasoning}",
            metadata={
                "status": "error",
                "reasoning": query_result.reasoning,
                "intent_confidence": intent_confidence,
                "generated_path": query_result.generated_path,
            },
        )

    def _handle_chitchat(
        self,
        user_query: str,
        intent_confidence: float,
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
                return ChatResponse(
                    success=True,
                    intent_type="chitchat",
                    message=response,
                    metadata={"intent_confidence": intent_confidence},
                )

        return ChatResponse(
            success=True,
            intent_type="chitchat",
            message="我是RSS数据聚合助手。您可以问我关于各种平台数据的问题，比如“虎扑步行街最新帖子”、“B站热门视频”等。",
            metadata={"intent_confidence": intent_confidence},
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
            if self.llm_planner and self.llm_planner.is_available():
                decision = self.llm_planner.plan(
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
            payload_items = dataset.payload.get("items")
            if isinstance(payload_items, list):
                return payload_items
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

    def _handle_research(
        self,
        user_query: str,
        filter_datasource: Optional[str],
        intent_confidence: float,
        client_task_id: Optional[str] = None,
    ) -> ChatResponse:
        """
        处理复杂研究意图（多轮动态研究）。

        Args:
            user_query: 用户查询
            filter_datasource: 过滤数据源（可选）
            intent_confidence: 意图置信度

        Returns:
            ChatResponse 对象
        """
        logger.debug("处理复杂研究意图")

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
