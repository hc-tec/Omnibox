from __future__ import annotations

from typing import Any, Dict, List, Sequence

from api.schemas.panel import LayoutHint, SourceInfo

from services.panel.view_models import validate_records
from .registry import AdapterBlockPlan, RouteAdapterResult, route_adapter
from .utils import safe_int, short_text


@route_adapter("/github/trending")
def github_trending_adapter(
    source_info: SourceInfo, records: Sequence[Dict[str, Any]]
) -> RouteAdapterResult:
    payload = records[0] if records else {}
    raw_items = payload.get("items") or []

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

    validated = validate_records("ListPanel", normalized)
    validate_records("LineChart", validated)

    list_plan = AdapterBlockPlan(
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
    chart_plan = AdapterBlockPlan(
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

    stats = {
        "datasource": source_info.datasource or "github",
        "route": source_info.route,
        "feed_title": payload.get("title"),
        "total_items": len(validated),
        "top_language": max(language_counter, key=language_counter.get)
        if language_counter
        else None,
        "top_stars": top_stars,
        "api_endpoint": source_info.route or "/github/trending",
    }

    return RouteAdapterResult(records=validated, block_plans=[list_plan, chart_plan], stats=stats)
