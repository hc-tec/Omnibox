"""
仪表盘服务

负责卡片管理、数据刷新、Pin 操作等核心业务逻辑。
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from .models import (
    DashboardCard,
    CardType,
    RefreshInterval,
    Trigger,
)
from .store import DashboardStore, get_dashboard_store

logger = logging.getLogger(__name__)


class DashboardService:
    """
    仪表盘服务

    核心功能：
    - Pin 数据产物/工作流到仪表盘
    - 卡片数据刷新
    - 布局管理
    """

    def __init__(self, store: Optional[DashboardStore] = None):
        self._store = store or get_dashboard_store()

    # ============ Pin 操作 ============

    def pin_artifact(
        self,
        artifact_id: str,
        name: str,
        description: str = "",
        view_config: Optional[Dict[str, Any]] = None,
        refresh_interval: str = RefreshInterval.MANUAL.value,
        triggers: Optional[List[Trigger]] = None,
        position: Optional[Dict[str, int]] = None
    ) -> DashboardCard:
        """
        将数据产物 Pin 到仪表盘

        Args:
            artifact_id: 数据产物 ID
            name: 卡片名称
            description: 卡片描述
            view_config: 可视化配置
            refresh_interval: 刷新频率
            triggers: 触发器列表
            position: 布局位置 {x, y, width, height}

        Returns:
            创建的卡片
        """
        # 创建卡片
        card = DashboardCard.create_artifact_card(
            artifact_id=artifact_id,
            name=name,
            description=description,
            view_config=view_config,
            refresh_interval=refresh_interval,
            position=position
        )

        # 添加触发器
        if triggers:
            for trigger in triggers:
                card.add_trigger(trigger)

        # 计算下次刷新时间
        if refresh_interval != RefreshInterval.MANUAL.value:
            card.next_refresh_at = self._calculate_next_refresh(refresh_interval)

        # 保存
        return self._store.create_card(card)

    def pin_workflow(
        self,
        workflow_id: str,
        name: str,
        variable_values: Dict[str, Any],
        description: str = "",
        view_config: Optional[Dict[str, Any]] = None,
        refresh_interval: str = RefreshInterval.DAILY.value,
        triggers: Optional[List[Trigger]] = None,
        position: Optional[Dict[str, int]] = None
    ) -> DashboardCard:
        """
        将工作流结果 Pin 到仪表盘

        Args:
            workflow_id: 工作流 ID
            name: 卡片名称
            variable_values: 工作流变量值
            description: 卡片描述
            view_config: 可视化配置
            refresh_interval: 刷新频率
            triggers: 触发器列表
            position: 布局位置

        Returns:
            创建的卡片
        """
        card = DashboardCard.create_workflow_card(
            workflow_id=workflow_id,
            name=name,
            variable_values=variable_values,
            description=description,
            view_config=view_config,
            refresh_interval=refresh_interval,
            position=position
        )

        if triggers:
            for trigger in triggers:
                card.add_trigger(trigger)

        if refresh_interval != RefreshInterval.MANUAL.value:
            card.next_refresh_at = self._calculate_next_refresh(refresh_interval)

        return self._store.create_card(card)

    # ============ 卡片管理 ============

    def get_card(self, card_id: str) -> Optional[DashboardCard]:
        """获取卡片"""
        return self._store.get_card(card_id)

    def list_cards(
        self,
        enabled_only: bool = False,
        card_type: Optional[str] = None
    ) -> List[DashboardCard]:
        """获取卡片列表"""
        cards, _ = self._store.list_cards(
            enabled_only=enabled_only,
            card_type=card_type
        )
        return cards

    def update_card(
        self,
        card_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        view_config: Optional[Dict[str, Any]] = None,
        refresh_interval: Optional[str] = None,
        enabled: Optional[bool] = None
    ) -> Optional[DashboardCard]:
        """更新卡片配置"""
        updates = {}

        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if view_config is not None:
            import json
            updates["view_config_json"] = json.dumps(view_config, ensure_ascii=False)
        if refresh_interval is not None:
            updates["refresh_interval"] = refresh_interval
            if refresh_interval != RefreshInterval.MANUAL.value:
                updates["next_refresh_at"] = self._calculate_next_refresh(refresh_interval)
            else:
                updates["next_refresh_at"] = None
        if enabled is not None:
            updates["enabled"] = enabled

        if not updates:
            return self.get_card(card_id)

        return self._store.update_card(card_id, updates)

    def delete_card(self, card_id: str) -> bool:
        """删除卡片"""
        return self._store.delete_card(card_id)

    # ============ 触发器管理 ============

    def get_triggers(self, card_id: str) -> List[Trigger]:
        """获取卡片的触发器列表"""
        card = self._store.get_card(card_id)
        if not card:
            return []
        return card.get_triggers()

    def add_trigger(self, card_id: str, trigger: Trigger) -> bool:
        """添加触发器"""
        card = self._store.get_card(card_id)
        if not card:
            return False

        card.add_trigger(trigger)
        import json
        self._store.update_card(card_id, {
            "triggers_json": json.dumps(
                [t.model_dump(mode='json') for t in card.get_triggers()],
                ensure_ascii=False
            )
        })
        return True

    def remove_trigger(self, card_id: str, trigger_id: str) -> bool:
        """移除触发器"""
        card = self._store.get_card(card_id)
        if not card:
            return False

        if card.remove_trigger(trigger_id):
            import json
            self._store.update_card(card_id, {
                "triggers_json": json.dumps(
                    [t.model_dump(mode='json') for t in card.get_triggers()],
                    ensure_ascii=False
                )
            })
            return True
        return False

    def update_triggers(
        self,
        card_id: str,
        triggers: List[Trigger]
    ) -> bool:
        """更新触发器列表（替换全部）"""
        card = self._store.get_card(card_id)
        if not card:
            return False

        card.set_triggers(triggers)
        import json
        self._store.update_card(card_id, {
            "triggers_json": json.dumps(
                [t.model_dump(mode='json') for t in triggers],
                ensure_ascii=False
            )
        })
        return True

    # ============ 布局管理 ============

    def update_layout(self, layouts: List[Dict[str, Any]]) -> int:
        """
        批量更新卡片布局

        Args:
            layouts: [{"card_id": "xxx", "x": 0, "y": 0, "width": 4, "height": 3}]

        Returns:
            更新成功的数量
        """
        return self._store.batch_update_positions(layouts)

    # ============ 数据刷新 ============

    def refresh_card(self, card_id: str) -> Optional[Dict[str, Any]]:
        """
        刷新卡片数据

        根据卡片类型获取最新数据：
        - artifact: 从 ArtifactStore 获取数据
        - workflow: 执行工作流并获取结果

        Returns:
            刷新后的数据，包含 data、layout、blocks 等
        """
        card = self._store.get_card(card_id)
        if not card:
            logger.warning(f"刷新失败: 卡片不存在 {card_id}")
            return None

        try:
            if card.card_type == CardType.ARTIFACT.value:
                data = self._refresh_artifact_card(card)
            elif card.card_type == CardType.WORKFLOW.value:
                data = self._refresh_workflow_card(card)
            else:
                data = {"error": f"不支持的卡片类型: {card.card_type}"}

            # 更新缓存
            self._store.update_card_cache(card_id, data)

            # 更新下次刷新时间
            if card.refresh_interval != RefreshInterval.MANUAL.value:
                next_refresh = self._calculate_next_refresh(card.refresh_interval)
                self._store.update_next_refresh_time(card_id, next_refresh)

            logger.info(f"刷新卡片成功: {card_id}")
            return data

        except Exception as e:
            logger.error(f"刷新卡片失败: {card_id}, {e}")
            return {"error": str(e)}

    def get_card_data(self, card_id: str) -> Optional[Dict[str, Any]]:
        """
        获取卡片数据（优先使用缓存）

        Returns:
            卡片数据或 None
        """
        card = self._store.get_card(card_id)
        if not card:
            return None

        # 如果有缓存数据，直接返回
        cached = card.get_cached_data()
        if cached:
            return cached

        # 否则刷新数据
        return self.refresh_card(card_id)

    def _refresh_artifact_card(self, card: DashboardCard) -> Dict[str, Any]:
        """刷新数据产物卡片"""
        from services.data_artifact import get_artifact_store

        source_config = card.get_source_config()
        artifact_id = source_config.get("artifact_id")

        if not artifact_id:
            return {"error": "缺少 artifact_id"}

        artifact_store = get_artifact_store()
        artifact = artifact_store.get_artifact(artifact_id)

        if not artifact:
            return {"error": f"数据产物不存在: {artifact_id}"}

        # 获取可视化配置
        view_config = card.get_view_config()

        # 构建响应数据
        return {
            "artifact_id": artifact_id,
            "data": artifact.get_data(),
            "schema": artifact.get_schema_info(),
            "suggested_views": artifact.get_suggested_views(),
            "view_config": view_config,
            "refreshed_at": datetime.now().isoformat()
        }

    def _refresh_workflow_card(self, card: DashboardCard) -> Dict[str, Any]:
        """刷新工作流卡片"""
        from services.workflow import get_workflow_engine, get_workflow_store

        source_config = card.get_source_config()
        workflow_id = source_config.get("workflow_id")
        variable_values = source_config.get("variable_values", {})

        if not workflow_id:
            return {"error": "缺少 workflow_id"}

        workflow_store = get_workflow_store()
        workflow = workflow_store.get_workflow(workflow_id)

        if not workflow:
            return {"error": f"工作流不存在: {workflow_id}"}

        # 执行工作流
        engine = get_workflow_engine()
        try:
            run = engine.execute_workflow(workflow_id, variable_values)

            # 获取最终产物
            artifact_ids = run.get_artifact_ids()
            if artifact_ids:
                # 取最后一个步骤的产物
                last_step_id = max(artifact_ids.keys())
                last_artifact_id = artifact_ids[last_step_id]

                from services.data_artifact import get_artifact_store
                artifact_store = get_artifact_store()
                artifact = artifact_store.get_artifact(last_artifact_id)

                if artifact:
                    view_config = card.get_view_config()
                    return {
                        "workflow_id": workflow_id,
                        "run_id": run.run_id,
                        "artifact_id": last_artifact_id,
                        "data": artifact.get_data(),
                        "schema": artifact.get_schema_info(),
                        "suggested_views": artifact.get_suggested_views(),
                        "view_config": view_config,
                        "refreshed_at": datetime.now().isoformat()
                    }

            return {
                "workflow_id": workflow_id,
                "run_id": run.run_id,
                "status": run.status,
                "refreshed_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"执行工作流失败: {workflow_id}, {e}")
            return {"error": str(e)}

    def _calculate_next_refresh(self, interval: str) -> datetime:
        """计算下次刷新时间"""
        now = datetime.now()

        if interval == RefreshInterval.HOURLY.value:
            return now + timedelta(hours=1)
        elif interval == RefreshInterval.DAILY.value:
            return now + timedelta(days=1)
        elif interval == RefreshInterval.WEEKLY.value:
            return now + timedelta(weeks=1)
        else:
            # 默认 1 天
            return now + timedelta(days=1)


# 全局实例
_dashboard_service: Optional[DashboardService] = None


def get_dashboard_service() -> DashboardService:
    """获取 DashboardService 单例"""
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = DashboardService()
    return _dashboard_service


def reset_dashboard_service() -> None:
    """重置 DashboardService（用于测试）"""
    global _dashboard_service
    _dashboard_service = None
