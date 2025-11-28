from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from api.schemas.panel import LayoutHint, SourceInfo

from services.panel.view_models import validate_records
from ..dataset_schema import DatasetSchemaDescriptor, DatasetSchemaField
from .registry import (
    AdapterBlockPlan,
    AdapterExecutionContext,
    ComponentManifestEntry,
    RouteAdapterManifest,
    RouteAdapterResult,
    route_adapter,
)
from .utils import safe_int, short_text, early_return_if_no_match, should_skip_component


TRENDING_SCHEMA = DatasetSchemaDescriptor(
    schema_id="github.trending.v1",
    display_name="GitHub Trending",
    description="GitHub Trending 榜单字段",
    primary_key="id",
    time_field="published_at",
    fields=[
        DatasetSchemaField(name="id", type="string", description="仓库唯一 ID", required=True, sortable=True),
        DatasetSchemaField(name="title", type="string", description="项目名称", required=True, filterable=True),
        DatasetSchemaField(name="link", type="string", description="仓库链接", required=True),
        DatasetSchemaField(name="summary", type="string", description="简介"),
        DatasetSchemaField(name="published_at", type="datetime", description="更新时间"),
        DatasetSchemaField(name="language", type="string", description="主要语言", filterable=True),
        DatasetSchemaField(name="stars", type="number", description="Star 总数", aggregatable=True, sortable=True),
        DatasetSchemaField(name="stars_today", type="number", description="今日 Star"),
        DatasetSchemaField(name="forks", type="number", description="Fork 数"),
        DatasetSchemaField(name="rank", type="integer", description="榜单排名", sortable=True),
        DatasetSchemaField(name="x", type="number", description="图表 X 轴（排名）"),
        DatasetSchemaField(name="y", type="number", description="图表 Y 轴（Star）"),
        DatasetSchemaField(name="series", type="string", description="图表分组（语言）"),
    ],
    tags=["github", "trending", "developer"],
)


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
    schema=TRENDING_SCHEMA,
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
                options={"show_description": True, "span": 12, "layout_size": "full"},
                title=payload.get("title") or "GitHub Trending",
                layout_hint=LayoutHint(layout_size="full", span=12, min_height=320),
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
                options={"area_style": False, "span": 12, "layout_size": "full"},
                title=f"{payload.get('title') or 'GitHub Trending'} Stars",
                layout_hint=LayoutHint(layout_size="full", span=12, min_height=280),
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
