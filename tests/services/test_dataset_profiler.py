import pytest

from services.panel.dataset_schema import DatasetSchemaDescriptor, DatasetSchemaField
from services.panel.dataset_profiler import build_dataset_profile


@pytest.fixture
def sample_schema():
    return DatasetSchemaDescriptor(
        schema_id="test.schema",
        fields=[
            DatasetSchemaField(name="title", type="string", description="标题"),
            DatasetSchemaField(name="play_count", type="number", description="播放量", aggregatable=True),
            DatasetSchemaField(name="tags", type="array", description="标签"),
        ],
    )


def test_build_dataset_profile_returns_stats(sample_schema):
    records = [
        {"title": "A", "play_count": 100, "tags": ["news", "tech"]},
        {"title": "B", "play_count": 200, "tags": ["news"]},
        {"title": "", "play_count": None, "tags": []},
    ]

    profile = build_dataset_profile(records, schema=sample_schema)

    assert profile["record_count"] == 3
    assert profile["sampled_count"] == 3
    title_profile = next(field for field in profile["fields"] if field["name"] == "title")
    assert title_profile["non_null_ratio"] > 0.0
    play_profile = next(field for field in profile["fields"] if field["name"] == "play_count")
    assert play_profile["numeric_stats"]["max"] == 200


def test_build_dataset_profile_handles_missing_records(sample_schema):
    profile = build_dataset_profile([], schema=sample_schema)
    assert profile["record_count"] == 0
    assert profile["fields"] == []
