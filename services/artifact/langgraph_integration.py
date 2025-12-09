"""
DataArtifact 与 LangGraph 的集成

提供辅助函数，用于：
1. 从 EnhancedDataReference 创建 DataArtifact
2. 自动推荐可视化
3. 可选的持久化

设计原则：
- 不修改现有 DataStasher 逻辑
- 作为可选的扩展点，在需要时调用
"""

import logging
from typing import Optional, List

from langgraph_agents.state import DataReference, EnhancedDataReference
from langgraph_agents.metadata_extractor import (
    extract_schema_info,
    extract_statistics,
    extract_sample_items,
    calculate_quality_score,
)

from .models import DataArtifact, ArtifactType, ViewSpec
from .store import ArtifactStore, get_artifact_store
from .view_suggester import suggest_views

logger = logging.getLogger(__name__)


def enhance_data_reference(
    ref: DataReference,
    raw_data: Optional[dict] = None,
) -> EnhancedDataReference:
    """
    将 DataReference 增强为 EnhancedDataReference

    Args:
        ref: 基础数据引用
        raw_data: 原始数据（用于提取元数据）

    Returns:
        增强的数据引用
    """
    # 提取元数据
    schema_info = None
    statistics = None
    sample_items = None
    quality_score = None

    if raw_data:
        schema_info = extract_schema_info(raw_data)
        statistics = extract_statistics(raw_data)
        sample_items = extract_sample_items(raw_data)
        if schema_info and statistics:
            quality_score = calculate_quality_score(schema_info, statistics)

    return EnhancedDataReference(
        step_id=ref.step_id,
        tool_name=ref.tool_name,
        data_id=ref.data_id,
        summary=ref.summary,
        status=ref.status,
        error_message=ref.error_message,
        schema_info=schema_info,
        statistics=statistics,
        sample_items=sample_items,
        quality_score=quality_score,
    )


def create_artifact_from_reference(
    ref: DataReference,
    workflow_id: Optional[str] = None,
    raw_data: Optional[dict] = None,
    persist: bool = True,
    store: Optional[ArtifactStore] = None,
) -> DataArtifact:
    """
    从 DataReference 创建 DataArtifact

    这是主要的集成入口，用于将 LangGraph 的数据引用转换为数据产物。

    Args:
        ref: 数据引用（可以是 DataReference 或 EnhancedDataReference）
        workflow_id: 工作流 ID（如果提供，会关联到工作流）
        raw_data: 原始数据（用于提取元数据和推荐可视化）
        persist: 是否持久化到数据库
        store: 自定义存储（默认使用全局单例）

    Returns:
        创建的 DataArtifact
    """
    # 如果是基础 DataReference，先增强
    if isinstance(ref, EnhancedDataReference):
        enhanced_ref = ref
    else:
        enhanced_ref = enhance_data_reference(ref, raw_data)

    # 推荐可视化
    suggested_views: List[ViewSpec] = []
    if enhanced_ref.schema_info:
        suggested_views = suggest_views(
            schema_info=enhanced_ref.schema_info,
            statistics=enhanced_ref.statistics,
            sample_items=enhanced_ref.sample_items,
        )

    # 创建 DataArtifact
    artifact = DataArtifact.from_enhanced_reference(
        ref=enhanced_ref,
        workflow_id=workflow_id,
        suggested_views=suggested_views,
    )

    # 可选持久化
    if persist:
        artifact_store = store or get_artifact_store()
        artifact_store.save_artifact(artifact)
        logger.info(
            f"已创建并持久化产物: artifact_id={artifact.artifact_id}, "
            f"workflow_id={workflow_id}, tool={artifact.tool_name}"
        )

    return artifact


def batch_create_artifacts(
    refs: List[DataReference],
    workflow_id: Optional[str] = None,
    raw_data_map: Optional[dict] = None,
    persist: bool = True,
    store: Optional[ArtifactStore] = None,
) -> List[DataArtifact]:
    """
    批量创建 DataArtifact

    Args:
        refs: 数据引用列表
        workflow_id: 工作流 ID
        raw_data_map: 原始数据映射 {data_id: raw_data}
        persist: 是否持久化
        store: 自定义存储

    Returns:
        创建的 DataArtifact 列表
    """
    artifacts = []
    raw_data_map = raw_data_map or {}

    for ref in refs:
        raw_data = raw_data_map.get(ref.data_id) if ref.data_id else None
        artifact = create_artifact_from_reference(
            ref=ref,
            workflow_id=workflow_id,
            raw_data=raw_data,
            persist=persist,
            store=store,
        )
        artifacts.append(artifact)

    return artifacts


def infer_artifact_type(tool_name: str) -> ArtifactType:
    """
    根据工具名推断产物类型

    Args:
        tool_name: 工具名称

    Returns:
        推断的产物类型
    """
    return DataArtifact._infer_artifact_type(tool_name)
