"""
GraphHelper - 知识图谱辅助函数（V5.0 Phase 5）。

为 Reflector 和其他 Agent 提供知识图谱查询功能。
"""

import logging
from typing import List, Optional, Dict, Any

from .knowledge_graph import KnowledgeGraph, GraphNode, NodeType
from .state import GraphState, DataReference

logger = logging.getLogger(__name__)


def get_data_lineage_summary(
    state: GraphState,
    step_id: int
) -> str:
    """
    获取数据血缘摘要（用于 Reflector 决策）。

    Args:
        state: 当前状态
        step_id: 步骤 ID

    Returns:
        血缘摘要文本
    """
    knowledge_graph = state.get("knowledge_graph")
    if not knowledge_graph:
        return "无知识图谱信息"

    node_id = f"dataset-{step_id}"
    ancestors = knowledge_graph.trace_lineage(node_id)

    if not ancestors:
        return "原始数据（无上游依赖）"

    # 构建血缘链
    lineage_chain = []
    for ancestor in ancestors:
        lineage_chain.append(f"步骤{ancestor.step_id}")

    return f"数据血缘: {' -> '.join(lineage_chain)} -> 步骤{step_id}"


def get_related_datasets_summary(
    state: GraphState,
    step_id: int
) -> str:
    """
    获取相关数据集摘要。

    Args:
        state: 当前状态
        step_id: 步骤 ID

    Returns:
        相关数据集摘要文本
    """
    knowledge_graph = state.get("knowledge_graph")
    if not knowledge_graph:
        return "无知识图谱信息"

    node_id = f"dataset-{step_id}"
    related = knowledge_graph.find_related_datasets(node_id)

    if not related:
        return "无相关数据集"

    # 构建摘要
    related_summaries = []
    for node in related[:3]:  # 只显示前 3 个
        related_summaries.append(f"步骤{node.step_id}")

    return f"相关数据集: {', '.join(related_summaries)}"


def get_graph_statistics_summary(state: GraphState) -> str:
    """
    获取知识图谱统计信息摘要。

    Args:
        state: 当前状态

    Returns:
        统计信息摘要文本
    """
    knowledge_graph = state.get("knowledge_graph")
    if not knowledge_graph:
        return "无知识图谱信息"

    stats = knowledge_graph.get_statistics()

    return (
        f"知识图谱: {stats['total_nodes']} 个节点, "
        f"{stats['total_edges']} 条边"
    )


def has_sufficient_data_coverage(
    state: GraphState,
    min_datasets: int = 2
) -> bool:
    """
    检查是否有足够的数据覆盖（用于 Reflector 决策）。

    Args:
        state: 当前状态
        min_datasets: 最小数据集数量

    Returns:
        是否有足够的数据覆盖
    """
    data_stash = state.get("data_stash", [])

    # 统计成功的数据集数量
    successful_datasets = sum(
        1 for ref in data_stash
        if ref.status == "success" and ref.data_id
    )

    return successful_datasets >= min_datasets


def get_quality_summary(state: GraphState) -> str:
    """
    获取数据质量摘要。

    Args:
        state: 当前状态

    Returns:
        质量摘要文本
    """
    from .state import EnhancedDataReference

    data_stash = state.get("data_stash", [])

    # 统计质量分数
    quality_scores = []
    for ref in data_stash:
        if isinstance(ref, EnhancedDataReference) and ref.quality_score:
            quality_scores.append(ref.quality_score)

    if not quality_scores:
        return "无质量评分数据"

    avg_quality = sum(quality_scores) / len(quality_scores)
    return f"平均数据质量: {avg_quality:.2f} ({len(quality_scores)} 个数据集)"


def should_continue_research(state: GraphState) -> bool:
    """
    判断是否应该继续研究（基于知识图谱和数据质量）。

    这是一个简化的决策函数，可以被 Reflector 使用。

    Args:
        state: 当前状态

    Returns:
        是否应该继续研究
    """
    # 规则 1：如果有严重错误，应该停止
    last_error = state.get("last_error")
    if last_error:
        logger.info("检测到错误，建议停止: %s", last_error)
        return False

    # 规则 2：如果数据覆盖不足，应该继续
    if not has_sufficient_data_coverage(state, min_datasets=1):
        logger.info("数据覆盖不足，建议继续")
        return True

    # 规则 3：如果已经有足够的数据，可以停止
    data_stash = state.get("data_stash", [])
    successful_count = sum(1 for ref in data_stash if ref.status == "success")

    if successful_count >= 3:  # 简化规则：3 个成功的数据集
        logger.info("已有足够数据 (%d 个数据集)，建议停止", successful_count)
        return False

    # 默认：继续
    return True
