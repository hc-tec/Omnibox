import importlib

import pytest

from api.schemas.panel import SourceInfo
import services.panel.adapters as adapters
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


@pytest.fixture(autouse=True)
def reload_panel_modules():
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
    assert first["author"] == "AuthorA"
    assert result.stats["feed_title"] == HUPU_FEED_SAMPLE["title"]
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

    assert result.payload.blocks, "panel generator should create UI blocks"
    block = result.payload.blocks[0]
    assert block.component == "ListPanel"
    assert block.props["title_field"] == "title"
    assert result.component_confidence[block.id] == pytest.approx(0.75)


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
