"""
测试 bilibili 热搜适配器
"""

import services.panel.adapters as adapters
from api.schemas.panel import SourceInfo


BILIBILI_HOT_SEARCH_SAMPLE = {
    "title": "热门",
    "link": "https://api.bilibili.com/x/web-interface/wbi/search/square",
    "description": "bilibili热搜",
    "item": [
        {
            "title": "原神新版本",
            "description": "原神新版本<br><img src=\"https://i0.hdslb.com/bfs/activity-plat/static/20220614/eaf2dd8cbe7f8fa78dda480a44a4d86b/icon.png\">",
            "link": "https://search.bilibili.com/all?keyword=%E5%8E%9F%E7%A5%9E%E6%96%B0%E7%89%88%E6%9C%AC",
            "url": "https://search.bilibili.com/all?keyword=%E5%8E%9F%E7%A5%9E%E6%96%B0%E7%89%88%E6%9C%AC",
        },
        {
            "title": "新番推荐",
            "description": "新番推荐",
            "link": "https://search.bilibili.com/all?keyword=%E6%96%B0%E7%95%AA%E6%8E%A8%E8%8D%90",
            "url": "https://search.bilibili.com/all?keyword=%E6%96%B0%E7%95%AA%E6%8E%A8%E8%8D%90",
        },
        {
            "title": "技术分享",
            "description": "技术分享<br>",
            "link": "https://search.bilibili.com/all?keyword=%E6%8A%80%E6%9C%AF%E5%88%86%E4%BA%AB",
            "url": "https://search.bilibili.com/all?keyword=%E6%8A%80%E6%9C%AF%E5%88%86%E4%BA%AB",
        },
    ],
}


def test_bilibili_hot_search_adapter():
    """测试 bilibili 热搜适配器数据转换"""
    adapter = adapters.get_route_adapter("/bilibili/hot-search")
    source_info = SourceInfo(
        datasource="rsshub",
        route="/bilibili/hot-search",
        params={},
        fetched_at=None,
        request_id=None,
    )

    result = adapter(source_info, [BILIBILI_HOT_SEARCH_SAMPLE])

    # 验证返回的记录
    assert len(result.records) == 3
    first = result.records[0]
    assert first["id"] == "hot-search-1"
    assert first["title"] == "#1 原神新版本"  # 包含排名前缀
    assert first["link"].startswith("https://search.bilibili.com")
    assert "原神新版本" in first["summary"]

    # 验证统计信息
    assert result.stats["datasource"] == "rsshub"
    assert result.stats["route"] == "/bilibili/hot-search"
    assert result.stats["api_endpoint"] == "/bilibili/hot-search"
    assert result.stats["feed_title"] == "热门"
    assert result.stats["total_items"] == 3

    # 验证组件计划
    assert len(result.block_plans) == 1
    plan = result.block_plans[0]
    assert plan.component_id == "ListPanel"
    assert plan.props["title_field"] == "title"
    assert plan.props["link_field"] == "link"
    assert plan.title is None  # 不设置标题，避免与外层标题重复

    # 验证使用了 normal 预设（10条，占半行）
    assert plan.options["max_items"] == 10
    assert plan.options["span"] == 6
    assert plan.options["compact"] is False


def test_bilibili_hot_search_manifest():
    """测试 bilibili 热搜的组件清单"""
    manifest = adapters.get_route_manifest("/bilibili/hot-search")
    assert manifest is not None

    component_ids = {entry.component_id for entry in manifest.components}
    assert component_ids == {"ListPanel"}

    list_panel = next(entry for entry in manifest.components if entry.component_id == "ListPanel")
    assert list_panel.required is True
    assert list_panel.cost == "low"
    assert list_panel.default_selected is True
