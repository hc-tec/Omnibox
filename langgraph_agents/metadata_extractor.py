"""
MetadataExtractor - 数据元数据提取器（V5.0 Phase 5）。

从工具执行结果中提取结构化元数据。
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def extract_schema_info(data: Any) -> Optional[Dict[str, str]]:
    """
    提取数据 Schema 信息。

    Args:
        data: 原始数据

    Returns:
        Schema 信息字典：{field_name: field_type}，失败返回 None
    """
    try:
        # 处理字典类型
        if isinstance(data, dict):
            if "items" in data and isinstance(data["items"], list) and data["items"]:
                # 从第一条记录推断 schema
                first_item = data["items"][0]
                if isinstance(first_item, dict):
                    return {key: type(value).__name__ for key, value in first_item.items()}

            elif "data" in data and isinstance(data["data"], list) and data["data"]:
                first_item = data["data"][0]
                if isinstance(first_item, dict):
                    return {key: type(value).__name__ for key, value in first_item.items()}

        # 处理列表类型
        elif isinstance(data, list) and data:
            first_item = data[0]
            if isinstance(first_item, dict):
                return {key: type(value).__name__ for key, value in first_item.items()}

        return None

    except Exception as e:
        logger.warning(f"Schema 提取失败: {e}")
        return None


def extract_statistics(data: Any) -> Optional[Dict[str, Any]]:
    """
    提取数据统计信息。

    Args:
        data: 原始数据

    Returns:
        统计信息字典，失败返回 None
    """
    try:
        stats = {}

        # 提取记录数
        if isinstance(data, dict):
            if "items" in data and isinstance(data["items"], list):
                stats["record_count"] = len(data["items"])
                items = data["items"]
            elif "data" in data and isinstance(data["data"], list):
                stats["record_count"] = len(data["data"])
                items = data["data"]
            else:
                return None
        elif isinstance(data, list):
            stats["record_count"] = len(data)
            items = data
        else:
            return None

        # 提取字段统计
        if items and isinstance(items[0], dict):
            field_stats = {}
            first_item = items[0]

            for key in first_item.keys():
                # 统计非空值数量
                non_null_count = sum(1 for item in items if item.get(key) is not None)
                field_stats[key] = {
                    "non_null_count": non_null_count,
                    "null_count": len(items) - non_null_count,
                    "completeness": non_null_count / len(items) if items else 0
                }

            stats["field_stats"] = field_stats

        return stats

    except Exception as e:
        logger.warning(f"统计信息提取失败: {e}")
        return None


def extract_sample_items(data: Any, sample_size: int = 3) -> Optional[List[Dict]]:
    """
    提取样本数据。

    Args:
        data: 原始数据
        sample_size: 样本大小

    Returns:
        样本数据列表，失败返回 None
    """
    try:
        # 提取 items
        if isinstance(data, dict):
            if "items" in data and isinstance(data["items"], list):
                items = data["items"]
            elif "data" in data and isinstance(data["data"], list):
                items = data["data"]
            else:
                return None
        elif isinstance(data, list):
            items = data
        else:
            return None

        # 返回前 N 条记录
        if items:
            return items[:sample_size]

        return None

    except Exception as e:
        logger.warning(f"样本数据提取失败: {e}")
        return None


def calculate_quality_score(
    schema_info: Optional[Dict[str, str]],
    statistics: Optional[Dict[str, Any]]
) -> float:
    """
    计算数据质量评分。

    基于以下维度：
    - 完整性：字段非空率
    - 一致性：Schema 完整性

    Args:
        schema_info: Schema 信息
        statistics: 统计信息

    Returns:
        质量评分 (0-1)
    """
    scores = []

    # 维度 1：Schema 完整性（有 schema 信息为 1，无为 0.5）
    if schema_info:
        scores.append(1.0)
    else:
        scores.append(0.5)

    # 维度 2：字段完整性（平均非空率）
    if statistics and "field_stats" in statistics:
        field_stats = statistics["field_stats"]
        completeness_values = [
            stats["completeness"]
            for stats in field_stats.values()
        ]
        if completeness_values:
            avg_completeness = sum(completeness_values) / len(completeness_values)
            scores.append(avg_completeness)

    # 计算平均分
    if scores:
        return sum(scores) / len(scores)
    else:
        return 0.5  # 默认中等质量
