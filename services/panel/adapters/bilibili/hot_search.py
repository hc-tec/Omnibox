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
from ..utils import short_text, early_return_if_no_match
from ..config_presets import list_panel_size_preset


HOT_SEARCH_MANIFEST = RouteAdapterManifest(
    components=[
        ComponentManifestEntry(
            component_id="ListPanel",
            description="展示 B 站实时热搜榜单",
            cost="low",
            default_selected=True,
            required=True,
            field_requirements=[
                {"field": "title", "description": "热搜关键词"},
                {"field": "link", "description": "搜索链接"},
                {"field": "summary", "description": "热搜关键词及图标"},
            ],
        )
    ],
    notes="展示 B 站实时热搜榜单，数据来自 /bilibili/hot-search 接口。",
)


@route_adapter("/bilibili/hot-search", manifest=HOT_SEARCH_MANIFEST)
def bilibili_hot_search_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    """
    B 站热搜适配器

    处理 RSSHub /bilibili/hot-search 返回的热搜榜单数据。
    数据结构包含热搜关键词、图标、搜索链接等信息。
    """
    payload = records[0] if records else {}
    raw_items = payload.get("item") or payload.get("items") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    # 先构建基础 stats（无论是否提前返回都需要）
    stats = {
        "datasource": source_info.datasource or "bilibili",
        "route": source_info.route,
        "feed_title": payload.get("title") or "B站热搜",
        "total_items": len(raw_items),
        "api_endpoint": source_info.route or "/bilibili/hot-search",
    }

    # 检查是否需要提前返回
    early = early_return_if_no_match(context, ["ListPanel"], stats)
    if early:
        return early

    # 标准化数据：为每个热搜添加排名信息
    normalized: list[Dict[str, Any]] = []
    for idx, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue

        keyword = item.get("title") or ""
        link = item.get("url") or ""
        description = short_text(item.get("description"))

        normalized.append(
            {
                "id": f"hot-search-{idx}",
                "title": f"#{idx} {keyword}",  # 添加排名前缀
                "link": link,
                "summary": description or keyword,
                "published_at": None,  # 热搜没有发布时间
            }
        )

    # 验证数据契约
    validated = validate_records("ListPanel", normalized)

    # 构建组件渲染计划 - 使用标准模式预设（10条）
    # AI planner 可以选择不同的尺寸预设：
    # - "compact": 紧凑（5条，占1/3行）
    # - "normal": 标准（10条，占半行）
    # - "large": 大型（20条，占全行）
    size_config = list_panel_size_preset("normal")

    block_plan = AdapterBlockPlan(
        component_id="ListPanel",
        props={
            "title_field": "title",
            "link_field": "link",
            "description_field": "summary",
            "pub_date_field": "published_at",
        },
        options=size_config,
        interactions=[ComponentInteraction(type="open_link", label="搜索关键词")],
        title=None,  # 不设置标题，避免与外层标题重复
        layout_hint=LayoutHint(span=size_config["span"], min_height=240),
        confidence=0.75,
    )

    stats["total_items"] = len(validated)

    return RouteAdapterResult(records=validated, block_plans=[block_plan], stats=stats)
