"""
Task Graph Planner

负责根据用户查询生成任务图。优先使用 LLM 生成结构化计划，若 LLM 不可用则
退化为单节点计划（仅 fetch_data），不再通过规则或启发式操作内容。

V5.0 架构：工具定义从 ToolRegistry 自动注入，不硬编码在 Prompt 中。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from .schema import (
    GraphNode,
    TaskGraph,
    TaskGraphPlan,
    PlannerContext,
)

if TYPE_CHECKING:
    from langgraph_agents.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class _PlannerDebug:
    mode: str
    raw_response: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {"mode": self.mode}
        if self.raw_response is not None:
            payload["raw_response"] = self.raw_response
        if self.error:
            payload["error"] = self.error
        return payload


class TaskGraphPlanner:
    """
    Task Graph Planner 实现。

    V5.0 架构：工具定义从 ToolRegistry 自动注入到 System Prompt。
    """

    # 基础 System Prompt（工具定义将动态注入）
    BASE_SYSTEM_PROMPT = """你是一名 Task Graph Planner。

目标：将自然语言查询转换为结构化的任务图（Task Graph），用于驱动多步骤调用。

输出要求：
- 仅输出 JSON 对象，不要额外文字。
- JSON 顶层需包含 `reasoning`、`nodes` 和 `metadata`。
- `nodes` 是有序数组，每个节点包含：
  - `id`: 唯一标识
  - `type`: fetch_data / transform / analysis
  - `tool`: 使用的工具名（必须是下方可用工具之一）
  - `description`: 对节点的自然语言说明
  - `params`: 执行该节点所需的参数（参考工具 schema）
  - `input_refs`: 依赖的上游节点 id 列表
  - `expected_output`: 对输出的描述
- `metadata` 需至少包含 `output_node`，指向最终输出节点 id。

{tools_section}

⚠️ 重要规划原则：
1. 当用户查询包含"筛选"、"过滤"、"包含XX的"、"只要XX"等条件时，必须添加 filter_data 节点。
2. transform 类型节点必须引用 fetch_data 节点作为输入（input_refs）。
3. 复杂查询模式："获取A数据中，满足B条件的" = fetch_data + filter_data 两个节点。

