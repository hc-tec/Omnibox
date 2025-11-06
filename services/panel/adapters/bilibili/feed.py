from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from api.schemas.panel import ComponentInteraction, LayoutHint, SourceInfo

from services.panel.view_models import validate_records
from ..registry import (
    AdapterBlockPlan,
    AdapterExecutionContext,
    ComponentManifestEntry,
    RouteAdapterManifest,
    RouteAdapterResult,
    route_adapter,
)
from ..utils import ensure_list, short_text, early_return_if_no_match


FEED_MANIFEST = RouteAdapterManifest(
    components=[
        ComponentManifestEntry(
            component_id="ListPanel",
            description="展示投稿 / 动态列表",
            cost="low",
            default_selected=True,
            required=True,
        )
    ],
    notes="适用于 B 站用户投稿、动态等内容型数据。",
)


@route_adapter(
    "/bilibili",
    "/bilibili/user/video",
    "/bilibili/user/dynamic",
    manifest=FEED_MANIFEST,
)
def bilibili_feed_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    payload = records[0] if records else {}
    raw_items = payload.get("items") or payload.get("item") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    # 先构建基础stats（无论是否提前返回都需要）
    stats = {
        "datasource": source_info.datasource or "bilibili",
        "route": source_info.route,
        "feed_title": payload.get("title"),
        "total_items": len(raw_items),
        "api_endpoint": source_info.route or "/bilibili",
    }

    # 检查是否需要提前返回
    early = early_return_if_no_match(context, ["ListPanel"], stats)
    if early:
        return early

    normalized: list[Dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        title = item.get("title") or item.get("name") or ""
        link = item.get("link") or item.get("url")
        summary = short_text(
            item.get("description")
            or item.get("summary")
            or item.get("content_html")
        )
        normalized.append(
            {
                "id": item.get("id") or link or title,
                "title": title,
                "link": link,
                "summary": summary,
                "published_at": item.get("pubDate") or item.get("date_published"),
                "author": item.get("author"),
                "categories": ensure_list(item.get("tags")),
            }
        )

    validated = validate_records("ListPanel", normalized)

    block_plan = AdapterBlockPlan(
        component_id="ListPanel",
        props={
            "title_field": "title",
            "link_field": "link",
            "description_field": "summary",
            "pub_date_field": "published_at",
        },
        options={"show_description": True, "span": 12},
        interactions=[ComponentInteraction(type="open_link", label="Open Link")],
        title=payload.get("title") or source_info.route,
        layout_hint=LayoutHint(span=12, min_height=320),
        confidence=0.7,
    )

    stats["total_items"] = len(validated)

    return RouteAdapterResult(records=validated, block_plans=[block_plan], stats=stats)
