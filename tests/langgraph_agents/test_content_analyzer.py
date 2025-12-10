"""
ContentAnalyzer Agent 单元测试
"""

import sys
import types

import pytest
from types import SimpleNamespace
from unittest.mock import Mock


def _install_rag_system_stubs() -> None:
    """避免在测试时加载真实 rag_system 依赖。"""
    if "rag_system" in sys.modules:
        return

    rag_pkg = types.ModuleType("rag_system")
    sys.modules["rag_system"] = rag_pkg
    rag_pkg.__path__ = []

    pipeline_mod = types.ModuleType("rag_system.rag_pipeline")
    pipeline_cls = type("RAGPipeline", (), {})
    pipeline_mod.RAGPipeline = pipeline_cls
    sys.modules["rag_system.rag_pipeline"] = pipeline_mod
    rag_pkg.RAGPipeline = pipeline_cls

    embedding_mod = types.ModuleType("rag_system.embedding_model")
    embedding_cls = type("EmbeddingModel", (), {})
    embedding_mod.EmbeddingModel = embedding_cls
    sys.modules["rag_system.embedding_model"] = embedding_mod
    rag_pkg.EmbeddingModel = embedding_cls

    vector_mod = types.ModuleType("rag_system.vector_store")
    vector_cls = type("VectorStore", (), {})
    retriever_cls = type("RouteRetriever", (), {})
    vector_mod.VectorStore = vector_cls
    vector_mod.RouteRetriever = retriever_cls
    sys.modules["rag_system.vector_store"] = vector_mod
    rag_pkg.VectorStore = vector_cls
    rag_pkg.RouteRetriever = retriever_cls

    semantic_mod = types.ModuleType("rag_system.semantic_doc_generator")
    semantic_cls = type("SemanticDocGenerator", (), {})
    semantic_mod.SemanticDocGenerator = semantic_cls
    sys.modules["rag_system.semantic_doc_generator"] = semantic_mod
    rag_pkg.SemanticDocGenerator = semantic_cls

    top_semantic = types.ModuleType("semantic_doc_generator")
    top_semantic.SemanticDocGenerator = semantic_cls
    sys.modules["semantic_doc_generator"] = top_semantic

    config_mod = types.ModuleType("rag_system.config")
    config_mod.RETRIEVAL_CONFIG = {}
    config_mod.EMBEDDING_CONFIG = {}
    sys.modules["rag_system.config"] = config_mod
    rag_pkg.config = config_mod


_install_rag_system_stubs()

from langgraph_agents.agents.content_analyzer import ContentAnalyzer, create_content_analyzer
from langgraph_agents.schema_registry import SchemaRegistry
from langgraph_agents.state import DataReference, ToolCall
from langgraph_agents.storage import InMemoryResearchDataStore
from langgraph_agents.tools.content_analysis import register_content_analysis_tool
from langgraph_agents.tools.data_ref_resolver import DataRefResolver
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.runtime import ToolExecutionContext


