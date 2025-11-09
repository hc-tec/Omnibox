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
from ..config_presets import list_panel_size_preset, statistic_card_size_preset


USER_VIDEO_MANIFEST = RouteAdapterManifest(
    components=[
        ComponentManifestEntry(
            component_id="StatisticCard",
            description="展示 UP 主的视频统计数据（总投稿数、总播放量、总点赞数等）",
            cost="low",
            default_selected=True,
            required=False,
            field_requirements=[
                {"field": "metric_title", "description": "指标名称"},
                {"field": "metric_value", "description": "指标数值"},
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
            component_id="ImageGallery",
            description="以图片画廊形式展示视频封面",
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
    notes="展示 B 站 UP 主的视频投稿列表，数据来自 /bilibili/user/video/:uid 接口。支持统计卡片+列表或图片画廊展示。",
)


@route_adapter("/bilibili/user/video", manifest=USER_VIDEO_MANIFEST)
def bilibili_user_video_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    """
    B 站 UP 主投稿适配器

    处理 RSSHub /bilibili/user/video/:uid 返回的 UP 主视频投稿数据。
    数据结构包含视频标题、封面、描述、播放量、点赞数等信息。

    支持三种展示模式：
    1. 统计卡片 + 视频列表（默认）
    2. 视频列表
    3. 图片画廊（视频封面）
    """
    payload = records[0] if records else {}
    raw_items = payload.get("item") or payload.get("items") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    # 提取 UP 主信息
    up_name = payload.get("author") or "UP主"
    up_face = payload.get("image")

    # 构建基础 stats
    stats = {
        "datasource": source_info.datasource or "bilibili",
        "route": source_info.route,
        "feed_title": payload.get("title") or f"{up_name} 的 bilibili 空间",
        "total_items": len(raw_items),
        "api_endpoint": source_info.route or "/bilibili/user/video",
        "up_name": up_name,
        "up_face": up_face,
    }

    # 计算统计数据（如果有足够信息）
    total_play = 0
    total_comment = 0
    total_favorite = 0

    for item in raw_items:
        if isinstance(item, dict):
            # 尝试提取播放量、评论数、收藏数（如果有的话）
            desc = item.get("description") or ""
            # RSSHub 可能在 description 中包含这些信息
            if "播放" in desc:
                try:
                    play_str = desc.split("播放")[0].strip().split()[-1]
                    # 可能包含"万"单位
                    if "万" in play_str:
                        total_play += int(float(play_str.replace("万", "")) * 10000)
                    else:
                        total_play += int(play_str)
                except (ValueError, IndexError):
                    pass

            if "comments" in item:
                total_comment += int(item.get("comments", 0))

    # 如果有统计数据，加入 metrics
    if total_play > 0 or total_comment > 0:
        stats["metrics"] = {
            "total_videos": len(raw_items),
            "total_play": total_play,
            "total_comment": total_comment,
        }

    # 检查是否需要提前返回
    requested = context.requested_components if context else None
    early = early_return_if_no_match(context, ["StatisticCard", "ListPanel", "ImageGallery"], stats)
    if early:
        return early

    # 标准化数据
    normalized_list: list[Dict[str, Any]] = []
    normalized_gallery: list[Dict[str, Any]] = []

    for idx, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue

        title = item.get("title") or ""
        link = item.get("link") or ""
        description = short_text(item.get("description"))
        pub_date = item.get("pubDate")
        author = item.get("author") or up_name

        # 尝试从 description 中提取封面图（RSSHub 通常会在 description 中包含 img 标签）
        cover_url = None
        if description:
            import re

            img_match = re.search(r'<img[^>]+src="([^"]+)"', str(description))
            if img_match:
                cover_url = img_match.group(1)

        # ListPanel 格式
        normalized_list.append(
            {
                "id": link or f"video-{idx}",
                "title": title,
                "link": link,
                "summary": description or "",
                "published_at": pub_date,
                "author": author,
            }
        )

        # ImageGallery 格式（如果有封面）
        if cover_url:
            normalized_gallery.append(
                {
                    "id": link or f"video-{idx}",
                    "image_url": cover_url,
                    "title": title,
                    "description": description or "",
                    "link": link,
                }
            )

    # 构建组件渲染计划
    block_plans = []

    # 1. 统计卡片（如果有 metrics 且被请求）
    if "metrics" in stats and (not requested or "StatisticCard" in requested):
        metrics = stats["metrics"]

        # 总投稿数卡片
        block_plans.append(
            AdapterBlockPlan(
                component_id="StatisticCard",
                props={
                    "title_field": "metric_title",
                    "value_field": "metric_value",
                },
                options=statistic_card_size_preset("normal"),
                title="总投稿",
                confidence=0.9,
            )
        )

        # 如果有播放量数据
        if metrics.get("total_play", 0) > 0:
            block_plans.append(
                AdapterBlockPlan(
                    component_id="StatisticCard",
                    props={
                        "title_field": "metric_title",
                        "value_field": "metric_value",
                    },
                    options=statistic_card_size_preset("normal"),
                    title="总播放",
                    confidence=0.7,
                )
            )

        # 如果有评论数据
        if metrics.get("total_comment", 0) > 0:
            block_plans.append(
                AdapterBlockPlan(
                    component_id="StatisticCard",
                    props={
                        "title_field": "metric_title",
                        "value_field": "metric_value",
                    },
                    options=statistic_card_size_preset("normal"),
                    title="总评论",
                    confidence=0.7,
                )
            )

    # 2. 视频列表或图片画廊
    if not requested or "ListPanel" in requested:
        # 验证 ListPanel 数据契约
        validated_list = validate_records("ListPanel", normalized_list)

        # 使用大型模式（20条，占全行）- 视频列表通常是主要内容
        list_config = list_panel_size_preset("large", show_description=True, show_metadata=True)

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
                title=None,  # 不设置标题，避免重复
                layout_hint=LayoutHint(span=list_config["span"], min_height=400),
                confidence=0.85,
            )
        )

        stats["total_items"] = len(validated_list)
        return RouteAdapterResult(records=validated_list, block_plans=block_plans, stats=stats)

    elif requested and "ImageGallery" in requested and normalized_gallery:
        # 使用图片画廊模式
        validated_gallery = validate_records("ImageGallery", normalized_gallery)

        block_plans.append(
            AdapterBlockPlan(
                component_id="ImageGallery",
                props={
                    "image_field": "image_url",
                    "title_field": "title",
                    "link_field": "link",
                },
                options={
                    "columns": 4,  # 4列网格
                    "span": 12,  # 占满整行
                },
                interactions=[ComponentInteraction(type="open_link", label="观看视频")],
                title=None,
                layout_hint=LayoutHint(span=12, min_height=400),
                confidence=0.75,
            )
        )

        stats["total_items"] = len(validated_gallery)
        return RouteAdapterResult(records=validated_gallery, block_plans=block_plans, stats=stats)

    # 默认返回列表
    validated_list = validate_records("ListPanel", normalized_list)
    stats["total_items"] = len(validated_list)
    return RouteAdapterResult(records=validated_list, block_plans=block_plans, stats=stats)
