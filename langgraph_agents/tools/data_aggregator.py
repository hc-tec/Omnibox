from __future__ import annotations

"""aggregate_data 工具实现：对数据进行聚合统计（计数、求和、平均、分组）。

V5.0 Phase 3 (P1) 工具。
V6.0 Phase 2: 支持统一的数据引用格式。
"""

import logging
from typing import Any, Dict, List, Literal, Union
from uuid import uuid4

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool
from .data_ref_resolver import create_resolver_from_context

logger = logging.getLogger(__name__)


def register_data_aggregator_tool(registry: ToolRegistry) -> None:
    """向注册表注册 aggregate_data 工具。"""

    @tool(
        registry,
        plugin_id="aggregate_data",
        description="对数据进行聚合统计（计数、求和、平均、分组）",
        execution_mode="full",  # 需要数据持久化和质量检查
        schema={
            "type": "object",
            "properties": {
                "source_ref": {
                    "type": ["string", "integer"],
                    "description": "数据引用（必填），支持: data_id字符串、步骤编号、步骤引用($step.N)",
                    "examples": ["lg-abc123", "$step.1", 1]
                },
                "group_by": {
                    "type": "array",
                    "description": "分组字段（可选）",
                    "items": {"type": "string"}
                },
                "metrics": {
                    "type": "array",
                    "description": "聚合指标（必填）",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {
                                "type": "string",
                                "description": "聚合字段"
                            },
                            "function": {
                                "type": "string",
                                "enum": ["count", "sum", "avg", "min", "max", "distinct_count"],
                                "description": "聚合函数"
                            },
                            "alias": {
                                "type": "string",
                                "description": "结果别名（可选）"
                            }
                        },
                        "required": ["field", "function"]
                    }
                },
                "filters": {
                    "type": "object",
                    "description": "预过滤条件（可选，同 filter_data 的 conditions）"
                },
                "sort_by": {
                    "type": "string",
                    "description": "排序字段（可选）"
                },
                "order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "排序方向（可选）",
                    "default": "desc"
                },
                "limit": {
                    "type": "number",
                    "description": "返回分组数量（可选）",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 100
                }
            },
            "required": ["source_ref", "metrics"]
        }
    )
    def aggregate_data(
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        """
        对数据进行聚合统计。

        支持功能：
        - group_by 分组
        - 6 种聚合函数：count, sum, avg, min, max, distinct_count
        - 预过滤
        - 排序和限制

        容量限制：
        - 最大输入数据量: 10,000 条
        - 最大分组数: 1,000 组
        """
        # 1. 参数验证
        source_ref = call.args.get("source_ref")
        if not source_ref:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "aggregation",
                    "error_code": "E101"
                },
                status="error",
                error_message="缺少必填参数 source_ref"
            )

        metrics = call.args.get("metrics")
        if not metrics:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "aggregation",
                    "error_code": "E101"
                },
                status="error",
                error_message="缺少必填参数 metrics"
            )

        # 2. 从 data_store 加载数据
        # V6.0 Phase 2: 使用统一的 DataRefResolver
        resolver = create_resolver_from_context(context)
        data_store = context.extras.get("data_store")

        if not data_store:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "aggregation",
                    "error_code": "E303"
                },
                status="error",
                error_message="data_store 不可用"
            )

        try:
            if resolver:
                # 使用解析器解析引用
                resolved = resolver.resolve(source_ref)
                data_package = resolved.data
                logger.debug(
                    "aggregate_data: 解析引用 %s -> data_id=%s",
                    source_ref, resolved.source_data_id
                )
            else:
                # 回退: 直接从 data_store 加载
                data_package = data_store.load(source_ref)
        except ValueError as e:
            # 解析器引发的明确错误
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "aggregation",
                    "error_code": "E301"
                },
                status="error",
                error_message=str(e)
            )
        except Exception as e:
            logger.error(f"aggregate_data: 加载数据失败 - {e}")
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "aggregation",
                    "error_code": "E301"
                },
                status="error",
                error_message=f"数据源 {source_ref} 不存在或无法加载"
            )

        if not data_package:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "aggregation",
                    "error_code": "E301"
                },
                status="error",
                error_message=f"数据源 {source_ref} 为空"
            )

        # 提取数据项（支持多种数据结构）
        items = _extract_items_from_package(data_package)
        if not items:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "aggregation",
                    "groups": [],
                    "total_groups": 0,
                    "total_items": 0,
                    "summary": "数据源为空，无法聚合"
                },
                status="success"
            )

        # 3. 容量检查
        if len(items) > 10000:
            logger.warning(f"aggregate_data: 数据量超过限制 ({len(items)} > 10000)，截断处理")
            items = items[:10000]

        # 4. 预过滤
        filters = call.args.get("filters")
        if filters:
            items = _apply_filters(items, filters)

        if not items:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "aggregation",
                    "groups": [],
                    "total_groups": 0,
                    "total_items": 0,
                    "summary": "过滤后无数据"
                },
                status="success"
            )

        # 5. 聚合计算
        group_by = call.args.get("group_by", [])
        try:
            groups = _compute_aggregation(items, group_by, metrics)
        except Exception as e:
            logger.error(f"aggregate_data: 聚合计算失败 - {e}")
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "aggregation",
                    "error_code": "E402"
                },
                status="error",
                error_message=f"聚合计算失败: {str(e)}"
            )

        # 6. 排序
        sort_by = call.args.get("sort_by")
        order = call.args.get("order", "desc")
        if sort_by:
            groups = _sort_groups(groups, sort_by, order)

        # 7. 限制结果数量
        limit = call.args.get("limit", 100)
        total_groups = len(groups)
        if len(groups) > limit:
            groups = groups[:limit]

        # 8. 生成摘要
        summary = _build_summary(group_by, metrics, total_groups, len(items))

        logger.info(
            f"aggregate_data: 成功 - {len(items)} 条数据，{total_groups} 个分组，返回 {len(groups)} 个"
        )

        return ToolExecutionPayload(
            call=call,
            raw_output={
                "type": "aggregation",
                "groups": groups,
                "total_groups": total_groups,
                "total_items": len(items),
                "summary": summary
            },
            status="success"
        )


