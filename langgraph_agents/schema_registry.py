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

    def clear(self) -> None:
        self.store.clear()
