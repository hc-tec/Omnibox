# 订阅管理系统设计方案（修订版）

> **核心问题**：用户记得的是"自然语言标识"（UP主名字），而API需要的是"机器标识"（UP主ID）。如何实现通用的ID映射和解析机制，同时支持同一实体的多种访问方式？

---

## 问题分析

### 典型场景

**场景1：B站UP主的多种访问方式**
```
用户输入："科技美学的最新投稿视频"
  → 实体: 科技美学 (uid=12345)
  → 动作: 投稿视频
  → RSSHub路径：/bilibili/user/video/12345

用户输入："科技美学的关注列表"
  → 实体: 科技美学 (uid=12345)  ← 同一个实体!
  → 动作: 关注列表
  → RSSHub路径：/bilibili/followings/video/12345

用户输入："科技美学的收藏"
  → 实体: 科技美学 (uid=12345)  ← 还是同一个实体!
  → 动作: 收藏
  → RSSHub路径：/bilibili/favorites/12345

用户输入："科技美学的动态"
  → 实体: 科技美学 (uid=12345)  ← 同一个实体!
  → 动作: 动态
  → RSSHub路径：/bilibili/user/dynamic/12345
```

**场景2：知乎专栏文章**
```
用户输入："少数派专栏的最新文章"
  → 实体: 少数派 (column_id=sspai)
  → 动作: 文章
  → RSSHub路径：/zhihu/zhuanlan/sspai
```

**场景3：GitHub仓库动态**
```
用户输入："langchain项目的最新commits"
  → 实体: langchain (owner=langchain-ai, repo=langchain)
  → 动作: commits
  → RSSHub路径：/github/commits/langchain-ai/langchain

用户输入："langchain项目的issues"
  → 实体: langchain (同一个实体!)
  → 动作: issues
  → RSSHub路径：/github/issue/langchain-ai/langchain
```

### 核心矛盾

| 用户视角 | API视角 | 矛盾点 |
|---------|---------|--------|
| 自然语言标识（名字） | 机器标识（ID） | 映射关系需要维护 |
| "科技美学" | uid=12345 | ID难以记忆 |
| 一个实体，多种访问方式 | 不同的API端点 | **需要分离实体和动作** ⭐ |
| 模糊匹配 | 精确匹配 | 容错性差 |

---

## 架构设计

### 核心概念

**实体 (Entity)** vs **动作 (Action)**

```
┌─────────────────────────────────────────────────────────────┐
│  订阅管理系统                                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  实体 (Entity)                    动作 (Action)              │
│  ┌─────────────────┐             ┌──────────────────┐       │
│  │ 科技美学          │             │ videos (投稿)     │       │
│  │ uid: 12345      │────────────▶│ following (关注)  │       │
│  │ platform: bili  │             │ favorites (收藏)  │       │
│  │ entity_type: user│             │ dynamics (动态)   │       │
│  └─────────────────┘             └──────────────────┘       │
│         ▲                                  │                 │
│         │                                  │                 │
│         │                                  ▼                 │
│  1. 订阅存储实体标识          2. 查询时动态组合路径            │
│  2. 一个实体支持多个动作      3. 路径模板配置化                │
│                                                              │
└─────────────────────────────────────────────────────────────┘

用户查询："科技美学的关注列表"
  ↓
QueryParser 提取：
  - entity_name: "科技美学"
  - action: "following"
  ↓
Subscription 系统查找：
  - entity_name → uid=12345
  ↓
ActionRegistry 查找：
  - (bilibili, user, following) → "/bilibili/followings/video/:uid"
  ↓
路径生成：
  - "/bilibili/followings/video/12345"
```

---

## 数据模型设计

### 1. 核心实体：Subscription（订阅）

```python
# services/database/subscription_models.py
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class Subscription(SQLModel, table=True):
    """订阅管理（修订版）

    只存储实体信息，不绑定特定的 resource_type 或路径模板。
    同一个实体可以通过不同的动作访问不同的API端点。

    修订原因：
    原设计将 entity + action 绑定在一起，导致同一UP主访问不同接口
    需要创建多个订阅记录，这是错误的。正确做法是分离实体和动作。
    """
    __tablename__ = "subscriptions"

    id: Optional[int] = Field(default=None, primary_key=True)

    # 显示信息
    display_name: str = Field(index=True, description="显示名称，如 '科技美学'")
    avatar_url: Optional[str] = Field(default=None, description="头像URL")
    description: Optional[str] = Field(default=None, description="简介")

    # 实体标识（修订：区分 entity_type 而非 resource_type）
    platform: str = Field(index=True, description="平台：bilibili/zhihu/weibo/github/...")
    entity_type: str = Field(
        description="实体类型：user/column/repo/topic（不是 user_video!）"
    )

    # API标识（JSON存储，支持多种标识符）
    identifiers: str = Field(
        description="JSON格式API标识，如 {\"uid\": \"12345\", \"uname\": \"科技美学Official\"}"
    )

    # 搜索优化
    aliases: str = Field(
        default="[]",
        description="JSON格式别名列表，如 [\"科技美学\", \"科技美学Official\", \"那岩\"]"
    )
    tags: str = Field(
        default="[]",
        description="JSON格式标签列表，如 [\"数码\", \"科技\", \"测评\"]"
    )

    # 支持的动作（修订：记录此实体支持哪些动作）
    supported_actions: str = Field(
        default="[]",
        description="JSON格式支持的动作列表，如 [\"videos\", \"following\", \"favorites\", \"dynamics\"]"
    )

    # 元数据
    subscribe_count: int = Field(default=0, description="订阅人数（多用户场景）")
    last_fetched_at: Optional[datetime] = Field(default=None, description="最后拉取时间")
    is_active: bool = Field(default=True, description="是否激活")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 多用户支持（Stage 4 之前为 NULL）
    user_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        description="NULL = 公共订阅（单用户阶段）"
    )


class SubscriptionEmbedding(SQLModel, table=True):
    """订阅向量化记录

    为订阅信息生成向量，支持语义搜索。
    实际向量存储在 ChromaDB（subscription Collection）。
    """
    __tablename__ = "subscription_embeddings"

    subscription_id: int = Field(foreign_key="subscriptions.id", primary_key=True)
    embedding_version: str = Field(description="向量模型版本")
    last_embedded_at: datetime = Field(description="最后向量化时间")
    is_stale: bool = Field(default=False, description="内容是否已过时")
```

#### 多用户隔离策略

**阶段性实施方案**（参考知识库系统设计）

在 Stage 4 用户系统实现之前：

1. **Phase 1-3**: `user_id` 字段允许为 `NULL`
   - 所有订阅数据的 `user_id` 保持 `NULL`
   - 系统按"单用户模式"运行
   - 不进行任何用户隔离
   - `subscribe_count` 保持为 0（多用户后才有意义）

2. **Stage 4 实现后**:
   - 创建 `users` 表
   - 为默认用户创建记录 (id=1)
   - 执行数据迁移: `UPDATE subscriptions SET user_id = 1 WHERE user_id IS NULL`
   - 在 API 层添加用户认证和隔离逻辑
   - `subscribe_count` 可通过多用户订阅同一实体来计算

3. **向后兼容**:
   - Service 层的查询在 Stage 4 之前忽略 `user_id`
   - Stage 4 之后自动从请求上下文获取 `user_id`

```python
# Service 层向后兼容示例
class SubscriptionService:
    def list_subscriptions(
        self,
        user_id: Optional[int] = None,  # Stage 4 之前为 None
        **filters
    ) -> List[Subscription]:
        """列出订阅

        Args:
            user_id: 用户ID（Stage 4 之前为 None，忽略用户隔离）
        """
        with self.db.get_session() as session:
            statement = select(Subscription)

            # Stage 4 之前: 忽略 user_id
            # Stage 4 之后: 添加 user_id 过滤
            if user_id is not None:
                statement = statement.where(Subscription.user_id == user_id)

            # 应用其他过滤器...
            if filters.get("platform"):
                statement = statement.where(
                    Subscription.platform == filters["platform"]
                )

            if filters.get("is_active") is not None:
                statement = statement.where(
                    Subscription.is_active == filters["is_active"]
                )

            return list(session.exec(statement).all())
```

**唯一约束**

为避免重复订阅，添加唯一约束：

```python
# 在 Subscription 模型中添加
from sqlmodel import UniqueConstraint

class Subscription(SQLModel, table=True):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "entity_type",
            "identifiers",
            "user_id",
            name="uq_subscription_entity_user"
        ),
    )
    # ... 其他字段
```

