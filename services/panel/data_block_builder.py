"""
智能数据面板中的数据块构建工具。
"""

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from api.schemas.panel import DataBlock, SchemaSummary, SourceInfo
from services.panel.schema_summary import SchemaSummaryBuilder


class DataBlockBuilder:
    """从原始数据构造DataBlock实体。"""

    def __init__(
        self,
        schema_builder: Optional[SchemaSummaryBuilder] = None,
        max_records: int = 20,
    ):
        self.schema_builder = schema_builder or SchemaSummaryBuilder()
        self.max_records = max_records

    def build(
        self,
        block_id: str,
        records: Sequence[Any],
        source_info: SourceInfo,
        full_data_ref: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None,
    ) -> DataBlock:
        normalized_records, canonical_records = self._prepare_records(records)
        schema_summary = self._build_schema_summary(canonical_records)

        block_stats = stats.copy() if stats else {}
        block_stats.setdefault("total", len(records))

        return DataBlock(
            id=block_id,
            source_info=source_info,
            records=normalized_records,
            stats=block_stats,
            schema_summary=schema_summary,
            full_data_ref=full_data_ref,
        )

    def build_from_fetch_result(
        self,
        block_id: str,
        fetch_items: Sequence[Any],
        datasource: str,
        route: str,
        params: Optional[Dict[str, Any]],
        fetched_at: Optional[str],
        request_id: Optional[str],
        full_data_ref: Optional[str],
    ) -> DataBlock:
        source_info = SourceInfo(
            datasource=datasource,
            route=route,
            params=params or {},
            fetched_at=fetched_at,
            request_id=request_id,
        )
        stats = {"source": datasource}
        return self.build(
            block_id=block_id,
            records=fetch_items,
            source_info=source_info,
            full_data_ref=full_data_ref,
            stats=stats,
        )

    def _prepare_records(
        self, records: Sequence[Any]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        trimmed_source = list(records)
        trimmed = trimmed_source[: self.max_records]
        normalized: List[Dict[str, Any]] = []

        for record in trimmed:
            normalized.append(self._record_to_dict(record))

        return normalized, normalized

    def _build_schema_summary(self, records: Iterable[Dict[str, Any]]) -> SchemaSummary:
        return self.schema_builder.build(records)

    @staticmethod
    def _record_to_dict(record: Any) -> Dict[str, Any]:
        if isinstance(record, dict):
            return dict(record)

        if is_dataclass(record):
            return dict(asdict(record))

        if hasattr(record, "__dict__"):
            return dict(record.__dict__)

        return {"value": record}
