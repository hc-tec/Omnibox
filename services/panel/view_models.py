"""
Contract-first Pydantic models for panel component view models.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, Sequence

from pydantic import BaseModel, Field, ValidationError, ConfigDict


class ListPanelRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Unique record identifier")
    title: str = Field(..., description="Display title")
    link: Optional[str] = Field(None, description="Target hyperlink")
    summary: Optional[str] = Field(None, description="Short description")
    published_at: Optional[str] = Field(None, description="ISO8601 timestamp")
    author: Optional[str] = Field(None, description="Author display name")
    categories: Optional[List[str]] = Field(None, description="Tags/categories")


class StatisticCardRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Unique record identifier")
    metric_title: str = Field(..., description="Metric title to display")
    metric_value: float = Field(..., description="Metric numeric value")
    metric_unit: Optional[str] = Field(None, description="Unit label displayed next to the value")
    metric_delta_text: Optional[str] = Field(
        None, description="Human readable delta, e.g. '+12% vs yesterday'"
    )
    metric_delta_value: Optional[float] = Field(
        None, description="Raw numeric delta for downstream calculations"
    )
    metric_trend: Optional[str] = Field(
        None,
        description="Semantic trend indicator used by the frontend to decide colours/icons",
        pattern="^(up|down|flat)$",
    )
    description: Optional[str] = Field(None, description="Optional supporting text shown under the value")


class NumberViewRecord(BaseModel):
    """Deprecated alias kept for backwards compatibility with existing adapters."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Unique record identifier")
    label: str = Field(..., description="Metric label")
    value: float = Field(..., description="Metric value")
    unit: Optional[str] = Field(None, description="Unit label")
    delta: Optional[Dict[str, Any]] = Field(None, description="Delta information payload")
    description: Optional[str] = Field(None, description="Additional text")


class TableColumn(BaseModel):
    key: str = Field(..., description="Field key inside record")
    label: str = Field(..., description="Column title")
    type: Optional[str] = Field(
        None, description="Value type", pattern="^(text|number|date|currency|tag)$"
    )
    sortable: bool = Field(default=False, description="Sortable flag")
    align: Optional[str] = Field(
        None, description="Alignment", pattern="^(left|center|right)$"
    )
    width: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Relative width between 0 and 1"
    )


class TableViewModel(BaseModel):
    columns: List[TableColumn] = Field(..., description="Column definitions")
    rows: List[Dict[str, Any]] = Field(..., description="Row data")


class LineChartRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    x: Any = Field(..., description="X axis value")
    y: float = Field(..., description="Y axis numeric value")
    series: Optional[str] = Field(None, description="Series identifier")
    tooltip: Optional[str] = Field(None, description="Tooltip text")


class BarChartRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Unique record identifier")
    x: str = Field(..., description="X axis category (e.g., language name, user name)")
    y: float = Field(..., description="Y axis numeric value")
    series: Optional[str] = Field(None, description="Series identifier for grouping")
    color: Optional[str] = Field(None, description="Custom bar color (hex, e.g., #3776ab)")
    tooltip: Optional[str] = Field(None, description="Custom tooltip text")


class PieChartRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Unique record identifier")
    name: str = Field(..., description="Category name")
    value: float = Field(..., description="Numeric value")
    color: Optional[str] = Field(None, description="Custom slice color (hex, e.g., #3776ab)")
    tooltip: Optional[str] = Field(None, description="Custom tooltip text")


class ImageGalleryRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Unique record identifier")
    image_url: str = Field(..., description="Image full URL")
    title: Optional[str] = Field(None, description="Image title")
    description: Optional[str] = Field(None, description="Image description")
    link: Optional[str] = Field(None, description="Click target URL")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail URL for performance")


class FallbackRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: Optional[str] = Field(None, description="Display title")
    content: str = Field(..., description="Markdown or HTML content")


def ensure_list_panel(records: Sequence[Dict[str, Any]]) -> List[ListPanelRecord]:
    return [ListPanelRecord.model_validate(record) for record in records]


def ensure_line_chart(records: Sequence[Dict[str, Any]]) -> List[LineChartRecord]:
    return [LineChartRecord.model_validate(record) for record in records]


def ensure_bar_chart(records: Sequence[Dict[str, Any]]) -> List[BarChartRecord]:
    return [BarChartRecord.model_validate(record) for record in records]


def ensure_pie_chart(records: Sequence[Dict[str, Any]]) -> List[PieChartRecord]:
    return [PieChartRecord.model_validate(record) for record in records]


def ensure_image_gallery(records: Sequence[Dict[str, Any]]) -> List[ImageGalleryRecord]:
    return [ImageGalleryRecord.model_validate(record) for record in records]


def ensure_number_view(records: Sequence[Dict[str, Any]]) -> List[NumberViewRecord]:
    return [NumberViewRecord.model_validate(record) for record in records]


def ensure_statistic_card(records: Sequence[Dict[str, Any]]) -> List[StatisticCardRecord]:
    return [StatisticCardRecord.model_validate(record) for record in records]


def ensure_table_view(model: TableViewModel) -> TableViewModel:
    return TableViewModel.model_validate(model.model_dump())


def ensure_table(records: Sequence[Dict[str, Any]]) -> List[TableViewModel]:
    """
    验证 Table 组件数据。

    由于 Table 的数据结构特殊（包含 columns 和 rows），
    records 应该是一个包含单个 TableViewModel 字典的列表。
    """
    if not records:
        return []
    # Table 通常只有一个 TableViewModel，取第一个元素验证
    table_model = TableViewModel.model_validate(records[0])
    return [table_model]


def ensure_fallback(records: Sequence[Dict[str, Any]]) -> List[FallbackRecord]:
    return [FallbackRecord.model_validate(record) for record in records]


class ContractViolation(ValueError):
    """Raised when adapter output violates component contract."""

    def __init__(self, component_id: str, error: ValidationError):
        self.component_id = component_id
        self.error = error
        message = f"{component_id} contract validation failed: {error}"
        super().__init__(message)


def validate_records(component_id: str, records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        if component_id == "ListPanel":
            return [model.model_dump() for model in ensure_list_panel(records)]
        if component_id == "LineChart":
            return [model.model_dump() for model in ensure_line_chart(records)]
        if component_id == "BarChart":
            return [model.model_dump() for model in ensure_bar_chart(records)]
        if component_id == "PieChart":
            return [model.model_dump() for model in ensure_pie_chart(records)]
        if component_id == "ImageGallery":
            return [model.model_dump() for model in ensure_image_gallery(records)]
        if component_id == "StatisticCard":
            return [model.model_dump() for model in ensure_statistic_card(records)]
        if component_id == "NumberView":
            return [model.model_dump() for model in ensure_number_view(records)]
        if component_id == "Table":
            return [model.model_dump() for model in ensure_table(records)]
        if component_id == "FallbackRichText":
            return [model.model_dump() for model in ensure_fallback(records)]
    except ValidationError as exc:
        raise ContractViolation(component_id, exc) from exc

    # Unknown component: return records without validation.
    return list(records)
