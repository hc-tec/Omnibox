from __future__ import annotations

from langgraph_agents.utils.raw_schema_profiler import (
    build_sample_records,
    summarize_payload,
)


def test_summarize_payload_includes_metadata_and_samples():
    payload = {
        "generated_path": "/bilibili/hot-search",
        "feed_title": "B站热搜",
        "source": "rsshub",
        "cache_hit": True,
        "items": [
            {"title": "#1 Foo", "description": "A" * 20},
            {"title": "#2 Bar", "description": "B" * 20},
        ],
    }

    summary = summarize_payload(payload, sample_limit=1)

    assert summary["metadata"]["generated_path"] == "/bilibili/hot-search"
    assert summary["metadata"]["feed_title"] == "B站热搜"
    assert summary["metadata"]["item_count"] == 2
    assert len(summary["samples"]) == 1
    assert summary["samples"][0]["title"].startswith("#1")


def test_build_sample_records_trims_large_fields():
    payload = {
        "items": [
            {
                "title": "demo",
                "description": "X" * 500,
                "nested": {"text": "Y" * 500},
            }
        ]
    }

    samples = build_sample_records(payload, max_samples=1, max_field_length=32)
    sample = samples[0]

    assert "__preview__" in sample["description"]
    assert sample["nested"]["text"]["__truncated__"] is True
