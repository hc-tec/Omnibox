from __future__ import annotations

import re
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
from ..config_presets import list_panel_size_preset, statistic_card_size_preset, media_card_size_preset


USER_VIDEO_MANIFEST = RouteAdapterManifest(
    components=[
        ComponentManifestEntry(
            component_id="StatisticCard",
            description="展示 UP 主的视频投稿统计数据（投稿数、播放量、评论量等）",
            cost="low",
            default_selected=True,
            required=False,
            field_requirements=[
                {"field": "metric_title", "description": "指标名称"},
                {"field": "metric_value", "description": "指标值"},
            ],
        ),
        ComponentManifestEntry(
            component_id="ListPanel",
            description="展示 UP 主的视频投稿列表",
            cost="medium",
            default_selected=True,
            required=True,
            field_requirements=[
                {"field": "title", "description": "视频标题"},
                {"field": "link", "description": "视频链接"},
                {"field": "summary", "description": "视频简介"},
                {"field": "published_at", "description": "发布时间"},
            ],
        ),
        ComponentManifestEntry(
            component_id="MediaCardGrid",
            description="展示包含封面、播放量、时长等信息的视频卡片网格",
            cost="medium",
            default_selected=True,
            required=False,
            field_requirements=[
                {"field": "cover_url", "description": "视频封面"},
                {"field": "title", "description": "视频标题"},
                {"field": "link", "description": "视频链接"},
            ],
        ),
        ComponentManifestEntry(
            component_id="ImageGallery",
            description="以图像拼贴形式展示视频封面",
            cost="medium",
            default_selected=False,
            required=False,
            field_requirements=[
                {"field": "image_url", "description": "视频封面"},
                {"field": "title", "description": "视频标题"},
                {"field": "link", "description": "视频链接"},
            ],
        ),
    ],
    notes="展示 B 站 UP 主的视频投稿数据，数据来自 /bilibili/user/video/:uid。支持统计卡片、列表、卡片网格以及封面画廊等多种展示方式。",
)


