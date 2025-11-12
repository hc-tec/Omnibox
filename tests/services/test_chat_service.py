import sys
import types

import pytest

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

from api.schemas.panel import LayoutNode, LayoutTree, PanelPayload
from services.chat_service import ChatService
from services.data_query_service import DataQueryResult
from services.panel.component_planner import PlannerDecision
import services.chat_service as chat_service_module


@pytest.fixture(autouse=True)
def disable_llm_planner(monkeypatch):
    """避免测试过程中真正初始化 LLMComponentPlanner。"""

    class _DummyLLMPlanner:
        def __init__(self, *args, **kwargs):
            pass

        def is_available(self) -> bool:
            return False

    monkeypatch.setattr(
        chat_service_module,
        "LLMComponentPlanner",
        lambda *args, **kwargs: _DummyLLMPlanner(),
    )


def _make_success_query_result() -> DataQueryResult:
    return DataQueryResult(
        status="success",
        items=[{"title": "item-1"}],
        payload={"items": [{"title": "item-1"}]},
        feed_title="Demo Feed",
        generated_path="/demo/route",
        source="local",
        cache_hit="rss_cache",
    )


class _DummyIntentService:
    def recognize(self, *args, **kwargs):
        return types.SimpleNamespace(intent_type="data_query", confidence=0.92)


class _DummyDataQueryService:
    def __init__(self, result: DataQueryResult):
        self._result = result

    def query(self, *args, **kwargs) -> DataQueryResult:
        return self._result


class _RecordingPanelGenerator:
    def __init__(self, result):
        self._result = result
        self.block_inputs = None

    def generate(self, mode, block_inputs, history_token=None):
        self.block_inputs = list(block_inputs)
        return self._result


def _empty_panel_result():
    layout = LayoutTree(mode="append", nodes=[], history_token=None)
    payload = PanelPayload(mode="append", layout=layout, blocks=[])
    return types.SimpleNamespace(
        payload=payload,
        data_blocks={},
        component_confidence={},
        debug={"blocks": [], "planner_reasons": [], "planner_engine": "rule"},
    )


def test_chat_service_exposes_panel_warnings(monkeypatch):
    query_result = _make_success_query_result()
    data_service = _DummyDataQueryService(query_result)
    chat = ChatService(data_query_service=data_service, intent_service=_DummyIntentService())

    layout = LayoutTree(mode="append", nodes=[LayoutNode(type="row", id="row-1", children=[], props={})], history_token=None)
    payload = PanelPayload(mode="append", layout=layout, blocks=[])
    block_debug = {
        "data_block_id": "db-1",
        "using_default_adapter": True,
        "adapter_warning": "no adapter",
        "using_fallback": True,
        "fallback_reason": "fallback plan",
        "skipped": True,
        "skip_reason": "forced skip",
    }
    stub_result = types.SimpleNamespace(
        payload=payload,
        data_blocks={},
        component_confidence={},
        debug={
            "blocks": [block_debug],
            "planner_engine": "rule",
            "planner_reasons": [],
            "requested_components": None,
        },
    )
    chat.panel_generator = _RecordingPanelGenerator(stub_result)

    response = chat.chat("show me data")

    warning_types = [entry["type"] for entry in response.metadata.get("warnings", [])]
    assert warning_types == [
        "missing_adapter",
        "fallback_rendering",
        "component_skipped",
    ]


def test_chat_service_ignores_empty_planner_components(monkeypatch):
    monkeypatch.setattr(
        chat_service_module,
        "plan_components_for_route",
        lambda *args, **kwargs: PlannerDecision(components=[], reasons=["empty"]),
    )

    data_service = _DummyDataQueryService(_make_success_query_result())
    chat = ChatService(data_query_service=data_service, intent_service=_DummyIntentService())
    chat.llm_planner = None

    recording_generator = _RecordingPanelGenerator(_empty_panel_result())
    chat.panel_generator = recording_generator

    chat._build_panel(
        query_result=_make_success_query_result(),
        intent_confidence=0.87,
        user_query="demo",
    )

    requested = recording_generator.block_inputs[0].requested_components
    assert requested is None


class _StubResearchService:
    def __init__(self):
        self.calls = []

    def research(self, user_query, filter_datasource=None, task_id=None):
        self.calls.append((user_query, filter_datasource, task_id))
        step = types.SimpleNamespace(
            step_id=1,
            node_name="router",
            action="路由判定",
            status="success",
            timestamp="2025-11-12T00:00:00Z",
        )
        return types.SimpleNamespace(
            success=True,
            final_report="研究完成",
            execution_steps=[step],
            data_stash=[],
            metadata={"thread_id": "thread-1", "task_id": task_id or "task-stub"},
            error=None,
        )


def test_chat_service_handles_research_mode():
    data_service = _DummyDataQueryService(_make_success_query_result())
    research_stub = _StubResearchService()
    chat = ChatService(
        data_query_service=data_service,
        intent_service=_DummyIntentService(),
        research_service=research_stub,
    )

    client_task_id = "task-client-123"
    response = chat.chat("需要复杂研究", mode="research", client_task_id=client_task_id)

    assert research_stub.calls == [("需要复杂研究", None, client_task_id)]
    assert response.intent_type == "research"
    assert response.metadata["mode"] == "research"
    assert response.metadata["total_steps"] == 1
    assert response.metadata["execution_steps"][0]["step_id"] == 1
    assert response.metadata["task_id"] == client_task_id
    assert response.message == "研究完成"
