"""
测试 bilibili UP 主投稿适配器
"""

import services.panel.adapters as adapters
from api.schemas.panel import SourceInfo

from .sample_payloads import BILIBILI_USER_VIDEO_SAMPLE


def test_bilibili_user_video_adapter():
    """测试 bilibili UP 主投稿适配器数据转换"""
    adapter = adapters.get_route_adapter("/bilibili/user/video")
    source_info = SourceInfo(
        datasource="rsshub",
        route="/bilibili/user/video/2267573",
        params={},
        fetched_at=None,
        request_id=None,
    )

    result = adapter(source_info, [BILIBILI_USER_VIDEO_SAMPLE])

    # 验证返回的记录
    assert len(result.records) == 2
    first = result.records[0]
    assert first["title"].startswith("英雄联盟总决赛")
    assert first["link"] == "https://www.bilibili.com/video/BV1uDCrBkEiw"
    assert first["author"] == "影视飓风"
    assert first["published_at"] == "2025-11-18T03:00:00.000Z"
    assert first["player_url"].startswith("https://www.bilibili.com/blackboard/newplayer.html")
    assert first["duration"] == "13:03"
    assert "字幕 - 日本語" in first["badges"]

    # 验证统计信息
    assert result.stats["datasource"] == "rsshub"
    assert result.stats["total_items"] == 2
    assert result.stats["profile_url"] == "https://space.bilibili.com/946974"
    assert result.stats["language"] == "zh-cn"
    assert result.stats["up_name"] == "影视飓风"
    assert result.stats["metrics"]["total_videos"] == 2
    assert result.stats["metrics"]["videos_with_subtitles"] == 1
    assert result.stats["metrics"]["avg_duration_text"] == "9:28"

    # 验证组件计划（默认应该是 ListPanel）
    assert len(result.block_plans) >= 1
    list_plan = next((p for p in result.block_plans if p.component_id == "ListPanel"), None)
    assert list_plan is not None
    assert list_plan.props["title_field"] == "title"
    assert list_plan.props["link_field"] == "link"

    media_child = list_plan.children[0] if list_plan.children else None
    if media_child:
        assert media_child.component_id == "MediaCardGrid"
    assert any(plan.component_id == "ImageGallery" for plan in result.block_plans)


def test_bilibili_user_video_manifest():
    """测试 bilibili UP 主投稿的组件清单"""
    manifest = adapters.get_route_manifest("/bilibili/user/video")
    assert manifest is not None

    component_ids = {entry.component_id for entry in manifest.components}
    assert {"ListPanel", "StatisticCard", "ImageGallery", "MediaCardGrid"} <= component_ids

    # 验证 ListPanel 是必需的
    list_panel = next(entry for entry in manifest.components if entry.component_id == "ListPanel")
    assert list_panel.required is True
    assert list_panel.cost == "medium"

    schema_fields = {field.name for field in manifest.schema.fields}
    assert {"player_url", "duration_seconds", "subtitle_languages"} <= schema_fields