def _apply_filters(items: List[Dict], filters: Dict) -> List[Dict]:
    """
    应用预过滤条件。

    支持操作符：$gt, $gte, $lt, $lte, $eq, $ne, $in, $between, $contains, $regex
    """
    import re

    filtered = []

    for item in items:
        matches = True
        for field, condition in filters.items():
            if not isinstance(condition, dict):
                # 简单等值匹配
                if item.get(field) != condition:
                    matches = False
                    break
            else:
                # 操作符匹配
                field_value = item.get(field)

                for op, value in condition.items():
                    try:
                        if op == "$eq":
                            if field_value != value:
                                matches = False
                        elif op == "$ne":
                            if field_value == value:
                                matches = False
                        elif op == "$gt":
                            if field_value is None or not (field_value > value):
                                matches = False
                        elif op == "$gte":
                            if field_value is None or not (field_value >= value):
                                matches = False
                        elif op == "$lt":
                            if field_value is None or not (field_value < value):
                                matches = False
                        elif op == "$lte":
                            if field_value is None or not (field_value <= value):
                                matches = False
                        elif op == "$in":
                            if not isinstance(value, list):
                                matches = False
                            elif field_value not in value:
                                matches = False
                        elif op == "$between":
                            if not isinstance(value, list) or len(value) != 2:
                                matches = False
                            elif field_value is None or not (value[0] <= field_value <= value[1]):
                                matches = False
                        elif op == "$contains":
                            if not isinstance(field_value, str):
                                matches = False
                            elif value.lower() not in field_value.lower():
                                matches = False
                        elif op == "$regex":
                            if not isinstance(field_value, str):
                                matches = False
                            elif not re.search(value, field_value):
                                matches = False
                        else:
                            # 未知操作符，跳过该条件（不报错，保持宽容）
                            logger.warning(f"未知的过滤操作符：{op}，已忽略")
                            continue
                    except (TypeError, ValueError) as e:
                        # 类型不兼容（如字符串和数字比较），该项不匹配
                        logger.debug(f"过滤条件类型不兼容：field={field}, op={op}, value={value}, error={e}")
                        matches = False

                    if not matches:
                        break

        if matches:
            filtered.append(item)

    return filtered


def _compute_aggregation(
    items: List[Dict],
    group_by: List[str],
    metrics: List[Dict]
) -> List[Dict]:
    """计算聚合结果。"""
    if not group_by:
        # 无分组，全局聚合
        return [_aggregate_single_group(items, metrics, {})]

    # 分组聚合
    groups_dict: Dict[tuple, List[Dict]] = {}

    for item in items:
        # 构建分组键
        key_parts = []
        for field in group_by:
            value = item.get(field)
            if value is None:
                value = "__null__"
            key_parts.append(str(value))

        key = tuple(key_parts)
        if key not in groups_dict:
            groups_dict[key] = []
        groups_dict[key].append(item)

    # 对每个分组进行聚合
    results = []
    for key, group_items in groups_dict.items():
        # 构建 group_key 对象
        group_key = {}
        for i, field in enumerate(group_by):
            raw_value = key[i]
            group_key[field] = None if raw_value == "__null__" else raw_value

        result = _aggregate_single_group(group_items, metrics, group_key)
        results.append(result)

    return results