**subscribe_count 计算策略**

Stage 4 之后，`subscribe_count` 的维护方式：

```python
# 方案A: 实时计算（推荐）
def get_subscribe_count(subscription_id: int) -> int:
    """实时统计订阅人数"""
    with db.get_session() as session:
        count = session.exec(
            select(func.count(Subscription.id))
            .where(Subscription.id == subscription_id)
        ).one()
        return count

# 方案B: 触发器维护（性能更好，但需要数据库触发器）
# 在创建/删除订阅时自动更新 subscribe_count
```

```

### 2. 数据示例

```json
// B站UP主订阅示例（修订版）
{
  "id": 1,
  "display_name": "科技美学",
  "avatar_url": "https://...",
  "description": "专注数码产品测评",
  "platform": "bilibili",
  "entity_type": "user",  // ← 修订：不是 "user_video"
  "identifiers": {
    "uid": "12345",
    "uname": "科技美学Official"
  },
  "aliases": ["科技美学", "科技美学Official", "那岩"],
  "tags": ["数码", "科技", "测评"],
  "supported_actions": ["videos", "following", "favorites", "dynamics"],  // ← 新增
  "subscribe_count": 1,
  "created_at": "2025-11-13T10:00:00Z"
}

// 知乎专栏订阅示例（修订版）
{
  "id": 2,
  "display_name": "少数派",
  "avatar_url": "https://...",
  "description": "高效工具和生活方式",
  "platform": "zhihu",
  "entity_type": "column",  // ← 修订：不是 "zhuanlan"
  "identifiers": {
    "column_id": "sspai",
    "column_name": "少数派"
  },
  "aliases": ["少数派", "sspai", "SSPai"],
  "tags": ["效率", "工具", "生活方式"],
  "supported_actions": ["articles"],  // ← 新增
  "subscribe_count": 1,
  "created_at": "2025-11-13T10:00:00Z"
}

// GitHub仓库订阅示例（修订版）
{
  "id": 3,
  "display_name": "LangChain",
  "avatar_url": "https://...",
  "description": "Building applications with LLMs through composability",
  "platform": "github",
  "entity_type": "repo",  // ← 修订：明确是 repo
  "identifiers": {
    "owner": "langchain-ai",
    "repo": "langchain"
  },
  "aliases": ["LangChain", "langchain-ai/langchain"],
  "tags": ["llm", "ai", "framework"],
  "supported_actions": ["commits", "issues", "pull_requests", "releases"],  // ← 新增
  "subscribe_count": 5,
  "created_at": "2025-11-13T10:00:00Z"
}
```

### 3. ActionRegistry（动作注册表）

```python
# services/subscription/action_registry.py
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass

@dataclass
class ActionDefinition:
    """动作定义

    描述一个实体支持的某个动作及其RSSHub路径模板。
    """
    action_name: str  # "videos", "following", "favorites"
    display_name: str  # "投稿视频", "关注列表", "收藏"
    path_template: str  # "/bilibili/user/video/:uid"
    required_identifiers: List[str]  # ["uid"]
    description: str  # "获取UP主的投稿视频"


class ActionRegistry:
    """动作注册表（配置驱动）

    维护 (platform, entity_type, action) → RSSHub路径模板 的映射。
    解决原设计中 resource_type 过于耦合的问题。
    """

    # 静态配置（可以从配置文件或数据库加载）
    ACTION_TEMPLATES: Dict[Tuple[str, str, str], ActionDefinition] = {
        # B站用户（UP主）
        ("bilibili", "user", "videos"): ActionDefinition(
            action_name="videos",
            display_name="投稿视频",
            path_template="/bilibili/user/video/:uid",
            required_identifiers=["uid"],
            description="获取UP主的投稿视频"
        ),
        ("bilibili", "user", "following"): ActionDefinition(
            action_name="following",
            display_name="关注列表",
            path_template="/bilibili/followings/video/:uid",
            required_identifiers=["uid"],
            description="获取UP主的关注列表"
        ),
        ("bilibili", "user", "favorites"): ActionDefinition(
            action_name="favorites",
            display_name="收藏",
            path_template="/bilibili/favorites/:uid",
            required_identifiers=["uid"],
            description="获取UP主的收藏夹"
        ),
        ("bilibili", "user", "dynamics"): ActionDefinition(
            action_name="dynamics",
            display_name="动态",
            path_template="/bilibili/user/dynamic/:uid",
            required_identifiers=["uid"],
            description="获取UP主的动态"
        ),

        # 知乎专栏
        ("zhihu", "column", "articles"): ActionDefinition(
            action_name="articles",
            display_name="专栏文章",
            path_template="/zhihu/zhuanlan/:column_id",
            required_identifiers=["column_id"],
            description="获取知乎专栏文章"
        ),

        # 知乎用户
        ("zhihu", "user", "activities"): ActionDefinition(
            action_name="activities",
            display_name="动态",
            path_template="/zhihu/people/activities/:id",
            required_identifiers=["id"],
            description="获取知乎用户动态"
        ),

        # 微博用户
        ("weibo", "user", "posts"): ActionDefinition(
            action_name="posts",
            display_name="微博",
            path_template="/weibo/user/:uid",
            required_identifiers=["uid"],
            description="获取微博用户的微博"
        ),

        # GitHub仓库
        ("github", "repo", "commits"): ActionDefinition(
            action_name="commits",
            display_name="提交记录",
            path_template="/github/commits/:owner/:repo",
            required_identifiers=["owner", "repo"],
            description="获取GitHub仓库的提交记录"
        ),
        ("github", "repo", "issues"): ActionDefinition(
            action_name="issues",
            display_name="Issues",
            path_template="/github/issue/:owner/:repo",
            required_identifiers=["owner", "repo"],
            description="获取GitHub仓库的Issues"
        ),
        ("github", "repo", "pull_requests"): ActionDefinition(
            action_name="pull_requests",
            display_name="Pull Requests",
            path_template="/github/pull/:owner/:repo",
            required_identifiers=["owner", "repo"],
            description="获取GitHub仓库的Pull Requests"
        ),
        ("github", "repo", "releases"): ActionDefinition(
            action_name="releases",
            display_name="版本发布",
            path_template="/github/release/:owner/:repo",
            required_identifiers=["owner", "repo"],
            description="获取GitHub仓库的版本发布"
        ),

        # ... 更多平台和动作
    }

    @classmethod
    def get_action(
        cls,
        platform: str,
        entity_type: str,
        action: str
    ) -> Optional[ActionDefinition]:
        """获取动作定义

        Args:
            platform: 平台（bilibili/zhihu/...）
            entity_type: 实体类型（user/column/repo/...）
            action: 动作名称（videos/following/...）

        Returns:
            动作定义，如果不存在则返回 None
        """
        return cls.ACTION_TEMPLATES.get((platform, entity_type, action))

    @classmethod
    def get_supported_actions(
        cls,
        platform: str,
        entity_type: str
    ) -> List[str]:
        """获取实体支持的所有动作

        Args:
            platform: 平台
            entity_type: 实体类型

        Returns:
            动作名称列表
        """
        actions = []
        for (p, et, action), _ in cls.ACTION_TEMPLATES.items():
            if p == platform and et == entity_type:
                actions.append(action)
        return actions

    @classmethod
    def build_path(
        cls,
        platform: str,
        entity_type: str,
        action: str,
        identifiers: Dict[str, str]
    ) -> Optional[str]:
        """构建RSSHub路径

        Args:
            platform: 平台
            entity_type: 实体类型
            action: 动作
            identifiers: 标识符字典（如 {"uid": "12345"}）

        Returns:
            完整的RSSHub路径，如果无法构建则返回 None

        示例：
            build_path(
                platform="bilibili",
                entity_type="user",
                action="following",
                identifiers={"uid": "12345"}
            )
            → "/bilibili/followings/video/12345"
        """
        action_def = cls.get_action(platform, entity_type, action)
        if not action_def:
            return None

        # 检查必需的标识符
        for req_id in action_def.required_identifiers:
            if req_id not in identifiers:
                raise ValueError(
                    f"缺少必需的标识符: {req_id}，"
                    f"需要: {action_def.required_identifiers}"
                )

        # 替换路径模板中的占位符
        path = action_def.path_template
        for key, value in identifiers.items():
            path = path.replace(f":{key}", str(value))

        return path
