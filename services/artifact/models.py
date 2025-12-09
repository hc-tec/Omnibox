"""
数据产物（DataArtifact）模型定义

设计原则：
1. 继承 EnhancedDataReference，保持与 LangGraph 的兼容性
2. 扩展来源追溯、可视化建议、引用关系等能力
3. 支持 SQLite 持久化（通过 ArtifactRecord 表）
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from langgraph_agents.state import EnhancedDataReference


class ArtifactType(str, Enum):
    """数据产物类型"""
    DATASET = "dataset"       # 原始数据集（来自 fetch_public_data 等）
    ANALYSIS = "analysis"     # 分析结果（来自 data_operator）
    INSIGHT = "insight"       # 洞察/见解（来自 synthesizer）
    DOCUMENT = "document"     # 文档/报告


class ViewType(str, Enum):
    """可视化类型"""
    TABLE = "table"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    LIST = "list"
    CARD = "card"
    TEXT = "text"


class ViewSpec(BaseModel):
    """可视化规格"""
    view_type: ViewType
    title: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    # 例如: {"x_field": "date", "y_field": "value", "group_by": "category"}


class ArtifactSource(BaseModel):
    """数据产物来源追溯"""
    workflow_id: Optional[str] = None   # 所属工作流 ID
    step_id: int                        # 步骤编号
    tool_name: str                      # 生成工具
    created_at: datetime = Field(default_factory=datetime.now)


class ArtifactRef(BaseModel):
    """数据产物引用"""
    artifact_id: str
    relation_type: str = "derived_from"  # derived_from / compared_with / generated


class DataArtifact(EnhancedDataReference):
    """
    数据产物 - 工作流工作台的核心数据单元

    继承自 EnhancedDataReference，扩展以下能力：
    - 产物类型分类
    - 完整来源追溯
    - 可视化建议
    - 引用关系追踪

    设计决策：
    - 继承而非组合，保持与 LangGraph data_stash 的兼容性
    - workflow_id 由后端生成（UUID），更可控
    - 产物名称自动生成，基于工具名 + 时间戳
    """

    # 产物唯一标识（区别于 data_id，data_id 是底层存储的 key）
    artifact_id: str = Field(default_factory=lambda: f"artifact-{uuid.uuid4().hex[:12]}")

    # 产物分类
    artifact_type: ArtifactType = ArtifactType.DATASET

    # 产物命名（自动生成）
    name: str = ""
    description: str = ""

    # 来源追溯（扩展 step_id + tool_name）
    source: Optional[ArtifactSource] = None

    # 可视化建议
    suggested_views: List[ViewSpec] = Field(default_factory=list)

    # 引用关系
    derived_from: List[ArtifactRef] = Field(default_factory=list)
    used_by: List[ArtifactRef] = Field(default_factory=list)

    # 标签（便于检索）
    tags: List[str] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        # 自动生成名称
        if not self.name:
            timestamp = datetime.now().strftime("%m%d_%H%M")
            self.name = f"{self.tool_name}_{timestamp}"
        # 自动设置 source
        if not self.source:
            self.source = ArtifactSource(
                step_id=self.step_id,
                tool_name=self.tool_name,
            )

    @classmethod
    def from_enhanced_reference(
        cls,
        ref: EnhancedDataReference,
        workflow_id: Optional[str] = None,
        artifact_type: Optional[ArtifactType] = None,
        name: Optional[str] = None,
        suggested_views: Optional[List[ViewSpec]] = None,
    ) -> "DataArtifact":
        """
        从现有 EnhancedDataReference 创建 DataArtifact

        这是主要的创建方式，确保与现有 LangGraph 工作流的兼容性
        """
        # 推断产物类型
        if artifact_type is None:
            artifact_type = cls._infer_artifact_type(ref.tool_name)

        return cls(
            # 继承所有父类字段
            step_id=ref.step_id,
            tool_name=ref.tool_name,
            data_id=ref.data_id,
            summary=ref.summary,
            status=ref.status,
            error_message=ref.error_message,
            schema_info=ref.schema_info,
            statistics=ref.statistics,
            sample_items=ref.sample_items,
            quality_score=ref.quality_score,
            # 新增字段
            artifact_type=artifact_type,
            name=name or "",  # 空字符串会触发自动生成
            source=ArtifactSource(
                workflow_id=workflow_id,
                step_id=ref.step_id,
                tool_name=ref.tool_name,
            ),
            suggested_views=suggested_views or [],
        )

    @staticmethod
    def _infer_artifact_type(tool_name: str) -> ArtifactType:
        """根据工具名推断产物类型"""
        if tool_name in ("fetch_public_data", "fetch_private_data", "search_data_sources"):
            return ArtifactType.DATASET
        elif tool_name in ("data_operator", "data_filter", "data_aggregation", "data_comparison"):
            return ArtifactType.ANALYSIS
        elif tool_name in ("synthesizer", "generate_insight"):
            return ArtifactType.INSIGHT
        else:
            return ArtifactType.DATASET

    @staticmethod
    def generate_workflow_id() -> str:
        """生成工作流 ID（后端统一生成）"""
        return f"wf-{uuid.uuid4().hex[:12]}"
