"""
条件触发服务

负责评估触发条件、执行触发动作。
"""

import re
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from .models import (
    DashboardCard,
    Trigger,
    TriggerType,
    TriggerAction,
)
from .store import DashboardStore, get_dashboard_store

logger = logging.getLogger(__name__)


class TriggerService:
    """
    条件触发服务

    负责：
    - 评估触发条件（值变化、阈值、模式匹配）
    - 执行触发动作（通知、刷新、工作流）
    """

    def __init__(self, store: Optional[DashboardStore] = None):
        self._store = store or get_dashboard_store()
        self._notification_service = None  # 延迟初始化

    def _get_notification_service(self):
        """获取通知服务（延迟初始化）"""
        if self._notification_service is None:
            from .notification_service import get_notification_service
            self._notification_service = get_notification_service()
        return self._notification_service

    def evaluate_triggers(
        self,
        card_id: str,
        old_data: Optional[Dict[str, Any]],
        new_data: Dict[str, Any]
    ) -> List[Trigger]:
        """
        评估卡片的触发器

        Args:
            card_id: 卡片 ID
            old_data: 旧数据（首次刷新为 None）
            new_data: 新数据

        Returns:
            被触发的触发器列表
        """
        card = self._store.get_card(card_id)
        if not card:
            logger.warning(f"评估触发器失败: 卡片不存在 {card_id}")
            return []

        triggers = card.get_triggers()
        triggered = []

        for trigger in triggers:
            if not trigger.enabled:
                continue

            try:
                if self._check_condition(trigger, old_data, new_data):
                    logger.info(
                        f"触发器触发: {trigger.name} (card={card_id})"
                    )
                    self._execute_action(trigger, card, new_data)
                    triggered.append(trigger)

                    # 更新触发记录
                    trigger.last_triggered_at = datetime.now()
                    trigger.trigger_count += 1

            except Exception as e:
                logger.error(
                    f"评估触发器失败: {trigger.name}, {e}",
                    exc_info=True
                )

        # 如果有触发器被触发，更新卡片
        if triggered:
            self._update_triggers(card, card.get_triggers())

        return triggered

    def _check_condition(
        self,
        trigger: Trigger,
        old_data: Optional[Dict[str, Any]],
        new_data: Dict[str, Any]
    ) -> bool:
        """检查触发条件"""
        trigger_type = trigger.trigger_type
        if isinstance(trigger_type, str):
            trigger_type = TriggerType(trigger_type)

        if trigger_type == TriggerType.VALUE_CHANGE:
            return self._check_value_change(
                trigger.condition, old_data, new_data
            )
        elif trigger_type == TriggerType.THRESHOLD:
            return self._check_threshold(trigger.condition, new_data)
        elif trigger_type == TriggerType.PATTERN:
            return self._check_pattern(trigger.condition, new_data)
        else:
            logger.warning(f"未知的触发类型: {trigger_type}")
            return False

    def _check_value_change(
        self,
        condition: Dict[str, Any],
        old_data: Optional[Dict[str, Any]],
        new_data: Dict[str, Any]
    ) -> bool:
        """
        检查值变化

        条件格式：
        {
            "field": "data.count",      # 字段路径
            "change_type": "increase"   # any | increase | decrease
        }
        """
        field = condition.get("field", "")
        change_type = condition.get("change_type", "any")

        # 首次数据，视为变化
        if old_data is None:
            return change_type == "any"

        old_value = self._get_field_value(old_data, field)
        new_value = self._get_field_value(new_data, field)

        if old_value is None or new_value is None:
            return False

        if change_type == "any":
            return old_value != new_value
        elif change_type == "increase":
            try:
                return float(new_value) > float(old_value)
            except (ValueError, TypeError):
                return False
        elif change_type == "decrease":
            try:
                return float(new_value) < float(old_value)
            except (ValueError, TypeError):
                return False

        return False

    def _check_threshold(
        self,
        condition: Dict[str, Any],
        data: Dict[str, Any]
    ) -> bool:
        """
        检查阈值

        条件格式：
        {
            "field": "data.count",    # 字段路径
            "operator": "gt",          # gt | lt | eq | gte | lte
            "value": 100               # 阈值
        }
        """
        field = condition.get("field", "")
        operator = condition.get("operator", "gt")
        threshold = condition.get("value")

        if threshold is None:
            return False

        current = self._get_field_value(data, field)
        if current is None:
            return False

        try:
            current_num = float(current)
            threshold_num = float(threshold)
        except (ValueError, TypeError):
            return False

        operators = {
            "gt": lambda a, b: a > b,
            "lt": lambda a, b: a < b,
            "eq": lambda a, b: a == b,
            "gte": lambda a, b: a >= b,
            "lte": lambda a, b: a <= b,
        }

        op_func = operators.get(operator)
        if not op_func:
            logger.warning(f"未知的操作符: {operator}")
            return False

        return op_func(current_num, threshold_num)

    def _check_pattern(
        self,
        condition: Dict[str, Any],
        data: Dict[str, Any]
    ) -> bool:
        """
        检查模式匹配

        条件格式：
        {
            "field": "data.title",    # 字段路径
            "regex": ".*关键词.*"      # 正则表达式
        }
        """
        field = condition.get("field", "")
        pattern = condition.get("regex", "")

        if not pattern:
            return False

        value = self._get_field_value(data, field)
        if value is None:
            return False

        try:
            return bool(re.search(pattern, str(value)))
        except re.error as e:
            logger.warning(f"无效的正则表达式: {pattern}, {e}")
            return False

    def _get_field_value(
        self,
        data: Dict[str, Any],
        field_path: str
    ) -> Optional[Any]:
        """
        获取字段值（支持点号路径）

        例如: "data.items.0.title" -> data["items"][0]["title"]
        """
        if not field_path:
            return None

        parts = field_path.split(".")
        current = data

        for part in parts:
            if current is None:
                return None

            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    index = int(part)
                    current = current[index] if 0 <= index < len(current) else None
                except ValueError:
                    return None
            else:
                return None

        return current

    def _execute_action(
        self,
        trigger: Trigger,
        card: DashboardCard,
        data: Dict[str, Any]
    ) -> None:
        """执行触发动作"""
        action = trigger.action
        if isinstance(action, str):
            action = TriggerAction(action)

        if action == TriggerAction.NOTIFY:
            self._send_notification(trigger, card, data)
        elif action == TriggerAction.REFRESH:
            # 刷新动作在调度器中已处理，此处跳过
            pass
        elif action == TriggerAction.RUN_WORKFLOW:
            self._run_workflow(trigger, data)
        else:
            logger.warning(f"未知的触发动作: {action}")

    def _send_notification(
        self,
        trigger: Trigger,
        card: DashboardCard,
        data: Dict[str, Any]
    ) -> None:
        """发送通知"""
        config = trigger.action_config
        message = config.get("message", f"触发器 [{trigger.name}] 已触发")

        # 支持消息模板变量
        message = self._render_message(message, card, data)

        notification_service = self._get_notification_service()
        notification_service.send(
            title=f"仪表盘提醒: {card.name}",
            message=message,
            source_type="trigger",
            source_id=trigger.trigger_id,
            card_id=card.card_id,
            data={"trigger": trigger.name, "card": card.name}
        )

    def _render_message(
        self,
        template: str,
        card: DashboardCard,
        data: Dict[str, Any]
    ) -> str:
        """渲染消息模板"""
        # 简单的变量替换
        message = template
        message = message.replace("{{card_name}}", card.name)
        message = message.replace("{{card_id}}", card.card_id)

        # 替换数据字段
        import re
        pattern = r"\{\{data\.([^}]+)\}\}"
        for match in re.finditer(pattern, template):
            field = match.group(1)
            value = self._get_field_value(data, f"data.{field}")
            if value is not None:
                message = message.replace(match.group(0), str(value))

        return message

    def _run_workflow(
        self,
        trigger: Trigger,
        data: Dict[str, Any]
    ) -> None:
        """执行工作流"""
        config = trigger.action_config
        workflow_id = config.get("workflow_id")
        variables = config.get("variables", {})

        if not workflow_id:
            logger.warning("触发器配置缺少 workflow_id")
            return

        try:
            from services.workflow import get_workflow_engine
            engine = get_workflow_engine()
            run = engine.execute_workflow(workflow_id, variables)
            logger.info(f"触发工作流执行: {workflow_id} -> {run.run_id}")
        except Exception as e:
            logger.error(f"执行工作流失败: {workflow_id}, {e}")

    def _update_triggers(
        self,
        card: DashboardCard,
        triggers: List[Trigger]
    ) -> None:
        """更新卡片的触发器列表"""
        import json
        self._store.update_card(card.card_id, {
            "triggers_json": json.dumps(
                [t.model_dump(mode='json') for t in triggers],
                ensure_ascii=False
            )
        })


# 全局实例
_trigger_service: Optional[TriggerService] = None


def get_trigger_service() -> TriggerService:
    """获取 TriggerService 单例"""
    global _trigger_service
    if _trigger_service is None:
        _trigger_service = TriggerService()
    return _trigger_service


def reset_trigger_service() -> None:
    """重置 TriggerService（用于测试）"""
    global _trigger_service
    _trigger_service = None
