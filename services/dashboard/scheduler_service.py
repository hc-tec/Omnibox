"""
仪表盘定时刷新调度服务

基于 Python threading 实现简化的后台调度。
无需外部依赖（APScheduler），满足基本的定时刷新需求。
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable

from .models import RefreshInterval, DashboardCard
from .store import DashboardStore, get_dashboard_store

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    仪表盘定时刷新调度服务

    功能：
    - 管理卡片的定时刷新任务
    - 支持 hourly/daily/weekly 三种刷新频率
    - 后台线程轮询检查待刷新卡片

    设计原则：
    - 使用简单的轮询机制，避免复杂的调度库
    - 轮询间隔为 60 秒，足够处理 hourly 级别的刷新
    - 线程安全，支持启动/停止
    """

    def __init__(
        self,
        store: Optional[DashboardStore] = None,
        poll_interval: int = 60  # 轮询间隔（秒）
    ):
        self._store = store or get_dashboard_store()
        self._poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._refresh_callback: Optional[Callable[[str], None]] = None

    def set_refresh_callback(
        self,
        callback: Callable[[str], None]
    ) -> None:
        """
        设置刷新回调函数

        Args:
            callback: 刷新回调，参数为 card_id
        """
        self._refresh_callback = callback

    def start(self) -> None:
        """启动调度器"""
        if self._running:
            logger.warning("调度器已在运行")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="DashboardScheduler"
        )
        self._thread.start()
        logger.info("仪表盘调度器已启动")

    def stop(self) -> None:
        """停止调度器"""
        if not self._running:
            return

        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        logger.info("仪表盘调度器已停止")

    def is_running(self) -> bool:
        """检查调度器是否运行中"""
        return self._running

    def _poll_loop(self) -> None:
        """轮询循环（在后台线程中运行）"""
        logger.info("调度器轮询循环开始")

        while self._running:
            try:
                self._check_and_refresh()
            except Exception as e:
                logger.error(f"调度器检查失败: {e}", exc_info=True)

            # 等待下一次轮询
            time.sleep(self._poll_interval)

        logger.info("调度器轮询循环结束")

    def _check_and_refresh(self) -> None:
        """检查并刷新到期的卡片"""
        now = datetime.now()

        # 获取需要刷新的卡片
        cards = self._store.get_cards_to_refresh()

        for card in cards:
            if not self._should_refresh(card, now):
                continue

            logger.info(f"触发定时刷新: {card.card_id} ({card.name})")

            try:
                # 执行刷新
                if self._refresh_callback:
                    self._refresh_callback(card.card_id)
                else:
                    # 默认刷新逻辑
                    self._default_refresh(card.card_id)

                # 更新下次刷新时间
                next_refresh = self._calculate_next_refresh(
                    card.refresh_interval,
                    now
                )
                self._store.update_next_refresh_time(card.card_id, next_refresh)

                logger.info(
                    f"刷新完成: {card.card_id}, "
                    f"下次刷新: {next_refresh.strftime('%Y-%m-%d %H:%M')}"
                )

            except Exception as e:
                logger.error(f"刷新卡片失败: {card.card_id}, {e}")

    def _should_refresh(self, card: DashboardCard, now: datetime) -> bool:
        """判断卡片是否需要刷新"""
        if not card.enabled:
            return False

        if card.refresh_interval == RefreshInterval.MANUAL.value:
            return False

        # 如果没有设置下次刷新时间，立即刷新
        if card.next_refresh_at is None:
            return True

        return card.next_refresh_at <= now

    def _default_refresh(self, card_id: str) -> None:
        """默认刷新逻辑"""
        from .dashboard_service import get_dashboard_service
        service = get_dashboard_service()
        service.refresh_card(card_id)

    def _calculate_next_refresh(
        self,
        interval: str,
        from_time: datetime
    ) -> datetime:
        """计算下次刷新时间"""
        if interval == RefreshInterval.HOURLY.value:
            return from_time + timedelta(hours=1)
        elif interval == RefreshInterval.DAILY.value:
            return from_time + timedelta(days=1)
        elif interval == RefreshInterval.WEEKLY.value:
            return from_time + timedelta(weeks=1)
        else:
            return from_time + timedelta(days=1)

    def refresh_now(self, card_id: str) -> bool:
        """
        立即刷新指定卡片（手动触发）

        Args:
            card_id: 卡片 ID

        Returns:
            是否成功
        """
        card = self._store.get_card(card_id)
        if not card:
            return False

        try:
            if self._refresh_callback:
                self._refresh_callback(card_id)
            else:
                self._default_refresh(card_id)

            # 更新下次刷新时间（如果是定时刷新卡片）
            if card.refresh_interval != RefreshInterval.MANUAL.value:
                next_refresh = self._calculate_next_refresh(
                    card.refresh_interval,
                    datetime.now()
                )
                self._store.update_next_refresh_time(card_id, next_refresh)

            return True

        except Exception as e:
            logger.error(f"手动刷新失败: {card_id}, {e}")
            return False

    def get_status(self) -> Dict:
        """获取调度器状态"""
        cards, total = self._store.list_cards(enabled_only=True)

        scheduled_count = sum(
            1 for c in cards
            if c.refresh_interval != RefreshInterval.MANUAL.value
        )

        pending_count = sum(
            1 for c in cards
            if c.refresh_interval != RefreshInterval.MANUAL.value
            and (c.next_refresh_at is None or c.next_refresh_at <= datetime.now())
        )

        return {
            "running": self._running,
            "poll_interval": self._poll_interval,
            "total_cards": total,
            "scheduled_cards": scheduled_count,
            "pending_refresh": pending_count
        }


# 全局实例
_scheduler_service: Optional[SchedulerService] = None


def get_scheduler_service() -> SchedulerService:
    """获取 SchedulerService 单例"""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service


def reset_scheduler_service() -> None:
    """重置 SchedulerService（用于测试）"""
    global _scheduler_service
    if _scheduler_service:
        _scheduler_service.stop()
    _scheduler_service = None


def start_scheduler() -> None:
    """启动全局调度器"""
    scheduler = get_scheduler_service()
    scheduler.start()


def stop_scheduler() -> None:
    """停止全局调度器"""
    scheduler = get_scheduler_service()
    scheduler.stop()
