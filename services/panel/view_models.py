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


class NumberViewDelta(BaseModel):
    model_config = ConfigDict(extra="allow")

    value: float = Field(..., description="Delta numeric value")
    label: Optional[str] = Field(None, description="Display label for delta")
    trend: Optional[str] = Field(
        None, description="Trend indicator", pattern="^(up|down|flat)$"
    )


class NumberViewRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Unique record identifier")
    label: str = Field(..., description="Metric label")
    value: float = Field(..., description="Metric value")
    unit: Optional[str] = Field(None, description="Unit label")
    delta: Optional[NumberViewDelta] = Field(None, description="Delta information")
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


class FallbackRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: Optional[str] = Field(None, description="Display title")
    content: str = Field(..., description="Markdown or HTML content")


def ensure_list_panel(records: Sequence[Dict[str, Any]]) -> List[ListPanelRecord]:
    return [ListPanelRecord.model_validate(record) for record in records]


def ensure_line_chart(records: Sequence[Dict[str, Any]]) -> List[LineChartRecord]:
    return [LineChartRecord.model_validate(record) for record in records]


def ensure_number_view(records: Sequence[Dict[str, Any]]) -> List[NumberViewRecord]:
    return [NumberViewRecord.model_validate(record) for record in records]


def ensure_table_view(model: TableViewModel) -> TableViewModel:
    return TableViewModel.model_validate(model.model_dump())


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
        if component_id == "NumberView":
            return [model.model_dump() for model in ensure_number_view(records)]
        if component_id == "FallbackRichText":
            return [model.model_dump() for model in ensure_fallback(records)]
    except ValidationError as exc:
        raise ContractViolation(component_id, exc) from exc

    # Unknown component: return records without validation.
    return list(records)
