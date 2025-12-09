"""
可视化推荐器

根据数据特征自动推荐合适的可视化方式。

复用现有组件：
- langgraph_agents.metadata_extractor 的输出（schema_info, statistics, sample_items）
"""

from typing import List, Dict, Any, Optional
from .models import ViewSpec, ViewType


def suggest_views(
    schema_info: Optional[Dict[str, str]] = None,
    statistics: Optional[Dict[str, Any]] = None,
    sample_items: Optional[List[Dict]] = None,
) -> List[ViewSpec]:
    """
    根据数据特征自动推荐合适的可视化方式

    Args:
        schema_info: 数据 Schema 信息，格式为 {field_name: field_type}
        statistics: 数据统计信息，包含 record_count 等
        sample_items: 样本数据（前几条记录）

    Returns:
        推荐的可视化规格列表（按优先级排序）

    推荐规则：
    1. 有日期 + 有数值 → 折线图（时序分析）
    2. 有分类 + 有数值 → 柱状图（分布统计）
    3. 少量数值项 → 饼图（占比分析）
    4. 有 title/name 字段 → 列表（内容展示）
    5. 多行数据 → 表格（详情查看）
    6. 兜底 → 文本
    """
    suggestions = []

    # 无法推断时返回默认文本视图
    if not schema_info:
        return [ViewSpec(view_type=ViewType.TEXT, title="数据预览")]

    # 分析字段类型
    numeric_fields = _get_fields_by_type(schema_info, ("int", "float", "number", "integer"))
    date_fields = _get_fields_by_type(schema_info, ("date", "datetime", "timestamp", "time"))
    text_fields = _get_fields_by_type(schema_info, ("str", "string", "text"))

    # 获取记录数
    record_count = _get_record_count(statistics, sample_items)

    # 识别特殊字段
    title_field = _find_title_field(schema_info)
    category_fields = _get_category_fields(schema_info, text_fields)

    # ========== 规则1: 时序数据 → 折线图 ==========
    if date_fields and numeric_fields:
        suggestions.append(ViewSpec(
            view_type=ViewType.LINE_CHART,
            title="趋势分析",
            config={
                "x_field": date_fields[0],
                "y_field": numeric_fields[0],
                "sort_by": date_fields[0],
            },
        ))

    # ========== 规则2: 分类 + 数值 → 柱状图 ==========
    if category_fields and numeric_fields:
        suggestions.append(ViewSpec(
            view_type=ViewType.BAR_CHART,
            title="分布统计",
            config={
                "x_field": category_fields[0],
                "y_field": numeric_fields[0],
                "sort_by": numeric_fields[0],
                "sort_order": "desc",
            },
        ))

    # ========== 规则3: 少量数值项 → 饼图 ==========
    if numeric_fields and record_count and 2 <= record_count <= 10:
        # 需要有分类字段来作为标签
        label_field = category_fields[0] if category_fields else title_field
        if label_field:
            suggestions.append(ViewSpec(
                view_type=ViewType.PIE_CHART,
                title="占比分析",
                config={
                    "label_field": label_field,
                    "value_field": numeric_fields[0],
                },
            ))

    # ========== 规则4: 有标题字段 → 列表 ==========
    if title_field:
        list_config = {"title_field": title_field}
        # 尝试找描述字段
        desc_field = _find_description_field(schema_info)
        if desc_field:
            list_config["description_field"] = desc_field
        # 尝试找链接字段
        link_field = _find_link_field(schema_info)
        if link_field:
            list_config["link_field"] = link_field

        suggestions.append(ViewSpec(
            view_type=ViewType.LIST,
            title="数据列表",
            config=list_config,
        ))

    # ========== 规则5: 多行数据 → 表格 ==========
    if record_count and record_count > 1:
        # 限制表格列数，优先显示重要字段
        columns = _select_table_columns(schema_info, title_field, numeric_fields, date_fields)
        suggestions.append(ViewSpec(
            view_type=ViewType.TABLE,
            title="数据详情",
            config={
                "columns": columns[:10],  # 最多 10 列
                "page_size": 20,
            },
        ))

    # ========== 规则6: 卡片视图（单条数据）==========
    if record_count == 1:
        suggestions.append(ViewSpec(
            view_type=ViewType.CARD,
            title="数据卡片",
            config={
                "title_field": title_field,
                "fields": list(schema_info.keys())[:8],
            },
        ))

    # ========== 兜底: 文本视图 ==========
    if not suggestions:
        suggestions.append(ViewSpec(
            view_type=ViewType.TEXT,
            title="数据预览",
        ))

    return suggestions


def _get_fields_by_type(schema_info: Dict[str, str], types: tuple) -> List[str]:
    """获取指定类型的字段列表"""
    return [k for k, v in schema_info.items() if v.lower() in types]


def _get_record_count(
    statistics: Optional[Dict[str, Any]],
    sample_items: Optional[List[Dict]],
) -> Optional[int]:
    """获取记录数"""
    if statistics and "record_count" in statistics:
        return statistics["record_count"]
    if sample_items:
        return len(sample_items)
    return None


def _find_title_field(schema_info: Dict[str, str]) -> Optional[str]:
    """查找标题字段"""
    title_candidates = ("title", "name", "label", "headline", "subject")
    for candidate in title_candidates:
        if candidate in schema_info:
            return candidate
        # 模糊匹配
        for field in schema_info:
            if candidate in field.lower():
                return field
    return None


def _find_description_field(schema_info: Dict[str, str]) -> Optional[str]:
    """查找描述字段"""
    desc_candidates = ("description", "desc", "content", "summary", "body", "text")
    for candidate in desc_candidates:
        if candidate in schema_info:
            return candidate
        for field in schema_info:
            if candidate in field.lower():
                return field
    return None


def _find_link_field(schema_info: Dict[str, str]) -> Optional[str]:
    """查找链接字段"""
    link_candidates = ("link", "url", "href", "uri")
    for candidate in link_candidates:
        if candidate in schema_info:
            return candidate
        for field in schema_info:
            if candidate in field.lower():
                return field
    return None


def _get_category_fields(
    schema_info: Dict[str, str],
    text_fields: List[str],
) -> List[str]:
    """获取分类字段（排除标题、描述、链接等长文本字段）"""
    exclude_keywords = ("id", "url", "link", "href", "content", "body", "description", "desc", "text")
    return [
        f for f in text_fields
        if not any(kw in f.lower() for kw in exclude_keywords)
    ]


def _select_table_columns(
    schema_info: Dict[str, str],
    title_field: Optional[str],
    numeric_fields: List[str],
    date_fields: List[str],
) -> List[str]:
    """为表格选择合适的列（优先级排序）"""
    columns = []

    # 1. 标题字段优先
    if title_field and title_field not in columns:
        columns.append(title_field)

    # 2. 日期字段
    for f in date_fields:
        if f not in columns:
            columns.append(f)

    # 3. 数值字段
    for f in numeric_fields:
        if f not in columns:
            columns.append(f)

    # 4. 其他字段（排除 ID 和长文本）
    exclude_keywords = ("id", "content", "body", "description", "text", "raw")
    for f in schema_info:
        if f not in columns and not any(kw in f.lower() for kw in exclude_keywords):
            columns.append(f)

    return columns
