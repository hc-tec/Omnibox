"""
简单的 Schema 摘要生成器：统计字段类型、样本与基础统计信息。
"""

from __future__ import annotations

from datetime import datetime
from statistics import mean, median, pstdev
from typing import Any, Dict, Iterable, List, Optional

from api.schemas.panel import SchemaFieldSummary, SchemaSummary


class SchemaSummaryBuilder:
    """根据原始记录构建 Schema 概览。"""

    def __init__(self, max_samples: int = 4):
        self.max_samples = max_samples

    def build(self, records: Iterable[Dict[str, Any]]) -> SchemaSummary:
        records_list = list(records)
        field_map: Dict[str, List[Any]] = {}

        for record in records_list:
            for key, value in record.items():
                if key.startswith("_"):
                    continue
                field_map.setdefault(key, []).append(value)

        field_summaries: List[SchemaFieldSummary] = []
        dataset_stats: Dict[str, Any] = {"total": len(records_list)}
        datetime_values: List[datetime] = []

        for name, values in field_map.items():
            data_type = self._infer_type(values)
            samples = self._collect_samples(values)
            stats = self._compute_stats(data_type, values)

            if data_type == "datetime":
                datetime_values.extend(self._parse_datetime(values))

            field_summaries.append(
                SchemaFieldSummary(
                    name=name,
                    type=data_type,
                    sample=samples,
                    stats=stats,
                )
            )

        if datetime_values:
            dataset_stats["time_range"] = [
                min(datetime_values).isoformat(),
                max(datetime_values).isoformat(),
            ]

        digest = "List(" + "/".join(sorted(f"{field.name}:{field.type}" for field in field_summaries)) + ")" if field_summaries else "Empty"
        return SchemaSummary(
            fields=sorted(field_summaries, key=lambda item: item.name),
            stats=dataset_stats,
            schema_digest=digest,
        )

    def _collect_samples(self, values: List[Any]) -> List[Any]:
        filtered = [value for value in values if value is not None]
        if len(filtered) <= self.max_samples:
            return filtered
        return filtered[: self.max_samples - 1] + [filtered[-1]]

    @staticmethod
    def _infer_type(values: List[Any]) -> str:
        detected: Optional[str] = None
        for value in values:
            current = SchemaSummaryBuilder._single_type(value)
            if detected is None:
                detected = current
            elif detected != current:
                if {detected, current} <= {"number", "null"}:
                    detected = "number"
                elif {detected, current} <= {"string", "datetime", "null"}:
                    detected = "string"
                else:
                    detected = "mixed"
            if detected == "mixed":
                break
        return detected or "unknown"

    @staticmethod
    def _single_type(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return "number"
        if isinstance(value, (datetime,)):
            return "datetime"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return "string"

    def _compute_stats(self, data_type: str, values: List[Any]) -> Optional[Dict[str, Any]]:
        if data_type == "number":
            numbers = [self._to_number(value) for value in values]
            numbers = [num for num in numbers if num is not None]
            if not numbers:
                return None
            payload = {
                "min": min(numbers),
                "max": max(numbers),
                "avg": mean(numbers),
                "median": median(numbers),
            }
            if len(numbers) > 1:
                payload["std"] = pstdev(numbers)
            return payload

        if data_type == "datetime":
            dates = self._parse_datetime(values)
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
    def _parse_datetime(values: Iterable[Any]) -> List[datetime]:
        result: List[datetime] = []
        for value in values:
            if isinstance(value, datetime):
                result.append(value)
            elif isinstance(value, str):
                try:
                    result.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
                except ValueError:
                    continue
        return result
