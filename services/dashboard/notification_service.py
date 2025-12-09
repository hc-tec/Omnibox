"""
通知服务

负责发送和管理应用内通知。
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from .models import (
    Notification,
    NotificationChannel,
    NotificationStatus,
)
from .store import DashboardStore, get_dashboard_store

logger = logging.getLogger(__name__)


class NotificationService:
    """
    通知服务

    负责：
    - 创建和发送通知
    - 管理通知状态（已读/未读）
    - 通过 WebSocket 推送实时通知
    """

    def __init__(self, store: Optional[DashboardStore] = None):
        self._store = store or get_dashboard_store()
        self._websocket_broadcast = None  # WebSocket 广播回调

    def set_websocket_broadcast(
        self,
        callback
    ) -> None:
        """
        设置 WebSocket 广播回调

        用于实时推送通知到前端。

        Args:
            callback: async def callback(message: dict)
        """
        self._websocket_broadcast = callback

    def send(
        self,
        title: str,
        message: str,
        channel: NotificationChannel = NotificationChannel.APP,
        source_type: str = "system",
        source_id: Optional[str] = None,
        card_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """
        发送通知

        Args:
            title: 通知标题
            message: 通知内容
            channel: 通知渠道
            source_type: 来源类型（trigger / system）
            source_id: 来源 ID
            card_id: 关联卡片 ID
            data: 附加数据

        Returns:
            创建的通知
        """
        # 创建通知
        notification = Notification.create(
            title=title,
            message=message,
            source_type=source_type,
            source_id=source_id,
            card_id=card_id,
            data=data
        )
        notification.channel = channel.value if isinstance(channel, NotificationChannel) else channel

        # 保存到数据库
        notification = self._store.create_notification(notification)

        # 根据渠道发送
        if channel == NotificationChannel.APP or channel == NotificationChannel.APP.value:
            self._send_app_notification(notification)

        logger.info(
            f"发送通知: {notification.notification_id} - {title}"
        )

        return notification

    def _send_app_notification(self, notification: Notification) -> None:
        """
        发送应用内通知

        通过 WebSocket 推送到前端。
        """
        # 标记为已发送
        notification.mark_sent()
        self._store.update_card(notification.notification_id, {
            "status": NotificationStatus.SENT.value,
            "sent_at": notification.sent_at
        })

        # 推送到 WebSocket（如果有回调）
        if self._websocket_broadcast:
            try:
                import asyncio
                message = {
                    "type": "notification",
                    "data": {
                        "notification_id": notification.notification_id,
                        "title": notification.title,
                        "message": notification.message,
                        "source_type": notification.source_type,
                        "card_id": notification.card_id,
                        "created_at": notification.created_at.isoformat()
                    }
                }

                # 尝试在事件循环中执行
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self._websocket_broadcast(message))
                    else:
                        loop.run_until_complete(self._websocket_broadcast(message))
                except RuntimeError:
                    # 没有事件循环，创建新的
                    asyncio.run(self._websocket_broadcast(message))

            except Exception as e:
                logger.warning(f"WebSocket 推送失败: {e}")

    def list_notifications(
        self,
        unread_only: bool = False,
        card_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Notification]:
        """获取通知列表"""
        notifications, _ = self._store.list_notifications(
            unread_only=unread_only,
            card_id=card_id,
            limit=limit
        )
        return notifications

    def get_unread_count(self) -> int:
        """获取未读通知数量"""
        return self._store.count_unread_notifications()

    def mark_read(self, notification_id: str) -> bool:
        """标记通知为已读"""
        return self._store.mark_notification_read(notification_id)

    def mark_all_read(self) -> int:
        """标记所有通知为已读"""
        return self._store.mark_all_notifications_read()

    def send_system_notification(
        self,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """发送系统通知（快捷方法）"""
        return self.send(
            title=title,
            message=message,
            source_type="system",
            data=data
        )

    def send_trigger_notification(
        self,
        trigger_id: str,
        trigger_name: str,
        card_id: str,
        card_name: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """发送触发器通知（快捷方法）"""
        return self.send(
            title=f"仪表盘提醒: {card_name}",
            message=message,
            source_type="trigger",
            source_id=trigger_id,
            card_id=card_id,
            data={
                "trigger_id": trigger_id,
                "trigger_name": trigger_name,
                "card_name": card_name,
                **(data or {})
            }
        )

    def cleanup_old_notifications(self, days: int = 30) -> int:
        """清理旧通知"""
        return self._store.delete_old_notifications(days)


# 全局实例
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """获取 NotificationService 单例"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


def reset_notification_service() -> None:
    """重置 NotificationService（用于测试）"""
    global _notification_service
    _notification_service = None
