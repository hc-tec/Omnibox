from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from api.schemas.panel import LayoutHint, SourceInfo

from services.panel.view_models import validate_records
from .registry import (
    AdapterBlockPlan,
    AdapterExecutionContext,
    ComponentManifestEntry,
    RouteAdapterManifest,
    RouteAdapterResult,
    route_adapter,
)
from .utils import safe_int, short_text, early_return_if_no_match, should_skip_component


GITHUB_TRENDING_MANIFEST = RouteAdapterManifest(
    components=[
        ComponentManifestEntry(
            component_id="ListPanel",
            description="展示热门仓库列表与语言/星标等信息",
            cost="medium",
            default_selected=True,
            required=True,
        ),
        ComponentManifestEntry(
            component_id="LineChart",
            description="按排名绘制 Star 数趋势",
            cost="medium",
            default_selected=False,
            hints={"shared_dataset": True, "min_items": 3},
        ),
    ],
    notes="基于 /github/trending，可覆盖 day/week/month 榜单。",
)


@route_adapter("/github/trending", manifest=GITHUB_TRENDING_MANIFEST)
def github_trending_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    payload = records[0] if records else {}
    raw_items = payload.get("items") or []

    stats = {
        "datasource": source_info.datasource or "github",
        "route": source_info.route,
        "feed_title": payload.get("title"),
        "total_items": len(raw_items),
        "api_endpoint": source_info.route or "/github/trending",
    }

    early = early_return_if_no_match(context, ["ListPanel", "LineChart"], stats)
    if early:
        early.stats.setdefault("top_language", None)
        early.stats.setdefault("top_stars", None)
        return early

    want_list = not should_skip_component(context, "ListPanel")
    want_chart = not should_skip_component(context, "LineChart")

    normalized: List[Dict[str, Any]] = []
    top_stars = 0
    language_counter: Dict[str, int] = {}

    for rank, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue

        extra = item.get("extra") or {}
        title = item.get("title") or extra.get("repo") or ""
        link = item.get("url") or extra.get("url")
        description = item.get("description") or item.get("content_text") or ""
        language = extra.get("language") or item.get("language")
        stars = safe_int(extra.get("stars") or extra.get("star") or item.get("star"))

        if language:
            language_counter[language] = language_counter.get(language, 0) + 1
        if stars:
            top_stars = max(top_stars, stars)

        normalized.append(
            {
                "rank": rank,
                "id": item.get("id") or link or title,
                "title": title,
                "link": link,
                "summary": short_text(description, limit=180),
                "published_at": item.get("date_published") or item.get("published"),
                "language": language,
                "stars": stars,
                "stars_today": safe_int(extra.get("stars_today") or extra.get("star_today")),
                "forks": safe_int(extra.get("forks") or item.get("forks")),
                "x": rank,
                "y": float(stars or 0.0),
                "series": language,
            }
        )

    list_records: List[Dict[str, Any]] = (
        validate_records("ListPanel", normalized) if want_list else []
    )
    chart_records: List[Dict[str, Any]] = (
        validate_records("LineChart", normalized) if want_chart else []
    )

    block_plans: List[AdapterBlockPlan] = []
    if want_list:
        block_plans.append(
            AdapterBlockPlan(
                component_id="ListPanel",
                props={
                    "title_field": "title",
                    "link_field": "link",
                    "description_field": "summary",
                    "pub_date_field": "published_at",
                },
                options={"show_description": True, "span": 12},
                title=payload.get("title") or "GitHub Trending",
                layout_hint=LayoutHint(span=12, min_height=320),
                confidence=0.74,
            )
        )
    if want_chart:
        block_plans.append(
            AdapterBlockPlan(
                component_id="LineChart",
                props={
                    "x_field": "x",
                    "y_field": "y",
                    "series_field": "series",
                },
                options={"area_style": False, "span": 12},
                title=f"{payload.get('title') or 'GitHub Trending'} Stars",
                layout_hint=LayoutHint(span=12, min_height=280),
                confidence=0.65,
            )
        )

    stats.update(
        {
            "total_items": len(list_records or chart_records),
            "top_language": max(language_counter, key=language_counter.get)
            if language_counter
            else None,
            "top_stars": top_stars,
        }
    )

    records_for_result = list_records if list_records else chart_records

    return RouteAdapterResult(records=records_for_result, block_plans=block_plans, stats=stats)
