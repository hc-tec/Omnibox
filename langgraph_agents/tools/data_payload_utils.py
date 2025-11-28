from __future__ import annotations

"""工具层数据载荷解包与辅助函数。"""

from typing import Any, Dict, List, Optional, Tuple


def select_non_empty(*values) -> Optional[str]:
    for value in values:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        elif value:
            return value
    return None


def unwrap_payload(envelope: Any, data_store=None) -> Tuple[Any, Optional[str]]:
    """
    从工具输出封装中提取原始数据载荷。

    - envelope 可能是 data_operator/filter 等工具返回的 dict
    - envelope 也可能只包含一个 payload_ref，需要到 data_store 中再次加载
    - 返回 (payload, payload_ref)，payload_ref 为引用的 data_id（如存在）
    """
    payload_ref: Optional[str] = None
    payload_candidate: Any = envelope

    if isinstance(envelope, dict):
        payload_ref = envelope.get("payload_ref")
        if payload_ref and data_store is not None:
            referenced = data_store.load(payload_ref)
            if isinstance(referenced, dict):
                payload_candidate = referenced
        else:
            for key in ("payload", "result"):
                candidate = envelope.get(key)
                if isinstance(candidate, dict):
                    payload_candidate = candidate
                    break

    # 复制并补充元数据，保证 route/feed_title 等信息在载荷上可用
    if isinstance(payload_candidate, dict) and isinstance(envelope, dict):
        payload = dict(payload_candidate)
        generated_path = select_non_empty(envelope.get("generated_path"), envelope.get("route"))
        if generated_path:
            payload.setdefault("generated_path", generated_path)
            payload.setdefault("route", generated_path)
        feed_title = select_non_empty(envelope.get("feed_title"), envelope.get("title"))
        if feed_title:
            payload.setdefault("feed_title", feed_title)
            payload.setdefault("title", payload.get("title") or feed_title)
        source = select_non_empty(envelope.get("source"), envelope.get("datasource"))
        if source:
            payload.setdefault("source", source)
            payload.setdefault("datasource", source)
        if "items" not in payload and isinstance(envelope.get("items"), list):
            payload["items"] = envelope["items"]
        return payload, payload_ref

    return payload_candidate, payload_ref


def extract_records(payload: Any) -> List[Dict[str, Any]]:
    """在 RSSHub 样式载荷中提取记录列表。"""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "records", "data", "results", "item"):
            items = payload.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
            if isinstance(items, dict):
                return [items]
    return []


def build_source_metadata(
    payload: Any,
    source_data_id: Optional[str],
    source_step_id: Optional[int],
    payload_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """统一构造源数据的元信息。"""
    metadata: Dict[str, Any] = {}

    if source_data_id:
        metadata["source_data_id"] = source_data_id
    if source_step_id is not None:
        metadata["source_step_id"] = source_step_id
    if payload_ref:
        metadata["payload_ref"] = payload_ref

    if isinstance(payload, dict):
        route = select_non_empty(payload.get("generated_path"), payload.get("route"))
        feed_title = select_non_empty(payload.get("feed_title"), payload.get("title"))
        datasource = select_non_empty(payload.get("datasource"), payload.get("source"))
        if route:
            metadata["generated_path"] = route
        if feed_title:
            metadata["feed_title"] = feed_title
        if datasource:
            metadata["datasource"] = datasource
        if payload.get("source"):
            metadata["source"] = payload.get("source")
        if payload.get("cache_hit"):
            metadata["cache_hit"] = payload.get("cache_hit")
        metadata["item_count"] = len(extract_records(payload))

    return {key: value for key, value in metadata.items() if value is not None}