def _aggregate_single_group(
    items: List[Dict],
    metrics: List[Dict],
    group_key: Dict
) -> Dict:
    """对单个分组进行聚合计算。"""
    metric_results = {}

    for metric in metrics:
        field = metric["field"]
        function = metric["function"]
        alias = metric.get("alias", f"{function}_{field}")

        # 提取字段值（保留所有非 None 值）
        all_values = []
        for item in items:
            value = item.get(field)
            if value is not None:
                all_values.append(value)

        # 计算聚合函数
        if function == "count":
            result = len(items)
        elif function == "distinct_count":
            # distinct_count 支持任意类型（可哈希）
            try:
                result = len(set(all_values)) if all_values else 0
            except TypeError:
                # 包含不可哈希类型（如 dict），回退到去重列表长度
                unique = []
                for v in all_values:
                    if v not in unique:
                        unique.append(v)
                result = len(unique)
        elif function in ("sum", "avg", "min", "max"):
            # 数值聚合函数：只保留数值类型
            numeric_values = []
            for value in all_values:
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    numeric_values.append(value)

            if not numeric_values:
                # 无有效数值
                result = 0 if function in ("sum", "avg") else None
            elif function == "sum":
                result = sum(numeric_values)
            elif function == "avg":
                result = sum(numeric_values) / len(numeric_values)
            elif function == "min":
                result = min(numeric_values)
            elif function == "max":
                result = max(numeric_values)
        else:
            # 未知聚合函数
            logger.warning(f"未知的聚合函数：{function}，返回 None")
            result = None

        metric_results[alias] = result

    return {
        "group_key": group_key if group_key else None,
        "metrics": metric_results,
        "item_count": len(items)
    }


def _sort_groups(groups: List[Dict], sort_by: str, order: str) -> List[Dict]:
    """对分组结果排序。"""
    # 检查 sort_by 是在 metrics 还是 group_key 中
    reverse = (order == "desc")

    def sort_key(group):
        # 优先从 metrics 中查找
        if sort_by in group["metrics"]:
            value = group["metrics"][sort_by]
        # 再从 group_key 中查找
        elif group["group_key"] and sort_by in group["group_key"]:
            value = group["group_key"][sort_by]
        else:
            value = None

        # None 值排到最后
        if value is None:
            return (1, 0) if reverse else (0, 0)
        return (0, value)

    try:
        sorted_groups = sorted(groups, key=sort_key, reverse=reverse)
        return sorted_groups
    except Exception as e:
        logger.warning(f"排序失败: {e}，返回原始顺序")
        return groups


def _extract_items_from_package(data_package: Any) -> List[Dict]:
    """
    从数据包中提取数据项列表。

    支持多种数据结构：
    - dict with "items" key: {"items": [...]}
    - dict with "data" key: {"data": [...]}
    - list: [...]
    - DataQueryResult: .datasets[0].items
    """
    # 1. 如果是字典
    if isinstance(data_package, dict):
        # 尝试 "items" 字段
        if "items" in data_package:
            items = data_package["items"]
            if isinstance(items, list):
                return items
        # 尝试 "data" 字段
        if "data" in data_package:
            data = data_package["data"]
            if isinstance(data, list):
                return data
        # 尝试 "results" 字段
        if "results" in data_package:
            results = data_package["results"]
            if isinstance(results, list):
                return results

    # 2. 如果是列表，直接返回
    if isinstance(data_package, list):
        return data_package

    # 3. 如果是 DataQueryResult 对象（有 datasets 属性）
    if hasattr(data_package, "datasets") and data_package.datasets:
        first_dataset = data_package.datasets[0]
        if hasattr(first_dataset, "items"):
            return first_dataset.items

    # 4. 无法提取，返回空列表
    logger.warning(
        f"无法从数据包中提取 items，类型：{type(data_package)}，"
        f"keys: {data_package.keys() if isinstance(data_package, dict) else 'N/A'}"
    )
    return []


def _build_summary(
    group_by: List[str],
    metrics: List[Dict],
    total_groups: int,
    total_items: int
) -> str:
    """生成聚合摘要。"""
    if not group_by:
        metric_desc = ", ".join([
            f"{m.get('alias', m['function'])}({m['field']})"
            for m in metrics
        ])
        return f"对 {total_items} 条数据进行了全局聚合：{metric_desc}"
    else:
        group_fields = ", ".join(group_by)
        metric_desc = ", ".join([
            f"{m['function']}({m['field']})"
            for m in metrics
        ])
        return f"按 {group_fields} 分组，共 {total_groups} 组，{total_items} 条数据，聚合指标：{metric_desc}"
