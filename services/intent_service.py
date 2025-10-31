"""
意图识别服务
职责：判断用户查询的意图类型（数据查询 vs 闲聊）
"""

import logging
from typing import Literal, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """
    意图识别结果

    Attributes:
        intent_type: 意图类型（data_query/chitchat）
        confidence: 置信度（0.0-1.0）
        reasoning: 推理过程（可选）
    """
    intent_type: Literal["data_query", "chitchat"]
    confidence: float
    reasoning: str = ""


class IntentService:
    """
    意图识别服务（同步实现）

    使用规则+关键词的方式判断用户意图：
    - data_query: 用户想查询具体数据（包含数据源、平台、内容类型等关键词）
    - chitchat: 用户进行闲聊（问候、闲谈、无明确数据需求）

    使用示例：
        service = IntentService()
        result = service.recognize("虎扑步行街最新帖子")
        if result.intent_type == "data_query":
            # 调用数据查询服务
            pass
        else:
            # 调用闲聊服务
            pass
    """

    # 数据查询关键词
    DATA_QUERY_KEYWORDS = {
        # 数据源
        "虎扑", "微博", "知乎", "bilibili", "b站", "抖音", "小红书",
        "github", "v2ex", "豆瓣", "reddit", "twitter", "youtube",

        # 内容类型
        "帖子", "文章", "视频", "动态", "评论", "热搜", "话题", "新闻",
        "博客", "问答", "讨论", "直播", "up主", "博主",

        # 操作动词
        "查看", "看看", "获取", "找", "搜", "查", "要", "给我", "帮我",
        "最新", "热门", "推荐", "订阅",

        # RSS相关
        "rss", "feed", "订阅源",
    }

    # 闲聊关键词
    CHITCHAT_KEYWORDS = {
        "你好", "您好", "hi", "hello", "早上好", "下午好", "晚上好",
        "谢谢", "感谢", "再见", "拜拜",
        "你是谁", "你叫什么", "什么是", "怎么样", "如何",
    }

    def __init__(self):
        """初始化意图识别服务"""
        logger.info("IntentService初始化完成")

    def recognize(self, user_query: str) -> IntentResult:
        """
        识别用户查询的意图

        Args:
            user_query: 用户查询文本

        Returns:
            IntentResult: 意图识别结果
        """
        user_query_lower = user_query.lower().strip()

        # 空查询默认为闲聊
        if not user_query_lower:
            return IntentResult(
                intent_type="chitchat",
                confidence=1.0,
                reasoning="空查询"
            )

        # 计算数据查询关键词匹配数
        data_query_matches = sum(
            1 for keyword in self.DATA_QUERY_KEYWORDS
            if keyword.lower() in user_query_lower
        )

        # 计算闲聊关键词匹配数
        chitchat_matches = sum(
            1 for keyword in self.CHITCHAT_KEYWORDS
            if keyword.lower() in user_query_lower
        )

        # 判断逻辑：数据查询关键词多 -> data_query
        if data_query_matches > chitchat_matches:
            confidence = min(0.7 + data_query_matches * 0.1, 0.99)
            return IntentResult(
                intent_type="data_query",
                confidence=confidence,
                reasoning=f"匹配到{data_query_matches}个数据查询关键词"
            )

        # 闲聊关键词多 -> chitchat
        elif chitchat_matches > 0:
            confidence = min(0.7 + chitchat_matches * 0.1, 0.99)
            return IntentResult(
                intent_type="chitchat",
                confidence=confidence,
                reasoning=f"匹配到{chitchat_matches}个闲聊关键词"
            )

        # 默认：包含问号 -> 可能是数据查询
        elif "?" in user_query or "？" in user_query:
            return IntentResult(
                intent_type="data_query",
                confidence=0.6,
                reasoning="包含问号，可能是查询"
            )

        # 默认：短查询（<5字） -> 闲聊
        elif len(user_query) < 5:
            return IntentResult(
                intent_type="chitchat",
                confidence=0.65,
                reasoning="短查询，可能是闲聊"
            )

        # 默认fallback：数据查询（因为这是一个数据聚合系统）
        else:
            return IntentResult(
                intent_type="data_query",
                confidence=0.5,
                reasoning="默认fallback为数据查询"
            )

    def is_data_query(self, user_query: str, threshold: float = 0.5) -> bool:
        """
        快捷方法：判断是否为数据查询意图

        Args:
            user_query: 用户查询
            threshold: 置信度阈值（默认0.5）

        Returns:
            True if 数据查询，False otherwise
        """
        result = self.recognize(user_query)
        return result.intent_type == "data_query" and result.confidence >= threshold


# 全局单例
_intent_service = None


def get_intent_service() -> IntentService:
    """
    获取意图识别服务单例

    Returns:
        IntentService: 全局唯一的IntentService实例
    """
    global _intent_service
    if _intent_service is None:
        _intent_service = IntentService()
    return _intent_service
