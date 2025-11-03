from __future__ import annotations

from typing import Any, Dict, Sequence

from api.schemas.panel import SourceInfo

from .common import build_list_plan, build_list_records, collect_feed_items, validate_records
from .registry import RouteAdapterResult, route_adapter


def _generic_list_result(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    *,
    confidence: float = 0.68,
) -> RouteAdapterResult:
    feed_title, items, feed_stats = collect_feed_items(records)
    validated = validate_records("ListPanel", build_list_records(items))
    stats = {
        "datasource": source_info.datasource,
        "route": source_info.route,
        "total_items": feed_stats.get("total_items", len(validated)),
    }
    return RouteAdapterResult(
        records=validated,
        block_plans=[build_list_plan(feed_title, confidence=confidence)],
        stats=stats,
    )


@route_adapter("/github/issue")
def github_issue_adapter(
    source_info: SourceInfo, records: Sequence[Dict[str, Any]]
) -> RouteAdapterResult:
    return _generic_list_result(source_info, records, confidence=0.66)


@route_adapter("/sspai")
def sspai_feed_adapter(
    source_info: SourceInfo, records: Sequence[Dict[str, Any]]
) -> RouteAdapterResult:
    return _generic_list_result(source_info, records)
