"""
仪表盘数据模型

Phase 5: Dashboard 核心模型定义
- DashboardCard: 仪表盘卡片（Pin 的数据产物/工作流）
- Trigger: 条件触发器
- Notification: 通知记录
"""

import json
import uuid
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField


class CardType(str, Enum):
    """卡片类型"""
    ARTIFACT = "artifact"       # 数据产物卡片
    WORKFLOW = "workflow"       # 工作流结果卡片
    CUSTOM = "custom"           # 自定义查询卡片


class RefreshInterval(str, Enum):
    """刷新频率"""
    MANUAL = "manual"           # 手动刷新
    HOURLY = "hourly"           # 每小时
    DAILY = "daily"             # 每天
    WEEKLY = "weekly"           # 每周


class TriggerType(str, Enum):
    """触发器类型"""
    VALUE_CHANGE = "value_change"     # 值变化时触发
    THRESHOLD = "threshold"           # 超过阈值触发
    PATTERN = "pattern"               # 模式匹配触发


class TriggerAction(str, Enum):
    """触发动作"""
    NOTIFY = "notify"                 # 发送通知
    REFRESH = "refresh"               # 刷新卡片
    RUN_WORKFLOW = "run_workflow"     # 执行工作流


class NotificationChannel(str, Enum):
    """通知渠道"""
    APP = "app"                       # 应用内通知


class NotificationStatus(str, Enum):
    """通知状态"""
    PENDING = "pending"
    SENT = "sent"
    READ = "read"
    FAILED = "failed"


class Trigger(BaseModel):
    """
    触发器定义

    设计理念：
    - 条件 + 动作的组合
    - 支持多种触发类型和动作
    - 可序列化为 JSON 存储
    """
    trigger_id: str = Field(
        default_factory=lambda: f"trg-{uuid.uuid4().hex[:8]}"
    )
    name: str = Field(..., description="触发器名称")
    enabled: bool = Field(default=True)

    # 触发条件
    trigger_type: TriggerType = Field(...)
    condition: Dict[str, Any] = Field(
        default_factory=dict,
        description="""
        条件配置（根据 trigger_type 不同）：
        - value_change: {"field": "count", "change_type": "increase"}
        - threshold: {"field": "count", "operator": "gt", "value": 100}
        - pattern: {"field": "title", "regex": ".*关键词.*"}
        """
    )

    # 触发动作
    action: TriggerAction = Field(...)
    action_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="""
        动作配置：
        - notify: {"message": "xxx"}
        - refresh: {}
        - run_workflow: {"workflow_id": "xxx", "variables": {...}}
        """
    )

    # 执行记录
    last_triggered_at: Optional[datetime] = Field(default=None)
    trigger_count: int = Field(default=0)


