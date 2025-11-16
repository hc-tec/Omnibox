"""extract_insights 工具单元测试。"""

import pytest
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.tools.insights_extractor import register_insights_extractor_tool
from langgraph_agents.state import ToolCall
from langgraph_agents.runtime import ToolExecutionContext
from unittest.mock import MagicMock


@pytest.fixture
def registry():
    """创建测试用工具注册表。"""
    reg = ToolRegistry()
    register_insights_extractor_tool(reg)
    return reg


@pytest.fixture
def mock_data_store():
    """创建 mock data_store。"""
    store = MagicMock()
    store.load.return_value = {
        "items": [
            {"title": "AI Agent 架构设计", "view_count": 50000},
            {"title": "ReAct 框架详解", "view_count": 40000},
            {"title": "长期记忆实现方案", "view_count": 30000},
        ]
    }
    return store


@pytest.fixture
def mock_llm():
    """创建 mock LLM。"""
    llm = MagicMock()
    llm.model_name = "gpt-4-turbo"
    llm.generate.return_value = """```json
{
  "insights": [
    {
      "type": "viewpoint",
      "title": "长期记忆是高频观点",
      "description": "多个视频强调 AI Agent 需要长期记忆能力",
      "evidence": ["视频1", "视频3"],
      "confidence": 0.85,
      "actionable": true
    }
  ],
  "overall_summary": "AI Agent 相关视频主要关注架构设计和长期记忆",
  "next_actions": ["考虑制作长期记忆相关内容"]
}
```"""
    return llm


def test_extract_insights_viewpoint(registry, mock_data_store, mock_llm):
    """测试观点提取。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={
            "data_store": mock_data_store,
            "planner_llm": mock_llm
        }
    )

    call = ToolCall(
        plugin_id="extract_insights",
        args={
            "source_ref": "test-data",
            "analysis_type": "viewpoint_extraction",
            "focus_areas": ["技术架构", "应用场景"]
        },
        step_id=1,
        description="观点提取测试"
    )

    result = registry.execute(call, context)

    assert result.status == "success"
    assert result.raw_output["type"] == "insights"
    assert len(result.raw_output["insights"]) > 0
    assert "overall_summary" in result.raw_output
    assert "metadata" in result.raw_output

    # 验证 LLM 被调用
    mock_llm.generate.assert_called_once()


def test_extract_insights_missing_source_ref(registry, mock_data_store, mock_llm):
    """测试缺少 source_ref 参数。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={
            "data_store": mock_data_store,
            "planner_llm": mock_llm
        }
    )

    call = ToolCall(
        plugin_id="extract_insights",
        args={
            "analysis_type": "summary"
        },
        step_id=1,
        description="缺少参数测试"
    )

    result = registry.execute(call, context)

    assert result.status == "error"
    assert result.raw_output["error_code"] == "E101"


def test_extract_insights_empty_data(registry, mock_llm):
    """测试空数据源。"""
    store = MagicMock()
    store.load.return_value = {"items": []}

    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={
            "data_store": store,
            "planner_llm": mock_llm
        }
    )

    call = ToolCall(
        plugin_id="extract_insights",
        args={
            "source_ref": "empty-data",
            "analysis_type": "summary"
        },
        step_id=1,
        description="空数据测试"
    )

    result = registry.execute(call, context)

    assert result.status == "success"
    assert len(result.raw_output["insights"]) == 0


def test_extract_insights_llm_failure(registry, mock_data_store):
    """测试 LLM 调用失败。"""
    llm = MagicMock()
    llm.generate.side_effect = Exception("LLM 服务不可用")

    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={
            "data_store": mock_data_store,
            "planner_llm": llm
        }
    )

    call = ToolCall(
        plugin_id="extract_insights",
        args={
            "source_ref": "test-data",
            "analysis_type": "summary"
        },
        step_id=1,
        description="LLM 失败测试"
    )

    result = registry.execute(call, context)

    assert result.status == "error"
    assert result.raw_output["error_code"] == "E501"


def test_extract_insights_invalid_analysis_type(registry, mock_data_store, mock_llm):
    """测试无效的分析类型。"""
    context = ToolExecutionContext(
        data_query_service=MagicMock(),
        extras={
            "data_store": mock_data_store,
            "planner_llm": mock_llm
        }
    )

    call = ToolCall(
        plugin_id="extract_insights",
        args={
            "source_ref": "test-data",
            "analysis_type": "invalid_type"
        },
        step_id=1,
        description="无效类型测试"
    )

    result = registry.execute(call, context)

    assert result.status == "error"
    assert result.raw_output["error_code"] == "E102"


def test_tool_registration(registry):
    """测试工具注册。"""
    spec = registry.get("extract_insights")
    assert spec is not None
    assert spec.plugin_id == "extract_insights"
    assert spec.execution_mode == "full"
    assert spec.description == "使用 LLM 从数据中提取洞察、趋势、模式"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
