import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.panel.panel_spec_builder import (
    _build_envelope,
    _build_display_schema,
    build_panel_spec_from_dataset,
)


def test_build_envelope_accepts_dict_summary():
    dataset = {
        "items": [{"title": "热点", "value": 10}],
        "metadata": {"instruction": "测试摘要"},
        "summary": {"total_count": 10},
        "feed_title": "Demo",
        "generated_path": "/demo",
    }

    envelope = _build_envelope(dataset, data_id="demo", max_items=5)

    assert envelope.summary == '{"total_count": 10}'


def test_display_schema_metric_summary_normalized():
    dataset = {
        "items": [{"label": "count", "value": 10}],
        "metadata": {"metric_value": 10},
        "summary": {"total_count": 10},
    }

    schema = _build_display_schema(dataset, source_ref="demo", max_items=5)

    assert schema.summary == '{"total_count": 10}'
    assert schema.kind == "metric_set"


def test_display_schema_record_summary_normalized():
    dataset = {
        "items": [{"title": "A"}],
        "summary": {"count": 1},
    }

    schema = _build_display_schema(dataset, source_ref="demo", max_items=5)

    assert schema.summary == '{"count": 1}'
    assert schema.kind == "record_set"


def test_display_schema_uses_component_contract():
    dataset = {
        "items": [
            {"metric_title": "数量", "metric_value": 10},
        ],
        "metadata": {
            "component_id": "StatisticCard",
            "contract_id": "StatisticCard-contract-v2",
            "component_props": {"title": "指标"},
        },
        "summary": "当前 10 条",
    }

    schema = _build_display_schema(dataset, source_ref="demo", max_items=5)

    assert schema.component_id == "StatisticCard"
    assert schema.contract_id == "StatisticCard-contract-v2"
    assert schema.kind == "metric_set"
    assert schema.fields["items"][0]["metric_value"] == 10


def test_build_panel_spec_with_component_contract():
    dataset = {
        "items": [
            {"metric_title": "数量", "metric_value": 10},
        ],
        "metadata": {
            "component_id": "StatisticCard",
            "contract_id": "StatisticCard-contract-v2",
            "component_props": {"title": "指标"},
        },
        "summary": "当前 10 条",
    }

    result = build_panel_spec_from_dataset(dataset, data_id="demo-data")
    panel_spec = result["panel_spec"]
    view_models = list(panel_spec["view_models"].values())
    assert view_models
    vm = view_models[0]
    assert vm["component_id"] == "StatisticCard"
    assert vm["contract_id"] == "StatisticCard-contract-v2"
    assert vm["data"]["items"][0]["metric_value"] == 10
    assert vm["data"]["items"][0]["id"].startswith("StatisticCard-record")


def test_barchart_records_respect_mapping():
    dataset = {
        "items": [
            {"category": "凌晨", "value": 3},
            {"category": "上午", "value": 5},
        ],
        "metadata": {
            "component_id": "BarChart",
            "contract_id": "BarChart-contract-v2",
        },
    }

    result = build_panel_spec_from_dataset(dataset, data_id="bar-data")
    vm = list(result["panel_spec"]["view_models"].values())[0]
    assert vm["component_id"] == "BarChart"
    first = vm["data"]["items"][0]
    assert first["x"] == "凌晨"
    assert first["y"] == 3
    assert vm["props"]["x_field"] == "category"
    assert vm["props"]["y_field"] == "value"
