"""订阅管理服务

负责订阅的 CRUD 操作和 ID 映射查询。

按照 subscription-system-design.md v2.2 设计方案实现：
- 分离实体和动作
- 支持多种搜索方式（模糊匹配/语义搜索）
- 自动从 ActionRegistry 获取支持的动作列表
"""

from sqlmodel import Session, select, or_
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import logging

from .models import Subscription, SubscriptionEmbedding
from .connection import get_db_connection
from services.subscription.action_registry import ActionRegistry

logger = logging.getLogger(__name__)


class SubscriptionService:
    """订阅管理服务（修订版 v2.2）

    负责实体订阅的 CRUD 操作和 ID 映射查询。
    不再直接存储 resource_type 和路径模板，改为存储 entity_type。

    使用示例：
    ```python
    from services.database import SubscriptionService

    service = SubscriptionService()

    # 创建订阅
    subscription = service.create_subscription(
        display_name="科技美学",
        platform="bilibili",
        entity_type="user",
        identifiers={"uid": "12345"},
        description="数码测评UP主",
        aliases=["科技美学", "科技美学Official"],
        tags=["数码", "科技"]
    )

    # 解析实体ID
    identifiers = service.resolve_entity(
        entity_name="科技美学",
        platform="bilibili",
        entity_type="user"
    )
    # 返回: {"uid": "12345"}
    ```
    """

    def __init__(self, vector_store=None):
        """初始化订阅服务

        Args:
            vector_store: 向量存储实例（可选，用于语义搜索）
        """
        self.db = get_db_connection()
        self._vector_store = vector_store

    @property
    def vector_store(self):
        """延迟加载向量存储（避免循环导入）"""
        if self._vector_store is None:
            try:
                from services.subscription.vector_service import SubscriptionVectorStore
                self._vector_store = SubscriptionVectorStore()
                logger.info("向量存储已加载")
            except Exception as e:
                logger.warning(f"向量存储加载失败: {e}")
                self._vector_store = None
        return self._vector_store

    def count_subscriptions(
        self,
        user_id: Optional[int] = None,
        platform: Optional[str] = None,
        entity_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> int:
        """统计订阅总数（修复：支持精确分页）

        Args:
            user_id: 用户ID（Stage 4 之前为 None，忽略用户隔离）
            platform: 平台过滤
            entity_type: 实体类型过滤
            is_active: 是否激活

        Returns:
            符合条件的订阅总数
        """
        with self.db.get_session() as session:
            from sqlmodel import func

            statement = select(func.count(Subscription.id))

            # 用户过滤
            effective_user_id = user_id if user_id is not None else 0
            statement = statement.where(Subscription.user_id == effective_user_id)

            # 平台过滤
            if platform:
                statement = statement.where(Subscription.platform == platform)

            # 实体类型过滤
            if entity_type:
                statement = statement.where(Subscription.entity_type == entity_type)

            # 激活状态过滤
            if is_active is not None:
                statement = statement.where(Subscription.is_active == is_active)

            return session.exec(statement).one()

    def list_subscriptions(
        self,
        user_id: Optional[int] = None,
        platform: Optional[str] = None,
        entity_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Subscription]:
        """列出订阅（支持多种过滤）

        Args:
            user_id: 用户ID（Stage 4 之前为 None，忽略用户隔离）
            platform: 平台过滤
            entity_type: 实体类型过滤
            is_active: 是否激活
            limit: 返回数量
            offset: 偏移量

        Returns:
            订阅列表
        """
        with self.db.get_session() as session:
            statement = select(Subscription)

            # 用户过滤
            # Stage 4 之前默认使用 user_id=0（单用户模式）
            effective_user_id = user_id if user_id is not None else 0
            statement = statement.where(Subscription.user_id == effective_user_id)

            # 平台过滤
            if platform:
                statement = statement.where(Subscription.platform == platform)

            # 实体类型过滤
            if entity_type:
                statement = statement.where(Subscription.entity_type == entity_type)

            # 激活状态过滤
            if is_active is not None:
                statement = statement.where(Subscription.is_active == is_active)

            # 分页
            statement = statement.limit(limit).offset(offset)

            # 按创建时间倒序
            statement = statement.order_by(Subscription.created_at.desc())

            return list(session.exec(statement).all())

    def get_subscription(self, subscription_id: int) -> Optional[Subscription]:
        """获取订阅详情

        Args:
            subscription_id: 订阅ID

        Returns:
            订阅对象，如果不存在则返回 None
        """
        with self.db.get_session() as session:
            return session.get(Subscription, subscription_id)

    def create_subscription(
        self,
        display_name: str,
        platform: str,
        entity_type: str,  # ← 修订：不是 resource_type
        identifiers: Dict[str, Any],
        user_id: Optional[int] = None,  # ← 新增：用户ID（Stage 4 之前默认为 0）
        **kwargs
    ) -> Subscription:
        """创建订阅

        Args:
            display_name: 显示名称（如"科技美学"）
            platform: 平台（bilibili/zhihu/...）
            entity_type: 实体类型（user/column/repo，不是 user_video!）
            identifiers: API标识字典（如 {"uid": "12345"}）
            user_id: 用户ID（Stage 4 之前为 None）
            **kwargs: 其他可选参数（avatar_url, description, aliases, tags）

        Returns:
            创建的订阅对象
        """
        with self.db.get_session() as session:
            # 自动获取支持的动作
            supported_actions = ActionRegistry.get_supported_actions(
                platform, entity_type
            )

            # 确保 aliases 包含 display_name（修复：复制列表避免副作用）
            # 修复：确保 aliases 永远不为 None，默认为空列表
            aliases = list(kwargs.get("aliases") or [])  # ← 复制列表，None 转为 []
            if display_name not in aliases:
                aliases.insert(0, display_name)

            # 标准化 identifiers JSON（修复：确保唯一约束生效）
            # 按键排序，确保相同数据生成相同字符串
            identifiers_json = json.dumps(
                identifiers,
                ensure_ascii=False,
                sort_keys=True  # ← 关键：按键排序
            )

            # 修复：在单用户阶段使用 user_id=0 而不是 NULL
            # SQLite 中 NULL != NULL，会导致唯一约束失效
            effective_user_id = user_id if user_id is not None else 0

            # 修复：确保 tags 永远不为 None，默认为空列表
            tags = kwargs.get("tags") or []

            subscription = Subscription(
                display_name=display_name,
                platform=platform,
                entity_type=entity_type,
                identifiers=identifiers_json,
                supported_actions=json.dumps(supported_actions, ensure_ascii=False),
                aliases=json.dumps(aliases, ensure_ascii=False),
                tags=json.dumps(tags, ensure_ascii=False),
                avatar_url=kwargs.get("avatar_url"),
                description=kwargs.get("description"),
                user_id=effective_user_id
            )

            session.add(subscription)
            session.commit()
            session.refresh(subscription)

            logger.info(
                f"✅ 创建订阅成功: {display_name} "
                f"({platform}/{entity_type}, id={subscription.id})"
            )

            # 触发向量化（Phase 2）
            self._trigger_embedding(subscription)

            return subscription

    def update_subscription(
        self,
        subscription_id: int,
        **updates
    ) -> Optional[Subscription]:
        """更新订阅

        Args:
            subscription_id: 订阅ID
            **updates: 要更新的字段

        Returns:
            更新后的订阅对象，如果不存在则返回 None
        """
        with self.db.get_session() as session:
            subscription = session.get(Subscription, subscription_id)
            if not subscription:
                return None

            # 检查 platform 或 entity_type 是否变更（修复：需要同步刷新 supported_actions）
            platform_changed = "platform" in updates and updates["platform"] != subscription.platform
            entity_type_changed = "entity_type" in updates and updates["entity_type"] != subscription.entity_type

            # 应用更新
            for key, value in updates.items():
                if key in ["aliases", "tags", "supported_actions"]:
                    # JSON 字段需要序列化（修复：确保 None 转为空列表）
                    safe_value = value if value is not None else []
                    setattr(subscription, key, json.dumps(safe_value, ensure_ascii=False))
                elif key == "identifiers":
                    # identifiers 也是 JSON 字段（标准化排序）
                    setattr(subscription, key, json.dumps(value, ensure_ascii=False, sort_keys=True))
                else:
                    setattr(subscription, key, value)

            # 如果 platform 或 entity_type 变更，重新获取 supported_actions
            if platform_changed or entity_type_changed:
                new_platform = updates.get("platform", subscription.platform)
                new_entity_type = updates.get("entity_type", subscription.entity_type)
                supported_actions = ActionRegistry.get_supported_actions(
                    new_platform, new_entity_type
                )
                subscription.supported_actions = json.dumps(supported_actions, ensure_ascii=False)
                logger.info(
                    f"🔄 重新获取 supported_actions: {new_platform}/{new_entity_type} "
                    f"-> {supported_actions}"
                )

            subscription.updated_at = datetime.now()

            session.add(subscription)
            session.commit()
            session.refresh(subscription)

            logger.info(f"✅ 更新订阅成功: id={subscription_id}")

            # 如果关键信息变更，重新向量化
            if any(k in updates for k in [
                "display_name", "description", "aliases", "tags"
            ]):
                self._trigger_embedding(subscription)

            return subscription

    def delete_subscription(self, subscription_id: int) -> bool:
        """删除订阅

        Args:
            subscription_id: 订阅ID

        Returns:
            是否删除成功
        """
        with self.db.get_session() as session:
            subscription = session.get(Subscription, subscription_id)
            if not subscription:
                return False

            session.delete(subscription)
            session.commit()

            logger.info(f"✅ 删除订阅成功: id={subscription_id}")

            # 同时删除向量数据（ChromaDB）
            if self.vector_store:
                try:
                    self.vector_store.delete_subscription(subscription_id)
                except Exception as e:
                    logger.warning(f"删除向量数据失败: {e}")

            return True

    def search_subscriptions(
        self,
        query: str,
        platform: Optional[str] = None,
        user_id: Optional[int] = None,  # ← 新增：用户过滤（安全）
        is_active: Optional[bool] = True,  # ← 新增：只搜索激活的订阅
        search_type: str = "fuzzy",
        top_k: int = 5,  # ← Phase 2: 语义搜索返回数量
        min_similarity: float = 0.7  # ← Phase 2: 最小相似度阈值
    ) -> List[Subscription]:
        """搜索订阅

        Args:
            query: 搜索查询（自然语言）
            platform: 平台过滤（可选）
            user_id: 用户ID（None = 游客模式，查询公共订阅）
            is_active: 是否只搜索激活的订阅（默认 True）
            search_type: 搜索类型
                - fuzzy: 模糊匹配（display_name/aliases）
                - semantic: 语义搜索（需要向量化，Phase 2 实现）
            top_k: 语义搜索返回数量（仅 search_type="semantic" 有效）
            min_similarity: 最小相似度阈值（仅 search_type="semantic" 有效）

        Returns:
            订阅列表
        """
        if search_type == "semantic":
            # Phase 2: 语义搜索
            return self._semantic_search(
                query, platform, user_id, is_active, top_k, min_similarity
            )
        else:
            return self._fuzzy_search(query, platform, user_id, is_active)

    def _fuzzy_search(
        self,
        query: str,
        platform: Optional[str],
        user_id: Optional[int],
        is_active: Optional[bool]
    ) -> List[Subscription]:
        """模糊搜索（修复：在 Python 层过滤 JSON 字段）

        注意：JSON 字段的 SQL LIKE 查询不可靠，改为先获取候选记录，
        然后在 Python 中解析 JSON 并精确匹配。

        修复：添加 user_id 和 is_active 过滤，防止越权。
        """
        with self.db.get_session() as session:
            # 先在 SQL 层过滤（user_id, platform, is_active）
            statement = select(Subscription)

            # 用户过滤（游客模式：user_id=None 时不过滤）
            if user_id is not None:
                statement = statement.where(Subscription.user_id == user_id)

            # 平台过滤
            if platform:
                statement = statement.where(Subscription.platform == platform)

            # 激活状态过滤（修复：防止停用订阅被搜索到）
            if is_active is not None:
                statement = statement.where(Subscription.is_active == is_active)

            all_subscriptions = list(session.exec(statement).all())

            # 在 Python 中过滤
            results = []
            query_lower = query.lower()

            for sub in all_subscriptions:
                # 检查 display_name
                if query_lower in sub.display_name.lower():
                    results.append(sub)
                    continue

                # 检查 description
                if sub.description and query_lower in sub.description.lower():
                    results.append(sub)
                    continue

                # 检查 aliases（解析 JSON）
                try:
                    aliases = json.loads(sub.aliases)
                    if any(query_lower in alias.lower() for alias in aliases):
                        results.append(sub)
                        continue
                except (json.JSONDecodeError, AttributeError):
                    pass

                # 检查 tags（解析 JSON）
                try:
                    tags = json.loads(sub.tags)
                    if any(query_lower in tag.lower() for tag in tags):
                        results.append(sub)
                except (json.JSONDecodeError, AttributeError):
                    pass

            return results

    def resolve_entity(
        self,
        entity_name: str,
        platform: str,
        entity_type: str,  # ← 修订：不是 resource_type
        user_id: Optional[int] = None,  # ← 新增：用户过滤（安全）
        is_active: bool = True  # ← 新增：只解析激活的订阅
    ) -> Optional[Dict[str, Any]]:
        """解析实体标识符（修订版）

        输入：\"科技美学\", platform=\"bilibili\", entity_type=\"user\"
        输出：{\"uid\": \"12345\", \"uname\": \"科技美学Official\"}

        修订：不再需要 resource_type，因为我们只查找实体。
        修复：添加 user_id 和 is_active 过滤，防止越权泄露。

        这是核心方法，供查询解析时调用。
        """
        # 1. 先尝试精确匹配（修复：传递 user_id 和 is_active）
        subscriptions = self.search_subscriptions(
            query=entity_name,
            platform=platform,
            user_id=user_id,
            is_active=is_active,
            search_type="fuzzy"
        )

        # 2. 过滤实体类型（修订：不再过滤 resource_type）
        matched = [
            sub for sub in subscriptions
            if sub.entity_type == entity_type and sub.display_name == entity_name
        ]

        if matched:
            return json.loads(matched[0].identifiers)

        # 3. 尝试 aliases 匹配
        alias_matched = [
            sub for sub in subscriptions
            if sub.entity_type == entity_type
            and entity_name in json.loads(sub.aliases)
        ]

        if alias_matched:
            return json.loads(alias_matched[0].identifiers)

        # 4. 找不到
        logger.warning(
            f"无法解析实体: entity_name='{entity_name}', "
            f"platform='{platform}', entity_type='{entity_type}'"
        )
        return None

    def _trigger_embedding(self, subscription: Subscription) -> None:
        """触发订阅向量化（Phase 2）

        Args:
            subscription: 订阅对象
        """
        if not self.vector_store:
            logger.debug("向量存储未启用，跳过向量化")
            return

        try:
            # 构建订阅数据字典
            subscription_data = {
                "display_name": subscription.display_name,
                "platform": subscription.platform,
                "entity_type": subscription.entity_type,
                "description": subscription.description,
                "aliases": subscription.aliases,  # JSON 字符串
                "tags": subscription.tags  # JSON 字符串
            }

            # 向量化
            self.vector_store.add_subscription(
                subscription.id,
                subscription_data
            )

            logger.info(f"✅ 订阅 {subscription.id} 向量化完成")

        except Exception as e:
            # 向量化失败不应阻塞订阅创建/更新
            logger.error(f"向量化失败: {e}", exc_info=True)

    def _semantic_search(
        self,
        query: str,
        platform: Optional[str],
        user_id: Optional[int],
        is_active: Optional[bool],
        top_k: int = 10,
        min_similarity: float = 0.7
    ) -> List[Subscription]:
        """语义搜索（Phase 2）

        使用向量相似度搜索订阅。

        Args:
            query: 搜索查询
            platform: 平台过滤
            user_id: 用户ID
            is_active: 是否激活
            top_k: 返回数量
            min_similarity: 最小相似度阈值

        Returns:
            订阅列表
        """
        if not self.vector_store:
            logger.warning("向量存储未启用，回退到模糊搜索")
            return self._fuzzy_search(query, platform, user_id, is_active)

        try:
            # 向量检索
            matches = self.vector_store.search(
                query=query,
                platform=platform,
                top_k=top_k,
                min_similarity=min_similarity
            )

            if not matches:
                logger.info(f"语义搜索无结果: '{query}'")
                return []

            # 获取订阅详情（并应用额外过滤）
            results = []
            for subscription_id, similarity in matches:
                subscription = self.get_subscription(subscription_id)

                if not subscription:
                    continue

                # 用户过滤（游客模式：user_id=None 时不过滤）
                if user_id is not None:
                    if subscription.user_id != user_id:
                        continue

                # 激活状态过滤
                if is_active is not None and subscription.is_active != is_active:
                    continue

                # 保存相似度分数（供 schema 解析辅助函数使用）
                subscription._similarity = similarity
                results.append(subscription)

            logger.info(
                f"语义搜索 '{query}' 返回 {len(results)} 个结果 "
                f"(min_similarity={min_similarity})"
            )

            return results

        except Exception as e:
            logger.error(f"语义搜索失败: {e}", exc_info=True)
            # 回退到模糊搜索
            return self._fuzzy_search(query, platform, user_id, is_active)
