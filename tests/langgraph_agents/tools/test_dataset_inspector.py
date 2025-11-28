import pytest

from langgraph_agents.tools.dataset_inspector import register_dataset_inspector_tool
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.state import ToolCall
from langgraph_agents.runtime import ToolExecutionContext


class _StubDataStore:
    def __init__(self):
        self._store = {}

    def save(self, key, value):
        self._store[key] = value

    def load(self, key):
        return self._store[key]


def _registry_with_tool():
    registry = ToolRegistry()
    register_dataset_inspector_tool(registry)
    return registry


def _context(store):
    return ToolExecutionContext(
        data_query_service=None,
        note_backend=None,
        extras={"data_store": store},
    )


def test_inspect_dataset_returns_schema_and_profile():
    registry = _registry_with_tool()
    store = _StubDataStore()
    store.save(
        "data-1",
        {
            "datasets": [
                {
                    "route": "/bilibili/hot-search",
                    "schema": {"schema_id": "demo"},
                    "profile": {"record_count": 30},
                    "available_components": [{"component_id": "ListPanel"}],
                    "items": [{"foo": "bar"}],
                }
            ]
        },
    )

    call = ToolCall(plugin_id="inspect_dataset", args={"data_id": "data-1"}, step_id=1, description="inspect")
    spec = registry.get("inspect_dataset")
    payload = spec.handler(call, _context(store))

    assert payload.status == "success"
    assert payload.raw_output["schema"]["schema_id"] == "demo"
    assert payload.raw_output["record_count"] == 30
    assert "items" not in payload.raw_output


def test_inspect_dataset_invalid_index():
    registry = _registry_with_tool()
    store = _StubDataStore()
    store.save("data-1", {"datasets": [{"route": "/demo"}]})

    call = ToolCall(
        plugin_id="inspect_dataset",
        args={"data_id": "data-1", "dataset_index": 5},
        step_id=1,
        description="inspect",
    )
    spec = registry.get("inspect_dataset")
    payload = spec.handler(call, _context(store))

    assert payload.status == "error"
    assert "超出范围" in payload.error_message
