"""订阅管理 Controller

提供订阅相关的 RESTful API 端点。
"""

import logging
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from api.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionListResponse,
    ResolveEntityRequest,
    ResolveEntityResponse,
    ActionInfo,
)
from services.database import SubscriptionService
from services.subscription.action_registry import ActionRegistry

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(
    prefix="/api/v1/subscriptions",
    tags=["subscriptions"]
)


def get_subscription_service() -> SubscriptionService:
    """获取订阅服务实例（支持测试时的依赖注入）"""
    return SubscriptionService()


def _subscription_to_response(subscription) -> SubscriptionResponse:
    """将 ORM 模型转换为响应 Schema

    处理 JSON 字段的反序列化，确保 None 值转为空列表。
    """
    # 安全解析 JSON 字段，None 转为空列表
    aliases = json.loads(subscription.aliases) if subscription.aliases else []
    tags = json.loads(subscription.tags) if subscription.tags else []
    supported_actions = json.loads(subscription.supported_actions) if subscription.supported_actions else []

    return SubscriptionResponse(
        id=subscription.id,
        display_name=subscription.display_name,
        platform=subscription.platform,
        entity_type=subscription.entity_type,
        identifiers=json.loads(subscription.identifiers),
        description=subscription.description,
        avatar_url=subscription.avatar_url,
        aliases=aliases,
        tags=tags,
        supported_actions=supported_actions,
        subscribe_count=subscription.subscribe_count,
        last_fetched_at=subscription.last_fetched_at,
        is_active=subscription.is_active,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
    )


