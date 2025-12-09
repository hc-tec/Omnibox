"""
仪表盘 API Schemas

Phase 5: Dashboard 请求/响应模型
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TriggerSchema(BaseModel):
    """触发器 Schema"""
    trigger_id: Optional[str] = None
    name: str = Field(..., description="触发器名称")
    enabled: bool = Field(default=True)
    trigger_type: str = Field(..., description="触发类型: value_change | threshold | pattern")
    condition: Dict[str, Any] = Field(default_factory=dict, description="触发条件配置")
    action: str = Field(..., description="触发动作: notify | refresh | run_workflow")
    action_config: Dict[str, Any] = Field(default_factory=dict, description="动作配置")


class PositionSchema(BaseModel):
    """布局位置 Schema"""
    x: int = Field(default=0, ge=0, description="网格 X 坐标")
    y: int = Field(default=0, ge=0, description="网格 Y 坐标")
    width: int = Field(default=4, ge=1, le=12, description="宽度（1-12）")
    height: int = Field(default=3, ge=1, description="高度")


# ============ 请求模型 ============

class PinArtifactRequest(BaseModel):
    """Pin 数据产物请求"""
    artifact_id: str = Field(..., description="数据产物 ID")
    name: str = Field(..., description="卡片名称")
    description: str = Field(default="", description="卡片描述")
    view_config: Optional[Dict[str, Any]] = Field(default=None, description="可视化配置")
    refresh_interval: str = Field(default="manual", description="刷新频率")
    triggers: Optional[List[TriggerSchema]] = Field(default=None, description="触发器列表")
    position: Optional[PositionSchema] = Field(default=None, description="布局位置")


class PinWorkflowRequest(BaseModel):
    """Pin 工作流请求"""
    workflow_id: str = Field(..., description="工作流 ID")
    name: str = Field(..., description="卡片名称")
    variable_values: Dict[str, Any] = Field(default_factory=dict, description="工作流变量值")
    description: str = Field(default="", description="卡片描述")
    view_config: Optional[Dict[str, Any]] = Field(default=None, description="可视化配置")
    refresh_interval: str = Field(default="daily", description="刷新频率")
    triggers: Optional[List[TriggerSchema]] = Field(default=None, description="触发器列表")
    position: Optional[PositionSchema] = Field(default=None, description="布局位置")


class PinPanelRequest(BaseModel):
    """
    Pin 面板请求

    面板数据来自 emit_panel_preview，包含完整的布局和数据块信息。
    这类卡片不需要后端刷新，数据直接存储在卡片中。
    """
    title: str = Field(..., description="面板标题")
    layout: Dict[str, Any] = Field(..., description="布局信息（LayoutTree）")
    blocks: List[Dict[str, Any]] = Field(..., description="UI 块列表")
    data_blocks: Dict[str, Any] = Field(..., description="数据块映射")
    description: str = Field(default="", description="卡片描述")
    position: Optional[PositionSchema] = Field(default=None, description="布局位置")


class UpdateCardRequest(BaseModel):
    """更新卡片请求"""
    name: Optional[str] = Field(default=None, description="卡片名称")
    description: Optional[str] = Field(default=None, description="卡片描述")
    view_config: Optional[Dict[str, Any]] = Field(default=None, description="可视化配置")
    refresh_interval: Optional[str] = Field(default=None, description="刷新频率")
    enabled: Optional[bool] = Field(default=None, description="是否启用")


class UpdateLayoutRequest(BaseModel):
    """更新布局请求"""
    layouts: List[Dict[str, Any]] = Field(
        ...,
        description="布局列表: [{card_id, x, y, width, height}]"
    )


class UpdateTriggersRequest(BaseModel):
    """更新触发器请求"""
    triggers: List[TriggerSchema] = Field(..., description="触发器列表")


# ============ 响应模型 ============

class CardResponse(BaseModel):
    """卡片响应"""
    card_id: str
    name: str
    description: str
    card_type: str
    source_config: Dict[str, Any]
    view_config: Dict[str, Any]
    refresh_interval: str
    last_refresh_at: Optional[str]
    next_refresh_at: Optional[str]
    triggers: List[TriggerSchema]
    position: PositionSchema
    enabled: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CardListResponse(BaseModel):
    """卡片列表响应"""
    cards: List[CardResponse]
    total: int


class CardDataResponse(BaseModel):
    """卡片数据响应"""
    card_id: str
    data: Any
    layout: Optional[Dict[str, Any]] = None
    blocks: Optional[List[Dict[str, Any]]] = None
    schema: Optional[Dict[str, Any]] = None
    suggested_views: Optional[List[Dict[str, Any]]] = None
    view_config: Optional[Dict[str, Any]] = None
    refreshed_at: str
    error: Optional[str] = None


class NotificationResponse(BaseModel):
    """通知响应"""
    notification_id: str
    title: str
    message: str
    source_type: str
    source_id: Optional[str]
    card_id: Optional[str]
    channel: str
    status: str
    data: Dict[str, Any]
    created_at: str
    sent_at: Optional[str]
    read_at: Optional[str]

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """通知列表响应"""
    notifications: List[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """未读数量响应"""
    count: int


# ============ 辅助函数 ============

def card_to_response(card) -> CardResponse:
    """将 DashboardCard 转换为响应模型"""
    from services.dashboard.models import Trigger

    triggers = card.get_triggers()
    trigger_schemas = [
        TriggerSchema(
            trigger_id=t.trigger_id,
            name=t.name,
            enabled=t.enabled,
            trigger_type=t.trigger_type.value if hasattr(t.trigger_type, 'value') else t.trigger_type,
            condition=t.condition,
            action=t.action.value if hasattr(t.action, 'value') else t.action,
            action_config=t.action_config
        )
        for t in triggers
    ]

    return CardResponse(
        card_id=card.card_id,
        name=card.name,
        description=card.description,
        card_type=card.card_type,
        source_config=card.get_source_config(),
        view_config=card.get_view_config(),
        refresh_interval=card.refresh_interval,
        last_refresh_at=card.last_refresh_at.isoformat() if card.last_refresh_at else None,
        next_refresh_at=card.next_refresh_at.isoformat() if card.next_refresh_at else None,
        triggers=trigger_schemas,
        position=PositionSchema(
            x=card.position_x,
            y=card.position_y,
            width=card.width,
            height=card.height
        ),
        enabled=card.enabled,
        created_at=card.created_at.isoformat(),
        updated_at=card.updated_at.isoformat()
    )


def notification_to_response(notification) -> NotificationResponse:
    """将 Notification 转换为响应模型"""
    return NotificationResponse(
        notification_id=notification.notification_id,
        title=notification.title,
        message=notification.message,
        source_type=notification.source_type,
        source_id=notification.source_id,
        card_id=notification.card_id,
        channel=notification.channel,
        status=notification.status,
        data=notification.get_data(),
        created_at=notification.created_at.isoformat(),
        sent_at=notification.sent_at.isoformat() if notification.sent_at else None,
        read_at=notification.read_at.isoformat() if notification.read_at else None
    )
