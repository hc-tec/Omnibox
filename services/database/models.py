"""订阅系统数据模型

按照 subscription-system-design.md v2.2 设计方案实现。

核心概念：实体 (Entity) vs 动作 (Action)
- Subscription 只存储实体信息，不绑定特定的 resource_type 或路径模板
- 同一个实体可以通过不同的动作访问不同的API端点
- ActionRegistry 负责动态构建路径模板
"""

from sqlmodel import SQLModel, Field, UniqueConstraint, Column, Integer
from sqlalchemy import ForeignKey
from datetime import datetime
from typing import Optional


class Subscription(SQLModel, table=True):
    """订阅管理（修订版 v2.2 - 实体/动作分离架构）

    只存储实体信息，不绑定特定的 resource_type 或路径模板。
    同一个实体可以通过不同的动作访问不同的API端点。

    修订原因：
    原设计将 entity + action 绑定在一起，导致同一UP主访问不同接口
    需要创建多个订阅记录，这是错误的。正确做法是分离实体和动作。

    示例：
    - B站UP主"科技美学"（uid=12345）是一个实体
    - 可以通过不同动作访问：videos/following/favorites/dynamics
    - 只需一个 Subscription 记录，supported_actions 包含所有动作
    """

    __tablename__ = "subscriptions"

    # 唯一约束：避免重复订阅
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "entity_type",
            "identifiers",
            "user_id",
            name="uq_subscription_entity_user"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # 显示信息
    display_name: str = Field(
        index=True,
        description="显示名称，如 '科技美学'"
    )
    avatar_url: Optional[str] = Field(
        default=None,
        description="头像URL"
    )
    description: Optional[str] = Field(
        default=None,
        description="简介"
    )

    # 实体标识（修订：区分 entity_type 而非 resource_type）
    platform: str = Field(
        index=True,
        description="平台：bilibili/zhihu/weibo/github/..."
    )
    entity_type: str = Field(
        description="实体类型：user/column/repo/topic（不是 user_video!）"
    )

    # API标识（JSON存储，支持多种标识符）
    identifiers: str = Field(
        description='JSON格式API标识，如 {"uid": "12345", "uname": "科技美学Official"}'
    )

    # 搜索优化
    aliases: str = Field(
        default="[]",
        description='JSON格式别名列表，如 ["科技美学", "科技美学Official", "那岩"]'
    )
    tags: str = Field(
        default="[]",
        description='JSON格式标签列表，如 ["数码", "科技", "测评"]'
    )

    # 支持的动作（修订：记录此实体支持哪些动作）
    supported_actions: str = Field(
        default="[]",
        description='JSON格式支持的动作列表，如 ["videos", "following", "favorites", "dynamics"]'
    )

    # 元数据
    subscribe_count: int = Field(
        default=0,
        description="订阅人数（多用户场景）"
    )
    last_fetched_at: Optional[datetime] = Field(
        default=None,
        description="最后拉取时间"
    )
    is_active: bool = Field(
        default=True,
        description="是否激活"
    )

    # 时间戳
    created_at: datetime = Field(
        default_factory=datetime.now,
        index=True
    )
    updated_at: datetime = Field(
        default_factory=datetime.now
    )

    # 多用户支持（Stage 4 之前为 NULL）
    # 注意：Stage 4 之前不添加外键约束（users 表尚未创建）
    user_id: Optional[int] = Field(
        default=None,
        # foreign_key="users.id",  # ← Stage 4 时通过 Alembic 迁移添加
        index=True,
        description="NULL = 公共订阅（单用户阶段）"
    )


class SubscriptionEmbedding(SQLModel, table=True):
    """订阅向量化记录

    为订阅信息生成向量，支持语义搜索。
    实际向量存储在 ChromaDB（独立 Collection: 'subscriptions'）。

    设计原因：
    - 分离关注点：SQLite 存储结构化数据，ChromaDB 存储向量
    - 独立 Collection：避免与 RSSHub 路由向量混淆
    - 版本追踪：记录向量模型版本，支持模型升级

    级联删除：当订阅被删除时，自动删除对应的向量化记录。
    """

    __tablename__ = "subscription_embeddings"

    subscription_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("subscriptions.id", ondelete="CASCADE"),  # ← 修复：添加级联删除
            primary_key=True
        )
    )
    embedding_version: str = Field(
        description="向量模型版本（如 bge-m3-v1.0）"
    )
    last_embedded_at: datetime = Field(
        description="最后向量化时间"
    )
    is_stale: bool = Field(
        default=False,
        description="内容是否已过时（订阅信息变更时标记为 True）"
    )