@router.get("", response_model=SubscriptionListResponse, summary="列出订阅")
async def list_subscriptions(
    platform: Optional[str] = Query(None, description="平台过滤"),
    entity_type: Optional[str] = Query(None, description="实体类型过滤"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """列出订阅

    支持按平台、实体类型、激活状态过滤。

    查询参数：
    - platform: 平台过滤（可选）
    - entity_type: 实体类型过滤（可选）
    - is_active: 是否激活（可选）
    - limit: 返回数量（默认 20，最大 100）
    - offset: 偏移量（默认 0）

    返回：
    - total: 总数
    - items: 订阅列表
    """
    try:
        service = get_subscription_service()

        # 修复：使用独立的 count 查询获取精确总数
        total = service.count_subscriptions(
            platform=platform,
            entity_type=entity_type,
            is_active=is_active
        )

        subscriptions = service.list_subscriptions(
            platform=platform,
            entity_type=entity_type,
            is_active=is_active,
            limit=limit,
            offset=offset
        )

        items = [_subscription_to_response(sub) for sub in subscriptions]

        return SubscriptionListResponse(total=total, items=items)

    except Exception as e:
        logger.error(f"列出订阅失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"列出订阅失败: {str(e)}")


@router.post("", response_model=SubscriptionResponse, status_code=201, summary="创建订阅")
async def create_subscription(request: SubscriptionCreate):
    """创建订阅

    请求体：
    ```json
    {
        "display_name": "科技美学",
        "platform": "bilibili",
        "entity_type": "user",
        "identifiers": {"uid": "12345"},
        "description": "数码测评UP主",
        "avatar_url": "https://...",
        "aliases": ["科技美学", "科技美学Official"],
        "tags": ["数码", "科技"]
    }
    ```

    返回：
    - 201: 创建成功，返回订阅详情
    - 400: 请求参数错误
    - 409: 订阅已存在（唯一约束冲突）
    - 500: 服务器错误
    """
    try:
        service = get_subscription_service()

        # 准备可选参数
        kwargs = {}
        if request.description is not None:
            kwargs["description"] = request.description
        if request.avatar_url is not None:
            kwargs["avatar_url"] = request.avatar_url
        if request.aliases is not None:
            kwargs["aliases"] = request.aliases
        if request.tags is not None:
            kwargs["tags"] = request.tags

        subscription = service.create_subscription(
            display_name=request.display_name,
            platform=request.platform,
            entity_type=request.entity_type,
            identifiers=request.identifiers,
            **kwargs
        )

        return _subscription_to_response(subscription)

    except Exception as e:
        error_msg = str(e)
        # 检查是否是唯一约束冲突
        if "UNIQUE constraint failed" in error_msg or "unique constraint" in error_msg.lower():
            raise HTTPException(
                status_code=409,
                detail=f"订阅已存在: {request.platform}/{request.entity_type}/{request.identifiers}"
            )
        logger.error(f"创建订阅失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建订阅失败: {str(e)}")


@router.get("/{subscription_id}", response_model=SubscriptionResponse, summary="获取订阅详情")
async def get_subscription(subscription_id: int):
    """获取订阅详情

    路径参数：
    - subscription_id: 订阅 ID

    返回：
    - 200: 订阅详情
    - 404: 订阅不存在
    """
    service = get_subscription_service()
    subscription = service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail=f"订阅不存在: id={subscription_id}")

    return _subscription_to_response(subscription)


@router.patch("/{subscription_id}", response_model=SubscriptionResponse, summary="更新订阅")
async def update_subscription(subscription_id: int, request: SubscriptionUpdate):
    """更新订阅

    路径参数：
    - subscription_id: 订阅 ID

    请求体：所有字段均可选，只更新提供的字段

    返回：
    - 200: 更新成功，返回订阅详情
    - 404: 订阅不存在
    - 500: 服务器错误
    """
    try:
        service = get_subscription_service()

        # 只传递非 None 的字段
        updates = {k: v for k, v in request.model_dump(exclude_unset=True).items() if v is not None}

        if not updates:
            raise HTTPException(status_code=400, detail="没有提供任何更新字段")

        subscription = service.update_subscription(subscription_id, **updates)

        if not subscription:
            raise HTTPException(status_code=404, detail=f"订阅不存在: id={subscription_id}")

        return _subscription_to_response(subscription)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新订阅失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新订阅失败: {str(e)}")


@router.delete("/{subscription_id}", status_code=204, summary="删除订阅")
async def delete_subscription(subscription_id: int):
    """删除订阅

    路径参数：
    - subscription_id: 订阅 ID

    返回：
    - 204: 删除成功（无响应体）
    - 404: 订阅不存在
    """
    service = get_subscription_service()
    success = service.delete_subscription(subscription_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"订阅不存在: id={subscription_id}")

    # 204 No Content - 不返回响应体
    return None


@router.get("/{subscription_id}/actions", response_model=List[ActionInfo], summary="获取支持的动作列表")
async def get_subscription_actions(subscription_id: int):
    """获取订阅支持的动作列表

    路径参数：
    - subscription_id: 订阅 ID

    返回：
    - 200: 动作列表
    - 404: 订阅不存在
    """
    service = get_subscription_service()
    subscription = service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail=f"订阅不存在: id={subscription_id}")

    # 获取支持的动作列表
    supported_actions = json.loads(subscription.supported_actions)

    # 获取每个动作的详细信息
    actions = []
    for action_name in supported_actions:
        action_detail = ActionRegistry.get_action(
            subscription.platform,
            subscription.entity_type,
            action_name
        )
        if action_detail:
            # ActionRegistry.get_action 返回 ActionDefinition 对象，不是字典
            actions.append(ActionInfo(
                action=action_name,
                display_name=action_detail.display_name,
                description=action_detail.description,
                path_template=action_detail.path_template
            ))

    return actions


@router.post("/resolve", response_model=ResolveEntityResponse, summary="解析实体标识符")
async def resolve_entity(request: ResolveEntityRequest):
    """解析实体标识符

    将自然语言标识（如 "科技美学"）转换为 API 标识（如 {"uid": "12345"}）。

    这是订阅系统的核心功能，用于查询解析时将用户输入映射到具体的 API 参数。

    请求体：
    ```json
    {
        "entity_name": "科技美学",
        "platform": "bilibili",
        "entity_type": "user"
    }
    ```

    返回：
    - 200: 解析成功，返回 identifiers
    - 404: 未找到对应的订阅
    """
    service = get_subscription_service()

    # 修复：传递 user_id 和 is_active 防止越权（Stage 4 之前 user_id=None 即默认 0）
    identifiers = service.resolve_entity(
        entity_name=request.entity_name,
        platform=request.platform,
        entity_type=request.entity_type,
        user_id=None,  # Stage 4 之前默认单用户模式
        is_active=True  # 只解析激活的订阅
    )

    if identifiers:
        # 获取订阅 ID（通过再次搜索）
        subscriptions = service.search_subscriptions(
            query=request.entity_name,
            platform=request.platform
        )
        matched = [
            sub for sub in subscriptions
            if sub.entity_type == request.entity_type
            and (sub.display_name == request.entity_name or
                 request.entity_name in json.loads(sub.aliases))
        ]

        subscription_id = matched[0].id if matched else None

        return ResolveEntityResponse(
            success=True,
            identifiers=identifiers,
            subscription_id=subscription_id,
            message=f"成功解析实体: {request.entity_name}"
        )
    else:
        return ResolveEntityResponse(
            success=False,
            message=f"未找到订阅: {request.entity_name} ({request.platform}/{request.entity_type})"
        )
