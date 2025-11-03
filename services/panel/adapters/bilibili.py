from __future__ import annotations

import re
from typing import Any, Dict, Optional, Sequence

from api.schemas.panel import SourceInfo

from .common import (
    build_api_candidate,
    build_list_plan,
    build_list_records,
    collect_feed_items,
    validate_records,
)
from .registry import RouteAdapterResult, route_adapter


@route_adapter("/bilibili", "/bilibili/user/video", "/bilibili/user/dynamic")
def bilibili_feed_adapter(
    source_info: SourceInfo, records: Sequence[Dict[str, Any]]
) -> RouteAdapterResult:
    feed_title, items, feed_stats = collect_feed_items(records)
    normalized = build_list_records(items)
    for item in normalized:
        item["source"] = "bilibili"
    validated = validate_records("ListPanel", normalized)

    stats = {
        "datasource": source_info.datasource or "bilibili",
        "route": source_info.route,
        "feed_title": feed_title,
        "total_items": feed_stats.get("total_items", len(validated)),
        "api_endpoint": source_info.route or "/bilibili",
    }

    return RouteAdapterResult(
        records=validated,
        block_plans=[build_list_plan(feed_title, confidence=0.7)],
        stats=stats,
    )


@route_adapter("/bilibili/user/followings")
def bilibili_followings_adapter(
    source_info: SourceInfo, records: Sequence[Dict[str, Any]]
) -> RouteAdapterResult:
    feed_title, items, feed_stats = collect_feed_items(records)
    validated = validate_records("ListPanel", build_list_records(items))

    follower_count = _extract_following_count(items)

    api_endpoint = source_info.route or "/bilibili/user/followings"

    stats = {
        "datasource": source_info.datasource or "bilibili",
        "route": source_info.route,
        "feed_title": feed_title,
        "total_items": feed_stats.get("total_items", len(validated)),
        "follower_count": follower_count,
        "api_endpoint": api_endpoint,
    }

    return RouteAdapterResult(
        records=validated,
        block_plans=[build_list_plan(feed_title, confidence=0.72)],
        stats=stats,
    )


def _extract_following_count(items: Sequence[Dict[str, Any]]) -> Optional[int]:
    pattern = re.compile(r"\u603b\u8ba1(\d+)")
    for item in items:
        description = item.get("description") or item.get("content") or ""
        match = pattern.search(str(description))
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return None