```

---

## 核心服务设计

### 1. SubscriptionService（订阅管理）

```python
# services/subscription/subscription_service.py
from sqlmodel import Session, select, or_
from typing import List, Optional, Dict, Any
import json

class SubscriptionService:
    """订阅管理服务（修订版）

    负责实体订阅的 CRUD 操作和 ID 映射查询。
    不再直接存储 resource_type 和路径模板，改为存储 entity_type。
    """

    def __init__(self, db: DatabaseConnection):
        self.db = db

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

            # 用户过滤（Stage 4 之前忽略）
            if user_id is not None:
                statement = statement.where(Subscription.user_id == user_id)

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
        user_id: Optional[int] = None,  # ← 新增：用户ID
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
        from services.subscription.action_registry import ActionRegistry

        with self.db.get_session() as session:
            # 自动获取支持的动作
            supported_actions = ActionRegistry.get_supported_actions(
                platform, entity_type
            )

            subscription = Subscription(
                display_name=display_name,
                platform=platform,
                entity_type=entity_type,
                identifiers=json.dumps(identifiers, ensure_ascii=False),
                supported_actions=json.dumps(supported_actions, ensure_ascii=False),
                aliases=json.dumps(
                    kwargs.get("aliases", [display_name]),
                    ensure_ascii=False
                ),
                tags=json.dumps(kwargs.get("tags", []), ensure_ascii=False),
                avatar_url=kwargs.get("avatar_url"),
                description=kwargs.get("description"),
                user_id=user_id  # ← 新增
            )

            session.add(subscription)
            session.commit()
            session.refresh(subscription)

            # 触发向量化（异步）
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

            # 应用更新
            for key, value in updates.items():
                if key in ["aliases", "tags", "supported_actions"]:
                    # JSON 字段需要序列化
                    setattr(subscription, key, json.dumps(value, ensure_ascii=False))
                else:
                    setattr(subscription, key, value)

            subscription.updated_at = datetime.now()

            session.add(subscription)
            session.commit()
            session.refresh(subscription)

            # 如果关键信息变更，重新向量化
            if any(k in updates for k in ["display_name", "description", "aliases", "tags"]):
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

            # TODO: 同时删除向量数据（ChromaDB）
            # vector_store.delete_subscription(subscription_id)

            return True

    def search_subscriptions(
        self,
        query: str,
        platform: Optional[str] = None,
        search_type: str = "fuzzy"
    ) -> List[Subscription]:
        """搜索订阅

        Args:
            query: 搜索查询（自然语言）
            platform: 平台过滤（可选）
            search_type: 搜索类型
                - fuzzy: 模糊匹配（display_name/aliases）
                - semantic: 语义搜索（需要向量化）

        Returns:
            订阅列表
        """
        if search_type == "semantic":
            return self._semantic_search(query, platform)
        else:
            return self._fuzzy_search(query, platform)

    def _fuzzy_search(
        self,
        query: str,
        platform: Optional[str]
    ) -> List[Subscription]:
        """模糊搜索（基于 SQL LIKE）"""
        with self.db.get_session() as session:
            statement = select(Subscription).where(
                or_(
                    Subscription.display_name.contains(query),
                    Subscription.aliases.contains(query),
                    Subscription.description.contains(query)
                )
            )

            if platform:
                statement = statement.where(Subscription.platform == platform)

            return list(session.exec(statement).all())

    def _semantic_search(
        self,
        query: str,
        platform: Optional[str]
    ) -> List[Subscription]:
        """语义搜索（基于向量检索）

        使用独立的 ChromaDB Collection 'subscriptions'。
        """
        from services.subscription.vector_service import SubscriptionVectorStore

        vector_store = SubscriptionVectorStore()
        results = vector_store.search_subscriptions(
            query,
            top_k=5,
            platform_filter=platform
        )

        # 从数据库加载完整订阅对象
        subscription_ids = [sub_id for sub_id, score, metadata in results]
        with self.db.get_session() as session:
            subscriptions = []
            for sub_id in subscription_ids:
                sub = session.get(Subscription, sub_id)
                if sub:
                    subscriptions.append(sub)
            return subscriptions

    def resolve_entity(
        self,
        entity_name: str,
        platform: str,
        entity_type: str  # ← 修订：不是 resource_type
    ) -> Optional[Dict[str, Any]]:
        """解析实体标识符（修订版）

        输入："科技美学", platform="bilibili", entity_type="user"
        输出：{"uid": "12345", "uname": "科技美学Official"}

        修订：不再需要 resource_type，因为我们只查找实体。

        这是核心方法，供查询解析时调用。
        """
        # 1. 先尝试精确匹配
        subscriptions = self.search_subscriptions(
            query=entity_name,
            platform=platform,
            search_type="fuzzy"
        )

        # 2. 过滤实体类型（修订：不再过滤 resource_type）
        matched = [
            sub for sub in subscriptions
            if sub.entity_type == entity_type and sub.display_name == entity_name
        ]

        if matched:
            return json.loads(matched[0].identifiers)

        # 3. 尝试语义搜索（容错）
        semantic_results = self.search_subscriptions(
            query=entity_name,
            platform=platform,
            search_type="semantic"
        )

        semantic_matched = [
            sub for sub in semantic_results
            if sub.entity_type == entity_type
        ]

        if semantic_matched:
            return json.loads(semantic_matched[0].identifiers)

        # 4. 找不到
        return None

    def _trigger_embedding(self, subscription: Subscription):
        """触发向量化（异步任务）

        在创建/更新订阅时调用，将订阅信息向量化并存储到 ChromaDB。
        """
        from services.subscription.vector_service import SubscriptionVectorStore

        vector_store = SubscriptionVectorStore()

        # 构建语义文档
        semantic_doc = self._build_semantic_doc(subscription)

        # 向量化并存储
        vector_store.add_subscription(
            subscription_id=subscription.id,
            semantic_doc=semantic_doc,
            platform=subscription.platform,
            entity_type=subscription.entity_type  # ← 修订
        )

    def _build_semantic_doc(self, subscription: Subscription) -> str:
        """构建语义文档

        将订阅信息组合为一段文本，供向量化模型使用。
        """
        aliases = json.loads(subscription.aliases)
        tags = json.loads(subscription.tags)

        doc = f"{subscription.display_name}\n"
        if subscription.description:
            doc += f"{subscription.description}\n"
        if aliases:
            doc += f"别名: {', '.join(aliases)}\n"
        if tags:
            doc += f"标签: {', '.join(tags)}\n"
        doc += f"平台: {subscription.platform}\n"
        doc += f"类型: {subscription.entity_type}"  # ← 修订

        return doc
```

### 2. 修订后的 QueryParser

```python
# services/subscription/query_parser.py
from typing import Optional, Dict, Any
from pydantic import BaseModel

class ParsedQuery(BaseModel):
    """解析后的查询结构（修订版）

    修订：分离实体和动作，不再混淆。
    """
    entity_name: str  # ← 修订：实体名称（如"科技美学"）
    entity_type: str  # ← 修订：实体类型（如"user"，不是"user_video"）
    action: str  # ← 新增：动作（如"videos"/"following"/"favorites"）
    platform: str  # 平台（bilibili/zhihu/...）
    filters: Dict[str, Any] = {}  # 可选过滤条件（如"最近一周"）


