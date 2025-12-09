"""
仪表盘 API Controller

Phase 5: Dashboard REST API 端点
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from api.schemas.dashboard import (
    PinArtifactRequest,
    PinWorkflowRequest,
    UpdateCardRequest,
    UpdateLayoutRequest,
    UpdateTriggersRequest,
    CardResponse,
    CardListResponse,
    CardDataResponse,
    NotificationListResponse,
    UnreadCountResponse,
    card_to_response,
    notification_to_response,
)
from services.dashboard import (
    Trigger,
    TriggerType,
    TriggerAction,
)
from services.dashboard.dashboard_service import get_dashboard_service
from services.dashboard.store import get_dashboard_store

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# ============ 卡片管理 ============

@router.get("/cards", response_model=CardListResponse)
async def list_cards(
    enabled_only: bool = Query(False, description="仅返回启用的卡片"),
    card_type: Optional[str] = Query(None, description="按类型筛选")
):
    """获取仪表盘卡片列表"""
    service = get_dashboard_service()
    cards = service.list_cards(enabled_only=enabled_only, card_type=card_type)

    return CardListResponse(
        cards=[card_to_response(card) for card in cards],
        total=len(cards)
    )


@router.get("/cards/{card_id}", response_model=CardResponse)
async def get_card(card_id: str):
    """获取卡片详情"""
    service = get_dashboard_service()
    card = service.get_card(card_id)

    if not card:
        raise HTTPException(status_code=404, detail=f"卡片不存在: {card_id}")

    return card_to_response(card)


@router.post("/pin/artifact", response_model=CardResponse)
async def pin_artifact(request: PinArtifactRequest):
    """将数据产物 Pin 到仪表盘"""
    service = get_dashboard_service()

    # 转换触发器
    triggers = None
    if request.triggers:
        triggers = [
            Trigger(
                name=t.name,
                enabled=t.enabled,
                trigger_type=TriggerType(t.trigger_type),
                condition=t.condition,
                action=TriggerAction(t.action),
                action_config=t.action_config
            )
            for t in request.triggers
        ]

    # 转换位置
    position = None
    if request.position:
        position = {
            "x": request.position.x,
            "y": request.position.y,
            "width": request.position.width,
            "height": request.position.height
        }

    card = service.pin_artifact(
        artifact_id=request.artifact_id,
        name=request.name,
        description=request.description,
        view_config=request.view_config,
        refresh_interval=request.refresh_interval,
        triggers=triggers,
        position=position
    )

    return card_to_response(card)


@router.post("/pin/workflow", response_model=CardResponse)
async def pin_workflow(request: PinWorkflowRequest):
    """将工作流结果 Pin 到仪表盘"""
    service = get_dashboard_service()

    triggers = None
    if request.triggers:
        triggers = [
            Trigger(
                name=t.name,
                enabled=t.enabled,
                trigger_type=TriggerType(t.trigger_type),
                condition=t.condition,
                action=TriggerAction(t.action),
                action_config=t.action_config
            )
            for t in request.triggers
        ]

    position = None
    if request.position:
        position = {
            "x": request.position.x,
            "y": request.position.y,
            "width": request.position.width,
            "height": request.position.height
        }

    card = service.pin_workflow(
        workflow_id=request.workflow_id,
        name=request.name,
        variable_values=request.variable_values,
        description=request.description,
        view_config=request.view_config,
        refresh_interval=request.refresh_interval,
        triggers=triggers,
        position=position
    )

    return card_to_response(card)


@router.put("/cards/{card_id}", response_model=CardResponse)
async def update_card(card_id: str, request: UpdateCardRequest):
    """更新卡片配置"""
    service = get_dashboard_service()

    card = service.update_card(
        card_id=card_id,
        name=request.name,
        description=request.description,
        view_config=request.view_config,
        refresh_interval=request.refresh_interval,
        enabled=request.enabled
    )

    if not card:
        raise HTTPException(status_code=404, detail=f"卡片不存在: {card_id}")

    return card_to_response(card)


@router.delete("/cards/{card_id}")
async def delete_card(card_id: str):
    """删除卡片"""
    service = get_dashboard_service()

    if not service.delete_card(card_id):
        raise HTTPException(status_code=404, detail=f"卡片不存在: {card_id}")

    return {"success": True, "message": f"卡片已删除: {card_id}"}


# ============ 数据刷新 ============

@router.post("/cards/{card_id}/refresh", response_model=CardDataResponse)
async def refresh_card(card_id: str):
    """手动刷新卡片数据"""
    service = get_dashboard_service()

    data = service.refresh_card(card_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"卡片不存在: {card_id}")

    return CardDataResponse(
        card_id=card_id,
        data=data.get("data"),
        layout=data.get("layout"),
        blocks=data.get("blocks"),
        schema=data.get("schema"),
        suggested_views=data.get("suggested_views"),
        view_config=data.get("view_config"),
        refreshed_at=data.get("refreshed_at", ""),
        error=data.get("error")
    )


@router.get("/cards/{card_id}/data", response_model=CardDataResponse)
async def get_card_data(card_id: str):
    """获取卡片数据（优先使用缓存）"""
    service = get_dashboard_service()

    data = service.get_card_data(card_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"卡片不存在: {card_id}")

    return CardDataResponse(
        card_id=card_id,
        data=data.get("data"),
        layout=data.get("layout"),
        blocks=data.get("blocks"),
        schema=data.get("schema"),
        suggested_views=data.get("suggested_views"),
        view_config=data.get("view_config"),
        refreshed_at=data.get("refreshed_at", ""),
        error=data.get("error")
    )


# ============ 布局管理 ============

@router.put("/layout")
async def update_layout(request: UpdateLayoutRequest):
    """批量更新卡片布局"""
    service = get_dashboard_service()

    updated = service.update_layout(request.layouts)

    return {
        "success": True,
        "updated": updated,
        "total": len(request.layouts)
    }


# ============ 触发器管理 ============

@router.get("/cards/{card_id}/triggers")
async def get_triggers(card_id: str):
    """获取卡片的触发器列表"""
    service = get_dashboard_service()

    triggers = service.get_triggers(card_id)

    return {
        "card_id": card_id,
        "triggers": [
            {
                "trigger_id": t.trigger_id,
                "name": t.name,
                "enabled": t.enabled,
                "trigger_type": t.trigger_type.value if hasattr(t.trigger_type, 'value') else t.trigger_type,
                "condition": t.condition,
                "action": t.action.value if hasattr(t.action, 'value') else t.action,
                "action_config": t.action_config,
                "last_triggered_at": t.last_triggered_at.isoformat() if t.last_triggered_at else None,
                "trigger_count": t.trigger_count
            }
            for t in triggers
        ]
    }


@router.put("/cards/{card_id}/triggers")
async def update_triggers(card_id: str, request: UpdateTriggersRequest):
    """更新卡片的触发器列表（替换全部）"""
    service = get_dashboard_service()

    triggers = [
        Trigger(
            trigger_id=t.trigger_id,
            name=t.name,
            enabled=t.enabled,
            trigger_type=TriggerType(t.trigger_type),
            condition=t.condition,
            action=TriggerAction(t.action),
            action_config=t.action_config
        )
        for t in request.triggers
    ]

    if not service.update_triggers(card_id, triggers):
        raise HTTPException(status_code=404, detail=f"卡片不存在: {card_id}")

    return {"success": True, "message": "触发器已更新"}


@router.delete("/cards/{card_id}/triggers/{trigger_id}")
async def delete_trigger(card_id: str, trigger_id: str):
    """删除触发器"""
    service = get_dashboard_service()

    if not service.remove_trigger(card_id, trigger_id):
        raise HTTPException(
            status_code=404,
            detail=f"触发器不存在: {trigger_id}"
        )

    return {"success": True, "message": f"触发器已删除: {trigger_id}"}


# ============ 通知管理 ============

@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(False, description="仅返回未读通知"),
    card_id: Optional[str] = Query(None, description="按卡片 ID 筛选"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """获取通知列表"""
    store = get_dashboard_store()

    notifications, total = store.list_notifications(
        unread_only=unread_only,
        card_id=card_id,
        limit=limit,
        offset=offset
    )
    unread_count = store.count_unread_notifications()

    return NotificationListResponse(
        notifications=[notification_to_response(n) for n in notifications],
        total=total,
        unread_count=unread_count
    )


@router.get("/notifications/unread/count", response_model=UnreadCountResponse)
async def get_unread_count():
    """获取未读通知数量"""
    store = get_dashboard_store()
    count = store.count_unread_notifications()

    return UnreadCountResponse(count=count)


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """标记通知为已读"""
    store = get_dashboard_store()

    if not store.mark_notification_read(notification_id):
        raise HTTPException(
            status_code=404,
            detail=f"通知不存在: {notification_id}"
        )

    return {"success": True, "message": "已标记为已读"}


@router.post("/notifications/read-all")
async def mark_all_notifications_read():
    """标记所有通知为已读"""
    store = get_dashboard_store()
    count = store.mark_all_notifications_read()

    return {"success": True, "marked": count}
