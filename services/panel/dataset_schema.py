from __future__ import annotations

"""
Dataset schema descriptor & profiling helpers.

这些数据结构用于在 adapter manifest 中声明字段契约，并在运行时向
LangGraph/前端暴露结构化元数据，方便后续的数据处理工具安全复用。
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional


DatasetFieldType = Literal["string", "number", "integer", "boolean", "datetime", "array", "object", "mixed"]


@dataclass(frozen=True)
class DatasetSchemaField:
    """
    描述单个字段的元信息，用于引导工具推理。
    """

    name: str
    type: DatasetFieldType
    description: Optional[str] = None
    required: bool = False
    filterable: bool = False
    aggregatable: bool = False
    sortable: bool = False
    semantic_type: Optional[str] = None
    unit: Optional[str] = None
    categories: List[str] = field(default_factory=list)

    def to_metadata(self) -> Dict[str, Any]:
        payload = asdict(self)
        # categories 为空时省略，避免噪音
        if not payload.get("categories"):
            payload.pop("categories", None)
        return payload


@dataclass(frozen=True)
class DatasetSchemaDescriptor:
    """
    数据集 Schema 描述符：声明字段、主键、时间字段等元信息。
    """

    schema_id: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    fields: List[DatasetSchemaField] = field(default_factory=list)
    primary_key: Optional[str] = None
    time_field: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    version: Optional[str] = None

    def to_metadata(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "schema_id": self.schema_id,
            "display_name": self.display_name,
            "description": self.description,
            "primary_key": self.primary_key,
            "time_field": self.time_field,
            "version": self.version,
            "tags": list(self.tags) if self.tags else None,
            "fields": [field.to_metadata() for field in self.fields],
        }
        # 移除为 None 的字段
        return {key: value for key, value in payload.items() if value not in (None, [], {})}