class QueryParser:
    """查询解析器（修订版 v2.2 - LLM驱动 + 工程可靠性）

    修订：始终使用 LLM 解析（不使用规则引擎），但增加工程可靠性措施。

    修订重点：
    1. 提取实体名称（"科技美学"）
    2. 提取动作意图（"投稿"→"videos"，"关注"→"following"）
    3. 分离这两个概念，不再混淆
    4. **不使用规则引擎**
    5. **新增工程可靠性**：缓存、重试、输出校验、降级策略

    示例：
        输入："科技美学的关注列表"
        输出：ParsedQuery(
            entity_name="科技美学",
            entity_type="user",
            action="following",  ← 关键：识别动作
            platform="bilibili"
        )

        输入："科技美学的最新投稿"
        输出：ParsedQuery(
            entity_name="科技美学",
            entity_type="user",
            action="videos",  ← 不同的动作
            platform="bilibili"
        )
    """

    def __init__(self):
        from query_processor.llm_client import create_llm_client_auto
        self.llm = create_llm_client_auto()
        self._cache: Dict[str, ParsedQuery] = {}  # 解析结果缓存

    def parse(self, query: str) -> Optional[ParsedQuery]:
        """解析自然语言查询（带缓存和可靠性保障）

        Args:
            query: 自然语言查询

        Returns:
            解析后的结构化对象，如果无法解析则返回 None

        可靠性措施：
        1. 缓存：相同查询直接返回缓存结果（避免重复LLM调用）
        2. 重试：LLM失败时自动重试（最多3次）
        3. 校验：验证LLM输出的合法性（枚举检查）
        4. 降级：多次失败后返回部分结果，提示用户手动选择
        """
        # 1. 缓存检查
        if query in self._cache:
            logger.debug(f"命中缓存: {query}")
            return self._cache[query]

        # 2. LLM解析（带重试）
        for attempt in range(3):
            try:
                parsed = self._parse_with_llm(query)

                # 3. 输出校验
                if parsed and self._validate_output(parsed):
                    self._cache[query] = parsed
                    logger.info(f"解析成功: {query} -> {parsed}")
                    return parsed
                else:
                    logger.warning(f"LLM输出校验失败 (尝试 {attempt + 1}/3)")

            except Exception as e:
                logger.error(f"LLM解析异常 (尝试 {attempt + 1}/3): {e}")

        # 4. 降级：多次失败后返回 None（由上层处理）
        logger.error(f"解析失败（已重试3次）: {query}")
        return None

    def _validate_output(self, parsed: ParsedQuery) -> bool:
        """校验LLM输出（枚举检查，不是规则引擎）

        只检查输出的合法性：
        - platform 是否在支持列表中
        - entity_type 是否有效
        - action 是否在 ActionRegistry 中存在

        注意：这不是规则引擎，只是枚举校验，LLM仍然负责语义理解。
        """
        # 检查平台枚举
        VALID_PLATFORMS = {"bilibili", "zhihu", "weibo", "github", "gitee"}
        if parsed.platform not in VALID_PLATFORMS:
            logger.warning(f"无效平台: {parsed.platform}")
            return False

        # 检查实体类型枚举
        VALID_ENTITY_TYPES = {"user", "column", "repo", "topic", "channel"}
        if parsed.entity_type not in VALID_ENTITY_TYPES:
            logger.warning(f"无效实体类型: {parsed.entity_type}")
            return False

        # 检查动作是否在 ActionRegistry 中注册
        from services.subscription.action_registry import ActionRegistry
        if not ActionRegistry.get_action(
            parsed.platform,
            parsed.entity_type,
            parsed.action
        ):
            logger.warning(
                f"ActionRegistry 中不存在此动作: "
                f"({parsed.platform}, {parsed.entity_type}, {parsed.action})"
            )
            return False

        return True

    def _parse_with_llm(self, query: str) -> Optional[ParsedQuery]:
        """使用 LLM 解析（唯一方法）

        优点：灵活、准确、容错性强
        """
        prompt = f"""
你是一个智能查询解析器。请将用户的自然语言查询解析为结构化JSON。

用户查询: "{query}"

请提取以下信息：
1. entity_name: 实体名称（UP主/专栏/博主的名字，如"科技美学"）
2. entity_type: 实体类型（user/column/repo）
3. action: 动作名称（videos/following/favorites/dynamics等）
4. platform: 平台（bilibili/zhihu/weibo/github）
5. filters: 可选过滤条件（如时间范围、数量限制）

**重要**：entity_type 和 action 是两个不同的概念！
- entity_type 描述实体本身（是用户、专栏还是仓库）
- action 描述对实体的具体操作（看投稿、看关注、看收藏）

支持的平台、实体类型和动作：

B站 (bilibili):
- entity_type: user
  - action: videos (投稿视频)
  - action: following (关注列表)
  - action: favorites (收藏)
  - action: dynamics (动态)

知乎 (zhihu):
- entity_type: column
  - action: articles (专栏文章)
- entity_type: user
  - action: activities (个人动态)

微博 (weibo):
- entity_type: user
  - action: posts (微博)

GitHub (github):
- entity_type: repo
  - action: commits (提交记录)
  - action: issues (Issues)
  - action: pull_requests (Pull Requests)
  - action: releases (版本发布)

输出格式（JSON）：
{{
  "entity_name": "...",
  "entity_type": "...",
  "action": "...",
  "platform": "...",
  "filters": {{}}
}}

示例：
- "科技美学的最新投稿" → {{"entity_name": "科技美学", "entity_type": "user", "action": "videos", "platform": "bilibili"}}
- "科技美学的关注列表" → {{"entity_name": "科技美学", "entity_type": "user", "action": "following", "platform": "bilibili"}}
- "langchain的最新commits" → {{"entity_name": "langchain", "entity_type": "repo", "action": "commits", "platform": "github"}}

如果无法解析，返回 null。
"""

        response = self.llm.generate(prompt)

        # 检查空响应
        if not response or not response.strip():
            logger.error("LLM返回空响应")
            return None

        try:
            import json
            parsed_json = json.loads(response)
            if not parsed_json:
                return None

            return ParsedQuery(
                entity_name=parsed_json["entity_name"],
                entity_type=parsed_json["entity_type"],
                action=parsed_json["action"],
                platform=parsed_json["platform"],
                filters=parsed_json.get("filters", {})
            )
        except json.JSONDecodeError as e:
            logger.error(f"LLM输出不是合法JSON: {e}, response={response[:200]}")
            return None
        except KeyError as e:
            logger.error(f"LLM输出缺少必需字段: {e}, response={response[:200]}")
            return None
        except Exception as e:
            logger.error(f"LLM解析失败: {e}")
            return None
```

---

## 集成到现有架构

### 增强 `fetch_public_data` 工具（修订版）

```python
# services/langgraph_agents/tools/public_data_tool.py（修订）
from services.subscription.subscription_service import SubscriptionService
from services.subscription.query_parser import QueryParser
from services.subscription.action_registry import ActionRegistry

@register_tool("fetch_public_data")
def fetch_public_data(query: str) -> List[Dict]:
    """从公共互联网获取实时信息（修订版）

    现在支持自然语言标识 + 动作分离，如：
    - "科技美学的最新视频"
    - "科技美学的关注列表"  ← 同一个实体，不同动作
    - "科技美学的收藏"      ← 同一个实体，不同动作
    - "少数派专栏的最新文章"
    - "langchain的最新commits"
    - "langchain的issues"   ← 同一个实体，不同动作

    Args:
        query: 自然语言查询

    Returns:
        数据列表
    """
    # 1. 解析查询（修订：提取实体 + 动作）
    parser = QueryParser()
    parsed = parser.parse(query)

    if not parsed:
        return [{"error": f"无法解析查询: {query}"}]

    # 2. 从订阅系统解析实体 ID（修订：使用 entity_type）
    subscription_service = SubscriptionService(DatabaseConnection())
    identifiers = subscription_service.resolve_entity(
        entity_name=parsed.entity_name,
        platform=parsed.platform,
        entity_type=parsed.entity_type  # ← 修订：不是 resource_type
    )

    if not identifiers:
        # Fallback: 尝试实时搜索（如果平台支持）
        identifiers = _fallback_search(parsed)

        if not identifiers:
            return [{
                "error": f"未找到 '{parsed.entity_name}' 的订阅信息",
                "suggestion": "你可以先订阅此数据源"
            }]

    # 3. 构建 RSSHub 路径（修订：使用 ActionRegistry）
    path = ActionRegistry.build_path(
        platform=parsed.platform,
        entity_type=parsed.entity_type,
        action=parsed.action,  # ← 关键：动态确定动作
        identifiers=identifiers
    )

    if not path:
        return [{
            "error": f"不支持的动作: {parsed.action}",
            "entity": parsed.entity_name,
            "supported_actions": ActionRegistry.get_supported_actions(
                parsed.platform,
                parsed.entity_type
            )
        }]

    # 4. 调用 RSSHub
    executor = DataExecutor()
    raw_data = executor.fetch_rss(path)

    # 5. 数据适配
    clean_data = _data_adapter(raw_data, parsed.platform)

    return clean_data


def _fallback_search(parsed: ParsedQuery) -> Optional[Dict]:
    """Fallback: 实时搜索（如果订阅系统找不到）

    调用平台搜索 API，查找用户/专栏 ID。

    警告：
    - 增加延迟
    - 不是所有平台都提供搜索 API
    - 搜索结果可能不准确

    推荐：提示用户"是否订阅此数据源"，避免频繁实时搜索。
    """
    # TODO: 实现平台搜索 API 调用
    # 示例：调用 B站搜索 API 查找 "科技美学" 的 uid
    return None