class DashboardCard(SQLModel, table=True):
    """
    仪表盘卡片

    核心设计：
    - 卡片是对数据源（Artifact/Workflow/Query）的引用
    - 支持定时刷新和条件触发
    - 支持自定义可视化配置
    """
    __tablename__ = "dashboard_cards"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    card_id: str = SQLField(index=True, description="卡片唯一标识")

    # 基本信息
    name: str = SQLField(..., description="卡片名称")
    description: str = SQLField(default="", description="卡片描述")
    card_type: str = SQLField(..., description="卡片类型")

    # 数据源配置（JSON 存储）
    source_config_json: str = SQLField(
        default="{}",
        description="""
        数据源配置（根据 card_type 不同）：
        - artifact: {"artifact_id": "xxx"}
        - workflow: {"workflow_id": "xxx", "variable_values": {...}}
        - custom: {"query": "xxx"}
        """
    )

    # 可视化配置（JSON 存储）
    view_config_json: str = SQLField(
        default="{}",
        description="""
        可视化配置：
        - component: 组件类型（LineChart、Table 等）
        - props: 组件属性
        """
    )

    # 刷新配置
    refresh_interval: str = SQLField(
        default=RefreshInterval.MANUAL.value,
        description="刷新频率"
    )
    last_refresh_at: Optional[datetime] = SQLField(default=None)
    next_refresh_at: Optional[datetime] = SQLField(default=None)

    # 触发器配置（JSON 数组）
    triggers_json: str = SQLField(default="[]", description="触发器列表")

    # 布局位置（12列网格系统）
    position_x: int = SQLField(default=0, description="网格 X 坐标")
    position_y: int = SQLField(default=0, description="网格 Y 坐标")
    width: int = SQLField(default=4, description="宽度（网格单位，共12列）")
    height: int = SQLField(default=3, description="高度（网格单位）")

    # 状态
    enabled: bool = SQLField(default=True, description="是否启用")

    # 缓存数据（JSON 存储，避免每次都重新获取）
    cached_data_json: Optional[str] = SQLField(
        default=None,
        description="缓存的卡片数据"
    )

    # 时间戳
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now)

    # --- 辅助方法 ---

    def get_source_config(self) -> Dict[str, Any]:
        """获取数据源配置"""
        try:
            return json.loads(self.source_config_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_source_config(self, config: Dict[str, Any]) -> None:
        """设置数据源配置"""
        self.source_config_json = json.dumps(config, ensure_ascii=False)
        self.updated_at = datetime.now()

    def get_view_config(self) -> Dict[str, Any]:
        """获取可视化配置"""
        try:
            return json.loads(self.view_config_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_view_config(self, config: Dict[str, Any]) -> None:
        """设置可视化配置"""
        self.view_config_json = json.dumps(config, ensure_ascii=False)
        self.updated_at = datetime.now()

    def get_triggers(self) -> List[Trigger]:
        """获取触发器列表"""
        try:
            data = json.loads(self.triggers_json)
            return [Trigger(**item) for item in data]
        except (json.JSONDecodeError, TypeError):
            return []

    def set_triggers(self, triggers: List[Trigger]) -> None:
        """设置触发器列表"""
        self.triggers_json = json.dumps(
            [t.model_dump(mode='json') for t in triggers],
            ensure_ascii=False
        )
        self.updated_at = datetime.now()

    def add_trigger(self, trigger: Trigger) -> None:
        """添加触发器"""
        triggers = self.get_triggers()
        triggers.append(trigger)
        self.set_triggers(triggers)

    def remove_trigger(self, trigger_id: str) -> bool:
        """移除触发器"""
        triggers = self.get_triggers()
        original_len = len(triggers)
        triggers = [t for t in triggers if t.trigger_id != trigger_id]
        if len(triggers) < original_len:
            self.set_triggers(triggers)
            return True
        return False

    def get_cached_data(self) -> Optional[Dict[str, Any]]:
        """获取缓存数据"""
        if not self.cached_data_json:
            return None
        try:
            return json.loads(self.cached_data_json)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_cached_data(self, data: Dict[str, Any]) -> None:
        """设置缓存数据"""
        self.cached_data_json = json.dumps(data, ensure_ascii=False)
        self.last_refresh_at = datetime.now()
        self.updated_at = datetime.now()

    def get_position(self) -> Dict[str, int]:
        """获取布局位置"""
        return {
            "x": self.position_x,
            "y": self.position_y,
            "width": self.width,
            "height": self.height
        }

    def set_position(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> None:
        """设置布局位置"""
        if x is not None:
            self.position_x = x
        if y is not None:
            self.position_y = y
        if width is not None:
            self.width = max(1, min(12, width))  # 限制在 1-12 范围
        if height is not None:
            self.height = max(1, height)
        self.updated_at = datetime.now()

    @staticmethod
    def generate_card_id() -> str:
        """生成卡片 ID"""
        return f"card-{uuid.uuid4().hex[:12]}"

    @classmethod
    def create_artifact_card(
        cls,
        artifact_id: str,
        name: str,
        description: str = "",
        view_config: Optional[Dict[str, Any]] = None,
        refresh_interval: str = RefreshInterval.MANUAL.value,
        position: Optional[Dict[str, int]] = None
    ) -> "DashboardCard":
        """工厂方法：创建数据产物卡片"""
        card = cls(
            card_id=cls.generate_card_id(),
            name=name,
            description=description,
            card_type=CardType.ARTIFACT.value,
            refresh_interval=refresh_interval
        )
        card.set_source_config({"artifact_id": artifact_id})
        if view_config:
            card.set_view_config(view_config)
        if position:
            card.set_position(**position)
        return card

    @classmethod
    def create_workflow_card(
        cls,
        workflow_id: str,
        name: str,
        variable_values: Dict[str, Any],
        description: str = "",
        view_config: Optional[Dict[str, Any]] = None,
        refresh_interval: str = RefreshInterval.DAILY.value,
        position: Optional[Dict[str, int]] = None
    ) -> "DashboardCard":
        """工厂方法：创建工作流卡片"""
        card = cls(
            card_id=cls.generate_card_id(),
            name=name,
            description=description,
            card_type=CardType.WORKFLOW.value,
            refresh_interval=refresh_interval
        )
        card.set_source_config({
            "workflow_id": workflow_id,
            "variable_values": variable_values
        })
        if view_config:
            card.set_view_config(view_config)
        if position:
            card.set_position(**position)
        return card

    @classmethod
    def create_panel_card(
        cls,
        name: str,
        layout: Dict[str, Any],
        blocks: List[Dict[str, Any]],
        data_blocks: Dict[str, Any],
        description: str = "",
        refresh_interval: str = RefreshInterval.MANUAL.value,
        position: Optional[Dict[str, int]] = None
    ) -> "DashboardCard":
        """
        工厂方法：创建面板卡片

        面板数据直接存储在 source_config 中，无需后端数据源刷新。
        这是从 emit_panel_preview 产出的可视化面板数据。

        Args:
            name: 卡片名称
            layout: 布局信息（LayoutTree）
            blocks: UI 块列表（UIBlock[]）
            data_blocks: 数据块映射（Record<string, DataBlock>）
            description: 卡片描述
            refresh_interval: 刷新频率（面板默认手动刷新）
            position: 布局位置
        """
        card = cls(
            card_id=cls.generate_card_id(),
            name=name,
            description=description,
            card_type=CardType.CUSTOM.value,
            refresh_interval=refresh_interval
        )
        # 将面板数据存储在 source_config 中
        card.set_source_config({
            "panel_type": "preview",
            "layout": layout,
            "blocks": blocks,
            "data_blocks": data_blocks
        })
        # 直接缓存数据，无需后续刷新
        card.set_cached_data({
            "layout": layout,
            "blocks": blocks,
            "data_blocks": data_blocks,
            "refreshed_at": datetime.now().isoformat()
        })
        if position:
            card.set_position(**position)
        return card


class Notification(SQLModel, table=True):
    """
    通知记录

    用于存储应用内通知，支持触发器产生的通知和系统通知。
    """
    __tablename__ = "notifications"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    notification_id: str = SQLField(index=True, description="通知唯一标识")

    # 来源
    source_type: str = SQLField(
        default="system",
        description="来源类型: trigger | system"
    )
    source_id: Optional[str] = SQLField(
        default=None,
        description="来源 ID（触发器 ID）"
    )
    card_id: Optional[str] = SQLField(
        default=None,
        index=True,
        description="关联卡片 ID"
    )

    # 内容
    title: str = SQLField(..., description="通知标题")
    message: str = SQLField(..., description="通知内容")
    data_json: str = SQLField(
        default="{}",
        description="附加数据（JSON）"
    )

    # 渠道和状态
    channel: str = SQLField(
        default=NotificationChannel.APP.value,
        description="通知渠道"
    )
    status: str = SQLField(
        default=NotificationStatus.PENDING.value,
        description="通知状态"
    )

    # 时间戳
    created_at: datetime = SQLField(default_factory=datetime.now, index=True)
    sent_at: Optional[datetime] = SQLField(default=None)
    read_at: Optional[datetime] = SQLField(default=None)

    # --- 辅助方法 ---

    def get_data(self) -> Dict[str, Any]:
        """获取附加数据"""
        try:
            return json.loads(self.data_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_data(self, data: Dict[str, Any]) -> None:
        """设置附加数据"""
        self.data_json = json.dumps(data, ensure_ascii=False)

    def mark_sent(self) -> None:
        """标记为已发送"""
        self.status = NotificationStatus.SENT.value
        self.sent_at = datetime.now()

    def mark_read(self) -> None:
        """标记为已读"""
        self.status = NotificationStatus.READ.value
        self.read_at = datetime.now()

    def mark_failed(self) -> None:
        """标记为发送失败"""
        self.status = NotificationStatus.FAILED.value

    @staticmethod
    def generate_notification_id() -> str:
        """生成通知 ID"""
        return f"notif-{uuid.uuid4().hex[:12]}"

    @classmethod
    def create(
        cls,
        title: str,
        message: str,
        source_type: str = "system",
        source_id: Optional[str] = None,
        card_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> "Notification":
        """工厂方法：创建通知"""
        notification = cls(
            notification_id=cls.generate_notification_id(),
            title=title,
            message=message,
            source_type=source_type,
            source_id=source_id,
            card_id=card_id
        )
        if data:
            notification.set_data(data)
        return notification
