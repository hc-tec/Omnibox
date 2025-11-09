import importlib

import pytest

from api.schemas.panel import SourceInfo
import services.panel.adapters as adapters
import services.panel.adapters.registry as adapter_registry_module
import services.panel.adapters.hupu as adapters_hupu_module
import services.panel.adapters.bilibili as adapters_bilibili_module
import services.panel.adapters.bilibili.feed as adapters_bilibili_feed_module
import services.panel.adapters.bilibili.followings as adapters_bilibili_followings_module
import services.panel.adapters.bilibili.hot_search as adapters_bilibili_hot_search_module
import services.panel.adapters.bilibili.user_video as adapters_bilibili_user_video_module
import services.panel.adapters.github as adapters_github_module
import services.panel.adapters.generic as adapters_generic_module
import services.panel.data_block_builder as data_block_builder
import services.panel.panel_generator as panel_generator
from services.panel.view_models import ContractViolation, validate_records


HUPU_FEED_SAMPLE = {
    "title": "Hupu Board #BXJ",
    "home_page_url": "https://bbs.hupu.com/bxj-postdate",
    "language": "zh-cn",
    "items": [
        {
            "id": "https://bbs.hupu.com/1.html",
            "url": "https://bbs.hupu.com/1.html",
            "title": "Sample Thread One",
            "content_html": "<p>Preview <strong>One</strong></p>",
            "date_published": "2024-01-01T00:00:00.000Z",
            "authors": [{"name": "AuthorA"}],
            "tags": ["tag-a", "tag-b"],
        },
        {
            "id": "https://bbs.hupu.com/2.html",
            "url": "https://bbs.hupu.com/2.html",
            "title": "Sample Thread Two",
            "content_html": "<p>Preview Two</p>",
            "date_published": "2024-01-02T00:00:00.000Z",
        },
    ],
}

GITHUB_TRENDING_SAMPLE = {
    "title": "GitHub Trending",
    "items": [
        {
            "id": "octocat/hello-world",
            "url": "https://github.com/octocat/hello-world",
            "title": "octocat/hello-world",
            "description": "Sample repository description.",
            "date_published": "2024-01-01T00:00:00.000Z",
            "extra": {"language": "Python", "stars": "1,234", "stars_today": "12", "forks": "56"},
        },
        {
            "id": "data/wrangler",
            "url": "https://github.com/data/wrangler",
            "title": "data/wrangler",
            "description": "Wrangle all the data.",
            "extra": {"language": "Python", "stars": "2,000"},
        },
        {
            "id": "rust/awesome",
            "url": "https://github.com/rust/awesome",
            "title": "rust/awesome",
            "description": "Awesome Rust things.",
            "extra": {"language": "Rust", "stars": "999"},
        },
    ],
}

SSPAI_FEED_SAMPLE = {
    "title": "SSPai Picks",
    "items": [
        {
            "id": "https://sspai.com/post/12345",
            "url": "https://sspai.com/post/12345",
            "title": "SSPai Article",
            "content_html": "<p>Curated content preview</p>",
        }
    ],
}

BILIBILI_FOLLOWINGS_SAMPLE = {
    "title": "Alice 的 bilibili 关注",
    "count": 42,
    "item": [
        {
            "title": "Alice 新关注 Bob",
            "description": "Bob<br>硬核程序员<br>总计42",
            "pubDate": "Fri, 01 Nov 2024 08:00:00 GMT",
            "link": "https://space.bilibili.com/1001",
        },
        {
            "title": "Alice 新关注 Carol",
            "description": "Carol<br>签名很长<br>总计42",
            "pubDate": "Fri, 01 Nov 2024 07:30:00 GMT",
            "link": "https://space.bilibili.com/1002",
        },
    ],
}

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


@pytest.fixture(autouse=True)
def reload_panel_modules():
    for module in [
        adapter_registry_module,
        adapters_hupu_module,
        adapters_bilibili_module,
        adapters_bilibili_feed_module,
        adapters_bilibili_followings_module,
        adapters_bilibili_hot_search_module,
        adapters_bilibili_user_video_module,
        adapters_github_module,
        adapters_generic_module,
    ]:
        importlib.reload(module)
    importlib.reload(adapters)
    importlib.reload(data_block_builder)
    importlib.reload(panel_generator)
    yield


def test_route_adapter_decorator_registers_prefix():
    @adapters.route_adapter("/demo/prefix")
    def _demo_adapter(source_info, records):
        return adapters.RouteAdapterResult(records=[], block_plans=[])

    adapter = adapters.get_route_adapter("/demo/prefix/resource")
    assert adapter is _demo_adapter