```

---

## 完整流程示例

### 场景A：用户查询"科技美学的关注列表"

```
1. 用户输入（前端）
   "科技美学的关注列表"
   ↓

2. ChatService 判断为 data_query
   ↓

3. fetch_public_data 工具被调用
   query = "科技美学的关注列表"
   ↓

4. QueryParser 解析查询
   → ParsedQuery(
       entity_name="科技美学",
       entity_type="user",      ← 实体类型
       action="following",      ← 动作（关键！）
       platform="bilibili"
     )
   ↓

5. SubscriptionService.resolve_entity()
   输入："科技美学", platform="bilibili", entity_type="user"

   5.1 查找订阅记录：
       → 找到：{"uid": "12345"}
   ↓

6. ActionRegistry.build_path()
   输入：
     - platform="bilibili"
     - entity_type="user"
     - action="following"  ← 根据动作选择路径模板
     - identifiers={"uid": "12345"}

   6.1 查找动作定义：
       (bilibili, user, following) → "/bilibili/followings/video/:uid"

   6.2 替换占位符：
       → path = "/bilibili/followings/video/12345"
   ↓

7. DataExecutor.fetch_rss(path)
   调用 RSSHub：http://localhost:1200/bilibili/followings/video/12345
   ↓

8. 数据适配器清洗数据
   ↓

9. 返回给前端
   Panel 展示关注列表
```

### 场景B：用户查询"科技美学的最新投稿"（同一实体，不同动作）

```
1-4. 同上

5. QueryParser 解析查询
   → ParsedQuery(
       entity_name="科技美学",      ← 同一个实体名
       entity_type="user",           ← 同一个实体类型
       action="videos",              ← 不同的动作！
       platform="bilibili"
     )
   ↓

6. SubscriptionService.resolve_entity()
   → 同样找到：{"uid": "12345"}   ← 复用同一订阅
   ↓

7. ActionRegistry.build_path()
   action="videos"                  ← 不同的动作
   → (bilibili, user, videos) → "/bilibili/user/video/:uid"
   → path = "/bilibili/user/video/12345"  ← 不同的路径
   ↓

8-9. 调用不同的 RSSHub 端点，展示投稿视频
```

---

## 复杂研究场景处理

### 场景C：多实体对比研究

**用户输入**："分析科技美学和何同学最近一个月的视频主题差异"

这是典型的研究模式（Research Mode）场景，涉及：
- 多个实体（科技美学、何同学）
- 时间过滤（最近一个月）
- 数据聚合 + 对比分析

```
1. 用户输入（前端 Research View）
   "分析科技美学和何同学最近一个月的视频主题差异"
   ↓

2. ChatService 判断为 research_task
   mode = "research"
   ↓

3. LangGraph PlannerAgent 分解任务
   → 生成研究计划：
   {
     "research_goal": "对比分析两位UP主的视频主题差异",
     "steps": [
       {
         "step_id": 1,
         "action": "fetch_data",
         "description": "获取科技美学最近一个月的视频",
         "tool": "fetch_public_data",
         "params": {
           "query": "科技美学的最近一个月投稿视频",
           "filters": {"date_range": "last_month"}
         }
       },
       {
         "step_id": 2,
         "action": "fetch_data",
         "description": "获取何同学最近一个月的视频",
         "tool": "fetch_public_data",
         "params": {
           "query": "何同学的最近一个月投稿视频",
           "filters": {"date_range": "last_month"}
         }
       },
       {
         "step_id": 3,
         "action": "analysis",
         "description": "对比分析两位UP主的视频主题",
         "tool": "analyze_data",
         "params": {
           "datasets": ["step_1_result", "step_2_result"],
           "analysis_type": "theme_comparison"
         }
       }
     ]
   }
   ↓

4. ExecutorAgent 执行 Step 1
   4.1 调用 fetch_public_data("科技美学的最近一个月投稿视频")

   4.2 QueryParser 解析
       → ParsedQuery(
           entity_name="科技美学",
           entity_type="user",
           action="videos",
           platform="bilibili",
           filters={"date_range": "last_month"}  ← 时间过滤
         )

   4.3 SubscriptionService.resolve_entity()
       → {"uid": "12345"}

   4.4 ActionRegistry.build_path()
       → path = "/bilibili/user/video/12345"

   4.5 DataExecutor.fetch_rss(path)
       返回最近一个月的视频列表 (30条)

   4.6 存储到 DataStash
       step_1_result = [
         {"title": "iPhone 15 Pro深度评测", "date": "2025-10-15", ...},
         {"title": "小米14 Ultra上手体验", "date": "2025-10-20", ...},
         ...
       ]
   ↓

5. ExecutorAgent 执行 Step 2（并行）
   5.1 调用 fetch_public_data("何同学的最近一个月投稿视频")

   5.2 QueryParser 解析
       → ParsedQuery(
           entity_name="何同学",
           entity_type="user",
           action="videos",
           platform="bilibili",
           filters={"date_range": "last_month"}
         )

   5.3 SubscriptionService.resolve_entity()
       → {"uid": "67890"}  ← 不同的 uid

   5.4 ActionRegistry.build_path()
       → path = "/bilibili/user/video/67890"

   5.5 DataExecutor.fetch_rss(path)
       返回何同学的视频列表 (15条)

   5.6 存储到 DataStash
       step_2_result = [
         {"title": "我做了一个AI机器人", "date": "2025-10-18", ...},
         {"title": "用代码控制真实世界", "date": "2025-10-25", ...},
         ...
       ]
   ↓

6. ExecutorAgent 执行 Step 3（分析）
   6.1 调用 analyze_data({
         datasets: ["step_1_result", "step_2_result"],
         analysis_type: "theme_comparison"
       })

   6.2 LLM 分析两个数据集
       → 提取视频主题关键词
       → 对比分析差异
       → 生成报告

   6.3 生成分析报告
       {
         "summary": "科技美学侧重消费电子评测，何同学侧重创意技术项目",
         "keji_meihue_themes": ["手机评测", "数码产品", "消费电子"],
         "hetongxue_themes": ["创意项目", "技术实验", "代码教学"],
         "differences": [
           "内容形式：科技美学以产品评测为主，何同学以项目展示为主",
           "更新频率：科技美学更频繁（30条 vs 15条）",
           "技术深度：何同学更深入底层技术原理"
         ]
       }
   ↓

7. 前端展示（Research View）
   左侧：研究计划 + 步骤进度
   右侧：
     - Panel 1: 科技美学视频列表（ListPanel）
     - Panel 2: 何同学视频列表（ListPanel）
     - Panel 3: 对比分析报告（RichText）
     - Panel 4: 主题分布对比图（BarChart）
```

### 场景D：跨平台多源研究

**用户输入**："追踪 LangChain 和 LlamaIndex 两个项目的最新进展"

涉及：
- 跨平台（GitHub）
- 多个仓库实体
- 多种数据源（commits/issues/releases）

```
1. PlannerAgent 分解任务
   {
     "steps": [
       {
         "step_id": 1,
         "parallel_group": 1,  ← 并行组
         "queries": [
           "LangChain 的最新 commits",
           "LangChain 的最新 issues",
           "LangChain 的最新 releases"
         ]
       },
       {
         "step_id": 2,
         "parallel_group": 1,  ← 同一并行组
         "queries": [
           "LlamaIndex 的最新 commits",
           "LlamaIndex 的最新 issues",
           "LlamaIndex 的最新 releases"
         ]
       },
       {
         "step_id": 3,
         "action": "synthesis",
         "description": "综合分析两个项目的进展情况"
       }
     ]
   }
   ↓

2. ExecutorAgent 并行执行（6个查询同时进行）

   2.1 LangChain commits:
       QueryParser → (github, repo, commits, {owner: "langchain-ai", repo: "langchain"})
       → /github/commits/langchain-ai/langchain

   2.2 LangChain issues:
       QueryParser → (github, repo, issues, {owner: "langchain-ai", repo: "langchain"})
       → /github/issue/langchain-ai/langchain

   2.3 LangChain releases:
       QueryParser → (github, repo, releases, {owner: "langchain-ai", repo: "langchain"})
       → /github/release/langchain-ai/langchain

   2.4-2.6 同样处理 LlamaIndex 的三个数据源
   ↓

3. DataStash 聚合
   {
     "langchain": {
       "commits": [...],    // 50条
       "issues": [...],     // 30条
       "releases": [...]    // 5条
     },
     "llamaindex": {
       "commits": [...],    // 40条
       "issues": [...],     // 25条
       "releases": [...]    // 3条
     }
   }
   ↓

