"""
仪表盘存储层

负责 DashboardCard 和 Notification 的数据库操作。
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlmodel import Session, select, func

from services.database.connection import DatabaseConnection
from .models import (
    DashboardCard,
    Notification,
    NotificationStatus,
    RefreshInterval,
)

logger = logging.getLogger(__name__)


class DashboardStore:
    """
    仪表盘存储层

    负责卡片和通知的 CRUD 操作。
    """

    def __init__(self, db: DatabaseConnection):
        self._db = db

    # ============ 卡片操作 ============

    def create_card(self, card: DashboardCard) -> DashboardCard:
        """创建卡片"""
        with Session(self._db.engine) as session:
            session.add(card)
            session.commit()
            session.refresh(card)
            logger.info(f"创建仪表盘卡片: {card.card_id} - {card.name}")
            return card

    def get_card(self, card_id: str) -> Optional[DashboardCard]:
        """获取卡片"""
        with Session(self._db.engine) as session:
            statement = select(DashboardCard).where(
                DashboardCard.card_id == card_id
            )
            return session.exec(statement).first()

    def list_cards(
        self,
        enabled_only: bool = False,
        card_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[DashboardCard], int]:
        """
        获取卡片列表

        Args:
            enabled_only: 仅返回启用的卡片
            card_type: 按类型筛选
            limit: 限制数量
            offset: 偏移量

        Returns:
            (卡片列表, 总数)
        """
        with Session(self._db.engine) as session:
            # 构建查询
            statement = select(DashboardCard)

            if enabled_only:
                statement = statement.where(DashboardCard.enabled == True)
            if card_type:
                statement = statement.where(DashboardCard.card_type == card_type)

            # 按位置排序（先Y后X）
            statement = statement.order_by(
                DashboardCard.position_y,
                DashboardCard.position_x
            )

            # 计算总数
            count_statement = select(func.count()).select_from(statement.subquery())
            total = session.exec(count_statement).one()

            # 分页
            statement = statement.offset(offset).limit(limit)
            cards = list(session.exec(statement).all())

            return cards, total

    def update_card(
        self,
        card_id: str,
        updates: Dict[str, Any]
    ) -> Optional[DashboardCard]:
        """
        更新卡片

        Args:
            card_id: 卡片 ID
            updates: 要更新的字段

        Returns:
            更新后的卡片，如果不存在返回 None
        """
        with Session(self._db.engine) as session:
            statement = select(DashboardCard).where(
                DashboardCard.card_id == card_id
            )
            card = session.exec(statement).first()

            if not card:
                return None

            # 更新字段
            for key, value in updates.items():
                if hasattr(card, key):
                    setattr(card, key, value)

            card.updated_at = datetime.now()
            session.add(card)
            session.commit()
            session.refresh(card)

            logger.info(f"更新仪表盘卡片: {card_id}")
            return card

    def delete_card(self, card_id: str) -> bool:
        """删除卡片"""
        with Session(self._db.engine) as session:
            statement = select(DashboardCard).where(
                DashboardCard.card_id == card_id
            )
            card = session.exec(statement).first()

            if not card:
                return False

            session.delete(card)
            session.commit()
            logger.info(f"删除仪表盘卡片: {card_id}")
            return True

    def update_card_position(
        self,
        card_id: str,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> bool:
        """更新卡片位置"""
        with Session(self._db.engine) as session:
            statement = select(DashboardCard).where(
                DashboardCard.card_id == card_id
            )
            card = session.exec(statement).first()

            if not card:
                return False

            card.position_x = x
            card.position_y = y
            card.width = max(1, min(12, width))
            card.height = max(1, height)
            card.updated_at = datetime.now()

            session.add(card)
            session.commit()
            return True

    def batch_update_positions(
        self,
        layouts: List[Dict[str, Any]]
    ) -> int:
        """
        批量更新卡片位置

        Args:
            layouts: [{"card_id": "xxx", "x": 0, "y": 0, "width": 4, "height": 3}]

        Returns:
            更新成功的数量
        """
        updated = 0
        with Session(self._db.engine) as session:
            for layout in layouts:
                card_id = layout.get("card_id")
                if not card_id:
                    continue

                statement = select(DashboardCard).where(
                    DashboardCard.card_id == card_id
                )
                card = session.exec(statement).first()

                if card:
                    card.position_x = layout.get("x", card.position_x)
                    card.position_y = layout.get("y", card.position_y)
                    card.width = max(1, min(12, layout.get("width", card.width)))
                    card.height = max(1, layout.get("height", card.height))
                    card.updated_at = datetime.now()
                    session.add(card)
                    updated += 1

            session.commit()

        logger.info(f"批量更新卡片位置: {updated}/{len(layouts)}")
        return updated

    def update_card_cache(
        self,
        card_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """更新卡片缓存数据"""
        with Session(self._db.engine) as session:
            statement = select(DashboardCard).where(
                DashboardCard.card_id == card_id
            )
            card = session.exec(statement).first()

            if not card:
                return False

            card.set_cached_data(data)
            session.add(card)
            session.commit()
            return True

    def get_cards_to_refresh(self) -> List[DashboardCard]:
        """
        获取需要刷新的卡片

        返回启用的、非手动刷新的、已到刷新时间的卡片。
        """
        now = datetime.now()
        with Session(self._db.engine) as session:
            statement = select(DashboardCard).where(
                DashboardCard.enabled == True,
                DashboardCard.refresh_interval != RefreshInterval.MANUAL.value,
            )
            cards = list(session.exec(statement).all())

            # 过滤需要刷新的
            result = []
            for card in cards:
                if card.next_refresh_at is None or card.next_refresh_at <= now:
                    result.append(card)

            return result

    def update_next_refresh_time(
        self,
        card_id: str,
        next_refresh_at: datetime
    ) -> bool:
        """更新下次刷新时间"""
        with Session(self._db.engine) as session:
            statement = select(DashboardCard).where(
                DashboardCard.card_id == card_id
            )
            card = session.exec(statement).first()

            if not card:
                return False

            card.next_refresh_at = next_refresh_at
            card.updated_at = datetime.now()
            session.add(card)
            session.commit()
            return True

    # ============ 通知操作 ============

    def create_notification(
        self,
        notification: Notification
    ) -> Notification:
        """创建通知"""
        with Session(self._db.engine) as session:
            session.add(notification)
            session.commit()
            session.refresh(notification)
            logger.debug(f"创建通知: {notification.notification_id}")
            return notification

    def get_notification(
        self,
        notification_id: str
    ) -> Optional[Notification]:
        """获取通知"""
        with Session(self._db.engine) as session:
            statement = select(Notification).where(
                Notification.notification_id == notification_id
            )
            return session.exec(statement).first()

    def list_notifications(
        self,
        unread_only: bool = False,
        card_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Notification], int]:
        """
        获取通知列表

        Args:
            unread_only: 仅返回未读通知
            card_id: 按卡片 ID 筛选
            limit: 限制数量
            offset: 偏移量

        Returns:
            (通知列表, 总数)
        """
        with Session(self._db.engine) as session:
            statement = select(Notification)

            if unread_only:
                statement = statement.where(
                    Notification.status != NotificationStatus.READ.value
                )
            if card_id:
                statement = statement.where(Notification.card_id == card_id)

            # 按创建时间倒序
            statement = statement.order_by(Notification.created_at.desc())

            # 计算总数
            count_statement = select(func.count()).select_from(statement.subquery())
            total = session.exec(count_statement).one()

            # 分页
            statement = statement.offset(offset).limit(limit)
            notifications = list(session.exec(statement).all())

            return notifications, total

    def count_unread_notifications(self) -> int:
        """获取未读通知数量"""
        with Session(self._db.engine) as session:
            statement = select(func.count()).where(
                Notification.status != NotificationStatus.READ.value
            )
            return session.exec(statement).one()

    def mark_notification_read(self, notification_id: str) -> bool:
        """标记通知为已读"""
        with Session(self._db.engine) as session:
            statement = select(Notification).where(
                Notification.notification_id == notification_id
            )
            notification = session.exec(statement).first()

            if not notification:
                return False

            notification.mark_read()
            session.add(notification)
            session.commit()
            return True

    def mark_all_notifications_read(self) -> int:
        """标记所有通知为已读"""
        with Session(self._db.engine) as session:
            statement = select(Notification).where(
                Notification.status != NotificationStatus.READ.value
            )
            notifications = list(session.exec(statement).all())

            count = 0
            for notification in notifications:
                notification.mark_read()
                session.add(notification)
                count += 1

            session.commit()
            logger.info(f"标记 {count} 条通知为已读")
            return count

    def delete_old_notifications(self, days: int = 30) -> int:
        """
        删除旧通知

        Args:
            days: 保留最近多少天的通知

        Returns:
            删除的数量
        """
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)

        with Session(self._db.engine) as session:
            statement = select(Notification).where(
                Notification.created_at < cutoff
            )
            notifications = list(session.exec(statement).all())

            count = len(notifications)
            for notification in notifications:
                session.delete(notification)

            session.commit()
            logger.info(f"删除 {count} 条旧通知（{days}天前）")
            return count


# 全局实例
_dashboard_store: Optional[DashboardStore] = None


def get_dashboard_store() -> DashboardStore:
    """获取 DashboardStore 单例"""
    global _dashboard_store
    if _dashboard_store is None:
        from services.database.connection import get_db_connection
        _dashboard_store = DashboardStore(get_db_connection())
    return _dashboard_store


def reset_dashboard_store() -> None:
    """重置 DashboardStore（用于测试）"""
    global _dashboard_store
    _dashboard_store = None
