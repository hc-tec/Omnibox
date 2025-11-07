"""
LLM 组件规划器（LLM Component Planner）

职责：
  使用大语言模型（LLM）进行智能组件选择，作为规则引擎的备选方案。

适用场景：
  1. 复杂的用户查询，规则引擎难以准确判断
  2. 需要理解用户意图的场景（如"帮我分析一下"）
  3. 作为规则引擎的兜底方案

输出格式：
  LLM 返回 JSON 格式的决策：
    {
      "selected": ["ListPanel", "LineChart"],
      "reasons": ["用户明确要求看趋势", "数据量足够绘制图表"]
    }
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from query_processor.config import llm_settings
from query_processor.llm_client import create_llm_client, LLMClient

from services.panel.adapters import RouteAdapterManifest
from services.panel.component_planner import (
    ComponentPlannerConfig,
    PlannerContext,
    PlannerDecision,
)

logger = logging.getLogger(__name__)


class LLMComponentPlanner:
    """
    基于 LLM 的组件规划器。

    功能：
      - 使用 LLM 分析用户查询和数据摘要
      - 返回 JSON 格式的组件选择决策
      - 自动验证组件有效性和必选组件
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        初始化 LLM 组件规划器。

        Args:
            llm_client: LLM 客户端实例（可选，默认从配置创建）

        Note:
            如果 LLM 客户端初始化失败，planner 会自动降级为不可用状态
        """
        try:
            self.client = llm_client or create_llm_client(
                llm_settings.llm_provider,
                model=llm_settings.openai_model if llm_settings.llm_provider == "openai" else None,
            )
        except Exception as exc:  # pragma: no cover - configuration failure
            logger.warning("LLM planner unavailable: %s", exc)
            self.client = None

    def is_available(self) -> bool:
        """
        检查 LLM 规划器是否可用。

        Returns:
            True: LLM 客户端初始化成功
            False: LLM 客户端不可用
        """
        return self.client is not None

    def plan(
        self,
        *,
        route: str,
        manifest: Optional[RouteAdapterManifest],
        summary: Dict[str, Any],
        context: PlannerContext,
        config: ComponentPlannerConfig,
    ) -> Optional[PlannerDecision]:
        """
        使用 LLM 规划组件选择。

        Args:
            route: 路由标识
            manifest: 组件清单
            summary: 数据摘要（来自 analytics 模块）
            context: 规划上下文
            config: 规划配置

        Returns:
            PlannerDecision 对象
            若 LLM 不可用或解析失败，返回 None

        处理流程：
            1. 构建 prompt（包含 manifest, summary, context）
            2. 调用 LLM 生成 JSON 响应
            3. 解析并验证组件有效性
            4. 自动补充必选组件
            5. 应用 max_components 限制
        """
        if not self.client or manifest is None:
            return None

        prompt = self._build_prompt(route, manifest, summary, context, config)
        try:
            # 使用较低的 temperature 确保输出稳定性
            raw = self.client.generate(
                prompt,
                temperature=min(llm_settings.llm_temperature, 0.5),
                max_tokens=min(llm_settings.llm_max_tokens, 800),
            )
        except Exception as exc:  # pragma: no cover - network failure
            logger.warning("LLM planner call failed: %s", exc)
            return None

        data = self._parse_response(raw)
        if not data:
            return None

        # 验证组件有效性（过滤不存在的组件 ID）
        selected = [
            component
            for component in data.get("selected", [])
            if component in {entry.component_id for entry in manifest.components}
        ]
        if not selected:
            return None

        # 补充必选组件（如果 LLM 遗漏）
        required = [entry.component_id for entry in manifest.components if entry.required]
        for component in required:
            if component not in selected:
                selected.insert(0, component)

        # 应用 max_components 限制
        selected = selected[: config.max_components or len(selected)]
        reasons = data.get("reasons") or []
        reasons.insert(0, "engine: llm")
        return PlannerDecision(components=selected, reasons=reasons)

    def _build_prompt(
        self,
        route: str,
        manifest: RouteAdapterManifest,
        summary: Dict[str, Any],
        context: PlannerContext,
        config: ComponentPlannerConfig,
    ) -> str:
        """
        构建 LLM prompt。

        Args:
            route: 路由标识
            manifest: 组件清单
            summary: 数据摘要
            context: 规划上下文
            config: 规划配置

        Returns:
            格式化的 prompt 字符串（包含 JSON 格式的输入）
        """
        # 提取组件信息
        component_lines = []
        for entry in manifest.components:
            component_lines.append(
                {
                    "component_id": entry.component_id,
                    "description": entry.description,
                    "cost": entry.cost,
                    "default_selected": entry.default_selected,
                    "required": entry.required,
                    "hints": entry.hints,
                }
            )

        # 构建结构化 prompt
        prompt = {
            "instruction": (
                "You are a UI component planner. Based on the manifest and data summary, "
                "select the best components to render. Return valid JSON only."
            ),
            "constraints": {
                "max_components": config.max_components,
                "allow_optional": config.allow_optional,
                "user_query": context.raw_query,
            },
            "route": route,
            "manifest": component_lines,
            "data_summary": {
                "item_count": summary.get("item_count"),
                "metrics": summary.get("metrics"),
                "sample_titles": summary.get("sample_titles"),
            },
        }

        return (
            "Decide which components to render. Output JSON with fields "
            '`selected` (array of component ids in order) and `reasons` (array of strings). '
            "Manifest and data summary:\n"
            f"{json.dumps(prompt, ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _parse_response(raw: str) -> Optional[Dict[str, Any]]:
        """
        解析 LLM 响应为 JSON 对象。

        容错处理：
            1. 移除 markdown 代码块标记（```json ... ```）
            2. 尝试直接解析 JSON
            3. 如果失败，尝试提取第一个 JSON 对象（{...}）

        Args:
            raw: LLM 原始响应文本

        Returns:
            解析后的字典对象
            若解析失败，返回 None
        """
        if not raw:
            return None
        raw = raw.strip()

        # 处理 markdown 代码块（LLM 常见输出格式）
        if "```" in raw:
            start = raw.find("```")
            end = raw.rfind("```")
            snippet = raw[start + 3 : end]
            # 移除 "json" 语言标识符
            if snippet.strip().startswith("json"):
                snippet = snippet.strip()[4:]
            raw = snippet.strip()

        # 尝试直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # 兜底：提取第一个 JSON 对象
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1:
                return None
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                return None