4. SynthesisAgent 综合分析
   → 对比提交频率
   → 对比 issue 解决速度
   → 对比版本发布节奏
   → 识别技术趋势差异
   ↓

5. 前端展示
   - Timeline: 两个项目的提交/发布时间线对比
   - Statistics: 活跃度指标对比（BarChart）
   - Issues: 热点问题列表（Table）
   - Analysis: 综合分析报告（RichText）
```

### 关键技术要点

#### 1. 多实体解析策略

QueryParser 需要支持解析包含多个实体的复杂查询：

```python
class QueryParser:
    def parse_complex_query(self, query: str) -> List[ParsedQuery]:
        """解析包含多个实体的复杂查询

        输入："对比科技美学和何同学的视频"
        输出：[
            ParsedQuery(entity_name="科技美学", ...),
            ParsedQuery(entity_name="何同学", ...)
        ]
        """
        prompt = f"""
解析以下查询，提取所有涉及的实体和操作：

查询: "{query}"

如果查询涉及多个实体（如对比、追踪多个来源），请分别提取每个实体。

输出格式（JSON数组）：
[
  {{
    "entity_name": "...",
    "entity_type": "...",
    "action": "...",
    "platform": "..."
  }},
  ...
]
"""
        response = self.llm.generate(prompt)

        try:
            parsed_list = json.loads(response)
            return [
                ParsedQuery(**item)
                for item in parsed_list
            ]
        except Exception as e:
            logger.error(f"多实体解析失败: {e}")
            return []
```

#### 2. LangGraph 集成增强

```python
# services/langgraph_agents/tools/public_data_tool.py（研究模式增强）

@register_tool("fetch_public_data_batch")
def fetch_public_data_batch(queries: List[str]) -> Dict[str, List[Dict]]:
    """批量获取公共数据（研究模式专用）

    支持：
    - 并行查询多个实体
    - 自动去重和缓存
    - 失败重试和部分成功

    Args:
        queries: 查询列表，如 ["科技美学的视频", "何同学的视频"]

    Returns:
        {
            "query_1": [{...}, {...}],
            "query_2": [{...}, {...}],
            "errors": ["query_3: 解析失败"]
        }
    """
    parser = QueryParser()
    results = {}
    errors = []

    # 1. 批量解析（并行）
    with ThreadPoolExecutor(max_workers=5) as executor:
        parse_futures = {
            executor.submit(parser.parse, q): q
            for q in queries
        }

        parsed_queries = {}
        for future in as_completed(parse_futures):
            query = parse_futures[future]
            try:
                parsed = future.result()
                if parsed:
                    parsed_queries[query] = parsed
                else:
                    errors.append(f"{query}: 解析失败")
            except Exception as e:
                errors.append(f"{query}: {e}")

    # 2. 批量获取数据（并行）
    subscription_service = SubscriptionService(DatabaseConnection())

    with ThreadPoolExecutor(max_workers=5) as executor:
        fetch_futures = {}

        for query, parsed in parsed_queries.items():
            # 解析实体ID
            identifiers = subscription_service.resolve_entity(
                parsed.entity_name,
                parsed.platform,
                parsed.entity_type
            )

            if not identifiers:
                errors.append(f"{query}: 未找到订阅")
                continue

            # 构建路径
            path = ActionRegistry.build_path(
                parsed.platform,
                parsed.entity_type,
                parsed.action,
                identifiers
            )

            if not path:
                errors.append(f"{query}: 无法构建路径")
                continue

            # 提交获取任务
            future = executor.submit(
                DataExecutor().fetch_rss,
                path
            )
            fetch_futures[future] = query

        # 3. 收集结果
        for future in as_completed(fetch_futures):
            query = fetch_futures[future]
            try:
                data = future.result()
                results[query] = data
            except Exception as e:
                errors.append(f"{query}: 获取失败 - {e}")

    # 4. 返回结果
    return {
        **results,
        "errors": errors if errors else []
    }
```

#### 3. 数据聚合策略

研究模式下，DataStash 需要支持多源数据聚合：

```python
# services/langgraph_agents/data_stash.py（增强）

class DataStash:
    def aggregate_datasets(
        self,
        dataset_ids: List[str],
        merge_strategy: str = "union"
    ) -> List[Dict]:
        """聚合多个数据集

        Args:
            dataset_ids: 数据集ID列表（如 ["step_1_result", "step_2_result"]）
            merge_strategy: 合并策略
                - union: 合并去重（默认）
                - intersect: 交集
                - concat: 直接拼接

        Returns:
            聚合后的数据列表
        """
        datasets = [self.get(ds_id) for ds_id in dataset_ids]

        if merge_strategy == "union":
            # 合并去重（按 link 字段）
            seen_links = set()
            result = []
            for dataset in datasets:
                for item in dataset:
                    link = item.get("link")
                    if link and link not in seen_links:
                        seen_links.add(link)
                        result.append(item)
            return result

        elif merge_strategy == "concat":
            # 直接拼接（保留来源标记）
            result = []
            for i, dataset in enumerate(datasets):
                for item in dataset:
                    item["_source_dataset"] = dataset_ids[i]
                    result.append(item)
            return result

        else:
            raise ValueError(f"不支持的合并策略: {merge_strategy}")
```

#### 4. 时间过滤处理

订阅系统需要支持时间范围过滤：

```python
# services/subscription/query_parser.py（增强 filters 解析）

class ParsedQuery(BaseModel):
    entity_name: str
    entity_type: str
    action: str
    platform: str
    filters: Dict[str, Any] = {}  # 支持更多过滤器

# fetch_public_data 工具增强时间过滤
def fetch_public_data(query: str) -> List[Dict]:
    # ... 现有逻辑 ...

    # 应用时间过滤
    if parsed.filters.get("date_range"):
        raw_data = _apply_time_filter(
            raw_data,
            parsed.filters["date_range"]
        )

    return raw_data

def _apply_time_filter(data: List[Dict], date_range: str) -> List[Dict]:
    """应用时间范围过滤

    支持：
    - "last_week": 最近一周
    - "last_month": 最近一个月
    - "last_3_months": 最近三个月
    - "2025-10-01:2025-10-31": 自定义日期范围
    """
    from datetime import datetime, timedelta

    now = datetime.now()

    if date_range == "last_week":
        cutoff = now - timedelta(days=7)
    elif date_range == "last_month":
        cutoff = now - timedelta(days=30)
    elif date_range == "last_3_months":
        cutoff = now - timedelta(days=90)
    else:
        # 自定义范围解析
        # TODO: 实现自定义日期范围
        return data

    # 过滤数据
    filtered = []
    for item in data:
        pub_date_str = item.get("pub_date")
        if not pub_date_str:
            continue

        try:
            pub_date = datetime.fromisoformat(pub_date_str)
            if pub_date >= cutoff:
                filtered.append(item)
        except:
            continue

    return filtered
```

---

## 前端订阅管理界面（修订）

```vue
<!-- frontend/src/views/SubscriptionsView.vue -->
<template>
  <div class="subscriptions-view">
    <div class="subscriptions-header">
      <h1>我的订阅</h1>
      <Button @click="showAddDialog = true">
        <Plus class="w-4 h-4 mr-2" />
        添加订阅
      </Button>
    </div>

    <!-- 订阅列表 -->
    <div class="subscriptions-list">
      <Card v-for="sub in subscriptions" :key="sub.id">
        <CardHeader>
          <div class="flex items-center gap-3">
            <Avatar>
              <AvatarImage :src="sub.avatar_url" :alt="sub.display_name" />
              <AvatarFallback>{{ sub.display_name[0] }}</AvatarFallback>
            </Avatar>
            <div>
              <CardTitle>{{ sub.display_name }}</CardTitle>
              <CardDescription>{{ sub.description }}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div class="flex items-center gap-2 text-sm text-muted-foreground">
            <Badge>{{ sub.platform }}</Badge>
            <Badge variant="outline">{{ sub.entity_type }}</Badge>
          </div>

          <!-- 修订：显示支持的动作 -->
          <div class="mt-3">
            <p class="text-sm font-medium mb-2">支持的操作：</p>
            <div class="flex flex-wrap gap-2">
              <Button
                v-for="action in sub.supported_actions"
                :key="action"
                variant="outline"
                size="sm"
                @click="queryAction(sub, action)"
              >
                {{ getActionDisplayName(sub.platform, sub.entity_type, action) }}
              </Button>
            </div>
          </div>
        </CardContent>
        <CardFooter class="gap-2">
          <Button variant="ghost" size="sm" @click="editSubscription(sub.id)">
            编辑
          </Button>
          <Button variant="destructive" size="sm" @click="deleteSubscription(sub.id)">
            删除
          </Button>
        </CardFooter>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useSubscriptionStore } from '@/store/subscriptionStore'
