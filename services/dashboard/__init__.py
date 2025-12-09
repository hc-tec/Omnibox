"""
仪表盘服务模块

Phase 5: Dashboard 实现
- 卡片管理（Pin 数据产物/工作流）
- 定时刷新
- 条件触发
- 通知推送

模块结构：
- models.py - 数据模型（DashboardCard、Trigger、Notification）
- store.py - 数据存储层（CRUD 操作）
- dashboard_service.py - 仪表盘服务
- scheduler_service.py - 定时刷新调度
- trigger_service.py - 条件触发评估
- notification_service.py - 通知服务
"""

from .models import (
    DashboardCard,
    Notification,
    Trigger,
    CardType,
    RefreshInterval,
    TriggerType,
    TriggerAction,
    NotificationChannel,
    NotificationStatus,
)
from .store import DashboardStore, get_dashboard_store, reset_dashboard_store
from .dashboard_service import (
    DashboardService,
    get_dashboard_service,
    reset_dashboard_service,
)
from .scheduler_service import (
    SchedulerService,
    get_scheduler_service,
    reset_scheduler_service,
    start_scheduler,
    stop_scheduler,
)
from .trigger_service import (
    TriggerService,
    get_trigger_service,
    reset_trigger_service,
)
from .notification_service import (
    NotificationService,
    get_notification_service,
    reset_notification_service,
)

__all__ = [
    # 模型
    "DashboardCard",
    "Notification",
    "Trigger",
    # 枚举
    "CardType",
    "RefreshInterval",
    "TriggerType",
    "TriggerAction",
    "NotificationChannel",
    "NotificationStatus",
    # Store
    "DashboardStore",
    "get_dashboard_store",
    "reset_dashboard_store",
    # Service
    "DashboardService",
    "get_dashboard_service",
    "reset_dashboard_service",
    # Scheduler
    "SchedulerService",
    "get_scheduler_service",
    "reset_scheduler_service",
    "start_scheduler",
    "stop_scheduler",
    # Trigger
    "TriggerService",
    "get_trigger_service",
    "reset_trigger_service",
    # Notification
    "NotificationService",
    "get_notification_service",
    "reset_notification_service",
]
