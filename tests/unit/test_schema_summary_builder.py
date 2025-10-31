from services.panel.schema_summary import SchemaSummaryBuilder


def test_schema_summary_with_semantics():
    builder = SchemaSummaryBuilder(max_samples=2)
    records = [
        {
            "title": "示例标题",
            "url": "https://example.com",
            "publishedAt": "2024-01-01T10:00:00Z",
            "metrics": {"views": 100, "likes": 5},
            "tags": ["tech", "ai"],
        },
        {
            "title": "另一条",
            "url": "https://example.org",
            "publishedAt": "2024-01-02T12:00:00Z",
            "metrics": {"views": 200, "likes": 10},
            "tags": ["science"],
        },
    ]

    summary = builder.build(records)

    field_map = {field.name: field for field in summary.fields}

    assert "title" in field_map
    assert "title" in field_map["title"].semantic

    assert "url" in field_map
    assert "url" in field_map["url"].semantic

    assert "publishedAt" in field_map
    assert "datetime" in field_map["publishedAt"].semantic
    assert summary.stats["time_range"][0] <= summary.stats["time_range"][1]

    assert "metrics.views" in field_map
    assert field_map["metrics.views"].type == "number"

    assert "tags" in field_map
    assert field_map["tags"].type == "array"