import { usePanelStore } from '@/store/panelStore'

const subscriptionStore = useSubscriptionStore()
const panelStore = usePanelStore()

// 查询指定动作的数据
function queryAction(subscription, action: string) {
  // 构建查询字符串
  const query = `${subscription.display_name}的${getActionDisplayName(
    subscription.platform,
    subscription.entity_type,
    action
  )}`

  // 发起查询
  panelStore.sendQuery(query)
}

// 获取动作的显示名称
function getActionDisplayName(
  platform: string,
  entityType: string,
  action: string
): string {
  const ACTION_DISPLAY_NAMES = {
    videos: '投稿视频',
    following: '关注列表',
    favorites: '收藏',
    dynamics: '动态',
    articles: '文章',
    commits: 'Commits',
    issues: 'Issues',
    pull_requests: 'Pull Requests',
    releases: 'Releases'
  }

  return ACTION_DISPLAY_NAMES[action] || action
}
</script>
```

---

## API 接口设计（完整版）

```python
# api/controllers/subscription_controller.py（完整版）
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from services.subscription.subscription_service import SubscriptionService
from services.subscription.action_registry import ActionRegistry
from api.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    ActionInfo,
    ResolveResponse
)

router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscription"])

# ==================== CRUD 接口 ====================

@router.get("/", response_model=List[SubscriptionResponse])
def list_subscriptions(
    user_id: Optional[int] = Query(None, description="用户ID（Stage 4 之前忽略）"),
    platform: Optional[str] = Query(None, description="平台过滤"),
    entity_type: Optional[str] = Query(None, description="实体类型过滤"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: SubscriptionService = Depends(get_subscription_service)
):
    """列出订阅

    支持按用户、平台、实体类型、激活状态筛选。
    """
    return service.list_subscriptions(
        user_id=user_id,
        platform=platform,
        entity_type=entity_type,
        is_active=is_active,
        limit=limit,
        offset=offset
    )


@router.post("/", response_model=SubscriptionResponse, status_code=201)
def create_subscription(
    data: SubscriptionCreate,
    service: SubscriptionService = Depends(get_subscription_service)
):
    """创建订阅

    请求示例：
    {
      "display_name": "科技美学",
      "platform": "bilibili",
      "entity_type": "user",
      "identifiers": {"uid": "12345"},
      "avatar_url": "...",
      "description": "数码测评UP主",
      "aliases": ["科技美学", "科技美学Official"],
      "tags": ["数码", "科技"]
    }
    """
    return service.create_subscription(**data.dict())


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription(
    subscription_id: int,
    service: SubscriptionService = Depends(get_subscription_service)
):
    """获取订阅详情"""
    subscription = service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="订阅不存在")
    return subscription


@router.patch("/{subscription_id}", response_model=SubscriptionResponse)
def update_subscription(
    subscription_id: int,
    data: SubscriptionUpdate,
    service: SubscriptionService = Depends(get_subscription_service)
):
    """更新订阅

    可更新字段：
    - display_name: 显示名称
    - description: 描述
    - avatar_url: 头像
    - aliases: 别名列表
    - tags: 标签列表
    - is_active: 是否激活
    """
    subscription = service.update_subscription(
        subscription_id,
        **data.dict(exclude_unset=True)
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="订阅不存在")
    return subscription


@router.delete("/{subscription_id}")
def delete_subscription(
    subscription_id: int,
    service: SubscriptionService = Depends(get_subscription_service)
):
    """删除订阅"""
    success = service.delete_subscription(subscription_id)
    if not success:
        raise HTTPException(status_code=404, detail="订阅不存在")
    return {"success": True, "message": "订阅已删除"}


# ==================== 功能接口 ====================


@router.get("/{subscription_id}/actions", response_model=List[ActionInfo])
def get_supported_actions(
    subscription_id: int,
    service: SubscriptionService = Depends(get_subscription_service)
):
    """获取订阅支持的所有动作

    返回示例：
    [
      {
        "action": "videos",
        "display_name": "投稿视频",
        "description": "获取UP主的投稿视频",
        "path_template": "/bilibili/user/video/:uid"
      },
      {
        "action": "following",
        "display_name": "关注列表",
        "description": "获取UP主的关注列表",
        "path_template": "/bilibili/followings/video/:uid"
      },
      ...
    ]
    """
    subscription = service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="订阅不存在")

    actions = []
    for action_name in json.loads(subscription.supported_actions):
        action_def = ActionRegistry.get_action(
            subscription.platform,
            subscription.entity_type,
            action_name
        )
        if action_def:
            actions.append({
                "action": action_def.action_name,
                "display_name": action_def.display_name,
                "description": action_def.description,
                "path_template": action_def.path_template
            })

    return actions


@router.post("/resolve", response_model=ResolveResponse)
def resolve_entity(
    entity_name: str,
    platform: str,
    entity_type: str,  # ← 修订：不是 resource_type
    action: str,       # ← 新增：动作参数
    service: SubscriptionService = Depends(get_subscription_service)
):
    """解析实体并构建路径（修订版）

    输入：
      entity_name: "科技美学"
      platform: "bilibili"
      entity_type: "user"
      action: "following"

    输出：
    {
      "identifiers": {"uid": "12345"},
      "path": "/bilibili/followings/video/12345"
    }
    """
    # 1. 解析实体 ID
    identifiers = service.resolve_entity(
        entity_name=entity_name,
        platform=platform,
        entity_type=entity_type
    )

    if not identifiers:
        raise HTTPException(
            status_code=404,
            detail=f"未找到 '{entity_name}' 的订阅信息"
        )

    # 2. 构建路径
    path = ActionRegistry.build_path(
        platform=platform,
        entity_type=entity_type,
        action=action,
        identifiers=identifiers
    )

    if not path:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的动作: {action}"
        )

    return {
        "identifiers": identifiers,
        "path": path
    }
```

---

## 数据库迁移（从旧版本升级）

如果已经使用了旧版本的订阅系统，需要执行数据库迁移：

```python
# alembic/versions/xxx_migrate_subscription_to_entity_action.py
"""Migrate subscription resource_type to entity_type + supported_actions

Revision ID: xxx
Revises: yyy
Create Date: 2025-11-13

修订内容：
1. 将 resource_type 字段重命名为 entity_type
2. 更新 entity_type 的值（user_video → user）
3. 新增 supported_actions 字段
4. 删除 rsshub_path_template 字段（路径由 ActionRegistry 动态生成）
"""

def upgrade():
    # 1. 添加新字段
    op.add_column(
        'subscriptions',
        sa.Column('entity_type', sa.String(), nullable=True)
    )
    op.add_column(
        'subscriptions',
        sa.Column('supported_actions', sa.String(), default='[]')
    )

    # 2. 迁移数据
    connection = op.get_bind()

    # 将 resource_type 转换为 entity_type
    RESOURCE_TYPE_TO_ENTITY_TYPE = {
        'user_video': 'user',
        'user_dynamic': 'user',
        'followings': 'user',
        'zhuanlan': 'column',
        'people_activities': 'user',
        'commits': 'repo',
        'issue': 'repo'
    }

    # 根据平台和实体类型推断支持的动作
    ENTITY_SUPPORTED_ACTIONS = {
        ('bilibili', 'user'): ['videos', 'following', 'favorites', 'dynamics'],
        ('zhihu', 'column'): ['articles'],
        ('zhihu', 'user'): ['activities'],
        ('github', 'repo'): ['commits', 'issues', 'pull_requests', 'releases']
    }

    subscriptions = connection.execute(
        sa.text("SELECT id, platform, resource_type FROM subscriptions")
    ).fetchall()

    for sub_id, platform, old_resource_type in subscriptions:
        entity_type = RESOURCE_TYPE_TO_ENTITY_TYPE.get(old_resource_type)
        if not entity_type:
            print(f"警告：未知的 resource_type: {old_resource_type}")
            continue

        supported_actions = ENTITY_SUPPORTED_ACTIONS.get((platform, entity_type), [])

        connection.execute(
            sa.text(
                "UPDATE subscriptions "
                "SET entity_type = :entity_type, "
                "    supported_actions = :actions "
                "WHERE id = :sub_id"
            ),
            {
                'entity_type': entity_type,
                'actions': json.dumps(supported_actions),
                'sub_id': sub_id
            }
        )

    # 3. 删除旧字段
    op.drop_column('subscriptions', 'resource_type')
    op.drop_column('subscriptions', 'rsshub_path_template')

    # 4. 设置新字段为 NOT NULL
    op.alter_column('subscriptions', 'entity_type', nullable=False)


