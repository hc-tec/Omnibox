import sys
import types

if "rag_system" not in sys.modules:
    rag_system_stub = types.ModuleType("rag_system")
    rag_system_stub.__path__ = []
    sys.modules["rag_system"] = rag_system_stub

if "rag_system.rag_pipeline" not in sys.modules:
    rag_pipeline_stub = types.ModuleType("rag_system.rag_pipeline")

    class _StubRAGPipeline:
        def search(self, *args, **kwargs):
            return []

    rag_pipeline_stub.RAGPipeline = _StubRAGPipeline
    sys.modules["rag_system.rag_pipeline"] = rag_pipeline_stub

from langgraph_agents.tools.panel_stream import register_panel_stream_tool
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.runtime import ToolExecutionContext
from langgraph_agents.state import ToolCall
from services.data_query_service import DataQueryResult


class _StubDataQuery:
    def query(self, *args, **kwargs):
        return DataQueryResult(
            status="success",
            items=[{"title": "demo"}],
            feed_title="Demo Feed",
            generated_path="/demo/path",
            source="local",
            payload={"items": [{"title": "demo"}]},
        )


def _build_tool():
    registry = ToolRegistry()
    register_panel_stream_tool(registry)
    return registry.get("emit_panel_preview")


def _build_call():
    return ToolCall(
        plugin_id="emit_panel_preview",
        args={"query": "demo preview"},
        step_id=1,
        description="emit preview",
    )


def test_panel_preview_skips_when_callback_missing():
    tool = _build_tool()
    context = ToolExecutionContext(
        data_query_service=_StubDataQuery(),
        note_backend=None,
        extras={},
    )

    payload = tool.handler(_build_call(), context)

    assert payload.status == "success"
    assert payload.raw_output["type"] == "panel_preview"
    assert payload.raw_output.get("skipped") is True


def test_panel_preview_emits_data_when_callback_present():
    tool = _build_tool()
    captured = []

    def emitter(data):
        captured.append(data)

    context = ToolExecutionContext(
        data_query_service=_StubDataQuery(),
        note_backend=None,
        extras={"emit_panel_preview": emitter},
    )

    payload = tool.handler(_build_call(), context)

    assert payload.status == "success"
    assert captured, "emitter should receive preview payload"
    preview = captured[0]["previews"][0]
    assert preview["title"] == "Demo Feed"
    assert preview["items"][0]["title"] == "demo"