class DummyLLM:
    """简单的顺序响应 LLM，用于替代真实模型。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def generate(self, prompt: str, **kwargs) -> str:
        self.calls.append(kwargs.get("role"))
        if not self._responses:
            raise RuntimeError("No responses left for DummyLLM")
        return self._responses.pop(0)


class TestContentAnalyzer:
    """测试 ContentAnalyzer Agent"""

    def _create_mock_runtime(self):
        """创建模拟 runtime"""
        runtime = Mock()
        runtime.data_store = InMemoryResearchDataStore()
        runtime.schema_registry = SchemaRegistry()
        runtime.planner_llm = Mock()
        return runtime

    def test_create_content_analyzer(self):
        """测试创建 ContentAnalyzer 实例"""
        runtime = self._create_mock_runtime()
        analyzer = create_content_analyzer(runtime)

        assert analyzer is not None
        assert isinstance(analyzer, ContentAnalyzer)
        assert analyzer.runtime == runtime

    def test_resolve_data_id_direct(self):
        """测试解析直接的 data_id"""
        runtime = self._create_mock_runtime()
        analyzer = ContentAnalyzer(runtime)

        data_id = analyzer._resolve_data_id("lg-abc123")
        assert data_id == "lg-abc123"

    def test_infer_limit_from_task_with_number(self):
        """测试从任务描述中推断记录数（包含数字）"""
        runtime = self._create_mock_runtime()
        analyzer = ContentAnalyzer(runtime)

        # 测试"前N"模式
        limit = analyzer._infer_limit_from_task("分析前3个热搜", 100)
        assert limit == 3

        # 测试"top N"模式
        limit = analyzer._infer_limit_from_task("分析 top 5 热搜", 100)
        assert limit == 5

        # 测试"N条"模式
        limit = analyzer._infer_limit_from_task("分析10条记录", 100)
        assert limit == 10

    def test_infer_limit_from_task_default(self):
        """测试从任务描述中推断记录数（无数字，使用默认值）"""
        runtime = self._create_mock_runtime()
        analyzer = ContentAnalyzer(runtime)

        # 没有数字，应使用总记录数（但不超过 MAX_RECORDS）
        limit = analyzer._infer_limit_from_task("分析所有热搜", 5)
        assert limit == 5

        limit = analyzer._infer_limit_from_task("分析所有热搜", 15)
        assert limit == 10  # 受 MAX_RECORDS = 10 限制

    def test_extract_records_from_items(self):
        """测试从 items 字段提取记录"""
        runtime = self._create_mock_runtime()
        analyzer = ContentAnalyzer(runtime)

        raw_data = {
            "type": "rss_data",
            "items": [
                {"title": "item1"},
                {"title": "item2"}
            ]
        }

        records = analyzer._extract_records(raw_data)
        assert len(records) == 2
        assert records[0]["title"] == "item1"

    def test_extract_records_from_list(self):
        """测试从列表数据提取记录"""
        runtime = self._create_mock_runtime()
        analyzer = ContentAnalyzer(runtime)

        raw_data = [
            {"title": "item1"},
            {"title": "item2"}
        ]

        records = analyzer._extract_records(raw_data)
        assert len(records) == 2

    def test_extract_records_single_object(self):
        """测试从单个对象提取记录（包装为列表）"""
        runtime = self._create_mock_runtime()
        analyzer = ContentAnalyzer(runtime)

        raw_data = {"title": "single item"}

        records = analyzer._extract_records(raw_data)
        assert len(records) == 1
        assert records[0]["title"] == "single item"

    def test_filter_and_truncate_fields(self):
        """测试字段过滤"""
        runtime = self._create_mock_runtime()
        analyzer = ContentAnalyzer(runtime)

        records = [
            {
                "title": "Title 1",
                "description": "Desc 1",
                "content": "Full content",  # 不在选择列表中，应被过滤
                "link": "http://..."  # 不在选择列表中，应被过滤
            },
            {
                "title": "Title 2",
                "description": "Desc 2"
            }
        ]

        selected_fields = ["title", "description"]
        filtered = analyzer._filter_and_truncate(records, selected_fields)

        assert len(filtered) == 2
        assert "title" in filtered[0]
        assert "description" in filtered[0]
        assert "content" not in filtered[0]
        assert "link" not in filtered[0]

    def test_filter_and_truncate_long_values(self):
        """测试值截断（超长字段值）"""
        runtime = self._create_mock_runtime()
        analyzer = ContentAnalyzer(runtime)

        long_text = "a" * 2000  # 超过 MAX_FIELD_LENGTH (1000)
        records = [
            {
                "title": "Title",
                "description": long_text
            }
        ]

        selected_fields = ["title", "description"]
        filtered = analyzer._filter_and_truncate(records, selected_fields)

        assert len(filtered[0]["description"]) <= 1003  # 1000 + "..."
        assert filtered[0]["description"].endswith("...")

    def test_check_token_safety_pass(self):
        """测试 token 安全检查（通过）"""
        runtime = self._create_mock_runtime()
        analyzer = ContentAnalyzer(runtime)

        # 小数据量，应该通过
        small_data = [
            {"title": "Title " + str(i), "description": "Desc " + str(i)}
            for i in range(5)
        ]

        # 不应抛出异常
        analyzer._check_token_safety(small_data)

    def test_check_token_safety_fail(self):
        """测试 token 安全检查（失败）"""
        runtime = self._create_mock_runtime()
        analyzer = ContentAnalyzer(runtime)

        # 超大数据量，应该失败
        large_data = [
            {"title": "T" * 10000, "description": "D" * 10000}
            for i in range(100)
        ]

        with pytest.raises(ValueError, match="数据量过大"):
            analyzer._check_token_safety(large_data)

    def test_format_schema(self):
        """测试 schema 格式化"""
        runtime = self._create_mock_runtime()
        analyzer = ContentAnalyzer(runtime)

        raw_schema = {
            "title": {"type": "string", "sample": "Sample title"},
            "description": {"type": "string", "sample": "Sample desc"},
            "count": {"type": "integer", "sample": 100}
        }

        formatted = analyzer._format_schema(raw_schema)

        assert "title" in formatted
        assert "description" in formatted
        assert "count" in formatted
        assert "Sample title" in formatted

    def test_format_schema_truncate_long_sample(self):
        """测试 schema 格式化（截断过长的示例值）"""
        runtime = self._create_mock_runtime()
        analyzer = ContentAnalyzer(runtime)

        long_sample = "a" * 200
        raw_schema = {
            "content": {"type": "string", "sample": long_sample}
        }

        formatted = analyzer._format_schema(raw_schema)

        # 示例值应被截断到 100 字符 + "..."
        assert len(formatted) < len(long_sample)
        assert "..." in formatted


class TestContentAnalyzerIntegration:
    """ContentAnalyzer 集成测试"""

    def _create_full_mock_runtime(self):
        """创建完整的模拟 runtime"""
        runtime = Mock()

        # data_store 与 schema_registry 使用真实实现，方便与解析器集成
        runtime.data_store = InMemoryResearchDataStore()
        runtime.schema_registry = SchemaRegistry()
        runtime.schema_registry.register(
            "lg-test",
            raw_schema={
                "title": {"type": "string", "sample": "Sample title"},
                "description": {"type": "string", "sample": "Sample desc"},
                "content": {"type": "string", "sample": "Very long content..."},
            },
            samples=[],
            metadata={"total_records": 3},
        )

        # Mock LLM
        runtime.planner_llm = Mock()

        return runtime

    def test_select_fields_success(self):
        """测试字段选择成功"""
        runtime = self._create_full_mock_runtime()

        # Mock LLM 返回字段选择结果
        runtime.planner_llm.generate = Mock(return_value="""
        {
            "selected_fields": ["title", "description"],
            "reasoning": "只需要标题和描述来分析主题",
            "limit": 3
        }
        """)

        analyzer = ContentAnalyzer(runtime)

        schema_info = runtime.schema_registry.get_schema("lg-test")
        result = analyzer._select_fields(schema_info, "分析前3个热搜的主题", None, 3)

        assert result["selected_fields"] == ["title", "description"]
        assert result["limit"] == 3
        assert "reasoning" in result

    def test_select_fields_limit_enforced(self):
        """测试字段数量限制强制执行"""
        runtime = self._create_full_mock_runtime()

        # Mock LLM 返回过多字段
        runtime.planner_llm.generate = Mock(return_value="""
        {
            "selected_fields": ["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10"],
            "reasoning": "选择了太多字段",
            "limit": 3
        }
        """)

        analyzer = ContentAnalyzer(runtime)

        schema_info = runtime.schema_registry.get_schema("lg-test")
        result = analyzer._select_fields(schema_info, "分析", None, 3)

        # 应该截断到 MAX_FIELDS (8)
        assert len(result["selected_fields"]) <= 8

    def test_select_fields_fallback_on_error(self):
        """测试字段选择失败时的降级行为"""
        runtime = self._create_full_mock_runtime()

        # Mock LLM 抛出异常
        runtime.planner_llm.generate = Mock(side_effect=Exception("LLM failed"))

        analyzer = ContentAnalyzer(runtime)

        schema_info = runtime.schema_registry.get_schema("lg-test")
        result = analyzer._select_fields(schema_info, "分析", None, 3)

        # 应该降级为默认字段
        assert result["selected_fields"] == ["title", "description"]
        assert "降级" in result["reasoning"] or "失败" in result["reasoning"]

    def test_analyze_with_resolver_step_ref(self):
        """使用 DataRefResolver 解析 $step 引用并完成分析"""
        data_store = InMemoryResearchDataStore()
        payload = {
            "items": [
                {"title": "Title 1", "description": "Desc 1", "content": "ignored"},
                {"title": "Title 2", "description": "Desc 2", "content": "ignored"},
            ]
        }
        data_id = data_store.save(payload)

        schema_registry = SchemaRegistry()
        schema_registry.register(
            data_id,
            raw_schema={
                "title": {"type": "string", "sample": "Title"},
                "description": {"type": "string", "sample": "Desc"},
            },
            samples=payload["items"][:1],
            metadata={"item_count": 2},
        )

        data_ref = DataReference(step_id=1, tool_name="fetch_public_data", data_id=data_id, summary="mock")
        resolver = DataRefResolver([data_ref], data_store)

        llm = DummyLLM(
            [
                """
                {
                    "selected_fields": ["title"],
                    "reasoning": "标题足够",
                    "limit": 5
                }
                """,
                """
                {
                    "analysis_result": {
                        "items": [{"index": 0, "title": "Title 1"}],
                        "summary": "done"
                    }
                }
                """,
            ]
        )

        runtime = SimpleNamespace(
            data_store=data_store,
            schema_registry=schema_registry,
            planner_llm=llm,
        )
        analyzer = ContentAnalyzer(runtime)

        result = analyzer.analyze("$step.1", "分析标题", resolver=resolver)

        assert result["data_id"] == data_id
        assert result["records_analyzed"] == 2
        assert result["fields_used"] == ["title"]
        assert result["analysis"]["summary"] == "done"


def test_analyze_content_tool_uses_resolver():
    """内容分析工具集成：可解析 $step 引用并返回结果"""
    registry = ToolRegistry()
    register_content_analysis_tool(registry)

    data_store = InMemoryResearchDataStore()
    payload = {
        "items": [
            {"title": "First", "description": "Desc"},
        ]
    }
    data_id = data_store.save(payload)

    schema_registry = SchemaRegistry()
    schema_registry.register(
        data_id,
        raw_schema={
            "title": {"type": "string", "sample": "First"},
            "description": {"type": "string", "sample": "Desc"},
        },
        samples=payload["items"],
        metadata={"item_count": 1},
    )

    llm = DummyLLM(
        [
            """
            {
                "selected_fields": ["title"],
                "reasoning": "只看标题",
                "limit": 3
            }
            """,
            """
            {
                "analysis_result": {
                    "items": [{"index": 0, "title": "First"}],
                    "summary": "ok"
                }
            }
            """,
        ]
    )

    data_ref = DataReference(step_id=1, tool_name="fetch_public_data", data_id=data_id, summary="mock")
    context = ToolExecutionContext(
        data_query_service=None,
        note_backend=None,
        extras={
            "data_store": data_store,
            "planner_llm": llm,
            "schema_registry": schema_registry,
            "data_stash": [data_ref],
        },
    )

    call = ToolCall(
        plugin_id="analyze_content",
        args={"source_ref": "$step.1", "task": "分析标题"},
        step_id=1,
        description="test content analysis",
    )

    payload = registry.execute(call, context, use_protection=False)

    assert payload.status == "success"
    assert payload.raw_output["data_id"] == data_id
    assert payload.raw_output["fields_used"] == ["title"]
    assert payload.raw_output["records_analyzed"] == 1
    assert payload.raw_output["analysis"]["items"][0]["title"] == "First"
