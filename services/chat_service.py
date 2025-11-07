"""
对话服务
职责：作为统一入口，整合意图识别、数据查询与智能数据面板输出。
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.intent_service import IntentService, get_intent_service
from services.data_query_service import DataQueryService, DataQueryResult
from api.schemas.panel import PanelPayload, DataBlock, SourceInfo
from services.panel.panel_generator import (
    PanelGenerator,
    PanelBlockInput,
    PanelGenerationResult,
)
from services.panel.analytics import summarize_payload
from services.panel.component_planner import ComponentPlannerConfig, PlannerContext, plan_components_for_route
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
        manage_data_service: bool = False,
        component_planner_config: Optional[ComponentPlannerConfig] = None,
    ):
        """
        初始化对话服务。

        Args:
            data_query_service: 数据查询服务实例
            intent_service: 意图识别服务（可选，默认使用全局单例）
            manage_data_service: 是否由ChatService负责关闭 data_query_service
            component_planner_config: 组件规划器配置（可选）
        """
        self.data_query_service = data_query_service
        self.intent_service = intent_service or get_intent_service()
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
    ) -> ChatResponse:
        """
        处理用户查询。

        Args:
            user_query: 用户输入的自然语言查询
            filter_datasource: 过滤特定数据源（可选）
            use_cache: 是否使用缓存

        Returns:
            ChatResponse 对象
        """
        logger.info("收到对话请求: %s", user_query)

        try:
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
    ) -> ChatResponse:
        """处理数据查询意图。"""
        logger.debug("处理数据查询意图")

        query_result = self.data_query_service.query(
            user_query=user_query,
            filter_datasource=filter_datasource,
            use_cache=use_cache,
        )

        if query_result.status == "success":
            item_count = self._infer_item_count(query_result)

            panel_result = self._build_panel(
                query_result=query_result,
                intent_confidence=intent_confidence,
                user_query=user_query,
                item_count=item_count,
            )

            message = self._format_success_message(
                feed_title=query_result.feed_title,
                item_count=item_count,
                source=query_result.source,
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
            }

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
        intent_confidence: float,
        user_query: str,
        item_count: Optional[int] = None,
    ) -> PanelGenerationResult:
        """将数据查询结果转换为智能面板结构。"""
        source_info = SourceInfo(
            datasource=self._guess_datasource(query_result.generated_path),
            route=query_result.generated_path or "",
            params={},
            fetched_at=None,
            request_id=None,
        )

        summary = summarize_payload(source_info.route or "", query_result.payload or {})

        try:
            planner_context = PlannerContext(
                item_count=summary.get("item_count", item_count),
                user_preferences=(),
                raw_query=user_query,
                layout_mode=None,
            )
            manifest = get_route_manifest(source_info.route)
            decision = None
            planner_engine = "rule"
            if self.llm_planner and self.llm_planner.is_available():
                decision = self.llm_planner.plan(
                    route=source_info.route,
                    manifest=manifest,
                    summary=summary,
                    context=planner_context,
                    config=self.component_planner_config,
                )
                if decision:
                    planner_engine = "llm"
            if decision is None:
                decision = plan_components_for_route(
                    source_info.route,
                    config=self.component_planner_config,
                    context=planner_context,
                )
            planner_reasons = decision.reasons if decision else []
            planner_reasons.insert(0, f"engine: {planner_engine}")
            planned_components = decision.components if decision else None
        except Exception as exc:
            logger.warning(f"组件规划失败，使用默认策略: {exc}")
            planner_reasons = [f"planner_error: {exc}"]
            planned_components = None

        block_input = PanelBlockInput(
            block_id="data_block_1",
            records=[query_result.payload] if query_result.payload else query_result.items,
            source_info=source_info,
            title=query_result.feed_title,
            stats={"intent_confidence": intent_confidence},
            requested_components=planned_components,
        )

        result = self.panel_generator.generate(
            mode="append",
            block_inputs=[block_input],
            history_token=None,
        )
        # 设置调试信息（用于追踪规划决策）
        result.debug.setdefault("planner_reasons", planner_reasons)
        result.debug.setdefault("planner_engine", planner_engine)  # 直接使用变量，不从字符串解析
        result.debug.setdefault("requested_components", planned_components)
        return result



    @staticmethod
    def _infer_item_count(query_result: DataQueryResult) -> int:
        if query_result.payload and isinstance(query_result.payload, dict):
            payload_items = query_result.payload.get("items")
            if isinstance(payload_items, list):
                return len(payload_items)
            payload_item = query_result.payload.get("item")
            if isinstance(payload_item, list):
                return len(payload_item)
        return len(query_result.items or [])

    @staticmethod
    def _guess_datasource(generated_path: Optional[str]) -> str:
        """通过生成的路径推测数据源标识。"""
        if not generated_path:
            return "unknown"
        stripped = generated_path.strip("/")
        if not stripped:
            return "unknown"
        return stripped.split("/")[0]

    @staticmethod
    def _format_success_message(
        feed_title: Optional[str],
        item_count: int,
        source: Optional[str],
    ) -> str:
        """格式化成功消息。"""
        parts = []

        if feed_title:
            parts.append(f"已获取「{feed_title}」")
        else:
            parts.append("已获取数据")

        parts.append(f"共{item_count}条")

        if source == "local":
            parts.append("（本地服务）")
        elif source == "fallback":
            parts.append("（公共服务）")

        return "".join(parts)

    def close(self):
        """关闭服务并释放资源。"""
        if self._manage_data_service and self.data_query_service:
            self.data_query_service.close()
            logger.info("ChatService 已关闭（管理 DataQueryService 资源）")

    def __enter__(self):
        """上下文管理器入口。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出时自动释放资源。"""
        self.close()