def _parse_count(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            stripped = value.replace(",", '').strip()
            if stripped.endswith('万'):
                return float(stripped[:-1]) * 10000
            return float(stripped)
        return float(value)
    except (ValueError, TypeError):
        return None


def _format_duration(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        seconds = int(value)
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    except (ValueError, TypeError):
        if isinstance(value, str) and value:
            return value
        return None


@route_adapter("/bilibili/user/video", manifest=USER_VIDEO_MANIFEST)
def bilibili_user_video_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    payload = records[0] if records else {}
    raw_items = payload.get("item") or payload.get("items") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    up_name = payload.get("title") or "UP主"
    up_face = payload.get("image")

    stats = {
        "datasource": source_info.datasource or "bilibili",
        "route": source_info.route,
        "feed_title": payload.get("title") or f"{up_name} 的 bilibili 空间",
        "total_items": len(raw_items),
        "api_endpoint": source_info.route or "/bilibili/user/video",
        "up_name": up_name,
        "up_face": up_face,
    }

    total_play = 0
    total_comment = 0

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        play_count = _parse_count(item.get("play") or item.get("stat", {}).get("view"))
        if play_count:
            total_play += play_count
        comment_count = _parse_count(item.get("stat", {}).get("reply"))
        if comment_count:
            total_comment += comment_count

    if total_play > 0 or total_comment > 0:
        stats["metrics"] = {
            "total_videos": len(raw_items),
            "total_play": total_play,
            "total_comment": total_comment,
        }

    requested = context.requested_components if context else None
    early = early_return_if_no_match(
        context,
        ["StatisticCard", "ListPanel", "ImageGallery"],
        stats,
    )
    if early:
        return early

    normalized_cards: list[Dict[str, Any]] = []
    normalized_gallery: list[Dict[str, Any]] = []

    for idx, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue

        title = item.get("title") or ""
        link = item.get("url") or ""
        description = short_text(item.get("description"))
        pub_date = item.get("date_published")
        author = item.get("authors")[0]["name"] or up_name
        content_html = item.get("content_html")
        cover_url = None
        if content_html:
            img_match = re.search(r'<img[^>]+src="([^"]+)"', str(content_html))
            if img_match:
                cover_url = img_match.group(1)

        view_count = _parse_count(item.get("play") or item.get("stat", {}).get("view"))
        like_count = _parse_count(item.get("stat", {}).get("like"))
        duration_text = _format_duration(item.get("duration"))

        badges = []
        if item.get("typename"):
            badges.append(str(item.get("typename")))
        if item.get("bvid"):
            bvid = str(item.get("bvid"))
            badges.append(bvid if bvid.startswith("BV") else f"BV{bvid}")

        record = {
            "id": link or f"video-{idx}",
            "title": title,
            "link": link,
            "summary": description or "",
            "published_at": pub_date,
            "author": author,
            "cover_url": cover_url,
            "duration": duration_text,
            "view_count": view_count,
            "like_count": like_count,
            "badges": badges,
        }
        normalized_cards.append(record)

        if cover_url:
            normalized_gallery.append(
                {
                    "id": record["id"],
                    "image_url": cover_url,
                    "title": title,
                    "description": description or "",
                    "link": link,
                }
            )

    block_plans: list[AdapterBlockPlan] = []
    list_records = validate_records("ListPanel", normalized_cards)
    # 确认卡片栅格契约，虽然最终数据仍由 ListPanel 承载
    validate_records("MediaCardGrid", list_records)

    if "metrics" in stats and (not requested or "StatisticCard" in requested):
        metrics = stats["metrics"]
        block_plans.append(
            AdapterBlockPlan(
                component_id="StatisticCard",
                props={"title_field": "metric_title", "value_field": "metric_value"},
                options=statistic_card_size_preset("normal"),
                title=f"{stats['feed_title']} 总投稿",
                confidence=0.9,
            )
        )
        if metrics.get("total_play", 0) > 0:
            block_plans.append(
                AdapterBlockPlan(
                    component_id="StatisticCard",
                    props={"title_field": "metric_title", "value_field": "metric_value"},
                    options=statistic_card_size_preset("normal"),
                    title="总播放量",
                    confidence=0.75,
                )
            )
        if metrics.get("total_comment", 0) > 0:
            block_plans.append(
                AdapterBlockPlan(
                    component_id="StatisticCard",
                    props={"title_field": "metric_title", "value_field": "metric_value"},
                    options=statistic_card_size_preset("normal"),
                    title="总评论数",
                    confidence=0.75,
                )
            )

    media_needed = requested is None or "MediaCardGrid" in requested
    media_config = media_card_size_preset("normal")
    media_max_items = min(len(normalized_cards), 30)
    media_config["max_items"] = media_max_items
    if media_max_items >= 18:
        media_config["columns"] = 5 if media_max_items >= 25 else 4
    media_child_plan = AdapterBlockPlan(
        component_id="MediaCardGrid",
        props={
            "title_field": "title",
            "link_field": "link",
            "cover_field": "cover_url",
            "author_field": "author",
            "summary_field": "summary",
            "duration_field": "duration",
            "view_count_field": "view_count",
            "like_count_field": "like_count",
            "badges_field": "badges",
        },
        options=media_config,
        interactions=[ComponentInteraction(type="open_link", label="观看视频")],
        title=f"{up_name} 最新投稿",
        confidence=0.82,
    )

    list_needed = (
        requested is None
        or "ListPanel" in requested
        or (requested is not None and "MediaCardGrid" in requested)
    )
    if list_needed:
        list_config = list_panel_size_preset("full", show_description=True, show_metadata=True)
        list_config.setdefault("horizontal_scroll", False)
        list_config.setdefault("item_min_width", 260)
        list_config["max_items"] = min(len(list_records), list_config.get("max_items", len(list_records)))
        if len(list_records) > 12:
            list_config["horizontal_scroll"] = True
            list_config["item_min_width"] = 260
            list_config["max_items"] = min(len(list_records), 18)
        children = [media_child_plan] if media_child_plan else None
        block_plans.append(
            AdapterBlockPlan(
                component_id="ListPanel",
                props={
                    "title_field": "title",
                    "link_field": "link",
                    "description_field": "summary",
                    "pub_date_field": "published_at",
                },
                options=list_config,
                interactions=[ComponentInteraction(type="open_link", label="观看视频")],
                title=stats["feed_title"],
                layout_hint=LayoutHint(
                    layout_size=list_config.get("layout_size"),
                    span=list_config.get("span"),
                    min_height=360,
                ),
                confidence=0.8,
                children=children,
            )
        )

    if (not requested or "ImageGallery" in requested) and normalized_gallery:
        validated_gallery = validate_records("ImageGallery", normalized_gallery)
        block_plans.append(
            AdapterBlockPlan(
                component_id="ImageGallery",
                props={"image_field": "image_url", "title_field": "title", "link_field": "link"},
                options={"columns": 4, "span": 12, "layout_size": "full"},
                interactions=[ComponentInteraction(type="open_link", label="观看视频")],
                title=f"{up_name} 精选封面",
                layout_hint=LayoutHint(layout_size="full", span=12, min_height=380),
                confidence=0.7,
            )
        )

    stats["total_items"] = len(list_records)
    return RouteAdapterResult(records=list_records, block_plans=block_plans, stats=stats)
