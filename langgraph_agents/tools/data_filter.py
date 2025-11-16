from __future__ import annotations

"""filter_data 工具实现：过滤和筛选数据。"""

import logging
import random
import re
from typing import Any, Dict, List, Optional

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool

logger = logging.getLogger(__name__)

# 容量限制常量
MAX_ROWS_LIMIT = 10000  # 最大返回行数
SAMPLING_RATE = 0.1  # 自动采样率


def _apply_condition(value: Any, operator: str, target: Any) -> bool:
    """
    应用单个过滤条件。

    Args:
        value: 字段值
        operator: 操作符（$eq, $gt, $contains 等）
        target: 目标值

    Returns:
        是否匹配条件
    """
    try:
        if operator == "$eq":
            return value == target
        elif operator == "$ne":
            return value != target
        elif operator == "$gt":
            return value > target
        elif operator == "$gte":
            return value >= target
        elif operator == "$lt":
            return value < target
        elif operator == "$lte":
            return value <= target
        elif operator == "$contains":
            # 字符串包含（不区分大小写）
            if isinstance(value, str) and isinstance(target, str):
                return target.lower() in value.lower()
            return False
        elif operator == "$regex":
            # 正则匹配（带安全保护）
            if isinstance(value, str) and isinstance(target, str):
                try:
                    # 限制正则复杂度，避免 ReDoS 攻击
                    if len(target) > 200:
                        logger.warning("正则表达式过长，拒绝执行: %d 字符", len(target))
                        return False
                    # 设置超时保护（通过限制匹配字符串长度）
                    if len(value) > 10000:
                        logger.warning("匹配目标过长，拒绝执行: %d 字符", len(value))
                        return False
                    return re.search(target, value, re.IGNORECASE) is not None
                except re.error as e:
                    # 非法正则表达式
                    logger.warning("非法正则表达式: pattern=%s, error=%s", target, e)
                    return False
            return False
        elif operator == "$in":
            # 在列表中
            if isinstance(target, list):
                return value in target
            return False
        elif operator == "$between":
            # 在范围内 [min, max]
            if isinstance(target, list) and len(target) == 2:
                return target[0] <= value <= target[1]
            return False
        else:
            logger.warning("不支持的操作符: %s", operator)
            return False
    except (TypeError, ValueError, AttributeError) as e:
        logger.warning("条件匹配失败: value=%s, operator=%s, target=%s, error=%s",
                      value, operator, target, e)
        return False