def test_hupu_adapter_normalizes_feed():
    adapter = adapters.get_route_adapter("/hupu/bbs/bxj/1")
    source_info = SourceInfo(
        datasource="rsshub",
        route="/hupu/bbs/bxj/1",
        params={},
        fetched_at=None,
        request_id=None,
    )

    result = adapter(source_info, [HUPU_FEED_SAMPLE])

    assert result.records, "adapter should return normalized records"
    first = result.records[0]
    assert first["title"] == "Sample Thread One"
    assert first["link"] == "https://bbs.hupu.com/1.html"
    assert first["summary"].startswith("Preview")
    assert "One" in first["summary"]  # HTML标签被清理但内容保留
    assert first["author"] == "AuthorA"
    assert result.stats["feed_title"] == HUPU_FEED_SAMPLE["title"]
    assert result.stats["api_endpoint"] == "/hupu/bbs/bxj/1"
    assert result.block_plans, "adapter should provide block plans"
    plan = result.block_plans[0]
    assert plan.component_id == "ListPanel"
    assert plan.props["title_field"] == "title"


def test_panel_generator_uses_route_adapter():
    generator = panel_generator.PanelGenerator()
    source_info = SourceInfo(
        datasource="rsshub",
        route="/hupu/bbs/bxj/1",
        params={},
        fetched_at=None,
        request_id=None,
    )
    block_input = panel_generator.PanelBlockInput(
        block_id="rss_block",
        records=[HUPU_FEED_SAMPLE],
        source_info=source_info,
        title="Sample Hupu Feed",
    )

    result = generator.generate(mode="append", block_inputs=[block_input])
    assert result.payload.blocks


def test_github_trending_adapter_enriches_stats():
    adapter = adapters.get_route_adapter("/github/trending/daily")
    source_info = SourceInfo(
        datasource="rsshub",
        route="/github/trending/daily",
        params={},
        fetched_at=None,
        request_id=None,
    )

    result = adapter(source_info, [GITHUB_TRENDING_SAMPLE])

    assert len(result.records) == 3
    first = result.records[0]
    assert first["language"] == "Python"
    assert first["stars"] == 1234
    assert result.stats["top_language"] == "Python"
    assert result.stats["top_stars"] == 2000
    assert result.stats["api_endpoint"] == "/github/trending/daily"
    assert len(result.block_plans) == 2
    assert result.block_plans[0].component_id == "ListPanel"
    assert result.block_plans[1].component_id == "LineChart"
    assert result.block_plans[1].props["x_field"] == "x"
    assert result.records[0]["rank"] == 1
    assert result.records[0]["x"] == 1
    assert result.records[0]["y"] == 1234.0


def test_sspai_adapter_falls_back_to_list():
    adapter = adapters.get_route_adapter("/sspai/series")
    source_info = SourceInfo(
        datasource="rsshub",
        route="/sspai/series",
        params={},
        fetched_at=None,
        request_id=None,
    )

    result = adapter(source_info, [SSPAI_FEED_SAMPLE])
    assert result.records
    assert result.block_plans[0].component_id == "ListPanel"
    assert result.block_plans[0].confidence == pytest.approx(0.68)


def test_contract_violation_raises():
    with pytest.raises(ContractViolation):
        validate_records("ListPanel", [{"id": "abc"}])


def test_statistic_card_contract():
    record = {
        "id": "metric-total",
        "metric_title": "新增关注",
        "metric_value": 1024.0,
        "metric_trend": "up",
        "metric_delta_text": "+12.5% 环比",
    }
    validated = validate_records("StatisticCard", [record])
    assert validated[0]["metric_title"] == "新增关注"
    assert validated[0]["metric_trend"] == "up"

    with pytest.raises(ContractViolation):
        validate_records("StatisticCard", [{"id": "broken", "metric_value": 100}])


def test_manifest_lists_available_components():
    manifest = adapters.get_route_manifest("/github/trending/weekly")
    assert manifest is not None
    component_ids = {entry.component_id for entry in manifest.components}
    assert component_ids == {"ListPanel", "LineChart"}
    line_chart_entry = next(entry for entry in manifest.components if entry.component_id == "LineChart")
    assert line_chart_entry.default_selected is False
    assert line_chart_entry.cost == "medium"


