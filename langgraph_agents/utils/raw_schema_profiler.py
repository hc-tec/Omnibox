from __future__ import annotations

import itertools
from typing import Any, Dict, List, Sequence

from genson import SchemaBuilder

DEFAULT_MAX_SAMPLES = 20
DEFAULT_MAX_FIELD_LENGTH = 400
DEFAULT_MAX_LIST_ITEMS = 5
DEFAULT_MAX_DICT_KEYS = 20


def _iter_candidate_records(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        items = payload.get("items") or payload.get("item")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        if isinstance(items, dict):
            return [items]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def build_raw_schema(payload: Any, max_samples: int = 100) -> Dict[str, Any]:
    records = _iter_candidate_records(payload)
    if not records:
        return {}

    builder = SchemaBuilder()
    for record in itertools.islice(records, max_samples):
        builder.add_object(record)
    try:
        schema = builder.to_schema()
    except Exception:
        schema = {}
    return schema


def build_sample_records(
    payload: Any,
    max_samples: int = DEFAULT_MAX_SAMPLES,
    max_field_length: int = DEFAULT_MAX_FIELD_LENGTH,
    max_list_items: int = DEFAULT_MAX_LIST_ITEMS,
    max_dict_keys: int = DEFAULT_MAX_DICT_KEYS,
) -> List[Dict[str, Any]]:
    records = _iter_candidate_records(payload)
    if not records:
        return []

    trimmed: List[Dict[str, Any]] = []
    for record in itertools.islice(records, max_samples):
        trimmed.append(
            _trim_value(
                record,
                max_field_length=max_field_length,
                max_list_items=max_list_items,
                max_dict_keys=max_dict_keys,
            )
        )
    return trimmed


def _trim_value(
    value: Any,
    *,
    max_field_length: int,
    max_list_items: int,
    max_dict_keys: int,
    depth: int = 0,
) -> Any:
    if isinstance(value, str):
        if len(value) <= max_field_length:
            return value
        return {
            "__preview__": value[:max_field_length],
            "__truncated__": True,
            "__original_length__": len(value),
        }

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    if isinstance(value, list):
        items = [
            _trim_value(
                item,
                max_field_length=max_field_length,
                max_list_items=max_list_items,
                max_dict_keys=max_dict_keys,
                depth=depth + 1,
            )
            for item in value[:max_list_items]
        ]
        if len(value) > max_list_items:
            items.append({"__truncated_items__": len(value) - max_list_items})
        return items

    if isinstance(value, dict):
        trimmed: Dict[str, Any] = {}
        for key in list(value.keys())[:max_dict_keys]:
            trimmed[key] = _trim_value(
                value[key],
                max_field_length=max_field_length,
                max_list_items=max_list_items,
                max_dict_keys=max_dict_keys,
                depth=depth + 1,
            )
        if len(value) > max_dict_keys:
            trimmed["__truncated_keys__"] = len(value) - max_dict_keys
        return trimmed

    return str(value)


def summarize_payload(payload: Any, *, sample_limit: int = DEFAULT_MAX_SAMPLES) -> Dict[str, Any]:
    """
    综合返回 schema + 样本 + 元数据，供 SchemaRegistry 使用。
    """
    raw_schema = build_raw_schema(payload)
    samples = build_sample_records(payload, max_samples=sample_limit)
    metadata = _extract_metadata(payload, len(samples))
    return {
        "schema": raw_schema,
        "samples": samples,
        "sample_count": len(samples),
        "metadata": metadata,
    }


def _extract_metadata(payload: Any, sample_count: int) -> Dict[str, Any]:
    """
    构建简要元数据，帮助 data_operator 了解原始路由和来源。
    """
    metadata: Dict[str, Any] = {"sample_count": sample_count}
    if isinstance(payload, dict):
        metadata.update(
            {
                "generated_path": payload.get("generated_path") or payload.get("route"),
                "feed_title": payload.get("feed_title") or payload.get("title"),
                "source": payload.get("source"),
                "datasource": payload.get("datasource"),
                "cache_hit": payload.get("cache_hit"),
                "item_count": len(_iter_candidate_records(payload)),
            }
        )
    return {key: value for key, value in metadata.items() if value is not None}
