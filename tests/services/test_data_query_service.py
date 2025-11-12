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

from integration.data_executor import FetchResult
from services.data_query_service import DataQueryService


class _DummyCache:
    def __init__(self):
        self._rag = {}
        self._rss = {}

    def get_rag_cache(self, key, filter_datasource=""):
        return self._rag.get((key, filter_datasource))

    def set_rag_cache(self, key, value, filter_datasource=""):
        self._rag[(key, filter_datasource)] = value

    def get_rss_cache(self, generated_path):
        return self._rss.get(generated_path)

    def set_rss_cache(self, generated_path, result):
        self._rss[generated_path] = result


class _StubRAG:
    def __init__(self, retrieved_tools, plans):
        self._retrieved = retrieved_tools
        self._plans = plans

    def process(self, user_query, filter_datasource=None, verbose=False):
        return {
            "status": "success",
            "reasoning": "primary-route",
            "generated_path": "/primary",
            "selected_tool": {
                "route_id": "primary",
                "provider": "demo",
                "name": "Primary Route",
            },
            "retrieved_tools": self._retrieved,
        }

    def plan_with_tool(self, user_query, tool_def):
        return self._plans[tool_def["route_id"]]


class _StubExecutor:
    def __init__(self, fetch_map):
        self._fetch_map = fetch_map

    def fetch_rss(self, path):
        return self._fetch_map[path]


def _fetch_result(path, title):
    return FetchResult(
        status="success",
        items=[{"title": f"{title}-item"}],
        source="local",
        feed_title=title,
        payload={"items": [{"title": f"{title}-item"}]},
    )


def test_data_query_service_returns_multiple_datasets():
    retrieved_tools = [
        {"route_id": "secondary", "name": "Secondary", "datasource": "demo"},
        {"route_id": "tertiary", "name": "Tertiary", "datasource": "demo"},
    ]
    plans = {
        "secondary": {"status": "success", "generated_path": "/secondary"},
        "tertiary": {"status": "success", "generated_path": "/tertiary"},
    }
    fetch_map = {
        "/primary": _fetch_result("/primary", "Primary Feed"),
        "/secondary": _fetch_result("/secondary", "Secondary Feed"),
        "/tertiary": _fetch_result("/tertiary", "Tertiary Feed"),
    }

    service = DataQueryService(
        rag_in_action=_StubRAG(retrieved_tools, plans),
        data_executor=_StubExecutor(fetch_map),
        cache_service=_DummyCache(),
    )

    result = service.query("多路查询", use_cache=False)

    assert result.status == "success"
    assert len(result.datasets) == 3
    assert {dataset.generated_path for dataset in result.datasets} == {
        "/primary",
        "/secondary",
        "/tertiary",
    }
    assert result.items == result.datasets[0].items
    assert result.retrieved_tools == retrieved_tools


class _ClarificationRAG(_StubRAG):
    def process(self, user_query, filter_datasource=None, verbose=False):
        return {
            "status": "needs_clarification",
            "reasoning": "问题不明确",
            "clarification_question": "请告诉我具体栏目",
            "retrieved_tools": self._retrieved,
        }


def test_data_query_service_propagates_retrieved_tools_on_failure():
    retrieved_tools = [
        {
            "route_id": "demo/route",
            "name": "Demo Route",
            "datasource": "demo",
            "score": 0.88,
            "route": "/demo/route",
        }
    ]

    service = DataQueryService(
        rag_in_action=_ClarificationRAG(retrieved_tools, plans={}),
        data_executor=_StubExecutor(fetch_map={}),
        cache_service=_DummyCache(),
    )

    result = service.query("需要澄清", use_cache=False)

    assert result.status == "needs_clarification"
    assert result.retrieved_tools == retrieved_tools
