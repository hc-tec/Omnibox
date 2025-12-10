"""
兼容别名：services.data_artifact → services.artifact

历史测试仍引用旧路径，提供薄封装以复用现有实现。
"""

from services.artifact import (  # noqa: F401
    ArtifactRef,
    ArtifactSource,
    ArtifactStore,
    ArtifactType,
    ViewSpec,
    ViewType,
    batch_create_artifacts,
    create_artifact_from_reference,
    enhance_data_reference,
    get_artifact_store,
    infer_artifact_type,
    reset_artifact_store,
    suggest_views,
    DataArtifact,
)

__all__ = [
    "DataArtifact",
    "ArtifactType",
    "ArtifactSource",
    "ArtifactRef",
    "ViewSpec",
    "ViewType",
    "ArtifactStore",
    "get_artifact_store",
    "reset_artifact_store",
    "suggest_views",
    "create_artifact_from_reference",
    "batch_create_artifacts",
    "enhance_data_reference",
    "infer_artifact_type",
]

