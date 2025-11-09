"""
测试 bilibili UP 主投稿适配器
"""

import services.panel.adapters as adapters
from api.schemas.panel import SourceInfo


BILIBILI_USER_VIDEO_SAMPLE = {
    "title": "某UP主 的 bilibili 空间",
    "link": "https://space.bilibili.com/2267573",
    "description": "某UP主 的 bilibili 空间",
    "author": "某UP主",
    "image": "https://i2.hdslb.com/bfs/face/example.jpg",
    "item": [
        {
            "title": "【教程】如何使用Python",
            "description": '<img src="https://i2.hdslb.com/bfs/archive/cover1.jpg"><br>这是一个Python教程视频<br>播放 10.5万 · 弹幕 234',
            "link": "https://www.bilibili.com/video/BV1xx411c7mD",
            "pubDate": "2024-01-15T10:30:00Z",
            "author": "某UP主",
            "comments": 156,
        },
        {
            "title": "【技术分享】Vue3最佳实践",
            "description": '<img src="https://i2.hdslb.com/bfs/archive/cover2.jpg"><br>Vue3开发经验分享<br>播放 8.3万 · 弹幕 189',
            "link": "https://www.bilibili.com/video/BV1yy4y1B7XX",
            "pubDate": "2024-01-12T14:20:00Z",
            "author": "某UP主",
            "comments": 234,
        },
        {
            "title": "【编程日常】Vlog #1",
            "description": '<img src="https://i2.hdslb.com/bfs/archive/cover3.jpg"><br>记录我的编程日常<br>播放 5.2万 · 弹幕 98',
            "link": "https://www.bilibili.com/video/BV1zz4y1B7AA",
            "pubDate": "2024-01-10T09:15:00Z",
            "author": "某UP主",
            "comments": 89,
        },
    ],
}


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
    assert len(result.records) == 3
    first = result.records[0]
    assert first["title"] == "【教程】如何使用Python"
    assert first["link"] == "https://www.bilibili.com/video/BV1xx411c7mD"
    assert first["author"] == "某UP主"
    assert first["published_at"] == "2024-01-15T10:30:00Z"

    # 验证统计信息
    assert result.stats["datasource"] == "rsshub"
    assert result.stats["total_items"] == 3
    # up_name 和 up_face 是可选的统计信息
    if "up_name" in result.stats:
        assert result.stats["up_name"] == "某UP主"

    # 验证组件计划（默认应该是 ListPanel）
    assert len(result.block_plans) >= 1
    list_plan = next((p for p in result.block_plans if p.component_id == "ListPanel"), None)
    assert list_plan is not None
    assert list_plan.props["title_field"] == "title"
    assert list_plan.props["link_field"] == "link"

    # 验证使用了配置（可能包含 show_description 和 span）
    assert "show_description" in list_plan.options or "span" in list_plan.options


def test_bilibili_user_video_manifest():
    """测试 bilibili UP 主投稿的组件清单"""
    manifest = adapters.get_route_manifest("/bilibili/user/video")
    assert manifest is not None

    component_ids = {entry.component_id for entry in manifest.components}
    assert "ListPanel" in component_ids
    assert "StatisticCard" in component_ids
    assert "ImageGallery" in component_ids

    # 验证 ListPanel 是必需的
    list_panel = next(entry for entry in manifest.components if entry.component_id == "ListPanel")
    assert list_panel.required is True
    assert list_panel.cost == "medium"
