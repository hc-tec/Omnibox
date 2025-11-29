import sys
import types
import json

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
from services.data_query_service import DataQueryResult, QueryDataset
from services.panel.component_planner import PlannerDecision
import services.chat_service as chat_service_module
from langgraph_agents.sync_executor import SyncLangGraphExecutor, LangGraphExecutionResult
from langgraph_agents.state import DataReference


@pytest.fixture(autouse=True)
def disable_llm_components(monkeypatch):
    """避免测试过程中真正初始化 LLMComponentPlanner 和三层架构组件。"""

    class _DummyLLMPlanner:
        def __init__(self, *args, **kwargs):
            pass

        def is_available(self) -> bool:
            return False

    # 禁用 LLMComponentPlanner
    monkeypatch.setattr(
        chat_service_module,
        "LLMComponentPlanner",
        lambda *args, **kwargs: _DummyLLMPlanner(),
    )

    # 禁用 LLM 客户端创建，避免触发三层架构初始化
    monkeypatch.setattr(
        chat_service_module,
        "create_llm_client",
        lambda *args, **kwargs: None,
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
    chat = ChatService(data_query_service=data_service)

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

    response = chat.chat("show me data", mode="simple")

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
    chat = ChatService(data_query_service=data_service)
    chat.llm_component_planner = None

    recording_generator = _RecordingPanelGenerator(_empty_panel_result())
    chat.panel_generator = recording_generator

    chat._build_panel(
        query_result=_make_success_query_result(),
        datasets=[],
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
    """测试研究模式由 ResearchService 执行。"""
    data_service = _DummyDataQueryService(_make_success_query_result())
    research_stub = _StubResearchService()
    chat = ChatService(
        data_query_service=data_service,
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


def test_chat_service_accepts_legacy_langgraph_alias():
    """向后兼容：mode=langgraph 将按 research 处理。"""
    data_service = _DummyDataQueryService(_make_success_query_result())
    research_stub = _StubResearchService()
    chat = ChatService(
        data_query_service=data_service,
        research_service=research_stub,
    )

    chat.chat("需要复杂研究", mode="langgraph")

    assert len(research_stub.calls) == 1


def test_chat_service_exposes_retrieved_tools_on_clarification():
    retrieved_tools = [
        {
            "route_id": "demo.route",
            "name": "Demo Route",
            "datasource": "demo",
            "description": "测试路由",
            "path_template": ["/demo/:category"],
            "score": 0.91,
        }
    ]
    query_result = DataQueryResult(
        status="needs_clarification",
        items=[],
        reasoning="需要具体栏目",
        clarification_question="你想看哪个栏目？",
        retrieved_tools=retrieved_tools,
    )

    data_service = _DummyDataQueryService(query_result)
    chat = ChatService(data_query_service=data_service)

    response = chat.chat("demo", mode="simple")

    tools = response.metadata["retrieved_tools"]
    assert tools[0]["route"] == "/demo/:category"
    assert tools[0]["score"] == pytest.approx(0.91)
    assert tools[0]["description"] == "测试路由"


def test_research_mode_respects_filter_datasource():
    """V5.0 架构：research 模式通过 Task Graph 处理，正确传递 filter_datasource。"""

    class _RecordingDataQueryService:
        def __init__(self):
            self.calls = []

        def query(self, **kwargs):
            self.calls.append(kwargs)
            return _make_success_query_result()

    data_service = _RecordingDataQueryService()
    chat = ChatService(data_query_service=data_service, llm_client=None)
    chat._build_panel = lambda *args, **kwargs: _empty_panel_result()

    # mode="research" 现在走 Task Graph，应该正确传递 filter_datasource
    response = chat.chat(
        user_query="demo request",
        filter_datasource="github",
        use_cache=False,
        mode="research",
    )

    assert data_service.calls, "数据查询应至少执行一次"
    first_call = data_service.calls[0]
    assert first_call["filter_datasource"] == "github"
    assert first_call["prefer_single_route"] is True


# Phase 3: 快速刷新功能测试


class _MockDataQueryServiceForRefresh:
    """Mock 数据查询服务，用于测试快速刷新"""

    def __init__(self):
        self.fetch_data_directly_calls = []

    def fetch_data_directly(self, route_id, generated_path, use_cache):
        self.fetch_data_directly_calls.append({
            "route_id": route_id,
            "generated_path": generated_path,
            "use_cache": use_cache,
        })
        return DataQueryResult(
            status="success",
            items=[{"title": "刷新后数据"}],
            feed_title="刷新后 Feed",
            generated_path=generated_path,
            source="rsshub",
            cache_hit="none",
        )


def test_quick_refresh_success():
    """测试快速刷新成功场景"""
    data_service = _MockDataQueryServiceForRefresh()
    chat = ChatService(data_query_service=data_service)
    chat.panel_generator = _RecordingPanelGenerator(_empty_panel_result())

    refresh_metadata = {
        "route_id": "demo/hot",
        "generated_path": "/demo/hot",
    }

    response = chat.quick_refresh(refresh_metadata=refresh_metadata)

    # 验证调用了 fetch_data_directly
    assert len(data_service.fetch_data_directly_calls) == 1
    call = data_service.fetch_data_directly_calls[0]
    assert call["route_id"] == "demo/hot"
    assert call["generated_path"] == "/demo/hot"
    assert call["use_cache"] is False  # 刷新时不使用缓存

    # 验证响应
    assert response.success is True
    assert "刷新成功" in response.message
    assert response.intent_type == "data_query"
    assert response.metadata["is_refresh"] is True
    assert response.metadata["refresh_metadata"]["route_id"] == "demo/hot"
    assert response.metadata["refresh_metadata"]["generated_path"] == "/demo/hot"


def test_quick_refresh_missing_generated_path():
    """测试快速刷新缺少 generated_path 时的错误处理"""
    data_service = _MockDataQueryServiceForRefresh()
    chat = ChatService(data_query_service=data_service)

    refresh_metadata = {
        "route_id": "demo/hot",
        # 缺少 generated_path
    }

    response = chat.quick_refresh(refresh_metadata=refresh_metadata)

    # 验证返回错误
    assert response.success is False
    assert response.intent_type == "error"
    assert "缺少 generated_path" in response.message

    # 验证没有调用 fetch_data_directly
    assert len(data_service.fetch_data_directly_calls) == 0


def test_quick_refresh_with_layout_snapshot():
    """测试快速刷新传递 layout_snapshot 到面板生成器"""
    data_service = _MockDataQueryServiceForRefresh()
    chat = ChatService(data_query_service=data_service)

    panel_generator = _RecordingPanelGenerator(_empty_panel_result())
    chat.panel_generator = panel_generator

    refresh_metadata = {
        "route_id": "demo/hot",
        "generated_path": "/demo/hot",
    }
    layout_snapshot = [
        {"block_id": "block-1", "component": "FeedList", "x": 0, "y": 0, "w": 12, "h": 4}
    ]

    response = chat.quick_refresh(
        refresh_metadata=refresh_metadata,
        layout_snapshot=layout_snapshot,
    )

    # 验证响应成功
    assert response.success is True

    # TODO: 验证 layout_snapshot 传递给面板生成器
    # 当前实现中 _build_panel 接收 layout_snapshot 参数，但 panel_generator 的测试桩可能需要扩展


class _FailingDataQueryService:
    """模拟数据查询失败的服务"""

    def fetch_data_directly(self, route_id, generated_path, use_cache):
        return DataQueryResult(
            status="error",
            items=[],
            reasoning="网络连接失败",
        )


def test_quick_refresh_handles_fetch_error():
    """测试快速刷新处理数据获取失败"""
    data_service = _FailingDataQueryService()
    chat = ChatService(data_query_service=data_service)
    chat.panel_generator = _RecordingPanelGenerator(_empty_panel_result())

    refresh_metadata = {
        "route_id": "demo/error",
        "generated_path": "/demo/error",
    }

    response = chat.quick_refresh(refresh_metadata=refresh_metadata)

    # 数据获取失败时应该返回失败的响应
    assert response.success is False
    assert response.intent_type == "data_query"
    assert "网络连接失败" in response.message
    assert response.metadata["status"] == "error"


def test_chat_service_langgraph_integration():
    """测试 ChatService 与 V5.0 LangGraph 的集成。"""
    # 过滤后只保留1条记录的数据集
    filtered_dataset = QueryDataset(
        route_id="demo.route",
        provider="bilibili",
        name="投稿",
        generated_path="/demo",
        items=[{"title": "英雄联盟周报"}],  # 只有1条
        feed_title="投稿",
        source="local",
    )
    filtered_query_result = DataQueryResult(
        status="success",
        items=list(filtered_dataset.items),
        feed_title="投稿",
        generated_path="/demo",
        source="local",
        datasets=[filtered_dataset],
    )

    class _GraphAwareDataService:
        def __init__(self):
            self.calls = 0

        def query(self, *args, **kwargs):
            self.calls += 1
            return filtered_query_result

    data_service = _GraphAwareDataService()
    chat = ChatService(data_query_service=data_service)
    chat.panel_generator = _RecordingPanelGenerator(_empty_panel_result())

    # 创建 Mock LangGraph 执行器
    class _MockLangGraphExecutor:
        def __init__(self):
            self.execute_calls = []

        def execute(self, user_query, filter_datasource=None):
            self.execute_calls.append({
                "user_query": user_query,
                "filter_datasource": filter_datasource,
            })
            # 返回成功的执行结果（包含 filter 步骤）
            return LangGraphExecutionResult(
                success=True,
                final_report="找到1条包含'英雄联盟'的视频",
                data_stash=[
                    DataReference(
                        step_id=1,
                        tool_name="fetch_public_data",
                        data_id="data_001",
                        status="success",
                        summary="获取投稿视频2条",
                    ),
                    DataReference(
                        step_id=2,
                        tool_name="filter_data",
                        data_id="data_002",
                        status="success",
                        summary="过滤后保留1条",
                    ),
                ],
                router_decision="simple_tool_call",
                execution_steps=[
                    {"step_id": 1, "tool_name": "fetch_public_data", "status": "success"},
                    {"step_id": 2, "tool_name": "filter_data", "status": "success"},
                ],
            )

        def get_final_data(self, result):
            # 返回过滤后的结果
            return filtered_query_result

    mock_executor = _MockLangGraphExecutor()
    chat.langgraph_executor = mock_executor

    response = chat.chat(
        'B站影视飓风投稿视频中，标题包含"英雄联盟"的视频',
        mode="simple",
    )

    # 验证 LangGraph 执行器被调用
    assert len(mock_executor.execute_calls) == 1
    assert "英雄联盟" in mock_executor.execute_calls[0]["user_query"]

    # 验证响应正确
    assert response.success is True
    dataset_summary = response.metadata["datasets"][0]
    assert dataset_summary["item_count"] == 1

    # 验证 langgraph 元数据
    langgraph_meta = response.metadata.get("langgraph")
    assert langgraph_meta is not None
    assert langgraph_meta["success"] is True
    assert len(langgraph_meta["execution_steps"]) == 2
