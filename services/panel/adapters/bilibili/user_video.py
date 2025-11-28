from __future__ import annotations

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
from ..utils import first_author, short_text, early_return_if_no_match
from ..config_presets import list_panel_size_preset, statistic_card_size_preset, media_card_size_preset


USER_VIDEO_SCHEMA = DatasetSchemaDescriptor(
    schema_id="bilibili.user_video.v1",
    display_name="B站 UP 主投稿",
    description="UP 主投稿视频的标准化字段",
    primary_key="id",
    time_field="published_at",
    fields=[
        DatasetSchemaField(name="id", type="string", description="视频唯一标识", required=True, sortable=True),
        DatasetSchemaField(name="title", type="string", description="视频标题", required=True, filterable=True),
        DatasetSchemaField(name="link", type="string", description="视频链接", required=True),
        DatasetSchemaField(name="summary", type="string", description="简介/描述"),
        DatasetSchemaField(name="published_at", type="datetime", description="发布时间", sortable=True),
        DatasetSchemaField(name="author", type="string", description="作者/UP 主名称", filterable=True),
        DatasetSchemaField(name="cover_url", type="string", description="封面图片 URL"),
        DatasetSchemaField(name="duration", type="string", description="视频时长（MM:SS）"),
        DatasetSchemaField(name="duration_seconds", type="number", description="视频时长（秒）"),
        DatasetSchemaField(name="view_count", type="number", description="播放量", aggregatable=True, sortable=True),
        DatasetSchemaField(name="like_count", type="number", description="点赞数", aggregatable=True),
        DatasetSchemaField(name="badges", type="array", description="标签/徽章"),
        DatasetSchemaField(name="player_url", type="string", description="可直接访问的播放器地址"),
        DatasetSchemaField(name="subtitle_languages", type="array", description="字幕语言标签"),
        DatasetSchemaField(name="image_url", type="string", description="封面图（用于画廊组件）"),
    ],
    tags=["bilibili", "video"],
)


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
                {"field": "player_url", "description": "外部播放器链接"},
                {"field": "view_count", "description": "播放量"},
                {"field": "duration", "description": "视频时长"},
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
    notes="展示 B 站 UP 主的视频投稿数据。基于 RSSHub JSONFeed (/bilibili/user/video/:uid)，解析 content_html/attachments 中的封面、播放器链接、字幕信息等结构化字段，支持列表、卡片和画廊多种呈现方式。",
    schema=USER_VIDEO_SCHEMA,
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


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            return int(float(value.strip()))
        return int(value)
    except (ValueError, TypeError):
        return None


def _extract_cover_image(item: Dict[str, Any], content_html: Optional[str]) -> Optional[str]:
    for key in ("cover", "cover_url", "banner_image", "image", "thumbnail"):
        candidate = item.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    if content_html:
        img_match = re.search(r'<img[^>]+src="([^"]+)"', str(content_html))
        if img_match:
            return img_match.group(1)
    return None


def _extract_media_metadata(item: Dict[str, Any], content_html: Optional[str]) -> tuple[Optional[str], Optional[int], list[str]]:
    attachments = item.get("attachments") or []
    if isinstance(attachments, dict):
        attachments = [attachments]
    player_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    subtitle_labels: list[str] = []

    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        mime_type = str(attachment.get("mime_type") or "").lower()
        url = attachment.get("url")
        duration_candidate = attachment.get("duration_in_seconds") or attachment.get("duration")
        duration_value = _coerce_int(duration_candidate)

        if not player_url and mime_type.startswith("text/html"):
            player_url = url
            if duration_value is not None:
                duration_seconds = duration_value

        if duration_seconds is None and duration_value is not None:
            duration_seconds = duration_value

        title = attachment.get("title")
        language = attachment.get("language")
        if (
            "srt" in mime_type
            or "subtitle" in mime_type
            or (isinstance(title, str) and "字幕" in title)
        ):
            label = title or language
            if label:
                subtitle_labels.append(str(label))

    if not player_url and content_html:
        iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', str(content_html))
        if iframe_match:
            player_url = iframe_match.group(1)

    return player_url, duration_seconds, subtitle_labels


