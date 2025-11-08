"""
LLM 组件规划器（LLM Component Planner）

职责：
  使用大语言模型（LLM）进行智��组件选择，作为规则引擎的备选方案。

适用场景：
  1. 复杂的用户查询，规则引擎难以准确判断
  2. 需要理解用户意图的场景（如"帮我分析一下"）
  3. 作为规则引擎的兜底方案

新增特性：
  - 缓存机制：避免重复调用 LLM（默认缓存 32 条决策）
  - 结构化 prompt：包含完整的上下文和约束信息
  - 类型验证：确保 LLM 返回的 JSON 格式正确

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
from query_processor.llm_client import LLMClient, create_llm_client

from services.panel.adapters import RouteAdapterManifest
from services.panel.component_planner import (
    ComponentPlannerConfig,
    PlannerContext,
    PlannerDecision,
)

logger = logging.getLogger(__name__)


class LLMComponentPlanner:
    """
    基于 LLM 的组件规划器（带缓存）。

    功能：
      - 使用 LLM 分析用户查询和数据摘要
      - 返回 JSON 格式的组件选择决策
      - ���动验证组件有效性和必选组件
      - 缓存决策结果，避免重复调用
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, cache_size: int = 32):
        """
        初始化 LLM 组件规划器。

        Args:
            llm_client: LLM 客户端实例（可选，默认从配置创建）
            cache_size: 缓存容量（默认 32 条）

        Note:
            如果 LLM 客户端初始化失败，planner 会自动降级为不可用状态
        """
        self._cache_size = cache_size
        self._cache: Dict[str, PlannerDecision] = {}  # 缓存字典：cache_key -> PlannerDecision
        try:
            self.client = llm_client or create_llm_client(
                llm_settings.llm_provider,
                model=llm_settings.openai_model
                if llm_settings.llm_provider == "openai"
                else None,
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
        使用 LLM 规划组件选择（带缓存）。

        Args:
            route: 路由标识
            manifest: 组件清单
            summary: 数据摘要（来自 analytics 模块）
            context: 规划上下文
            config: 规划配置

        Returns:
            PlannerDecision 对象
            若 LLM 不可用、解析失败或缓存命中，返回对应结果

        处理流程：
            1. 检查缓存，命中则直接返回
            2. 构建 prompt（包含 manifest, summary, context）
            3. 调用 LLM 生成 JSON 响应
            4. 解析并验证组件有效性
            5. 自动补充必选组件
            6. 应用 max_components 限制
            7. 存入缓存
        """
        if not self.client or manifest is None:
            return None

        # 检查缓存
        cache_key = self._cache_key(route, summary, context, config)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 构建 prompt 并调用 LLM
        prompt = self._build_prompt(route, manifest, summary, context, config)
        try:
            # 使用较低的 temperature 确保输出稳定性
            raw = self.client.generate(
                prompt,
                temperature=min(llm_settings.llm_temperature, 0.5),
                max_tokens=min(llm_settings.llm_max_tokens, 800),
            )
        except Exception as exc:  # pragma: no cover - LLM failure
            logger.warning("LLM planner call failed: %s", exc)
            return None

        # 解析 LLM 响应
        data = self._parse_response(raw)
        if not data:
            return None

        # 验证组件有效性（过滤不存在的组件 ID）
        manifest_components = {entry.component_id for entry in manifest.components}
        # NOTE: data["selected"] 和 data["reasons"] 已由 _parse_response 验证存在
        selected = [
            component for component in data["selected"] if component in manifest_components
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
        reasons = data["reasons"]
        reasons.insert(0, "engine: llm")
        decision = PlannerDecision(components=selected, reasons=reasons)

        # 存入缓存
        self._store_cache(cache_key, decision)
        return decision

    def _build_prompt(
        self,
        route: str,
        manifest: RouteAdapterManifest,
        summary: Dict[str, Any],
        context: PlannerContext,
        config: ComponentPlannerConfig,
    ) -> str:
        """
        构建结构化的 LLM prompt。

        Args:
            route: 路由标识
            manifest: 组件清单
            summary: 数据摘要
            context: 规划上下文
            config: 规划配置

        Returns:
            格式化的 prompt 字符串（包含 JSON 格式的输入）
        """
        # 提取组件清单信息
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

        # 构建结构化 payload
        payload = {
            "instruction": (
                "You are a UI component planner. Based on the manifest, data summary, "
                "and user request, choose the best components. Output valid JSON."
            ),
            "constraints": {
                "max_components": config.max_components,
                "allow_optional": config.allow_optional,
                "preferred_components": list(config.preferred_components),
            },
            "context": {
                "user_query": context.raw_query,
                "layout_mode": context.layout_mode,
                "user_preferences": list(context.user_preferences),
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
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _parse_response(raw: str) -> Optional[Dict[str, Any]]:
        """
        解析 LLM 响应为 JSON 对象（带验证）。

        容错处理：
            1. 移除 markdown 代码块标记（```json ... ```）
            2. 尝试直接解析 JSON
            3. 如果失败，尝试提取第一个 JSON 对象（{...}）

        类型验证：
            - 确保返回的是字典
            - 验证 "selected" 是字符串列表
            - 验证 "reasons" 是字符串列表

        Args:
            raw: LLM 原始响应文本

        Returns:
            包含 "selected" 和 "reasons" 键的字典
            若解析失败或格式不正确，返回 None
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

        # 尝试直接解析 JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # 兜底：提取第一个 JSON 对象
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1:
                return None
            try:
                data = json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                return None

        # 验证数据结构和类型
        if not isinstance(data, dict):
            return None
        selected = data.get("selected")
        reasons = data.get("reasons")
        if not isinstance(selected, list) or not all(isinstance(s, str) for s in selected):
            return None
        if not isinstance(reasons, list) or not all(isinstance(r, str) for r in reasons):
            return None

        return {"selected": selected, "reasons": reasons}

    def _cache_key(
        self,
        route: str,
        summary: Dict[str, Any],
        context: PlannerContext,
        config: ComponentPlannerConfig,
    ) -> str:
        """
        生成缓存键。

        缓存键包含所有影响决策的因素：
            - route: 路由标识
            - summary: 数据摘要（item_count, metrics, sample_titles）
            - context: 用户查询、布局模式、用户偏好
            - config: max_components, allow_optional, preferred_components

        Args:
            route: 路由标识
            summary: 数据摘要
            context: 规划上下文
            config: 规划配置

        Returns:
            JSON 格式的缓存键（确保键的稳定性和唯一性）
        """
        return json.dumps(
            {
                "route": route,
                "item_count": summary.get("item_count"),
                "metrics": summary.get("metrics"),
                "samples": summary.get("sample_titles"),
                "user_query": context.raw_query,
                "layout_mode": context.layout_mode,
                "user_preferences": list(context.user_preferences),
                "max_components": config.max_components,
                "allow_optional": config.allow_optional,
                "preferred": list(config.preferred_components),
            },
            ensure_ascii=False,
            sort_keys=True,  # 确保键顺序一致
        )

    def _store_cache(self, key: str, decision: PlannerDecision) -> None:
        """
        存储缓存决策（LRU 淘汰策略）。

        策略说明：
            - 如果键已存在，先删除再插入（实现 LRU）
            - 超过容量时淘汰最早的条目（Python 3.7+ dict 保持插入顺序）

        Args:
            key: 缓存键
            decision: 规划决策
        """
        # 如果键已存在，先删除（实现 LRU：最近使用的移到最后）
        if key in self._cache:
            self._cache.pop(key)

        # 插入新决策
        self._cache[key] = decision

        # 超过容量时淘汰最早的条目
        if len(self._cache) > self._cache_size:
            oldest_key = next(iter(self._cache))
            self._cache.pop(oldest_key)
