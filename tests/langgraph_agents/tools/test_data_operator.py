from __future__ import annotations

import json
from dataclasses import asdict
from typing import Dict

import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_rag_system_stubs() -> None:
    """避免测试时加载真实 rag_system 依赖。"""
    if "rag_system" in sys.modules:
        return

    rag_pkg = types.ModuleType("rag_system")
    sys.modules["rag_system"] = rag_pkg

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

    config_mod = types.ModuleType("rag_system.config")
    config_mod.RETRIEVAL_CONFIG = {}
    sys.modules["rag_system.config"] = config_mod
    rag_pkg.config = config_mod

    semantic_mod = types.ModuleType("rag_system.semantic_doc_generator")
    semantic_cls = type("SemanticDocGenerator", (), {})
    semantic_mod.SemanticDocGenerator = semantic_cls
    sys.modules["rag_system.semantic_doc_generator"] = semantic_mod
    rag_pkg.SemanticDocGenerator = semantic_cls

    # 一些模块使用顶级 semantic_doc_generator 导入
    top_semantic = types.ModuleType("semantic_doc_generator")
    top_semantic.SemanticDocGenerator = semantic_cls
    sys.modules["semantic_doc_generator"] = top_semantic


_install_rag_system_stubs()

from langgraph_agents.schema_registry import SchemaRegistry
from langgraph_agents.storage import InMemoryResearchDataStore
from langgraph_agents.state import ToolCall
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.tools.data_operator import register_data_operator_tool
from langgraph_agents.component_contracts import get_contract_by_component, get_contract_by_id


class DummyLLM:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload, ensure_ascii=False)
        self.last_prompt = None

    def generate(self, prompt: str, **kwargs) -> str:
        self.last_prompt = prompt
        return self.payload


def test_data_operator_executes_generated_code():
    registry = ToolRegistry()
    register_data_operator_tool(registry)

    records = [
        {"title": "#1 香港火灾已致128人遇难", "summary": "香港火灾已致128人遇难"},
        {"title": "#2 国省考政治理论考前速成", "summary": "其他内容"},
    ]
    source_payload = {
        "type": "rss_public_data",
        "feed_title": "B站热搜",
        "generated_path": "/bilibili/hot-search",
        "source": "rsshub",
        "items": records,
    }

    dummy_llm = DummyLLM(
        {
            "code": """
def transform(records):
    filtered = []
    for item in records:
        title = item.get("title", "")
        if "火灾" in title:
            filtered.append(item)
    return {"items": filtered}
""",
            "explanation": "筛选包含火灾的条目",
        }
    )

    data_store = InMemoryResearchDataStore()
    data_id = data_store.save(source_payload)

    context = DummyContext(
        extras={
            "planner_llm": dummy_llm,
            "data_store": data_store,
            "schema_registry": SchemaRegistry(),
            "data_operator_prompt": "你是 SchemaCoder，生成 transform 函数返回 dict。",
        },
    )

    call = ToolCall(
        plugin_id="data_operator",
        args={"source_ref": data_id, "instruction": "筛选标题中包含火灾的热搜"},
        step_id=1,
        description="test",
    )

    payload = registry.execute(call, context, use_protection=False)

    assert payload.status == "success"
    assert payload.raw_output["type"] == "data_operator"
    assert payload.raw_output["explanation"] == "筛选包含火灾的条目"
    assert len(payload.raw_output["items"]) == 1
    assert payload.raw_output["items"][0]["title"].startswith("#1")
    assert payload.raw_output["generated_path"] == "/bilibili/hot-search"
    assert payload.raw_output["feed_title"].startswith("B站热搜")
    assert payload.raw_output["metadata"]["source_data_id"] == data_id


def test_data_operator_strips_panel_metadata():
    registry = ToolRegistry()
    register_data_operator_tool(registry)

    records = [
        {"title": "视频1", "views": 100},
        {"title": "视频2", "views": 200},
    ]
    source_payload = {
        "type": "rss_public_data",
        "feed_title": "B站视频",
        "generated_path": "/bilibili/video",
        "source": "rsshub",
        "items": records,
    }

    dummy_llm = DummyLLM(
        {
            "code": """
def transform(records):
    return {
        "items": records,
        "metadata": {
            "panel_hint": "statistic_card",
            "metric_value": 123,
            "item_count": len(records)
        }
    }
""",
            "explanation": "保留原始数据",
        }
    )

    data_store = InMemoryResearchDataStore()
    data_id = data_store.save(source_payload)
    context = DummyContext(
        extras={
            "planner_llm": dummy_llm,
            "data_store": data_store,
            "schema_registry": SchemaRegistry(),
            "data_operator_prompt": "你是 SchemaCoder。",
        },
    )
    call = ToolCall(
        plugin_id="data_operator",
        args={"source_ref": data_id, "instruction": "保持字段不变"},
        step_id=2,
        description="sanitize metadata",
    )
    payload = registry.execute(call, context, use_protection=False)

    assert payload.status == "success"
    metadata = payload.raw_output["metadata"]
    assert "panel_hint" not in metadata
    assert "metric_value" not in metadata
    assert metadata["item_count"] == len(records)


