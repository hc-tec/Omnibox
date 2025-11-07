from __future__ import annotations

import re
from typing import Any, Dict, Optional, Sequence

from api.schemas.panel import ComponentInteraction, LayoutHint, SourceInfo

from services.panel.analytics import summarize_payload
from services.panel.view_models import validate_records
from ..registry import (
    AdapterBlockPlan,
    AdapterExecutionContext,
    ComponentManifestEntry,
    RouteAdapterManifest,
    RouteAdapterResult,
    route_adapter,
)
from ..utils import safe_int, short_text, early_return_if_no_match

_FOLLOWER_COUNT_KEYS = ("count", "total", "follower_count", "total_followings")
_COUNT_PATTERN = re.compile(r"总计(\d+)")


FOLLOWINGS_MANIFEST = RouteAdapterManifest(
    components=[
        ComponentManifestEntry(
            component_id="ListPanel",
            description="展示关注列表及备注信息",
            cost="low",
            default_selected=True,
            required=True,
            hints={"metrics": ["follower_count"]},
        )
    ],
    notes="使用 RSSHub /bilibili/user/followings 接口，提取关注动态。",
)


@route_adapter("/bilibili/user/followings", manifest=FOLLOWINGS_MANIFEST)
def bilibili_followings_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    payload = records[0] if records else {}
    raw_items = payload.get("item") or payload.get("items") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    summary = summarize_payload(source_info.route or "", payload)

    follower_count = _extract_follower_count(payload, raw_items)

    # 先构建基础stats（无论是否提前返回都需要）
    stats = {
        "datasource": source_info.datasource or "bilibili",
        "route": source_info.route,
        "feed_title": payload.get("title"),
        "total_items": summary.get("item_count", len(raw_items)),
        "api_endpoint": source_info.route or "/bilibili/user/followings",
        "sample_titles": summary.get("sample_titles", []),
        "metrics": summary.get("metrics", {}),
    }
    if follower_count is not None:
        stats["follower_count"] = follower_count

    # 检查是否需要提前返回
    early = early_return_if_no_match(context, ["ListPanel"], stats)
    if early:
        return early

    normalized: list[Dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        title = item.get("title") or ""
        link = item.get("link")
        summary = short_text(item.get("description"))
        normalized.append(
            {
                "id": item.get("id") or link or title,
                "title": title,
                "link": link,
                "summary": summary,
                "published_at": item.get("pubDate") or item.get("date_published"),
            }
        )

    validated_list = validate_records("ListPanel", normalized)
    stats["total_items"] = len(validated_list)

    block_plans = [
        AdapterBlockPlan(
            component_id="ListPanel",
            props={
                "title_field": "title",
                "link_field": "link",
                "description_field": "summary",
                "pub_date_field": "published_at",
            },
            options={"show_description": True, "span": 12},
            interactions=[ComponentInteraction(type="open_link", label="Open Profile")],
            title=payload.get("title") or "Bilibili 关注动态",
            layout_hint=LayoutHint(span=12, min_height=320),
            confidence=0.72,
        )
    ]

    return RouteAdapterResult(records=validated_list, block_plans=block_plans, stats=stats)


def _extract_follower_count(
    payload: Dict[str, Any], items: Sequence[Dict[str, Any]]
) -> Optional[int]:
    for key in _FOLLOWER_COUNT_KEYS:
        value = payload.get(key)
        converted = safe_int(value)
        if converted is not None:
            return converted

    for item in items:
        match = _COUNT_PATTERN.search(str(item.get("description") or ""))
        if match:
            return safe_int(match.group(1))
    return None
