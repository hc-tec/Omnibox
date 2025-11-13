"""订阅解析器（SubscriptionResolver）

整合 QueryParser + VectorStore + ActionRegistry，
实现从自然语言到 RSSHub 路径的完整解析。

使用流程：
1. QueryParser 解析自然语言查询
2. VectorStore 语义搜索订阅
3. SubscriptionService 获取订阅详情
4. ActionRegistry 构建 RSSHub 路径
"""

import logging
import json
from typing import Optional, Dict, Any
from services.subscription.query_parser import QueryParser, ParsedQuery
from services.database.subscription_service import SubscriptionService
from services.subscription.action_registry import ActionRegistry

logger = logging.getLogger(__name__)


class SubscriptionResolver:
    """订阅解析器

    整合 QueryParser + VectorStore + ActionRegistry，
    实现从自然语言到 RSSHub 路径的完整解析。
    """

    def __init__(self, llm_client):
        """初始化订阅解析器

        Args:
            llm_client: LLM 客户端实例（用于 QueryParser）
        """
        self.query_parser = QueryParser(llm_client)
        self.subscription_service = SubscriptionService()
        self.action_registry = ActionRegistry()
        logger.info("SubscriptionResolver 初始化完成")

    def resolve(
        self,
        query: str,
        user_id: int,
        min_similarity: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """解析查询并返回 RSSHub 路径

        Args:
            query: 用户输入的自然语言查询
            user_id: 用户 ID（用于过滤订阅）
            min_similarity: 最小相似度阈值

        Returns:
            {
                "subscription_id": 1,
                "path": "/bilibili/user/video/12345",
                "display_name": "科技美学",
                "action_display_name": "投稿视频",
                "entity_name": "科技美学",
                "action": "videos",
                "similarity": 0.95
            }
            或 None（解析失败）
        """
        try:
            # Step 1: 解析查询
            logger.info(f"开始解析查询: '{query}'")
            parsed = self.query_parser.parse(query)

            logger.info(
                f"查询解析结果: entity='{parsed.entity_name}', "
                f"action='{parsed.action}', platform='{parsed.platform}', "
                f"confidence={parsed.confidence}"
            )

            # Step 2: 语义搜索订阅
            matches = self.subscription_service.search_subscriptions(
                query=parsed.entity_name,
                platform=parsed.platform,
                user_id=user_id,
                is_active=True,
                search_type="semantic",  # 使用语义搜索
                top_k=5,
                min_similarity=min_similarity
            )

            if not matches:
                logger.info(f"未找到匹配的订阅（相似度 >= {min_similarity}）")
                return None

            # 取相似度最高的订阅
            subscription = matches[0]
            similarity = getattr(subscription, '_similarity', 1.0)  # 获取相似度

            logger.info(
                f"找到匹配订阅: id={subscription.id}, "
                f"display_name='{subscription.display_name}', "
                f"similarity={similarity:.3f}"
            )

            # Step 3: 解析动作
            action = self._resolve_action(parsed.action, subscription)

            if not action:
                # 如果未指定动作，使用默认动作
                supported_actions = json.loads(subscription.supported_actions)
                action = supported_actions[0] if supported_actions else None
                logger.info(f"未指定动作，使用默认动作: '{action}'")

            if not action:
                logger.warning("无法确定动作")
                return None

            # Step 4: 获取动作定义
            action_def = self.action_registry.get_action(
                subscription.platform,
                subscription.entity_type,
                action
            )

            if not action_def:
                logger.warning(
                    f"未找到动作定义: platform='{subscription.platform}', "
                    f"entity_type='{subscription.entity_type}', action='{action}'"
                )
                return None

            # Step 5: 构建路径
            identifiers = json.loads(subscription.identifiers)
            path = self.action_registry.build_path(
                subscription.platform,
                subscription.entity_type,
                action,
                identifiers
            )

            result = {
                "subscription_id": subscription.id,
                "path": path,
                "display_name": subscription.display_name,
                "action_display_name": action_def.display_name,
                "entity_name": parsed.entity_name,
                "action": action,
                "similarity": similarity,
                "platform": subscription.platform,
                "entity_type": subscription.entity_type
            }

            logger.info(
                f"解析成功: '{query}' → path='{path}', "
                f"similarity={similarity:.3f}"
            )

            return result

        except Exception as e:
            logger.error(f"解析查询失败: {e}", exc_info=True)
            return None

    def _resolve_action(
        self,
        action_text: Optional[str],
        subscription
    ) -> Optional[str]:
        """解析动作名称

        将自然语言动作（如"投稿视频"）映射到动作名称（如"videos"）

        Args:
            action_text: 自然语言动作（可选）
            subscription: 订阅对象

        Returns:
            动作名称或 None
        """
        if not action_text:
            return None

        supported_actions = json.loads(subscription.supported_actions)

        # 构建动作名称到显示名称的映射
        action_map = {}
        for action in supported_actions:
            action_def = self.action_registry.get_action(
                subscription.platform,
                subscription.entity_type,
                action
            )
            if action_def:
                action_map[action_def.display_name.lower()] = action
                # 也添加动作名称本身的映射
                action_map[action.lower()] = action

        # 模糊匹配
        action_text_lower = action_text.lower()

        # 1. 精确匹配
        if action_text_lower in action_map:
            return action_map[action_text_lower]

        # 2. 包含匹配
        for display_name, action_name in action_map.items():
            if action_text_lower in display_name or display_name in action_text_lower:
                logger.info(f"动作模糊匹配: '{action_text}' → '{action_name}'")
                return action_name

        logger.warning(f"无法匹配动作: '{action_text}' (支持的动作: {supported_actions})")
        return None

    def batch_resolve(
        self,
        queries: list[str],
        user_id: int,
        min_similarity: float = 0.7
    ) -> list[Optional[Dict[str, Any]]]:
        """批量解析查询

        Args:
            queries: 查询列表
            user_id: 用户 ID
            min_similarity: 最小相似度阈值

        Returns:
            解析结果列表（包含 None）
        """
        results = []
        for query in queries:
            result = self.resolve(query, user_id, min_similarity)
            results.append(result)

        logger.info(
            f"批量解析完成: {len(queries)} 个查询, "
            f"{sum(1 for r in results if r is not None)} 个成功"
        )

        return results