def test_adapter_respects_requested_components():
    adapter = adapters.get_route_adapter("/github/trending/daily")
    source_info = SourceInfo(
        datasource="rsshub",
        route="/github/trending/daily",
        params={},
        fetched_at=None,
        request_id=None,
    )
    context = adapters.AdapterExecutionContext(requested_components=["LineChart"])

    result = adapter(source_info, [GITHUB_TRENDING_SAMPLE], context)

    assert len(result.block_plans) == 1
    plan = result.block_plans[0]
    assert plan.component_id == "LineChart"
    assert plan.props["x_field"] == "x"
    assert result.stats["total_items"] == 3
    assert result.records and result.records[0]["x"] == 1


def test_panel_generator_skips_when_no_matching_component():
    generator = panel_generator.PanelGenerator()
    source_info = SourceInfo(
        datasource="rsshub",
        route="/bilibili/user/followings/2267573/3",
        params={},
        fetched_at=None,
        request_id=None,
    )
    block_input = panel_generator.PanelBlockInput(
        block_id="bili-followings",
        records=[BILIBILI_FOLLOWINGS_SAMPLE],
        source_info=source_info,
        requested_components=["StatisticCard"],  # 当前适配器不支持
    )

    result = generator.generate(mode="append", block_inputs=[block_input])

    assert result.payload.blocks == []
    assert result.debug["blocks"][0]["skipped"] is True
    # DataBlock 仍然可用于调试或统计
    assert "bili-followings" in result.data_blocks

def test_bilibili_followings_adapter_extracts_count():
    adapter = adapters.get_route_adapter("/bilibili/user/followings/2267573/3")
    source_info = SourceInfo(
        datasource="rsshub",
        route="/bilibili/user/followings/2267573/3",
        params={},
        fetched_at=None,
        request_id=None,
    )

    result = adapter(source_info, [BILIBILI_FOLLOWINGS_SAMPLE])

    assert result.records
    first = result.records[0]
    assert first["title"].startswith("Alice 新关注")
    assert first["link"] == "https://space.bilibili.com/1001"
    assert "总计42" in first["summary"]
    assert result.block_plans[0].component_id == "ListPanel"
    assert result.stats["metrics"]["follower_count"] == 42  # follower_count 现在在 metrics 中
    assert result.stats["api_endpoint"] == "/bilibili/user/followings/2267573/3"


def test_backwards_compat_adapter_without_context_param():
    """测试向后兼容：不接受context参数的旧adapter也能正常工作"""
    from services.panel.adapters.registry import route_adapter, RouteAdapterResult

    # 创建一个旧风格的adapter（只有2个参数）
    @route_adapter("/test/old-style")
    def old_style_adapter(source_info, records):
        return RouteAdapterResult(
            records=[{"id": "test", "value": "old-style"}],
            block_plans=[],
            stats={"route": source_info.route}
        )

    adapter = adapters.get_route_adapter("/test/old-style")
    source_info = SourceInfo(
        datasource="test",
        route="/test/old-style",
        params={},
        fetched_at=None,
        request_id=None,
    )

    # 即使传入context，旧adapter也应该正常工作
    result = adapter(source_info, [{"sample": "data"}], context=None)
    assert result.records[0]["value"] == "old-style"


def test_context_requested_components_empty_list():
    """测试边界情况：requested_components为空列表"""
    adapter = adapters.get_route_adapter("/github/trending/daily")
    source_info = SourceInfo(
        datasource="rsshub",
        route="/github/trending/daily",
        params={},
        fetched_at=None,
        request_id=None,
    )
    # 空列表表示不请求任何组件
    context = adapters.AdapterExecutionContext(requested_components=[])

    result = adapter(source_info, [GITHUB_TRENDING_SAMPLE], context)

    # 应该提前返回，不生成任何组件
    assert result.block_plans == []
    assert result.records == []
    assert result.stats["api_endpoint"] == "/github/trending/daily"


def test_context_requested_components_none():
    """测试边界情况：requested_components为None（无限制）"""
    adapter = adapters.get_route_adapter("/github/trending/daily")
    source_info = SourceInfo(
        datasource="rsshub",
        route="/github/trending/daily",
        params={},
        fetched_at=None,
        request_id=None,
    )
    # None表示无限制，生成所有默认组件
    context = adapters.AdapterExecutionContext(requested_components=None)

    result = adapter(source_info, [GITHUB_TRENDING_SAMPLE], context)

    # 应该生成所有组件（ListPanel默认选中，LineChart默认不选中）
    assert len(result.block_plans) >= 1  # 至少有ListPanel
    component_ids = {plan.component_id for plan in result.block_plans}
    assert "ListPanel" in component_ids


