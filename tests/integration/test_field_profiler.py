from services.panel.field_profiler import FieldProfiler, FieldProfile


def test_default_semantic_detection():
    profiler = FieldProfiler()
    records = [
        {
            "title": "示例标题",
            "link": "https://example.com/article",
            "author": "作者A",
            "publishedAt": "2024-01-02T10:00:00Z",
            "stats": {"views": 1234},
            "cover": {
                "image": "https://example.com/cover.png",
            },
        }
    ]

    result = profiler.profile(records)

    assert "title" in result and "title" in result["title"].semantic
    assert "link" in result and "url" in result["link"].semantic
    assert "author" in result and "author" in result["author"].semantic
    assert "publishedAt" in result and "datetime" in result["publishedAt"].semantic
    assert "cover.image" in result and "image" in result["cover.image"].semantic


def test_custom_rule_registration():
    def is_price(path: str, profile: FieldProfile) -> bool:
        return path.endswith("price") and profile.data_type == "number"

    FieldProfiler.register_rule("price", is_price, priority=15)
    profiler = FieldProfiler()
    records = [{"product": {"price": 19.99}}]

    result = profiler.profile(records)

    assert "product.price" in result
    assert "price" in result["product.price"].semantic

    FieldProfiler.unregister_rule("price")