def _apply_conditions(item: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
    """
    应用所有过滤条件（AND 逻辑）。

    Args:
        item: 数据项
        conditions: 过滤条件字典

    Returns:
        是否所有条件都匹配
    """
    for field, condition in conditions.items():
        # 获取字段值（支持嵌套字段，如 "author.name"）
        value = item
        for key in field.split("."):
            if isinstance(value, dict):
                value = value.get(key)
            else:
                value = None
                break

        if value is None:
            # 字段不存在，视为不匹配
            return False

        # 如果 condition 是简单值（如 {"view_count": 500000}），默认使用 $eq
        if not isinstance(condition, dict):
            if value != condition:
                return False
            continue

        # 应用所有操作符（AND 逻辑）
        for operator, target in condition.items():
            if not _apply_condition(value, operator, target):
                return False

    return True


def _filter_items(
    source_data: List[Dict[str, Any]],
    conditions: Dict[str, Any],
    limit: int,
    offset: int
) -> tuple[List[Dict[str, Any]], int, bool, Optional[float]]:
    """
    过滤数据项。

    Args:
        source_data: 原始数据
        conditions: 过滤条件
        limit: 返回数量限制
        offset: 分页偏移

    Returns:
        (filtered_items, total_before_filter, sampled, sampling_rate) 元组
    """
    # 1. 应用过滤条件
    if conditions:
        filtered = [item for item in source_data if _apply_conditions(item, conditions)]
    else:
        filtered = source_data

    total = len(filtered)

    # 2. 检查容量限制
    sampled = False
    sampling_rate = None

    if total > MAX_ROWS_LIMIT:
        # 超过限制，自动采样
        logger.warning(
            "filter_data: 过滤结果 %d 行超过限制 %d，自动采样",
            total,
            MAX_ROWS_LIMIT
        )
        sampled = True
        sampling_rate = SAMPLING_RATE

        # 随机采样
        sample_size = int(total * sampling_rate)
        sample_size = max(sample_size, 1000)  # 至少采样 1000 条
        sample_size = min(sample_size, MAX_ROWS_LIMIT)  # 不超过限制

        filtered = random.sample(filtered, sample_size)

    # 3. 应用分页
    start_idx = offset
    end_idx = start_idx + limit

    paginated = filtered[start_idx:end_idx]

    return paginated, total, sampled, sampling_rate


def register_data_filter_tool(registry: ToolRegistry) -> None:
    """向注册表注册 filter_data 工具。"""

    @tool(
        registry,
        plugin_id="filter_data",
        description="根据条件过滤数据，支持 10 种操作符和分页",
        schema={
            "type": "object",
            "properties": {
                "source_ref": {
                    "type": "string",
                    "description": "数据引用 ID（data_id，必填）",
                    "examples": ["lg-abc123", "lg-def456"]
                },
                "conditions": {
                    "type": "object",
                    "description": "过滤条件（必填）",
                    "examples": [
                        {"view_count": {"$gt": 500000}},
                        {"title": {"$contains": "AI Agent"}},
                        {"published_date": {"$between": ["2024-01-01", "2024-12-31"]}}
                    ]
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量限制（可选，默认 1000）",
                    "minimum": 1,
                    "maximum": 10000,
                    "default": 1000
                },
                "offset": {
                    "type": "integer",
                    "description": "分页偏移（可选，默认 0）",
                    "minimum": 0,
                    "default": 0
                }
            },
            "required": ["source_ref", "conditions"]
        }
    )
    def filter_data(
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        """
        根据条件过滤数据。

        支持的操作符：
        - $eq, $ne: 等于/不等于
        - $gt, $gte, $lt, $lte: 大于/大于等于/小于/小于等于
        - $contains: 包含（字符串，不区分大小写）
        - $regex: 正则匹配
        - $in: 在列表中
        - $between: 在范围内 [min, max]
        """
        # 1. 参数验证
        source_ref = call.args.get("source_ref")
        if not source_ref:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_filter",
                    "error_code": "E101"
                },
                status="error",
                error_message="缺少必填参数 source_ref"
            )

        conditions = call.args.get("conditions")
        if conditions is None:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_filter",
                    "error_code": "E101"
                },
                status="error",
                error_message="缺少必填参数 conditions"
            )

        if not isinstance(conditions, dict):
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_filter",
                    "error_code": "E102"
                },
                status="error",
                error_message="参数 conditions 必须是对象类型"
            )

        limit = call.args.get("limit", 1000)
        offset = call.args.get("offset", 0)

        # 验证 limit 和 offset
        if not isinstance(limit, int) or limit < 1 or limit > 10000:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_filter",
                    "error_code": "E102"
                },
                status="error",
                error_message="参数 limit 必须是 1-10000 之间的整数"
            )

        if not isinstance(offset, int) or offset < 0:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_filter",
                    "error_code": "E102"
                },
                status="error",
                error_message="参数 offset 必须是非负整数"
            )

        # 2. 检查依赖
        data_store = context.extras.get("data_store")
        if data_store is None:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_filter",
                    "error_code": "E501"
                },
                status="error",
                error_message="data_store 不可用，请确保已在 context.extras 中注入"
            )

        try:
            # 3. 从 data_store 加载数据

            source_data = data_store.load(source_ref)

            if source_data is None:
                # 无效的数据引用
                return ToolExecutionPayload(
                    call=call,
                    raw_output={
                        "type": "data_filter",
                        "error_code": "E105"
                    },
                    status="error",
                    error_message=f"无效的数据引用: {source_ref}"
                )

            # 4. 确保 source_data 是列表格式
            if isinstance(source_data, dict):
                # 如果是 DataQueryResult 对象，提取 items
                items = source_data.get("items", [])
            elif isinstance(source_data, list):
                items = source_data
            else:
                logger.error("filter_data: 不支持的数据格式 - %s", type(source_data))
                return ToolExecutionPayload(
                    call=call,
                    raw_output={
                        "type": "data_filter",
                        "error_code": "E303"
                    },
                    status="error",
                    error_message=f"数据格式异常: {type(source_data)}"
                )

            logger.info(
                "filter_data: 加载 %d 条记录, 条件=%s, limit=%d, offset=%d",
                len(items),
                conditions,
                limit,
                offset
            )

            # 5. 应用过滤
            filtered_items, total, sampled, sampling_rate = _filter_items(
                items,
                conditions,
                limit,
                offset
            )

            # 6. 构造返回结果
            result = {
                "type": "data_filter",
                "items": filtered_items,
                "total_before_filter": len(items),
                "total_after_filter": total,
                "returned": len(filtered_items),
                "offset": offset,
                "limit": limit
            }

            warning_message = None
            if sampled:
                result["sampled"] = True
                result["sampling_rate"] = sampling_rate
                warning_message = f"数据量过大（{total} 行），已采样至 {len(filtered_items)} 行"

            logger.info(
                "filter_data: 返回 %d 条记录 (过滤后 %d 条，原始 %d 条)",
                len(filtered_items),
                total,
                len(items)
            )

            return ToolExecutionPayload(
                call=call,
                raw_output=result,
                status="success",
                warning=warning_message
            )

        except Exception as e:
            # 其他异常
            logger.exception("filter_data: 执行失败 - %s", e)
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_filter",
                    "error_code": "E505"
                },
                status="error",
                error_message=f"未预期的异常: {e}"
            )
