"""
Chat 服务数据集工具模块

提供数据集相关的转换、聚合、预览等功能。
"""

from typing import Dict, Any, List, Tuple, Optional
import logging

from services.data_query_service import DataQueryResult, QueryDataset

logger = logging.getLogger(__name__)


def dataset_from_result(query_result: DataQueryResult) -> QueryDataset:
    """
    从 DataQueryResult 构造 QueryDataset。

    Args:
        query_result: 数据查询结果

    Returns:
        QueryDataset 对象
    """
    return QueryDataset(
        route_id=None,
        provider=None,
        name=query_result.feed_title,
        generated_path=query_result.generated_path,
        items=query_result.items,
        feed_title=query_result.feed_title,
        source=query_result.source,
        cache_hit=query_result.cache_hit,
        reasoning=query_result.reasoning,
        payload=query_result.payload,
    )


def dataset_records(dataset: QueryDataset) -> List[Dict[str, Any]]:
    """
    从数据集中提取记录列表。

    Args:
        dataset: 数据集对象

    Returns:
        记录列表
    """
    if dataset.payload and isinstance(dataset.payload, dict):
        return [dataset.payload]
    return dataset.items or []


def infer_dataset_item_count(dataset: QueryDataset) -> int:
    """
    推断数据集中的记录数量。

    Args:
        dataset: 数据集对象

    Returns:
        记录数量
    """
    records = dataset_records(dataset)
    return len(records)


def build_dataset_preview(datasets: List[QueryDataset], max_items: int = 20) -> Tuple[str, int]:
    """
    构建数据集预览文本，在多个数据集间均匀分配采样数量。

    Args:
        datasets: 数据集列表
        max_items: 最大采样数量

    Returns:
        (预览文本, 实际采样数量)
    """
    if not datasets:
        return "", 0

    lines: List[str] = []
    count = 0

    # 计算每个数据集的采样数量（均匀分配）
    items_per_dataset = max(1, max_items // len(datasets))

    for dataset in datasets:
        header = dataset.feed_title or dataset.generated_path or "数据集"
        lines.append(f"[{header}]")
        records = dataset_records(dataset)

        # 限制当前数据集的采样数量
        dataset_count = 0
        for record in records:
            if count >= max_items:
                break
            if dataset_count >= items_per_dataset:
                break

            title = record.get("title") or record.get("name") or record.get("keyword") or "未命名"
            desc = record.get("description") or record.get("summary") or ""
            lines.append(f"- {title}: {desc[:120]}")
            count += 1
            dataset_count += 1

    return "\n".join(lines), count


def summarize_datasets(datasets: List[QueryDataset], query_result: DataQueryResult) -> List[Dict[str, Any]]:
    """
    生成数据集摘要列表。

    Args:
        datasets: 数据集列表
        query_result: 查询结果（用于 fallback）

    Returns:
        数据集摘要列表
    """
    summary: List[Dict[str, Any]] = []
    records = datasets or [dataset_from_result(query_result)]
    for dataset in records:
        summary.append(
            {
                "route": dataset.generated_path,
                "feed_title": dataset.feed_title,
                "source": dataset.source,
                "item_count": len(dataset.items or []),
            }
        )
    return summary


def format_success_message(
    datasets: List[QueryDataset],
    fallback_feed: Optional[str],
    fallback_source: Optional[str],
) -> str:
    """
    格式化成功消息。

    Args:
        datasets: 数据集列表
        fallback_feed: 备用 feed 名称
        fallback_source: 备用数据源

    Returns:
        格式化的成功消息
    """
    from .utils import format_source_hint

    if not datasets:
        if fallback_feed:
            return f"已获取 {fallback_feed} 的数据卡片"
        return "已获取数据卡片"

    if len(datasets) == 1:
        dataset = datasets[0]
        feed = dataset.feed_title or dataset.name or fallback_feed or "数据"
        source_hint = format_source_hint(dataset.source or fallback_source)
        return f"已获取 {feed}（{len(dataset.items or [])} 条{source_hint}）"

    parts = []
    for dataset in datasets:
        feed = dataset.feed_title or dataset.name or "数据"
        source_hint = format_source_hint(dataset.source)
        parts.append(f"{feed}（{len(dataset.items or [])} 条{source_hint}）")
    return f"已获取 {len(datasets)} 组数据：" + "；".join(parts)


def build_analysis_prompt(analysis_query: str, dataset_summary: str) -> str:
    """
    构建分析查询的 LLM prompt。

    Args:
        analysis_query: 分析查询文本
        dataset_summary: 数据集摘要文本

    Returns:
        LLM prompt 文本
    """
    return (
        f"用户需要回答的问题是：{analysis_query}\n"
        "以下是最近抓取到的数据，请基于这些数据总结内容趋势、主题或方向。"
        "务必引用数据中的具体现象，输出要点式总结。\n"
        f"{dataset_summary}\n"
        "请给出不超过4条的分析结论。"
    )


# 为了保持向后兼容，导出一个带下划线的别名
_dataset_from_result = dataset_from_result
_dataset_records = dataset_records
_infer_dataset_item_count = infer_dataset_item_count
_build_dataset_preview = build_dataset_preview
_summarize_datasets = summarize_datasets
_format_success_message = format_success_message
_build_analysis_prompt = build_analysis_prompt