def test_data_operator_applies_component_contract():
    registry = ToolRegistry()
    register_data_operator_tool(registry)

    records = [{"title": "热搜", "value": 10}]
    source_payload = {
        "items": records,
        "feed_title": "B站热搜",
        "generated_path": "/bilibili/hot-search",
        "metadata": {},
    }

    dummy_llm = DummyLLM(
        {
            "code": """
def transform(records):
    return {"items": [{"id": "metric-1", "metric_title": "数量", "metric_value": len(records)}]}
""",
            "explanation": "统计数量",
        }
    )
    data_store = InMemoryResearchDataStore()
    data_id = data_store.save(source_payload)
    contract_entry = _build_contract_entry("StatisticCard")
    context = DummyContext(
        extras={
            "planner_llm": dummy_llm,
            "data_store": data_store,
            "schema_registry": SchemaRegistry(),
            "data_operator_prompt": "prompt",
            "component_contracts_for_call": [contract_entry],
        }
    )
    call = ToolCall(plugin_id="data_operator", args={"source_ref": data_id, "instruction": "统计热搜数量"}, step_id=1, description="contract")
    payload = registry.execute(call, context, use_protection=False)

    assert payload.status == "success"
    metadata = payload.raw_output["metadata"]
    assert metadata["component_id"] == "StatisticCard"
    assert metadata["contract_id"] == "StatisticCard-contract-v2"
    assert metadata["component_props"]["title"] == "StatisticCard 测试"


def test_data_operator_contract_violation():
    registry = ToolRegistry()
    register_data_operator_tool(registry)

    records = [{"title": "热搜"}]
    source_payload = {
        "items": records,
    }

    dummy_llm = DummyLLM(
        {
            "code": """
def transform(records):
    return {"items": [{"id": "metric-1", "metric_title": "数量"}]}
""",
            "explanation": "缺少值",
        }
    )
    data_store = InMemoryResearchDataStore()
    data_id = data_store.save(source_payload)
    contract_entry = _build_contract_entry("StatisticCard")
    context = DummyContext(
        extras={
            "planner_llm": dummy_llm,
            "data_store": data_store,
            "schema_registry": SchemaRegistry(),
            "component_contracts_for_call": [contract_entry],
        }
    )
    call = ToolCall(plugin_id="data_operator", args={"source_ref": data_id, "instruction": "测试"}, step_id=1, description="contract violation")
    payload = registry.execute(call, context, use_protection=False)

    assert payload.status == "error"
    assert payload.raw_output["error"] == "contract_violation"
    assert payload.raw_output["error_code"] == "contract_violation"


def test_data_operator_trims_disallowed_fields_for_contract():
    registry = ToolRegistry()
    register_data_operator_tool(registry)

    records = [{"title": "热搜", "summary": "说明"}]
    source_payload = {"items": records}

    dummy_llm = DummyLLM(
        {
            "code": """
def transform(records):
    return {"items": [{"title": records[0].get("title"), "summary": "情感分析", "url": "https://example.com", "content_html": "<p>desc</p>"}]}
""",
            "explanation": "保持标题并附加描述",
        }
    )
    data_store = InMemoryResearchDataStore()
    data_id = data_store.save(source_payload)
    contract_entry = _build_contract_entry("ListPanel")
    context = DummyContext(
        extras={
            "planner_llm": dummy_llm,
            "data_store": data_store,
            "schema_registry": SchemaRegistry(),
            "component_contracts_for_call": [contract_entry],
        }
    )
    call = ToolCall(
        plugin_id="data_operator",
        args={"source_ref": data_id, "instruction": "生成列表数据"},
        step_id=1,
        description="trim disallowed",
    )
    payload = registry.execute(call, context, use_protection=False)

    assert payload.status == "success"
    item = payload.raw_output["items"][0]
    assert item["title"] == "热搜"
    assert item["summary"] == "情感分析"
    assert "url" not in item
    assert "content_html" not in item
    metadata = payload.raw_output["metadata"]
    assert metadata["contract_id"] == "ListPanel-contract-v3"
    assert "trimmed_fields" in metadata and set(metadata["trimmed_fields"]) == {"content_html", "url"}


def test_data_operator_allows_datetime_import():
    registry = ToolRegistry()
    register_data_operator_tool(registry)

    records = [
        {"published": "2025-11-30T01:23:00+08:00"},
        {"published": "2025-11-30T02:45:00+08:00"},
    ]
    source_payload = {
        "items": records,
    }

    dummy_llm = DummyLLM(
        {
            "code": """
import datetime

def transform(records):
    buckets = {}
    for item in records:
        ts = item.get("published")
        if not ts:
            continue
        hour = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).hour
        bucket = f"{hour:02d}:00"
        buckets[bucket] = buckets.get(bucket, 0) + 1
    items = [{"category": key, "value": value} for key, value in sorted(buckets.items())]
    return {"items": items}
""",
            "explanation": "按小时分桶",
        }
    )

    data_store = InMemoryResearchDataStore()
    data_id = data_store.save(source_payload)
    contract_entry = _build_contract_entry("BarChart")
    context = DummyContext(
        extras={
            "planner_llm": dummy_llm,
            "data_store": data_store,
            "schema_registry": SchemaRegistry(),
            "component_contracts_for_call": [contract_entry],
        },
    )
    call = ToolCall(plugin_id="data_operator", args={"source_ref": data_id, "instruction": "按小时分桶"}, step_id=1, description="datetime import")
    payload = registry.execute(call, context, use_protection=False)

    assert payload.status == "success"
    items = payload.raw_output["items"]
    assert isinstance(items, list)
    assert items[0]["value"] >= 1
class DummyContext:
    def __init__(self, *, data_query_service=None, note_backend=None, extras=None):
        self.data_query_service = data_query_service
        self.note_backend = note_backend
        self.extras = extras or {}


def _build_contract_entry(component_id: str) -> Dict[str, Any]:
    contract = get_contract_by_id(f"{component_id}-contract-v2") or get_contract_by_component(component_id)
    if not contract:
        raise AssertionError(f"missing contract for {component_id}")
    return {
        "component_id": component_id,
        "contract_id": contract.contract_id,
        "targets": ["$step.1"],
        "definition": asdict(contract),
        "props": {"title": f"{component_id} 测试"},
    }