def downgrade():
    # 回滚逻辑（如需要）
    pass
```

---

## 实施路线图

### Phase 1: 基础订阅管理（1-2周）
- [ ] 数据模型（Subscription表，entity_type + supported_actions）
- [ ] ActionRegistry（动作注册表）
- [ ] SubscriptionService（CRUD，resolve_entity）
- [ ] 前端订阅管理界面
- [ ] 手动添加订阅功能

**验收标准**：✅ 可以手动添加B站UP主订阅，点击不同动作查看不同数据

---

### Phase 2: 智能解析（1周）
- [ ] QueryParser实现（LLM解析，分离实体和动作）
- [ ] SubscriptionVectorStore（语义搜索）
- [ ] resolve_entity 集成
- [ ] fetch_public_data 增强（使用 ActionRegistry）

**验收标准**：✅ 可以输入"科技美学的关注列表"自动解析并调用正确的API

---

### Phase 3: URL智能导入（1周）
- [ ] URL解析器（提取UID/ID）
- [ ] 一键导入订阅
- [ ] 批量导入（如导入关注列表）

**验收标准**：✅ 粘贴B站UP主链接自动导入订阅

---

### Phase 4: 与知识库集成（1周）
- [ ] 笔记中引用订阅 `[[subscription://]]`
- [ ] 订阅内容一键记笔记
- [ ] LangGraph同时检索知识库和订阅

**验收标准**：✅ 笔记和订阅无缝协作

---

## 技术决策记录

### 决策1: 为什么分离 entity_type 和 action？

**理由**：
1. **符合现实** - 同一个UP主可以有多种访问方式（投稿/关注/收藏）
2. **避免重复** - 不需要为同一实体创建多个订阅记录
3. **扩展性强** - 新增动作无需修改订阅表
4. **职责清晰** - Subscription存储实体，ActionRegistry管理动作

**旧设计的问题**：
- ❌ `resource_type="user_video"` 过于具体，绑定了实体和动作
- ❌ 同一UP主的不同访问方式需要多个订阅记录
- ❌ 不符合直觉，用户只想"订阅科技美学"，而非"订阅科技美学的投稿视频"

---

### 决策2: 为什么用 ActionRegistry 而非存储路径模板？

**理由**：
1. **配置集中** - 所有路径模板统一管理，便于维护
2. **动态组合** - 查询时根据动作动态选择路径
3. **减少冗余** - 订阅表不存储重复的路径模板
4. **便于扩展** - 新增平台或动作只需修改 ActionRegistry

**替代方案**：为每个 (entity, action) 组合存储路径模板（❌不推荐，数据冗余）

---

### 决策3: Fallback机制的优先级？

**推荐顺序**：
1. **订阅系统（模糊搜索）** - 最快、最准确
2. **订阅系统（语义搜索）** - 容错性强
3. **实时搜索API** - 兜底方案（有延迟）
4. **提示用户订阅** - 避免频繁实时搜索

---

## 修订总结

### 修订前（错误设计）

```python
class Subscription:
    resource_type: str = "user_video"  # ❌ 绑定了实体和动作
    rsshub_path_template: str = "/bilibili/user/video/:uid"  # ❌ 只支持一个端点

# 问题：同一UP主的不同访问方式需要多个订阅
subscriptions = [
    {"display_name": "科技美学", "resource_type": "user_video"},     # 投稿
    {"display_name": "科技美学", "resource_type": "followings"},     # 关注
    {"display_name": "科技美学", "resource_type": "favorites"},      # 收藏
]
```

### 修订后（正确设计）

```python
class Subscription:
    entity_type: str = "user"  # ✅ 只描述实体类型
    supported_actions: List[str] = ["videos", "following", "favorites"]  # ✅ 支持多个动作

class ActionRegistry:
    ACTION_TEMPLATES = {
        ("bilibili", "user", "videos"): "/bilibili/user/video/:uid",
        ("bilibili", "user", "following"): "/bilibili/followings/video/:uid",
        ("bilibili", "user", "favorites"): "/bilibili/favorites/:uid",
    }

# 解决：一个订阅，多种访问方式
subscription = {"display_name": "科技美学", "entity_type": "user"}
actions = ["videos", "following", "favorites"]  # 动态选择
```

---

## 重要参考文档

- **ActionRegistry 自动化生成方案**：`.agentdocs/subscription-action-registry-automation.md`
  - 从 `datasource_definitions.json` 自动生成 ActionRegistry 配置
  - 推断规则：参数名 → entity_type，路径模式 → action
  - 置信度评分系统
  - 使用方式：`python -m scripts.generate_action_registry`

---

**方案制定时间**：2025-11-13
**预计实施周期**：Phase 1-4 共 4-5 周

---

## 修订历史

### v2.2 (2025-11-13) - Codex 审查修正 + 复杂研究场景

**修复问题**：

1. **P0 - QueryParser 可靠性**：
   - 保持 LLM 驱动（不使用规则引擎）
   - 新增工程可靠性措施：
     - 缓存：相同查询直接返回缓存（避免重复 LLM 调用）
     - 重试：LLM 失败时自动重试（最多 3 次）
     - 校验：验证 LLM 输出合法性（枚举检查，非规则引擎）
     - 降级：多次失败后返回 None，由上层处理
   - 添加空响应检查和详细异常日志
   - 新增 `_validate_output()` 方法校验 platform/entity_type/action 枚举

2. **P1 - API 完整性**：
   - 补充完整的 CRUD 接口：
     - `GET /subscriptions` - 列出订阅（支持多种过滤）
     - `GET /subscriptions/{id}` - 获取订阅详情
     - `PATCH /subscriptions/{id}` - 更新订阅
     - `DELETE /subscriptions/{id}` - 删除订阅
   - Service 层新增方法：
     - `list_subscriptions()` - 支持 user_id/platform/entity_type/is_active 过滤
     - `get_subscription()` - 根据 ID 获取订阅
     - `update_subscription()` - 更新订阅，自动触发重新向量化
     - `delete_subscription()` - 删除订阅

3. **P2 - 多用户隔离与计数策略**：
   - 新增 "多用户隔离策略" 章节（1.3）
   - 明确 Stage 4 之前 `user_id` 为 NULL（单用户模式）
   - Stage 4 之后自动迁移数据：`UPDATE subscriptions SET user_id = 1 WHERE user_id IS NULL`
   - Service 层向后兼容：`user_id=None` 时忽略用户过滤
   - 添加唯一约束：`(platform, entity_type, identifiers, user_id)`
   - `subscribe_count` 计算策略：实时计算 vs 触发器维护

**新增内容**：

4. **复杂研究场景处理**：
   - 新增 "场景C：多实体对比研究" - 演示如何处理涉及多个实体、时间过滤、数据聚合的复杂研究任务
   - 新增 "场景D：跨平台多源研究" - 演示如何并行查询多个数据源（commits/issues/releases）并综合分析
   - 关键技术要点：
     - 多实体解析策略：`parse_complex_query()` 支持解析包含多个实体的查询
     - LangGraph 集成增强：`fetch_public_data_batch()` 批量并行获取数据
     - 数据聚合策略：`DataStash.aggregate_datasets()` 支持 union/concat 等合并策略
     - 时间过滤处理：`_apply_time_filter()` 支持 last_week/last_month 等时间范围
   - 与 LangGraph Agents 完整集成流程：PlannerAgent 分解任务 → ExecutorAgent 并行执行 → DataStash 聚合 → SynthesisAgent 分析

**文档版本**：v2.2 (基于 Codex 审查反馈修正 + 复杂研究场景补充)

### v2.1 (2025-11-13) - 移除规则引擎

**修订原因**：
- 不可能手动维护 ACTION_TEMPLATES，绝对不能使用规则引擎
- 添加自动化方案引用：`.agentdocs/subscription-action-registry-automation.md`

### v2.0 (2025-11-13) - 实体/动作分离架构

**修订原因**：
- 原设计混淆实体和动作，导致同一实体需要多个订阅记录
- 修正：`resource_type="user_video"` → `entity_type="user"` + `ActionRegistry`
