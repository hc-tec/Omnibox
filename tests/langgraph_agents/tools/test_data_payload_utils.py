from langgraph_agents.storage import InMemoryResearchDataStore
from langgraph_agents.tools.data_payload_utils import (
    unwrap_payload,
    extract_records,
    build_source_metadata,
)


def test_unwrap_payload_with_reference():
    store = InMemoryResearchDataStore()
    payload_id = store.save(
        {
            "title": "影视飓风 的 bilibili 空间",
            "items": [
                {"id": "a", "title": "A"},
                {"id": "b", "title": "B"},
            ],
        }
    )
    envelope = {
        "generated_path": "/bilibili/user/video/123",
        "feed_title": "影视飓风 的 bilibili 空间",
        "payload_ref": payload_id,
    }

    payload, ref = unwrap_payload(envelope, store)

    assert ref == payload_id
    assert payload["generated_path"] == "/bilibili/user/video/123"
    assert payload["title"] == "影视飓风 的 bilibili 空间"
    assert len(payload["items"]) == 2


def test_unwrap_payload_with_result_key():
    store = InMemoryResearchDataStore()
    result_payload = {
        "generated_path": "/bilibili/hot-search",
        "items": [{"title": "A"}, {"title": "B"}],
    }
    envelope = {
        "type": "data_operator",
        "result": result_payload,
    }

    payload, ref = unwrap_payload(envelope, store)

    assert ref is None
    assert payload["generated_path"] == "/bilibili/hot-search"
    assert len(payload["items"]) == 2


def test_extract_and_metadata_helpers():
    payload = {
        "items": [{"id": 1}, {"id": 2}],
        "metadata": {
            "source_route": "/foo",
            "source_feed_title": "示例",
            "source_datasource": "rsshub",
        },
    }
    records = extract_records(payload)
    assert len(records) == 2

    metadata = build_source_metadata(payload, "lg-1", 3, payload_ref="lg-raw")
    assert metadata["source_data_id"] == "lg-1"
    assert metadata["source_step_id"] == 3
    assert metadata["payload_ref"] == "lg-raw"
    assert metadata["generated_path"] == "/foo"
    assert metadata["feed_title"] == "示例"
    assert metadata["datasource"] == "rsshub"
    assert metadata["item_count"] == 2
