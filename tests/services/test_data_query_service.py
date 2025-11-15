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


def test_data_query_service_respects_single_route_flag():
    retrieved_tools = [
        {"route_id": "secondary", "name": "Secondary", "datasource": "demo"},
    ]
    plans = {
        "secondary": {"status": "success", "generated_path": "/secondary"},
    }
    fetch_map = {
        "/primary": _fetch_result("/primary", "Primary Feed"),
        "/secondary": _fetch_result("/secondary", "Secondary Feed"),
    }

    service = DataQueryService(
        rag_in_action=_StubRAG(retrieved_tools, plans),
        data_executor=_StubExecutor(fetch_map),
        cache_service=_DummyCache(),
    )

    result = service.query("单路查询", use_cache=False, prefer_single_route=True)

    assert result.status == "success"
    assert len(result.datasets) == 1
    assert result.datasets[0].generated_path == "/primary"


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


# Phase 3: 快速刷新功能测试


class _MockDataExecutor:
    """Mock 数据执行器，用于测试快速刷新功能"""

    def __init__(self, fetch_return_value):
        self._fetch_return_value = fetch_return_value
        self.fetch_calls = []

    def fetch(self, generated_path, cache_key, use_cache=True):
        self.fetch_calls.append({
            "generated_path": generated_path,
            "cache_key": cache_key,
            "use_cache": use_cache,
        })
        return self._fetch_return_value


def test_fetch_data_directly_success():
    """测试快速刷新成功获取数据"""
    mock_api_result = {
        "items": [{"title": "刷新后数据-1"}, {"title": "刷新后数据-2"}],
        "title": "刷新后 Feed",
        "source": "rsshub",
        "cache_hit": "none",
    }
    executor = _MockDataExecutor(mock_api_result)

    service = DataQueryService(
        rag_in_action=None,  # 快速刷新不需要 RAG
        data_executor=executor,
        cache_service=_DummyCache(),
    )

    result = service.fetch_data_directly(
        route_id="demo/hot",
        generated_path="/demo/hot",
        use_cache=False,
    )

    # 验证返回结果
    assert result.status == "success"
    assert len(result.items) == 2
    assert result.items[0]["title"] == "刷新后数据-1"
    assert result.feed_title == "刷新后 Feed"
    assert result.generated_path == "/demo/hot"
    assert result.source == "rsshub"
    assert result.cache_hit == "none"

    # 验证调用参数
    assert len(executor.fetch_calls) == 1
    assert executor.fetch_calls[0]["generated_path"] == "/demo/hot"
    assert executor.fetch_calls[0]["use_cache"] is False


def test_fetch_data_directly_no_items():
    """测试快速刷新返回空数据"""
    mock_api_result = {"items": [], "title": "Empty Feed"}
    executor = _MockDataExecutor(mock_api_result)

    service = DataQueryService(
        rag_in_action=None,
        data_executor=executor,
        cache_service=_DummyCache(),
    )

    result = service.fetch_data_directly(
        route_id="demo/empty",
        generated_path="/demo/empty",
        use_cache=False,
    )

    assert result.status == "not_found"
    assert result.items == []
    assert result.reasoning == "数据获取失败：未返回数据"


def test_fetch_data_directly_with_cache():
    """测试快速刷新使用缓存"""
    mock_api_result = {
        "items": [{"title": "cached-data"}],
        "title": "Cached Feed",
        "source": "rsshub",
        "cache_hit": "rss_cache",
    }
    executor = _MockDataExecutor(mock_api_result)

    service = DataQueryService(
        rag_in_action=None,
        data_executor=executor,
        cache_service=_DummyCache(),
    )

    result = service.fetch_data_directly(
        route_id="demo/cached",
        generated_path="/demo/cached",
        use_cache=True,
    )

    assert result.status == "success"
    assert len(result.items) == 1
    assert result.cache_hit == "rss_cache"

    # 验证使用了缓存参数
    assert executor.fetch_calls[0]["use_cache"] is True


def test_fetch_data_directly_exception_handling():
    """测试快速刷新异常处理"""
    executor = _MockDataExecutor(None)
    # 模拟抛出异常
    def fetch_with_error(*args, **kwargs):
        raise RuntimeError("网络连接失败")
    executor.fetch = fetch_with_error

    service = DataQueryService(
        rag_in_action=None,
        data_executor=executor,
        cache_service=_DummyCache(),
    )

    result = service.fetch_data_directly(
        route_id="demo/error",
        generated_path="/demo/error",
        use_cache=False,
    )

    assert result.status == "error"
    assert result.items == []
    assert "网络连接失败" in result.reasoning