def _extract_bvid(item: Dict[str, Any], link: str) -> Optional[str]:
    bvid = item.get("bvid")
    if isinstance(bvid, str) and bvid:
        return bvid if bvid.startswith("BV") else f"BV{bvid}"
    if link:
        match = re.search(r"(BV[a-zA-Z0-9]+)", link)
        if match:
            return match.group(1)
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

    fallback_author = None
    if raw_items:
        first_item = raw_items[0]
        fallback_author = first_author(first_item.get("authors")) or first_item.get("author")

    up_name = payload.get("author") or payload.get("title") or fallback_author or "UP主"
    if isinstance(up_name, str) and up_name.endswith(" 的 bilibili 空间"):
        up_name = up_name.replace(" 的 bilibili 空间", "")
    up_face = payload.get("image") or payload.get("icon")

    stats = {
        "datasource": source_info.datasource or "bilibili",
        "route": source_info.route,
        "feed_title": payload.get("title") or f"{up_name} 的 bilibili 空间",
        "total_items": len(raw_items),
        "api_endpoint": source_info.route or "/bilibili/user/video",
        "up_name": up_name,
        "up_face": up_face,
        "profile_url": payload.get("home_page_url"),
        "language": payload.get("language"),
    }

    total_play = 0
    total_comment = 0
    total_duration_seconds = 0
    duration_count = 0
    longest_duration_seconds = 0
    subtitle_video_count = 0

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        play_count = _parse_count(item.get("play") or item.get("stat", {}).get("view"))
        if play_count:
            total_play += play_count
        comment_count = _parse_count(item.get("stat", {}).get("reply"))
        if comment_count:
            total_comment += comment_count

    metrics: Dict[str, Any] = {"total_videos": len(raw_items)}
    if total_play > 0:
        metrics["total_play"] = total_play
    if total_comment > 0:
        metrics["total_comment"] = total_comment


    requested = context.requested_components if context else None
    early = early_return_if_no_match(
        context,
        ["StatisticCard", "ListPanel", "ImageGallery", "MediaCardGrid"],
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
        link = item.get("url") or item.get("link") or ""
        description_source = (
            item.get("description")
            or item.get("summary")
            or item.get("content_html")
            or item.get("content_text")
        )
        description = short_text(description_source)
        pub_date = item.get("date_published") or item.get("pubDate")
        author = first_author(item.get("authors")) or item.get("author") or up_name
        content_html = item.get("content_html")
        cover_url = _extract_cover_image(item, content_html)
        player_url, duration_seconds, subtitle_labels = _extract_media_metadata(item, content_html)

        if duration_seconds:
            total_duration_seconds += duration_seconds
            duration_count += 1
            longest_duration_seconds = max(longest_duration_seconds, duration_seconds)

        if subtitle_labels:
            subtitle_video_count += 1

        view_count = _parse_count(item.get("play") or item.get("stat", {}).get("view"))
        like_count = _parse_count(item.get("stat", {}).get("like"))
        duration_source = item.get("duration") or duration_seconds
        duration_text = _format_duration(duration_source)

        badges: list[str] = []
        if item.get("typename"):
            badges.append(str(item.get("typename")))
        bvid = _extract_bvid(item, link)
        if bvid:
            badges.append(bvid)
        for subtitle in subtitle_labels:
            if subtitle and subtitle not in badges:
                badges.append(subtitle)

        record = {
            "id": item.get("id") or link or f"video-{idx}",
            "title": title,
            "link": link,
            "summary": description or "",
            "published_at": pub_date,
            "author": author,
            "cover_url": cover_url,
            "duration": duration_text,
            "duration_seconds": duration_seconds,
            "view_count": view_count,
            "like_count": like_count,
            "badges": badges,
            "player_url": player_url,
            "subtitle_languages": subtitle_labels or None,
        }
        normalized_cards.append(record)

        if cover_url:
            normalized_gallery.append(
                {
                    "id": record["id"],
                    "image_url": cover_url,
                    "thumbnail_url": cover_url,
                    "title": title,
                    "description": description or "",
                    "link": link,
                }
            )

    if normalized_cards and duration_count:
        avg_seconds = max(1, int(round(total_duration_seconds / duration_count)))
        metrics["avg_duration_seconds"] = avg_seconds
        metrics["avg_duration_text"] = _format_duration(avg_seconds)
        metrics["longest_duration_seconds"] = longest_duration_seconds
        metrics["longest_duration_text"] = _format_duration(longest_duration_seconds)
    if subtitle_video_count:
        metrics["videos_with_subtitles"] = subtitle_video_count
    stats["metrics"] = metrics

    block_plans: list[AdapterBlockPlan] = []
    list_records = validate_records("ListPanel", normalized_cards)
    # 确认卡片栅格契约，虽然最终数据仍由 ListPanel 承载
    validate_records("MediaCardGrid", list_records)

    metrics_payload = stats.get("metrics") or {}
    if metrics_payload and (not requested or "StatisticCard" in requested):
        block_plans.append(
            AdapterBlockPlan(
                component_id="StatisticCard",
                props={"title_field": "metric_title", "value_field": "metric_value"},
                options=statistic_card_size_preset("normal"),
                title="投稿数量",
                confidence=0.9,
            )
        )
        if metrics_payload.get("avg_duration_seconds"):
            block_plans.append(
                AdapterBlockPlan(
                    component_id="StatisticCard",
                    props={"title_field": "metric_title", "value_field": "metric_value"},
                    options=statistic_card_size_preset("normal"),
                    title="平均时长",
                    confidence=0.75,
                )
            )
        if metrics_payload.get("videos_with_subtitles"):
            block_plans.append(
                AdapterBlockPlan(
                    component_id="StatisticCard",
                    props={"title_field": "metric_title", "value_field": "metric_value"},
                    options=statistic_card_size_preset("normal"),
                    title="含字幕视频",
                    confidence=0.75,
                )
            )

    media_child_plan = None
    if requested is None or "MediaCardGrid" in requested:
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
        gallery_columns = max(1, min(4, len(validated_gallery)))
        block_plans.append(
            AdapterBlockPlan(
                component_id="ImageGallery",
                props={"image_field": "image_url", "title_field": "title", "link_field": "link"},
                options={"columns": gallery_columns, "span": 12, "layout_size": "full"},
                interactions=[ComponentInteraction(type="open_link", label="观看视频")],
                title=f"{up_name} 精选封面",
                layout_hint=LayoutHint(layout_size="full", span=12, min_height=380),
                confidence=0.7,
            )
        )

    stats["total_items"] = len(list_records)
    return RouteAdapterResult(records=list_records, block_plans=block_plans, stats=stats)
