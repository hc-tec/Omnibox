from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from api.schemas.panel import ComponentInteraction, LayoutHint, SourceInfo

from services.panel.analytics import summarize_payload
from services.panel.view_models import validate_records
from .registry import (
    AdapterBlockPlan,
    AdapterExecutionContext,
    ComponentManifestEntry,
    RouteAdapterManifest,
    RouteAdapterResult,
    route_adapter,
)
from .utils import short_text, first_author, early_return_if_no_match


HUPU_MANIFEST = RouteAdapterManifest(
    components=[
        ComponentManifestEntry(
            component_id="ListPanel",
            description="虎扑帖子列表（标题 + 摘要）",
            cost="low",
            default_selected=True,
            required=True,
        )
    ],
    notes="适用于虎扑社区帖子聚合路由，例如 /hupu/bbs/bxj/1。",
)


@route_adapter("/hupu", "/hupu/bbs", "/hupu/all", manifest=HUPU_MANIFEST)
def hupu_board_list_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    payload = records[0] if records else {}
    raw_items = payload.get("items") or []
    summary = summarize_payload(source_info.route or "", payload)

    stats = {
        "datasource": source_info.datasource or "hupu",
        "route": source_info.route,
        "feed_title": payload.get("title"),
        "total_items": summary.get("item_count", len(raw_items)),
        "api_endpoint": source_info.route or "/hupu",
        "sample_titles": summary.get("sample_titles"),
        "metrics": summary.get("metrics", {}),
    }

    early = early_return_if_no_match(context, ["ListPanel"], stats)
    if early:
        return early

    normalized: list[Dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or ""
        link = item.get("url") or item.get("link")
        summary_text = short_text(item.get("content_html") or item.get("description"))
        normalized.append(
            {
                "id": item.get("id") or link or title,
                "title": title,
                "link": link,
                "summary": summary_text,
                "published_at": item.get("date_published"),
                "author": first_author(item.get("authors")),
            }
        )

    validated = validate_records("ListPanel", normalized)
    stats["total_items"] = len(validated)

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

    return RouteAdapterResult(records=validated, block_plans=[block_plan], stats=stats)
