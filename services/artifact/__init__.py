"""
数据产物（DataArtifact）模块

工作流工作台的核心基础设施，负责：
- 数据产物的定义和管理
- 持久化存储（SQLite）
- 可视化推荐
- 导出能力

复用现有组件：
- langgraph_agents.state.EnhancedDataReference - 作为 DataArtifact 的基类
- langgraph_agents.storage.ResearchDataStore - 作为底层数据存储
"""

from .models import (
    DataArtifact,
    ArtifactType,
    ArtifactSource,
    ArtifactRef,
    ViewSpec,
    ViewType,
)
from .store import ArtifactStore, get_artifact_store, reset_artifact_store
from .view_suggester import suggest_views
from .langgraph_integration import (
    create_artifact_from_reference,
    batch_create_artifacts,
    enhance_data_reference,
    infer_artifact_type,
)

__all__ = [
    # 模型
    "DataArtifact",
    "ArtifactType",
    "ArtifactSource",
    "ArtifactRef",
    "ViewSpec",
    "ViewType",
    # 存储
    "ArtifactStore",
    "get_artifact_store",
    "reset_artifact_store",
    # 可视化
    "suggest_views",
    # LangGraph 集成
    "create_artifact_from_reference",
    "batch_create_artifacts",
    "enhance_data_reference",
    "infer_artifact_type",
]