示例 - 带筛选条件的查询：
用户: "B站影视飓风投稿视频中，标题包含英雄联盟的视频"
{{
  "reasoning": "需要先获取影视飓风投稿，再过滤标题包含'英雄联盟'的视频",
  "nodes": [
    {{
      "id": "fetch",
      "type": "fetch_data",
      "tool": "fetch_public_data",
      "description": "获取影视飓风投稿视频",
      "params": {{"query": "B站 影视飓风 投稿视频", "filter_datasource": "bilibili"}},
      "input_refs": [],
      "expected_output": "DataQueryResult"
    }},
    {{
      "id": "filter",
      "type": "transform",
      "tool": "filter_data",
      "description": "筛选标题包含英雄联盟的视频",
      "params": {{"source_ref": "fetch", "conditions": {{"title": {{"$contains": "英雄联盟"}}}}}},
      "input_refs": ["fetch"],
      "expected_output": "DataQueryResult"
    }}
  ],
  "metadata": {{"output_node": "filter"}}
}}
"""

    # 用于 Task Graph 的核心工具 ID 列表（与 ToolRegistry 中注册的 plugin_id 一致）
    TASK_GRAPH_TOOLS = ["fetch_public_data", "filter_data", "compare_data", "aggregate_data"]

    MAX_LLM_RETRY = 2

    def __init__(self, llm_client=None, tool_registry: Optional["ToolRegistry"] = None):
        """
        初始化 Task Graph Planner。

        Args:
            llm_client: LLM 客户端
            tool_registry: 工具注册表（可选，用于自动注入工具定义）
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self._system_prompt_cache: Optional[str] = None

    def _build_tools_section(self) -> str:
        """
        从 ToolRegistry 构建工具定义部分。

        Returns:
            工具定义的 Markdown 格式文本
        """
        if not self.tool_registry:
            # 降级：无注册表时使用最小化内置定义
            return """可用工具：
1. fetch_public_data (type: fetch_data): 获取 RSSHub 公共数据
   - params: {"query": "自然语言查询", "filter_datasource": "可选数据源"}
2. filter_data (type: transform): 根据条件过滤数据
   - params: {"source_ref": "数据引用ID", "conditions": {"字段": {"$操作符": "值"}}}
   - 支持操作符: $eq, $contains, $gt, $lt, $in, $between"""

        lines = ["可用工具："]
        for tool_id in self.TASK_GRAPH_TOOLS:
            try:
                spec = self.tool_registry.get(tool_id)
                node_type = self._infer_node_type(tool_id)
                lines.append(f"\n### {tool_id} (type: {node_type})")
                lines.append(f"描述: {spec.description}")
                if spec.schema:
                    schema_json = json.dumps(spec.schema, ensure_ascii=False, indent=2)
                    lines.append(f"参数 schema:\n```json\n{schema_json}\n```")
            except KeyError:
                logger.debug("工具 %s 未注册，跳过", tool_id)
                continue

        return "\n".join(lines)

    @staticmethod
    def _infer_node_type(tool_id: str) -> str:
        """根据工具 ID 推断节点类型。"""
        if tool_id in ("fetch_public_data", "source_discovery"):
            return "fetch_data"
        elif tool_id in ("filter_data", "compare_data"):
            return "transform"
        elif tool_id in ("aggregate_data", "insights_extractor"):
            return "analysis"
        return "transform"

    def _get_system_prompt(self) -> str:
        """获取完整的 System Prompt（带工具定义注入）。"""
        if self._system_prompt_cache is None:
            tools_section = self._build_tools_section()
            self._system_prompt_cache = self.BASE_SYSTEM_PROMPT.format(
                tools_section=tools_section
            )
        return self._system_prompt_cache

    def plan(
        self,
        user_query: str,
        context: Optional[PlannerContext] = None,
    ) -> TaskGraphPlan:
        context = context or PlannerContext()

        if self.llm_client:
            try:
                return self._plan_with_llm(user_query, context)
            except (ValueError, json.JSONDecodeError) as exc:
                # 明确的解析错误
                logger.warning("LLM Task Graph 规划失败（解析错误），降级为单节点: %s", exc)
            except (ConnectionError, TimeoutError) as exc:
                # 网络相关错误
                logger.warning("LLM Task Graph 规划失败（网络错误），降级为单节点: %s", exc)
            except Exception as exc:
                # 其他未预期的错误，仍然降级但记录详细信息
                logger.warning(
                    "LLM Task Graph 规划失败（未知错误 %s），降级为单节点: %s",
                    type(exc).__name__,
                    exc,
                )

        return self._plan_simple_fetch(user_query, context)

    def _plan_with_llm(self, user_query: str, context: PlannerContext) -> TaskGraphPlan:
        """LLM 驱动规划逻辑。"""
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "query": user_query,
                        "intent_hint": context.intent_hint,
                        "filter_datasource": context.filter_datasource,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        payload, raw_response = self._invoke_llm(messages)
        debug = _PlannerDebug(mode="llm", raw_response=raw_response)
        nodes = [
            GraphNode(
                id=node["id"],
                type=node["type"],
                tool=node.get("tool"),
                description=node.get("description", ""),
                params=node.get("params", {}),
                input_refs=node.get("input_refs", []),
                expected_output=node.get("expected_output"),
                streaming_label=node.get("streaming_label"),
            )
            for node in payload.get("nodes", [])
        ]

        graph = TaskGraph(nodes=nodes, metadata=payload.get("metadata", {}))
        reasoning = payload.get("reasoning", "LLM 规划")
        complexity = "multi_step" if len(nodes) > 1 else "single_step"

        # 输出规划结果日志，便于调试
        node_summary = [f"{n.id}({n.type})" for n in nodes]
        logger.info(
            "Task Graph 规划完成: %d 节点 [%s], 复杂度=%s",
            len(nodes),
            " → ".join(node_summary),
            complexity,
        )

        plan = TaskGraphPlan(
            graph=graph,
            reasoning=reasoning,
            complexity=complexity,
            requires_research=False,
            llm_trace=debug.to_dict(),
        )
        return plan

    def _plan_simple_fetch(self, user_query: str, context: PlannerContext) -> TaskGraphPlan:
        nodes = [
            GraphNode(
                id="fetch_primary",
                type="fetch_data",
                tool="fetch_public_data",
                description="获取原始数据",
                params={
                    "query": user_query,
                    "filter_datasource": context.filter_datasource,
                },
                input_refs=[],
                expected_output="DataQueryResult",
            )
        ]
        graph = TaskGraph(nodes=nodes, metadata={"output_node": nodes[-1].id})
        plan = TaskGraphPlan(
            graph=graph,
            reasoning="LLM 不可用或解析失败，使用单节点计划",
            complexity="single_step",
            llm_trace=_PlannerDebug(mode="fallback_simple").to_dict(),
        )
        return plan

    def _invoke_llm(self, messages: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], str]:
        last_response = ""
        for attempt in range(1, self.MAX_LLM_RETRY + 1):
            response = self.llm_client.chat(messages=messages, temperature=0.2)
            last_response = response
            try:
                payload = self._extract_json_payload(response)
                return payload, response
            except ValueError as exc:
                if attempt == self.MAX_LLM_RETRY:
                    raise exc
                logger.warning("LLM 响应解析失败，第 %d 次重试: %s", attempt, exc)
                messages.append(
                    {
                        "role": "user",
                        "content": "⚠️ 上一次回答不是合法 JSON。请仅输出 JSON 对象，严格按照系统提示。",
                    }
                )
        raise ValueError("LLM 响应无法解析为 JSON", last_response)

    @staticmethod
    def _extract_json_payload(response: str) -> Dict[str, Any]:
        cleaned = response.strip()
        if not cleaned:
            raise ValueError("LLM 返回空响应")

        fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.S)
        if fenced_match:
            cleaned = fenced_match.group(1)

        if not cleaned.startswith("{"):
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[start : end + 1]

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"无法解析 LLM JSON 响应: {exc}") from exc