def test_early_return_preserves_stats():
    """测试提前返回时stats正确保留"""
    adapter = adapters.get_route_adapter("/hupu/bbs/bxj/1")
    source_info = SourceInfo(
        datasource="rsshub",
        route="/hupu/bbs/bxj/1",
        params={},
        fetched_at=None,
        request_id=None,
    )
    # 请求不存在的组件
    context = adapters.AdapterExecutionContext(requested_components=["StatisticCard"])

    result = adapter(source_info, [HUPU_FEED_SAMPLE], context)

    # 应该提前返回空结果，但stats应该完整
    assert result.block_plans == []
    assert result.records == []
    assert result.stats["datasource"] == "rsshub"
    assert result.stats["route"] == "/hupu/bbs/bxj/1"
    assert result.stats["api_endpoint"] == "/hupu/bbs/bxj/1"
    assert "feed_title" in result.stats


def test_bilibili_hot_search_adapter():
    """测试 bilibili 热搜适配器"""
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
    """测试 bilibili 热搜的 manifest"""
    manifest = adapters.get_route_manifest("/bilibili/hot-search")
    assert manifest is not None
    component_ids = {entry.component_id for entry in manifest.components}
    assert component_ids == {"ListPanel"}
    list_panel = next(entry for entry in manifest.components if entry.component_id == "ListPanel")
    assert list_panel.required is True
    assert list_panel.cost == "low"
    assert list_panel.default_selected is True


def test_default_adapter_warning():
    """测试默认适配器会返回警告信息"""
    adapter = adapters.get_route_adapter("/nonexistent/route")
    source_info = SourceInfo(
        datasource="test",
        route="/nonexistent/route",
        params={},
        fetched_at=None,
        request_id=None,
    )

    result = adapter(source_info, [{"title": "test"}])

    # 验证返回了警告信息
    assert result.stats.get("using_default_adapter") is True
    assert "warning" in result.stats
    assert "/nonexistent/route" in result.stats["warning"]
    assert result.block_plans == []


def test_panel_generator_fallback_with_debug():
    """测试 PanelGenerator 在使用兜底渲染时的 debug 信息"""
    generator = panel_generator.PanelGenerator()
    source_info = SourceInfo(
        datasource="test",
        route="/nonexistent/route",
        params={},
        fetched_at=None,
        request_id=None,
    )

    block_input = panel_generator.PanelBlockInput(
        block_id="test_block",
        records=[{"title": "test data"}],
        source_info=source_info,
        title="Test Block",
        requested_components=None,  # 未指定，会触发 fallback
    )

    result = generator.generate(mode="append", block_inputs=[block_input])

    # 验证生成了 fallback 组件
    assert len(result.payload.blocks) == 1
    assert result.payload.blocks[0].component == "FallbackRichText"

    # 验证 debug 信息
    blocks_debug = result.debug["blocks"]
    assert len(blocks_debug) == 1
    block_debug = blocks_debug[0]
    assert block_debug.get("using_default_adapter") is True
    assert block_debug.get("using_fallback") is True
    assert "adapter_warning" in block_debug
    assert "fallback_reason" in block_debug


def test_panel_generator_skip_with_empty_requested_components():
    """测试明确请求空组件列表时跳过渲染"""
    generator = panel_generator.PanelGenerator()
    source_info = SourceInfo(
        datasource="test",
        route="/nonexistent/route",
        params={},
        fetched_at=None,
        request_id=None,
    )

    block_input = panel_generator.PanelBlockInput(
        block_id="test_block",
        records=[{"title": "test data"}],
        source_info=source_info,
        title="Test Block",
        requested_components=[],  # 明确请求空列表
    )

    result = generator.generate(mode="append", block_inputs=[block_input])

    # 验证没有生成任何组件
    assert len(result.payload.blocks) == 0

    # 验证 debug 信息
    blocks_debug = result.debug["blocks"]
    assert len(blocks_debug) == 1
    block_debug = blocks_debug[0]
    assert block_debug.get("skipped") is True
    assert "skip_reason" in block_debug
    assert "Empty requested_components list" in block_debug["skip_reason"]


