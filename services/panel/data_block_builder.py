"""
从原始数据构造 DataBlock，并允许根据 route 注入自定义适配器。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, is_dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from api.schemas.panel import DataBlock, SchemaSummary, SourceInfo
from services.panel.adapters import (
    AdapterBlockPlan,
    AdapterExecutionContext,
    RouteAdapterResult,
    get_route_adapter,
)
from services.panel.schema_summary import SchemaSummaryBuilder


@dataclass
class BlockBuildResult:
    data_block: DataBlock
    block_plans: List[AdapterBlockPlan]


class DataBlockBuilder:
    def __init__(self, schema_builder: Optional[SchemaSummaryBuilder] = None, max_records: int = 20):
        self.schema_builder = schema_builder or SchemaSummaryBuilder()
        self.max_records = max_records

    def build(
        self,
        block_id: str,
        records: Sequence[Any],
        source_info: SourceInfo,
        full_data_ref: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None,
        requested_components: Optional[Sequence[str]] = None,
    ) -> BlockBuildResult:
        adapter_result = self._apply_adapter(source_info, records, requested_components)
        normalized_records, canonical_records = self._prepare_records(adapter_result.records)
        schema_summary = self._build_schema_summary(canonical_records)

        merged_stats = stats.copy() if stats else {}
        merged_stats.setdefault("total", len(adapter_result.records))
        merged_stats.update(adapter_result.stats)

        data_block = DataBlock(
            id=block_id,
            source_info=source_info,
            records=normalized_records,
            stats=merged_stats,
            schema_summary=schema_summary,
            full_data_ref=full_data_ref,
        )

        return BlockBuildResult(data_block=data_block, block_plans=list(adapter_result.block_plans))

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
        requested_components: Optional[Sequence[str]] = None,
    ) -> BlockBuildResult:
        source_info = SourceInfo(
            datasource=datasource,
            route=route,
            params=params or {},
            fetched_at=fetched_at,
            request_id=request_id,
        )
        return self.build(
            block_id=block_id,
            records=fetch_items,
            source_info=source_info,
            full_data_ref=full_data_ref,
            stats={"source": datasource},
            requested_components=requested_components,
        )

    def _apply_adapter(
        self,
        source_info: SourceInfo,
        records: Sequence[Any],
        requested_components: Optional[Sequence[str]] = None,
    ) -> RouteAdapterResult:
        adapter = get_route_adapter(source_info.route or "")
        record_dicts = [self._record_to_dict(record) for record in records]
        context = AdapterExecutionContext(requested_components=requested_components)
        return adapter(source_info, record_dicts, context)

    def _prepare_records(self, records: Sequence[Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        trimmed = list(records)[: self.max_records]
        normalized = [self._record_to_dict(record) for record in trimmed]
        return normalized, normalized

    def _build_schema_summary(self, records: Iterable[Dict[str, Any]]) -> SchemaSummary:
        return self.schema_builder.build(records)

    @staticmethod
    def _record_to_dict(record: Any) -> Dict[str, Any]:
        if isinstance(record, dict):
            return dict(record)
        if is_dataclass(record):
            return dict(asdict(record))
        if hasattr(record, "model_dump"):
            try:
                return dict(record.model_dump())
            except Exception:
                pass
        if hasattr(record, "__dict__"):
            return dict(record.__dict__)
        return {"value": record}
