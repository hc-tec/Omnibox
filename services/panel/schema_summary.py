"""
智能数据面板的 Schema 摘要构建工具。
"""

from __future__ import annotations

from datetime import datetime
from statistics import mean, median, pstdev
from typing import Any, Dict, Iterable, List, Optional

from api.schemas.panel import SchemaFieldSummary, SchemaSummary
from services.panel.field_profiler import FieldProfiler, profiler as default_profiler


class SchemaSummaryBuilder:
    """从原始记录提取 Schema 信息并生成摘要。"""

    def __init__(self, max_samples: int = 4, field_profiler: Optional[FieldProfiler] = None):
        self.max_samples = max_samples
        self.field_profiler = field_profiler or default_profiler

    def build(self, records: Iterable[Dict[str, Any]]) -> SchemaSummary:
        records_list = list(records)
        dataset_stats: Dict[str, Any] = {"total": len(records_list)}

        profiles = self.field_profiler.profile(records_list)
        field_summaries: List[SchemaFieldSummary] = []
        dataset_datetimes: List[datetime] = []

        for path, profile in profiles.items():
            samples = self._select_samples(profile.sample, self.max_samples)
            stats_payload = self._compute_stats(profile.data_type, profile.sample)

            if profile.data_type == "datetime" or "datetime" in profile.semantic:
                dataset_datetimes.extend(self._parse_datetimes(profile.sample))

            field_summaries.append(
                SchemaFieldSummary(
                    name=path,
                    type=profile.data_type,
                    sample=samples,
                    stats=stats_payload,
                    semantic=profile.semantic,
                )
            )

        if dataset_datetimes:
            dataset_stats["time_range"] = [
                min(dataset_datetimes).isoformat(),
                max(dataset_datetimes).isoformat(),
            ]

        schema_digest = self._build_digest(field_summaries)
        return SchemaSummary(
            fields=sorted(field_summaries, key=lambda field: field.name),
            stats=dataset_stats,
            schema_digest=schema_digest,
        )

    @staticmethod
    def _select_samples(values: List[Any], max_samples: int) -> List[Any]:
        if not values:
            return []
        if len(values) <= max_samples:
            return values
        head = values[: max_samples - 1]
        tail = [values[-1]]
        return head + tail

    def _compute_stats(self, data_type: str, values: List[Any]) -> Optional[Dict[str, Any]]:
        if not values:
            return None

        if data_type == "number":
            numeric_values = [self._to_number(value) for value in values]
            numeric_values = [value for value in numeric_values if value is not None]
            if not numeric_values:
                return None
            payload = {
                "min": min(numeric_values),
                "max": max(numeric_values),
                "avg": mean(numeric_values),
                "median": median(numeric_values),
            }
            if len(numeric_values) > 1:
                payload["std"] = pstdev(numeric_values)
            return payload

        if data_type == "datetime":
            dates = self._parse_datetimes(values)
            if not dates:
                return None
            return {
                "min": min(dates).isoformat(),
                "max": max(dates).isoformat(),
                "count": len(dates),
            }

        if data_type == "array":
            lengths = [len(value) for value in values if isinstance(value, list)]
            if lengths:
                return {"avg_length": mean(lengths)}
            return None

        return None

    @staticmethod
    def _build_digest(fields: List[SchemaFieldSummary]) -> str:
        if not fields:
            return "Empty"
        tokens = [f"{field.name}:{field.type}" for field in fields]
        return "List(" + "/".join(sorted(tokens)) + ")"

    @staticmethod
    def _to_number(value: Any) -> Optional[float]:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_datetimes(values: Iterable[Any]) -> List[datetime]:
        collected: List[datetime] = []
        for value in values:
            if isinstance(value, datetime):
                collected.append(value)
                continue
            if isinstance(value, str):
                try:
                    collected.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
                except ValueError:
                    continue
        return collected
