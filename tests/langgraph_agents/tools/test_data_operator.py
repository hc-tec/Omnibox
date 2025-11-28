from __future__ import annotations

import json

import pytest

from langgraph_agents.storage import InMemoryResearchDataStore
from langgraph_agents.state import ToolCall
from langgraph_agents.runtime import ToolExecutionContext
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.tools.data_operator import register_data_operator_tool


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

    context = ToolExecutionContext(
        data_query_service=None,
        note_backend=None,
        extras={
            "planner_llm": dummy_llm,
            "data_store": InMemoryResearchDataStore(),
            "data_operator_prompt": "你是 SchemaCoder，生成 transform 函数返回 dict。",
        },
    )

    call = ToolCall(
        plugin_id="data_operator",
        args={"source_ref": records, "instruction": "筛选标题中包含火灾的热搜"},
        step_id=1,
        description="test",
    )

    payload = registry.execute(call, context, use_protection=False)

    assert payload.status == "success"
    assert payload.raw_output["type"] == "data_operator"
    assert payload.raw_output["explanation"] == "筛选包含火灾的条目"
    assert len(payload.raw_output["result"]["items"]) == 1
    assert payload.raw_output["result"]["items"][0]["title"].startswith("#1")

