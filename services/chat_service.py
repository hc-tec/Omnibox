"""
对话服务
职责：统一的对话入口，整合意图识别和数据查询
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.intent_service import IntentService, get_intent_service
from services.data_query_service import DataQueryService, DataQueryResult
from integration.data_executor import FeedItem

logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    """
    对话响应

    Attributes:
        success: 是否成功
        intent_type: 识别的意图类型（data_query/chitchat）
        message: 响应消息文本
        data: 数据项列表（仅data_query时有值）
        metadata: 元数据（路径、来源、缓存命中等）
    """
    success: bool
    intent_type: str
    message: str
    data: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class ChatService:
    """
    对话服务（同步实现）

    统一的对话入口，负责：
    1. 意图识别（数据查询 vs 闲聊）
    2. 根据意图路由到不同的处理服务
    3. 格式化响应

    使用示例：
        service = ChatService(data_query_service)
        response = service.chat("虎扑步行街最新帖子")
        print(response.message)
        if response.data:
            for item in response.data:
                print(item['title'])
    """

    def __init__(
        self,
        data_query_service: DataQueryService,
        intent_service: Optional[IntentService] = None,
        manage_data_service: bool = False,
    ):
        """
        初始化对话服务

        Args:
            data_query_service: 数据查询服务
            intent_service: 意图识别服务（可选，None则使用全局单例）
            manage_data_service: 是否由ChatService负责关闭data_query_service（默认False）
        """
        self.data_query_service = data_query_service
        self.intent_service = intent_service or get_intent_service()
        self._manage_data_service = manage_data_service

        logger.info("ChatService初始化完成")

    def chat(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        use_cache: bool = True,
    ) -> ChatResponse:
        """
        处理用户对话

        Args:
            user_query: 用户查询
            filter_datasource: 过滤特定数据源（可选）
            use_cache: 是否使用缓存

        Returns:
            ChatResponse: 对话响应
        """
        logger.info(f"收到用户查询: {user_query}")

        try:
            # ========== 阶段1: 意图识别 ==========
            intent_result = self.intent_service.recognize(user_query)
            logger.debug(
                f"意图识别: {intent_result.intent_type} "
                f"(置信度: {intent_result.confidence:.2f})"
            )

            # ========== 阶段2: 根据意图路由 ==========
            if intent_result.intent_type == "data_query":
                return self._handle_data_query(
                    user_query,
                    filter_datasource,
                    use_cache,
                    intent_result.confidence,
                )
            else:
                return self._handle_chitchat(user_query, intent_result.confidence)

        except Exception as e:
            logger.error(f"对话处理失败: {e}", exc_info=True)
            return ChatResponse(
                success=False,
                intent_type="error",
                message=f"抱歉，处理您的请求时发生了错误：{str(e)}",
                metadata={"error": str(e)},
            )

    def _handle_data_query(
        self,
        user_query: str,
        filter_datasource: Optional[str],
        use_cache: bool,
        intent_confidence: float,
    ) -> ChatResponse:
        """处理数据查询意图"""
        logger.debug("处理数据查询意图")

        # 调用数据查询服务
        query_result = self.data_query_service.query(
            user_query=user_query,
            filter_datasource=filter_datasource,
            use_cache=use_cache,
        )

        # 根据查询结果生成响应
        if query_result.status == "success":
            # 成功获取数据
            data_items = [self._feed_item_to_dict(item) for item in query_result.items]

            message = self._format_success_message(
                query_result.feed_title,
                len(data_items),
                query_result.source,
            )

            return ChatResponse(
                success=True,
                intent_type="data_query",
                message=message,
                data=data_items,
                metadata={
                    "generated_path": query_result.generated_path,
                    "source": query_result.source,
                    "cache_hit": query_result.cache_hit,
                    "intent_confidence": intent_confidence,
                    "feed_title": query_result.feed_title,
                },
            )

        elif query_result.status == "needs_clarification":
            # 需要澄清
            return ChatResponse(
                success=False,
                intent_type="data_query",
                message=query_result.clarification_question or "需要更多信息",
                metadata={
                    "status": "needs_clarification",
                    "reasoning": query_result.reasoning,
                    "intent_confidence": intent_confidence,
                },
            )

        elif query_result.status == "not_found":
            # 未找到匹配
            return ChatResponse(
                success=False,
                intent_type="data_query",
                message=query_result.clarification_question or "抱歉，没有找到相关功能",
                metadata={
                    "status": "not_found",
                    "reasoning": query_result.reasoning,
                    "intent_confidence": intent_confidence,
                },
            )

        else:
            # 错误
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
        """处理闲聊意图"""
        logger.debug("处理闲聊意图")

        # 简单的闲聊响应（后续可接入闲聊LLM）
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

        # 查找匹配的响应
        user_query_lower = user_query.lower().strip()
        for keyword, response in chitchat_responses.items():
            if keyword.lower() in user_query_lower:
                return ChatResponse(
                    success=True,
                    intent_type="chitchat",
                    message=response,
                    metadata={
                        "intent_confidence": intent_confidence,
                    },
                )

        # 默认闲聊响应
        return ChatResponse(
            success=True,
            intent_type="chitchat",
            message='我是RSS数据聚合助手。您可以问我关于各种平台数据的问题，比如“虎扑步行街最新帖子”、“B站热门视频”等。',
            metadata={
                "intent_confidence": intent_confidence,
            },
        )

    @staticmethod
    def _feed_item_to_dict(item: FeedItem) -> Dict[str, Any]:
        """将FeedItem转换为字典"""
        return {
            "title": item.title,
            "link": item.link,
            "description": item.description,
            "pub_date": item.pub_date,
            "author": item.author,
            "guid": item.guid,
            "category": item.category,
            "media_url": item.media_url,
            "media_type": item.media_type,
        }

    @staticmethod
    def _format_success_message(
        feed_title: Optional[str],
        item_count: int,
        source: Optional[str],
    ) -> str:
        """格式化成功消息"""
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
        """关闭服务，释放资源"""
        if self._manage_data_service and self.data_query_service:
            self.data_query_service.close()
            logger.info("ChatService已关闭（管理DataQueryService资源）")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
