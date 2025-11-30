from __future__ import annotations

import html
import re
from typing import Any, Dict, Optional, Sequence

from api.schemas.panel import ComponentInteraction, LayoutHint, SourceInfo

from services.panel.view_models import validate_records
from ...dataset_schema import DatasetSchemaDescriptor, DatasetSchemaField
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


HOT_SEARCH_SCHEMA = DatasetSchemaDescriptor(
    schema_id="bilibili.hot_search.v1",
    display_name="B站热搜榜",
    description="标准化后的热搜条目字段",
    primary_key="id",
    fields=[
        DatasetSchemaField(
            name="id",
            type="string",
            description="内部唯一 ID",
            required=True,
            sortable=True,
        ),
        DatasetSchemaField(
            name="title",
            type="string",
            description="热搜关键词",
            required=True,
            filterable=True,
        ),
        DatasetSchemaField(
            name="link",
            type="string",
            description="跳转链接",
        ),
        DatasetSchemaField(
            name="summary",
            type="string",
            description="热搜关键词摘要/说明",
        ),
        DatasetSchemaField(
            name="published_at",
            type="datetime",
            description="发布时间（热搜无时间时为空）",
        ),
        DatasetSchemaField(
            name="image_url",
            type="string",
            description="热搜卡片配图",
        ),
    ],
    tags=["hot_search", "bilibili"],
)


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
    schema=HOT_SEARCH_SCHEMA,
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
    feed_title = payload.get("title") or "B站热搜"
    stats = {
        "datasource": source_info.datasource or "bilibili",
        "route": source_info.route,
        "feed_title": feed_title,
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
        summary_text, image_url = _parse_content_html(item.get("content_html"))
        description = short_text(summary_text or keyword)

        normalized.append(
            {
                "id": f"hot-search-{idx}",
                "title": f"#{idx} {keyword}",  # 添加排名前缀
                "link": link,
                "summary": description,
                "published_at": None,  # 热搜没有发布时间
                "image_url": image_url,
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
        title=None,
        layout_hint=LayoutHint(
            layout_size=size_config.get("layout_size"),
            span=size_config.get("span"),
            min_height=240,
        ),
        confidence=1.0,
    )

    stats["total_items"] = len(validated)

    return RouteAdapterResult(records=validated, block_plans=[block_plan], stats=stats)


def _parse_content_html(content_html: Optional[str]) -> tuple[str, Optional[str]]:
    """
    从 content_html 中提取纯文本描述与配图链接。
    """
    if not content_html:
        return "", None

    image_url: Optional[str] = None
    match = re.search(r'<img[^>]+src="([^"]+)"', content_html)
    if match:
        image_url = match.group(1)

    text = content_html.replace("<br/>", " ").replace("<br>", " ")
    text = re.sub(r"<img[^>]*>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = " ".join(text.split())
    return text, image_url
