from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SchemaRecord:
    """存储与 data_id 关联的原始 schema 与样本。"""

    raw_schema: Dict[str, Any]
    samples: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchemaRegistry:
    """原始 schema 与样本的注册表。"""

    store: Dict[str, SchemaRecord] = field(default_factory=dict)

    def register(
        self,
        data_id: str,
        *,
        raw_schema: Dict[str, Any],
        samples: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.store[data_id] = SchemaRecord(
            raw_schema=raw_schema,
            samples=samples,
            metadata=metadata or {},
        )

    def get(self, data_id: str) -> Optional[SchemaRecord]:
        return self.store.get(data_id)

    def get_schema(self, data_id: str) -> Optional[Dict[str, Any]]:
        """
        返回标准化的 schema 信息，方便调用方直接使用。

        结构：
        {
            "schema": {...},
            "samples": [...],
            "metadata": {...},
            "sample_count": int
        }
        """
        record = self.get(data_id)
        if record is None:
            return None

        schema_info = {
            "schema": record.raw_schema or {},
            "samples": record.samples or [],
            "metadata": record.metadata or {},
        }
        sample_count = schema_info["metadata"].get("sample_count")
        if sample_count is None:
            schema_info["metadata"]["sample_count"] = len(schema_info["samples"])
        schema_info["sample_count"] = schema_info["metadata"]["sample_count"]
        return schema_info

    def clear(self) -> None:
        self.store.clear()