def test_bar_chart_contract():
    """测试 BarChart 组件契约"""
    record = {
        "id": "python-stars",
        "x": "Python",
        "y": 1234.0,
        "series": "Languages",
        "color": "#3776ab",
        "tooltip": "Python: 1,234 stars",
    }
    validated = validate_records("BarChart", [record])
    assert validated[0]["x"] == "Python"
    assert validated[0]["y"] == 1234.0
    assert validated[0]["color"] == "#3776ab"

    # 测试缺少必填字段
    with pytest.raises(ContractViolation):
        validate_records("BarChart", [{"id": "broken", "y": 100}])  # 缺少 x 字段


def test_pie_chart_contract():
    """测试 PieChart 组件契约"""
    record = {
        "id": "python-projects",
        "name": "Python",
        "value": 1234.0,
        "color": "#3776ab",
        "tooltip": "Python: 1,234 projects (34.5%)",
    }
    validated = validate_records("PieChart", [record])
    assert validated[0]["name"] == "Python"
    assert validated[0]["value"] == 1234.0
    assert validated[0]["color"] == "#3776ab"
    assert validated[0]["tooltip"] == "Python: 1,234 projects (34.5%)"

    # 测试最小必填字段
    minimal_record = {
        "id": "js-projects",
        "name": "JavaScript",
        "value": 2100.0,
    }
    validated_minimal = validate_records("PieChart", [minimal_record])
    assert validated_minimal[0]["name"] == "JavaScript"
    assert validated_minimal[0]["value"] == 2100.0
    assert validated_minimal[0].get("color") is None
    assert validated_minimal[0].get("tooltip") is None

    # 测试缺少必填字段
    with pytest.raises(ContractViolation):
        validate_records("PieChart", [{"id": "broken", "value": 100}])  # 缺少 name 字段

    with pytest.raises(ContractViolation):
        validate_records("PieChart", [{"id": "broken", "name": "Test"}])  # 缺少 value 字段


def test_table_contract():
    """测试 Table 组件契约"""
    # 正确的 TableViewModel 数据
    table_data = {
        "columns": [
            {
                "key": "name",
                "label": "项目名称",
                "type": "text",
                "sortable": True,
                "align": "left",
                "width": 0.4,
            },
            {
                "key": "stars",
                "label": "Stars",
                "type": "number",
                "sortable": True,
                "align": "right",
                "width": 0.2,
            },
            {
                "key": "language",
                "label": "语言",
                "type": "tag",
                "sortable": False,
                "align": "center",
                "width": 0.2,
            },
            {
                "key": "updated_at",
                "label": "更新时间",
                "type": "date",
                "sortable": True,
                "align": "left",
                "width": 0.2,
            },
        ],
        "rows": [
            {
                "name": "octocat/hello-world",
                "stars": 12345,
                "language": "Python",
                "updated_at": "2024-01-15T10:30:00Z",
            },
            {
                "name": "user/awesome",
                "stars": 9876,
                "language": "JavaScript",
                "updated_at": "2024-01-14T08:20:00Z",
            },
        ],
    }

    validated = validate_records("Table", [table_data])
    assert len(validated) == 1
    assert len(validated[0]["columns"]) == 4
    assert len(validated[0]["rows"]) == 2
    assert validated[0]["columns"][0]["key"] == "name"
    assert validated[0]["columns"][0]["label"] == "项目名称"
    assert validated[0]["rows"][0]["name"] == "octocat/hello-world"
    assert validated[0]["rows"][0]["stars"] == 12345

    # 测试缺少必填字段 - columns
    with pytest.raises(ContractViolation):
        validate_records("Table", [{"rows": [{"name": "test"}]}])  # 缺少 columns

    # 测试缺少必填字段 - rows
    with pytest.raises(ContractViolation):
        validate_records("Table", [{"columns": [{"key": "name", "label": "Name"}]}])  # 缺少 rows

    # 测试列定义缺少必填字段
    with pytest.raises(ContractViolation):
        validate_records(
            "Table",
            [
                {
                    "columns": [{"label": "Name"}],  # 缺少 key 字段
                    "rows": [],
                }
            ],
        )

    # 测试空表格（有列定义但无数据行）
    empty_table = {
        "columns": [
            {"key": "name", "label": "Name"},
            {"key": "value", "label": "Value"},
        ],
        "rows": [],
    }
    validated_empty = validate_records("Table", [empty_table])
    assert len(validated_empty) == 1
    assert len(validated_empty[0]["columns"]) == 2
    assert len(validated_empty[0]["rows"]) == 0


def test_bilibili_user_video_adapter():
    """测试 bilibili UP 主投稿适配器"""
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
    """测试 bilibili UP 主投稿的 manifest"""
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

