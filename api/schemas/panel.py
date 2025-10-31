"""
智能数据面板相关Schema定义。
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    """数据块的数据源元信息。"""

    datasource: str = Field(..., description="Datasource identifier, e.g. hupu")
    route: str = Field(..., description="Resolved RSSHub route or endpoint")
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Query parameters used for the fetch"
    )
    fetched_at: Optional[str] = Field(
        None, description="ISO timestamp when the data was fetched"
    )
    request_id: Optional[str] = Field(None, description="Trace identifier")


class SchemaFieldSummary(BaseModel):
    """字段级摘要信息。"""

    name: str = Field(..., description="Field name")
    type: str = Field(..., description="Inferred field type, e.g. text/url/datetime")
    sample: List[Any] = Field(default_factory=list, description="Representative values")
    stats: Optional[Dict[str, Any]] = Field(
        None, description="Optional statistics such as min/max"
    )
    semantic: List[str] = Field(default_factory=list, description="Semantic tags for this field")


class SchemaSummary(BaseModel):
    """数据集结构摘要。"""

    fields: List[SchemaFieldSummary] = Field(..., description="Field summaries")
    stats: Dict[str, Any] = Field(default_factory=dict, description="Dataset metrics")
    schema_digest: str = Field(..., description="Human readable schema digest")


class DataBlock(BaseModel):
    """面板使用的数据块。"""

    id: str = Field(..., description="Unique data block identifier")
    source_info: SourceInfo = Field(..., description="Datasource metadata")
    records: List[Dict[str, Any]] = Field(
        default_factory=list, description="Trimmed sample records"
    )
    stats: Dict[str, Any] = Field(default_factory=dict, description="Summary metrics")
    schema_summary: SchemaSummary = Field(..., description="Schema summary")
    full_data_ref: Optional[str] = Field(
        None, description="Reference to persisted full dataset"
    )


class ComponentInteraction(BaseModel):
    """组件交互定义。"""

    type: str = Field(..., description="Interaction type, e.g. action/filter")
    label: Optional[str] = Field(None, description="Display label")
    payload: Optional[Dict[str, Any]] = Field(
        default=None, description="Opaque payload returned to backend"
    )


class LayoutHint(BaseModel):
    """布局引擎可选提示信息。"""

    span: Optional[int] = Field(None, description="Grid span suggestion")
    order: Optional[int] = Field(None, description="Preferred ordering")
    priority: Optional[int] = Field(None, description="Priority for placement")
    min_height: Optional[int] = Field(None, description="Minimum height requirement")
    responsive: Optional[Dict[str, Any]] = Field(
        None, description="Responsive layout overrides"
    )


class ViewDescriptor(BaseModel):
    """指向数据块的组件推荐描述。"""

    id: str = Field(..., description="View descriptor identifier")
    component_id: str = Field(..., description="Component identifier")
    data_ref: str = Field(..., description="Referenced data block id")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Recommendation score")
    props: Dict[str, Any] = Field(default_factory=dict, description="Required bindings")
    options: Dict[str, Any] = Field(default_factory=dict, description="Component options")
    interactions: List[ComponentInteraction] = Field(
        default_factory=list, description="Component interactions"
    )
    layout_hint: Optional[LayoutHint] = Field(
        None, description="Layout hint for this view"
    )


class LayoutNode(BaseModel):
    """布局树节点。"""

    type: Literal["row", "column", "grid", "cell"] = Field(
        ..., description="Layout node type"
    )
    id: str = Field(..., description="Layout node identifier")
    children: List[str] = Field(
        default_factory=list, description="Ordered child node or block ids"
    )
    props: Dict[str, Any] = Field(default_factory=dict, description="Layout properties")


class LayoutTree(BaseModel):
    """布局树定义。"""

    mode: Literal["append", "replace", "insert"] = Field(
        ..., description="How the new layout should merge with existing"
    )
    nodes: List[LayoutNode] = Field(..., description="Layout nodes in rendering order")
    history_token: Optional[str] = Field(
        None, description="Token to reference previous layout state"
    )


class UIBlock(BaseModel):
    """可渲染的UI块定义。"""

    id: str = Field(..., description="UI block identifier")
    component: str = Field(..., description="Component identifier")
    data_ref: Optional[str] = Field(
        None, description="Referenced data block id for large payloads"
    )
    data: Optional[Dict[str, Any]] = Field(
        None, description="Inline payload for small datasets"
    )
    props: Dict[str, Any] = Field(default_factory=dict, description="Component props")
    options: Dict[str, Any] = Field(default_factory=dict, description="Options")
    interactions: List[ComponentInteraction] = Field(
        default_factory=list, description="Component interactions"
    )
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Confidence score for recommendation"
    )
    title: Optional[str] = Field(None, description="Display title")


class PanelPayload(BaseModel):
    """REST与WebSocket统一的面板载荷。"""

    mode: Literal["append", "replace", "insert"] = Field(
        ..., description="Layout merge mode requested by the user"
    )
    layout: LayoutTree = Field(..., description="Layout tree for the UI")
    blocks: List[UIBlock] = Field(..., description="Renderable UI blocks")
