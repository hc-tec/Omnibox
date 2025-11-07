"""
自适应组件规划器

根据路由清单和运行时上下文选择合适的组件，支持：
- 必选组件（required）: 总是包含，不计入 max_components 限制
- 用户偏好组件（user_preferences）: 运行时明确指定，优先选择
- 配置偏好组件（preferred_components）: 静态配置的优先组件
- 可选组件（optional）: 默认选中的组件，在配额允许时包含

组件选择策略：
1. 先选择所有必选组件
2. 再选择用户偏好组件（跳过启发式过滤）
3. 然后选择配置偏好组件（应用启发式过滤）
4. 在配额允许时选择默认可选组件
5. 最后按优先级选择其他可选组件
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set

from services.panel.adapters import (
    ComponentManifestEntry,
    RouteAdapterManifest,
    get_route_manifest,
)

# 组件成本排序：成本越低越优先（用于兜底选择时的排序）
_COST_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass
class ComponentPlannerConfig:
    """
    组件选择静态配置

    Args:
        max_components: 最大组件数量（必选组件不计入此限制）
        preferred_components: 静态配置的偏好组件列表
        allow_optional: 是否允许选择可选组件（非必须的组件）
    """

    max_components: int = 2
    preferred_components: Sequence[str] = ()
    allow_optional: bool = True


@dataclass
class PlannerContext:
    """
    组件选择运行时上下文

    从 payload 和用户请求中提取的动态信息，用于启发式过滤。

    Args:
        item_count: 数据项数量（用于过滤需要最小数据量的组件，如图表）
        available_metrics: 可用的指标字段集合（用于过滤依赖特定指标的组件）
        user_preferences: 用户运行时偏好的组件列表（优先级最高，跳过过滤）
    """

    item_count: Optional[int] = None
    available_metrics: Optional[Set[str]] = None
    user_preferences: Sequence[str] = ()


def plan_components_for_route(
    route: str,
    *,
    config: Optional[ComponentPlannerConfig] = None,
    context: Optional[PlannerContext] = None,
    manifest: Optional[RouteAdapterManifest] = None,
) -> Optional[List[str]]:
    """
    根据路由和配置选择合适的组件

    Args:
        route: RSSHub 路由路径
        config: 静态配置，指定最大组件数、静态偏好等
        context: 运行时上下文，包含数据项数量、可用指标、用户偏好等
        manifest: 已获取的清单，避免重复查询；为 None 时自动调用 get_route_manifest

    Returns:
        选中的组件 ID 列表；若清单不存在，返回 None 表示使用默认路径

    选择策略：
        1. 必选组件总是包含（不计入 max_components 限制）
        2. 用户偏好组件优先（跳过启发式过滤）
        3. 配置偏好组件次之（应用启发式过滤）
        4. 在配额允许时选择默认可选组件
        5. 最后按优先级选择其他可选组件
        6. 兜底策略：如无组件被选中，选择成本最低的组件
    """
    manifest = manifest or get_route_manifest(route)
    if manifest is None:
        return None

    config = config or ComponentPlannerConfig()
    context = context or PlannerContext()

    # 分类提取不同类型的组件
    required = [entry.component_id for entry in manifest.components if entry.required]
    selected: List[str] = []
    seen: Set[str] = set()

    def _add_components(components: Iterable[str], *, force: bool = False) -> None:
        """
        添加组件到选中列表

        Args:
            components: 要添加的组件列表
            force: 是否强制添加（忽略 max_components 限制，用于必选组件）
        """
        for component in components:
            if component in seen:
                continue
            if not force and len(selected) >= config.max_components:
                break
            selected.append(component)
            seen.add(component)

    _add_components(required, force=True)

    # 用户偏好组件（运行时明确指定）不检查 _should_include
    user_preferred = [
        entry.component_id
        for entry in manifest.components
        if entry.component_id in context.user_preferences
    ]
    _add_components(user_preferred)

    # 配置偏好组件（静态配置）仍然检查 _should_include
    config_preferred = [
        entry.component_id
        for entry in manifest.components
        if entry.component_id in config.preferred_components
        and entry.component_id not in seen
        and _should_include(entry, context)
    ]
    _add_components(config_preferred)

    if config.allow_optional:
        defaults = [
            entry.component_id
            for entry in manifest.components
            if entry.default_selected
            and entry.component_id not in seen
            and _should_include(entry, context)
        ]
        _add_components(defaults)

        remaining = sorted(
            (
                entry
                for entry in manifest.components
                if entry.component_id not in seen and _should_include(entry, context)
            ),
            key=_manifest_sort_key,
        )
        for entry in remaining:
            if len(selected) >= config.max_components:
                break
            selected.append(entry.component_id)
            seen.add(entry.component_id)

    # 兜底策略：如果没有任何组件被选中，选择成本最低的组件（仅在允许可选时）
    if not selected and config.allow_optional:
        eligible = [entry for entry in manifest.components if _should_include(entry, context)]
        fallback_pool = eligible if eligible else list(manifest.components)
        if fallback_pool:
            best = min(fallback_pool, key=_manifest_sort_key)
            selected.append(best.component_id)

    return selected


def _manifest_sort_key(entry: ComponentManifestEntry) -> tuple[int, int, int]:
    """排序优先级：成本 -> 是否 required -> 是否默认"""
    cost_rank = _COST_ORDER.get(entry.cost, 1)
    required_rank = 0 if entry.required else 1
    default_rank = 0 if entry.default_selected else 1
    return cost_rank, required_rank, default_rank


def _should_include(entry: ComponentManifestEntry, context: PlannerContext) -> bool:
    """
    基于组件 hints 的启发式过滤规则

    支持的 hints：
    - min_items: 最小数据项要求（如图表组件通常需要至少 3 个数据点）
    - metrics: 依赖的指标字段列表（如统计卡片需要特定的指标字段）
    """
    # 检查最小数据项要求
    min_items = entry.hints.get("min_items")
    if min_items is not None and context.item_count is not None:
        if context.item_count < min_items:
            return False

    # 检查指标依赖
    metrics_required = set(entry.hints.get("metrics", []))
    if metrics_required:
        metrics_available = context.available_metrics
        if metrics_available is None:
            return False
        if metrics_required.isdisjoint(metrics_available):
            return False

    return True
