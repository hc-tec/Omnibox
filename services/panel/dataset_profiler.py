from __future__ import annotations

"""
轻量级数据集画像生成器。

用于在不暴露原始数据的前提下，输出字段存在性、类型、长度等统计信息，
帮助 LangGraph/LLM 工具在二次处理前了解数据结构。
"""

from collections import Counter
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .dataset_schema import DatasetSchemaDescriptor, DatasetSchemaField, DatasetFieldType

MAX_SAMPLES = 50  # 避免大数据集带来额外开销


def build_dataset_profile(
    records: Sequence[Dict[str, Any]],
    schema: Optional[DatasetSchemaDescriptor] = None,
    max_samples: int = MAX_SAMPLES,
) -> Dict[str, Any]:
    """
    根据样本记录生成字段级画像，不返回任何原始值，仅包含统计指标。
    """

    if not records:
        return {"record_count": 0, "sampled_count": 0, "fields": []}

    sample = [record for record in records if isinstance(record, dict)]
    if not sample:
        return {"record_count": len(records), "sampled_count": 0, "fields": []}

    sample = sample[: max_samples]
    field_defs = schema.fields if schema else _infer_fields(sample)

    profile_fields: List[Dict[str, Any]] = []
    for field in field_defs:
        values = [record.get(field.name) for record in sample]
        profile_fields.append(_analyze_field(field, values, len(sample)))

    return {
        "record_count": len(records),
        "sampled_count": len(sample),
        "fields": [field for field in profile_fields if field],
    }


def _infer_fields(sample: Sequence[Dict[str, Any]]) -> List[DatasetSchemaField]:
    keys = set()
    for record in sample:
        keys.update(record.keys())
    inferred: List[DatasetSchemaField] = []
    for name in sorted(keys):
        inferred.append(
            DatasetSchemaField(
                name=name,
                type=_infer_type_from_values([record.get(name) for record in sample]),
                description=None,
            )
        )
    return inferred


def _analyze_field(
    field: DatasetSchemaField,
    values: Sequence[Any],
    sample_size: int,
) -> Dict[str, Any]:
    presence = sum(1 for value in values if _has_value(value))
    non_null_ratio = round(presence / sample_size, 3) if sample_size else 0.0

    observed_types = Counter(_infer_single_type(value) for value in values if value is not None)
    observed_payload = dict(observed_types) if observed_types else None

    entry: Dict[str, Any] = {
        "name": field.name,
        "declared_type": field.type,
        "non_null_ratio": non_null_ratio,
        "observed_types": observed_payload,
    }

    numeric_stats = _numeric_stats(values)
    if numeric_stats:
        entry["numeric_stats"] = numeric_stats

    text_stats = _text_length_stats(values)
    if text_stats:
        entry["text_stats"] = text_stats

    array_stats = _array_stats(values)
    if array_stats:
        entry["array_stats"] = array_stats

    distinct_count = _estimate_distinct(values)
    if distinct_count is not None:
        entry["distinct_estimate"] = distinct_count

    # 移除空字段
    return {key: value for key, value in entry.items() if value not in (None, {})}


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _infer_type_from_values(values: Iterable[Any]) -> DatasetFieldType:
    detected: Optional[DatasetFieldType] = None
    for value in values:
        current = _infer_single_type(value)
        if detected is None:
            detected = current
            continue
        if detected == current:
            continue
        if {"number", current} <= {"number", "integer", "null"}:
            detected = "number"
            continue
        if {detected, current} <= {"string", "datetime", "null"}:
            detected = "string"
            continue
        detected = "mixed"
        break
    return detected or "unknown"  # type: ignore[return-value]


def _infer_single_type(value: Any) -> DatasetFieldType:
    if value is None:
        return "mixed"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, (list, tuple)):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _numeric_stats(values: Sequence[Any]) -> Optional[Dict[str, float]]:
    numbers: List[float] = []
    for value in values:
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)):
            numbers.append(float(value))
        elif isinstance(value, str):
            try:
                numbers.append(float(value))
            except ValueError:
                continue
    if not numbers:
        return None
    return {
        "min": min(numbers),
        "max": max(numbers),
        "avg": round(mean(numbers), 3),
    }


def _text_length_stats(values: Sequence[Any]) -> Optional[Dict[str, float]]:
    lengths = [len(value) for value in values if isinstance(value, str)]
    if not lengths:
        return None
    return {
        "min": min(lengths),
        "max": max(lengths),
        "avg": round(mean(lengths), 2),
    }


def _array_stats(values: Sequence[Any]) -> Optional[Dict[str, float]]:
    lengths = [len(value) for value in values if isinstance(value, (list, tuple))]
    if not lengths:
        return None
    return {
        "avg_length": round(mean(lengths), 2),
        "max_length": max(lengths),
    }


def _estimate_distinct(values: Sequence[Any], threshold: int = 25) -> Optional[int]:
    seen = set()
    limited = 0
    for value in values:
        if value is None:
            continue
        seen.add(_hashable(value))
        if len(seen) > threshold:
            limited = threshold + 1
            break
    if not seen:
        return None
    return threshold if limited else len(seen)


def _hashable(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_hashable(item) for item in value)
    return value
