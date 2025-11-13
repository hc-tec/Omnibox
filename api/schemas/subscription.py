"""订阅管理 API Schema 定义

定义订阅相关的请求/响应模型，用于 API 接口数据验证。
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class SubscriptionCreate(BaseModel):
    """创建订阅请求

    示例：
    ```json
    {
        "display_name": "科技美学",
        "platform": "bilibili",
        "entity_type": "user",
        "identifiers": {"uid": "12345"},
        "description": "数码测评UP主",
        "avatar_url": "https://...",
        "aliases": ["科技美学", "科技美学Official", "那岩"],
        "tags": ["数码", "科技", "测评"]
    }
    ```
    """

    display_name: str = Field(
        ...,
        description="显示名称，如 '科技美学'",
        min_length=1,
        max_length=100
    )
    platform: str = Field(
        ...,
        description="平台：bilibili/zhihu/weibo/github/...",
        min_length=1,
        max_length=50
    )
    entity_type: str = Field(
        ...,
        description="实体类型：user/column/repo（不是 user_video!）",
        min_length=1,
        max_length=50
    )
    identifiers: Dict[str, Any] = Field(
        ...,
        description="API 标识字典，如 {\"uid\": \"12345\"}"
    )
    description: Optional[str] = Field(
        None,
        description="简介",
        max_length=500
    )
    avatar_url: Optional[str] = Field(
        None,
        description="头像 URL",
        max_length=500
    )
    aliases: Optional[List[str]] = Field(
        None,
        description="别名列表，如 [\"科技美学\", \"那岩\"]"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="标签列表，如 [\"数码\", \"科技\"]"
    )


class SubscriptionUpdate(BaseModel):
    """更新订阅请求

    所有字段均可选，只更新提供的字段。
    """

    display_name: Optional[str] = Field(
        None,
        description="显示名称",
        min_length=1,
        max_length=100
    )
    platform: Optional[str] = Field(
        None,
        description="平台",
        min_length=1,
        max_length=50
    )
    entity_type: Optional[str] = Field(
        None,
        description="实体类型",
        min_length=1,
        max_length=50
    )
    identifiers: Optional[Dict[str, Any]] = Field(
        None,
        description="API 标识字典"
    )
    description: Optional[str] = Field(
        None,
        description="简介",
        max_length=500
    )
    avatar_url: Optional[str] = Field(
        None,
        description="头像 URL",
        max_length=500
    )
    aliases: Optional[List[str]] = Field(
        None,
        description="别名列表"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="标签列表"
    )
    is_active: Optional[bool] = Field(
        None,
        description="是否激活"
    )


class ActionInfo(BaseModel):
    """动作信息

    描述实体支持的动作（如 videos/following/favorites）。
    """

    action: str = Field(
        ...,
        description="动作名称（如 'videos'）"
    )
    display_name: str = Field(
        ...,
        description="显示名称（如 '投稿视频'）"
    )
    description: Optional[str] = Field(
        None,
        description="动作描述"
    )
    path_template: str = Field(
        ...,
        description="路径模板（如 '/bilibili/user/video/:uid'）"
    )


class SubscriptionResponse(BaseModel):
    """订阅响应

    返回完整的订阅信息，包含支持的动作列表。
    """

    id: int = Field(
        ...,
        description="订阅 ID"
    )
    display_name: str = Field(
        ...,
        description="显示名称"
    )
    platform: str = Field(
        ...,
        description="平台"
    )
    entity_type: str = Field(
        ...,
        description="实体类型"
    )
    identifiers: Dict[str, Any] = Field(
        ...,
        description="API 标识字典"
    )
    description: Optional[str] = Field(
        None,
        description="简介"
    )
    avatar_url: Optional[str] = Field(
        None,
        description="头像 URL"
    )
    aliases: List[str] = Field(
        ...,
        description="别名列表"
    )
    tags: List[str] = Field(
        ...,
        description="标签列表"
    )
    supported_actions: List[str] = Field(
        ...,
        description="支持的动作列表（如 ['videos', 'following']）"
    )
    subscribe_count: int = Field(
        ...,
        description="订阅人数"
    )
    last_fetched_at: Optional[datetime] = Field(
        None,
        description="最后拉取时间"
    )
    is_active: bool = Field(
        ...,
        description="是否激活"
    )
    created_at: datetime = Field(
        ...,
        description="创建时间"
    )
    updated_at: datetime = Field(
        ...,
        description="更新时间"
    )

    model_config = {"from_attributes": True}  # Pydantic v2: 允许从 ORM 模型创建


class SubscriptionListResponse(BaseModel):
    """订阅列表响应"""

    total: int = Field(
        ...,
        description="总数"
    )
    items: List[SubscriptionResponse] = Field(
        ...,
        description="订阅列表"
    )


class ResolveEntityRequest(BaseModel):
    """解析实体请求

    将自然语言标识（如 "科技美学"）转换为 API 标识（如 {"uid": "12345"}）。
    """

    entity_name: str = Field(
        ...,
        description="实体名称（如 '科技美学'）",
        min_length=1,
        max_length=100
    )
    platform: str = Field(
        ...,
        description="平台",
        min_length=1,
        max_length=50
    )
    entity_type: str = Field(
        ...,
        description="实体类型",
        min_length=1,
        max_length=50
    )


class ResolveEntityResponse(BaseModel):
    """解析实体响应"""

    success: bool = Field(
        ...,
        description="是否解析成功"
    )
    identifiers: Optional[Dict[str, Any]] = Field(
        None,
        description="API 标识字典（成功时返回）"
    )
    subscription_id: Optional[int] = Field(
        None,
        description="订阅 ID（成功时返回）"
    )
    message: Optional[str] = Field(
        None,
        description="提示信息"
    )
