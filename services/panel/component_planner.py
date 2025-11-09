"""
组件规划器（Component Planner）

职责：
  根据路由的 manifest 和运行时上下文，智能选择需要渲染的可视化组件。

选择策略：
  1. 必选组件：无论配置如何，必须包含（如 ListPanel）
  2. 用户偏好：通过 raw_query 提取的关键词推断偏好（优先级最高）
  3. 默认推荐：manifest 中标记为 default_selected 的组件
  4. 动态过滤：根据 hints（如 min_items）和 context 过滤不合适的组件
  5. 兜底机制：若无组件可选，选择成本最低的组件
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Set, Tuple

from services.panel.adapters import (
    ComponentManifestEntry,
    RouteAdapterManifest,
    get_route_manifest,
)

logger = logging.getLogger(__name__)

# 组件成本排序（用于优先选择低成本组件）
_COST_ORDER = {"low": 0, "medium": 1, "high": 2}

# 组件标签映射（用于将组件 ID 映射到语义标签）
_COMPONENT_TAGS = {
    "ListPanel": "list",
    "LineChart": "chart",
    "StatisticCard": "stat",
}


@dataclass
class ComponentPlannerConfig:
    """
    组件规划器配置。

    Attributes:
        max_components: 最多选择的组件数量（不影响必选组件）
        preferred_components: 配置偏好的组件列表（会被 _should_include 过滤）
        allow_optional: 是否允许选择可选组件
    """

    max_components: int = 2
    preferred_components: Sequence[str] = ()
    allow_optional: bool = True


@dataclass
class PlannerContext:
    """
    规划器运行时上下文。

    Attributes:
        item_count: 数据项数量（用于 min_items 过滤）
        user_preferences: 用户明确指定的偏好标签（跳过过滤）
        raw_query: 用户原始查询文本（用于关键词提取）
        layout_mode: 布局模式（如 single_card, dashboard 等）
    """

    item_count: Optional[int] = None
    user_preferences: Sequence[str] = ()
    raw_query: Optional[str] = None
    layout_mode: Optional[str] = None


@dataclass
class PlannerDecision:
    """
    规划决策结果。

    Attributes:
        components: 选中的组件 ID 列表（有序）
        reasons: 决策理由列表（用于调试和日志）
    """

    components: List[str]
    reasons: List[str]


def plan_components_for_route(
    route: str,
    *,
    config: Optional[ComponentPlannerConfig] = None,
    context: Optional[PlannerContext] = None,
    manifest: Optional[RouteAdapterManifest] = None,
) -> Optional[PlannerDecision]:
    """
    为指定路由规划需要渲染的组件。

    Args:
        route: 路由标识（如 "/github/trending/daily"）
        config: 规划器配置
        context: 运行时上下文
        manifest: 路由的组件清单（可选，默认自动获取）

    Returns:
        PlannerDecision 对象（包含选中的组件和决策理由）
        若路由没有对应的 manifest，返回 None

    规划逻辑：
        1. 强制包含所有必选组件
        2. 根据用户偏好（从 raw_query 提取关键词）添加组件
        3. 添加默认推荐的可选组件（如果 allow_optional=True）
        4. 添加剩余组件直到达到 max_components 限制
        5. 如果没有任何组件被选中，兜底选择成本最低的组件
    """
    manifest = manifest or get_route_manifest(route)
    if manifest is None:
        logger.warning(
            f"组件规划失败：路由 '{route}' 没有注册 RouteAdapterManifest。"
            "这通常意味着该路由缺少适配器实现或 manifest 声明。"
        )
        return None

    config = config or ComponentPlannerConfig()
    context = context or PlannerContext()
    preference_tags = _derive_preference_tags(context)  # 从用户查询提取偏好标签
    reasons: List[str] = []

    # 收集必选组件
    required = [entry.component_id for entry in manifest.components if entry.required]
    selected: List[str] = []
    seen: Set[str] = set()

    def _add_components(
        components: Iterable[str],
        *,
        force: bool = False,
        reason_provider: Optional[Callable[[str], str]] = None,
    ) -> None:
        """
        批量添加组件到 selected 列表。

        Args:
            components: 待添加的组件 ID 列表
            force: 是否强制添加（不受 max_components 限制）
            reason_provider: 生成决策理由的回调函数
        """
        for component in components:
            if component in seen:
                continue
            if not force and len(selected) >= config.max_components:
                break
            selected.append(component)
            seen.add(component)
            if reason_provider:
                reasons.append(reason_provider(component))

    # 阶段 1: 强制添加必选组件
    _add_components(
        required,
        force=True,
        reason_provider=lambda component: f"{component} is required by manifest.",
    )

    # 阶段 2: 根据用户偏好添加组件（优先级最高，跳过过滤）
    for entry in manifest.components:
        tag = _component_tag(entry.component_id)
        # 用户偏好组件跳过 _should_include 过滤（尊重用户明确意图）
        if tag and tag in preference_tags:
            text = f"User preference favors '{tag}', include {entry.component_id}."
            _add_components([entry.component_id], reason_provider=lambda _, r=text: r)

    # 阶段 3: 添加可选组件（如果允许）
    if config.allow_optional:
        # 3.1: 添加默认推荐组件
        for entry in manifest.components:
            if (
                entry.default_selected
                and entry.component_id not in seen
                and _should_include(entry, context, reasons)
            ):
                text = f"{entry.component_id} is default-recommended."
                _add_components([entry.component_id], reason_provider=lambda _, r=text: r)

        # 3.2: 添加剩余组件（按偏好和成本排序）
        remaining = sorted(
            (
                entry
                for entry in manifest.components
                if entry.component_id not in seen
                and _should_include(entry, context, reasons)
            ),
            key=lambda entry: (
                _preference_penalty(entry, preference_tags),  # 偏好惩罚（匹配偏好标签优先）
                *_manifest_sort_key(entry),  # 成本、必选、默认推荐排序
            ),
        )
        for entry in remaining:
            if len(selected) >= config.max_components:
                break
            text = f"{entry.component_id} added as optional component (cost={entry.cost})."
            _add_components([entry.component_id], reason_provider=lambda _, r=text: r)

    # 阶段 4: 兜底逻辑（如果没有任何组件被选中）
    if not selected:
        fallback_pool = [
            entry for entry in manifest.components if _should_include(entry, context, reasons)
        ]
        if not fallback_pool:
            fallback_pool = list(manifest.components)
        if fallback_pool:
            best = min(
                fallback_pool,
                key=lambda entry: (
                    _preference_penalty(entry, preference_tags),
                    *_manifest_sort_key(entry),
                ),
            )
            selected.append(best.component_id)
            reasons.append(f"No other candidates available, fallback to {best.component_id}.")

    return PlannerDecision(components=selected, reasons=reasons)


def _manifest_sort_key(entry: ComponentManifestEntry) -> Tuple[int, int, int]:
    """
    生成组件的排序键（用于优先级排序）。

    排序规则（从高到低）：
        1. 成本低的优先（low < medium < high）
        2. 必选组件优先
        3. 默认推荐组件优先

    Returns:
        (cost_rank, required_rank, default_rank) 三元组
    """
    cost_rank = _COST_ORDER.get(entry.cost, 1)
    required_rank = 0 if entry.required else 1
    default_rank = 0 if entry.default_selected else 1
    return cost_rank, required_rank, default_rank


def _should_include(
    entry: ComponentManifestEntry,
    context: PlannerContext,
    reasons: List[str],
) -> bool:
    """
    判断组件是否应该被包含。

    检查规则：
    1. min_items 约束：如果组件要求最小数据项数，检查 context.item_count
    """
    # 检查 min_items 约束（通用规则）
    min_items = entry.hints.get("min_items")
    if min_items is not None and context.item_count is not None:
        if context.item_count < min_items:
            reasons.append(
                f"Skip {entry.component_id}: fewer than {min_items} records "
                f"(current: {context.item_count})."
            )
            return False

    return True


def _derive_preference_tags(context: PlannerContext) -> Set[str]:
    """
    从上下文中提取用户偏好标签。

    提取来源：
        1. user_preferences: 用户明确指定的标签
        2. layout_mode: 布局模式（如 single_card → stat, dashboard → chart）
        3. raw_query: 从用户查询文本中提取关键词

    关键词规则：
        - chart: "chart", "trend", "graph", "曲线", "走势图"
        - list: "list", "table", "列表", "清单"
        - stat: "card", "stat", "指标", "数值", "指标卡"

    Returns:
        偏好标签集合（全部小写）
    """
    tags = {tag.lower() for tag in context.user_preferences}

    # 从布局模式推断偏好
    if context.layout_mode:
        mode = context.layout_mode.lower()
        if mode in {"single_card", "stat"}:
            tags.add("stat")
        if mode in {"timeline", "dashboard"}:
            tags.add("chart")

    # 从用户查询文本提取关键词
    if context.raw_query:
        text = context.raw_query.lower()
        # 图表相关关键词
        if any(keyword in text for keyword in ("chart", "trend", "graph", "曲线", "走势图")):
            tags.add("chart")
        # 列表相关关键词
        if any(keyword in text for keyword in ("list", "table", "列表", "清单")):
            tags.add("list")
        # 指标卡相关关键词
        if any(keyword in text for keyword in ("card", "stat", "指标", "数值", "指标卡")):
            tags.add("stat")

    return tags


def _component_tag(component_id: str) -> Optional[str]:
    """
    获取组件对应的语义标签。

    Args:
        component_id: 组件 ID（如 "ListPanel", "LineChart"）

    Returns:
        语义标签（如 "list", "chart", "stat"）
        若组件未定义标签，返回 None
    """
    return _COMPONENT_TAGS.get(component_id)


def _preference_penalty(entry: ComponentManifestEntry, tags: Set[str]) -> int:
    """
    计算组件的偏好惩罚分数（用于排序）。

    Args:
        entry: 组件清单条目
        tags: 用户偏好标签集合

    Returns:
        0: 组件匹配用户偏好标签（优先选择）
        1: 组件不匹配用户偏好标签（低优先级）
    """
    tag = _component_tag(entry.component_id)
    return 0 if tag and tag in tags else 1
