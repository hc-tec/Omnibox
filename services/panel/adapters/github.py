from __future__ import annotations

from typing import Any, Dict, List, Sequence

from api.schemas.panel import LayoutHint, SourceInfo

from .common import (
    build_list_plan,
    build_list_records,
    collect_feed_items,
    safe_int,
    short_text,
    validate_records,
)
from .registry import AdapterBlockPlan, RouteAdapterResult, route_adapter


@route_adapter("/github/trending")
def github_trending_adapter(
    source_info: SourceInfo, records: Sequence[Dict[str, Any]]
) -> RouteAdapterResult:
    feed_title, items, feed_stats = collect_feed_items(records)

    enriched: List[Dict[str, Any]] = []
    top_stars = 0
    language_counter: Dict[str, int] = {}

    for rank, item in enumerate(items, start=1):
        extra = item.get("extra") or {}
        title = item.get("title") or extra.get("repo")
        if not title:
            continue

        link = item.get("url") or extra.get("url")
        description = (
            item.get("description")
            or item.get("content_text")
            or item.get("content_html")
        )
        language = extra.get("language") or item.get("language")
        stars = safe_int(extra.get("stars") or extra.get("star") or item.get("star"))
        stars_today = safe_int(extra.get("stars_today") or extra.get("star_today"))
        forks = safe_int(extra.get("forks") or item.get("forks"))

        if language:
            language_counter[language] = language_counter.get(language, 0) + 1

        if stars:
            top_stars = max(top_stars, stars)

        enriched.append(
            {
                "rank": rank,
                "id": item.get("id") or link or title,
                "title": title,
                "link": link,
                "summary": short_text(description, limit=180),
                "published_at": item.get("date_published") or item.get("published"),
                "language": language,
                "stars": stars,
                "stars_today": stars_today,
                "forks": forks,
                "author": (title.split("/", 1)[0].strip() if "/" in title else None),
                "raw_excerpt_length": len(description) if isinstance(description, str) else 0,
                "x": rank,
                "y": float(stars or 0.0),
                "series": language,
            }
        )

    validated_list = validate_records("ListPanel", enriched)
    validate_records("LineChart", validated_list)

    stats = {
        "datasource": source_info.datasource or "github",
        "route": source_info.route,
        "feed_title": feed_title,
        "total_items": feed_stats.get("total_items", len(validated_list)),
        "top_language": max(language_counter, key=language_counter.get)
        if language_counter
        else None,
        "top_stars": top_stars,
        "api_endpoint": source_info.route or "/github/trending",
    }

    return RouteAdapterResult(
        records=validated_list,
        block_plans=[
            build_list_plan(feed_title or "GitHub Trending", confidence=0.74),
            AdapterBlockPlan(
                component_id="LineChart",
                props={
                    "x_field": "x",
                    "y_field": "y",
                    "series_field": "series",
                },
                options={"area_style": False, "span": 12},
                title=f"{feed_title or 'GitHub Trending'} Stars",
                layout_hint=LayoutHint(span=12, min_height=280),
                confidence=0.65,
            ),
        ],
        stats=stats,
    )
