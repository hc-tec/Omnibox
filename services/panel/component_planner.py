"""
组件选择规划器

根据路由清单和配置选择合适的组件，支持：
- 必选组件（required）: 总是包含，不计入 max_components 限制
- 偏好组件（preferred）: 优先选择，但受 max_components 限制
- 可选组件（optional）: 默认选中的组件，在配额允许时包含

组件选择策略：
1. 先选择所有必选组件
2. 再选择偏好组件（按配置顺序）
3. 最后选择可选组件（按优先级排序：成本低 → required → default）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set

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
    组件选择配置

    Args:
        max_components: 最大组件数量（必选组件不计入此限制）
        preferred_components: 用户偏好的组件列表，优先于其他可选组件
        allow_optional: 是否允许选择可选组件（非必须的组件）
    """

    max_components: int = 2
    preferred_components: Sequence[str] = ()
    allow_optional: bool = True


def plan_components_for_route(
    route: str,
    *,
    config: Optional[ComponentPlannerConfig] = None,
    manifest: Optional[RouteAdapterManifest] = None,
) -> Optional[List[str]]:
    """
    根据路由和配置选择合适的组件

    Args:
        route: RSSHub 路由路径
        config: 规划器配置，指定最大组件数、用户偏好等
        manifest: 已获取的清单，避免重复查询；为 None 时自动调用 get_route_manifest

    Returns:
        选中的组件 ID 列表；若清单不存在，返回 None 表示使用默认路径

    选择策略：
        1. 必选组件总是包含（不计入 max_components 限制）
        2. 优先选择配置中的偏好组件
        3. 在配额允许时选择默认选中的可选组件
        4. 最后按优先级选择其他可选组件
    """
    manifest = manifest or get_route_manifest(route)
    if manifest is None:
        return None

    config = config or ComponentPlannerConfig()

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
            if component not in seen:
                if not force and len(selected) >= config.max_components:
                    break
                selected.append(component)
                seen.add(component)

    # 第一步：必选组件总是保留，即便超过 max_components
    _add_components(required, force=True)

    # 第二步：偏好组件（用户配置中的优先组件）
    preferred = [
        entry.component_id
        for entry in manifest.components
        if entry.component_id in config.preferred_components
    ]
    _add_components(preferred)

    # 第三步：默认选中的可选组件（仅在允许可选时）
    if config.allow_optional:
        defaults = [
            entry.component_id
            for entry in manifest.components
            if entry.default_selected and entry.component_id not in seen
        ]
        _add_components(defaults)

    # 第四步：其他可选组件按优先级排序选择（仅在允许可选时）
    if config.allow_optional:
        remaining = sorted(
            (
                entry
                for entry in manifest.components
                if entry.component_id not in seen
            ),
            key=_manifest_sort_key,
        )
        for entry in remaining:
            if len(selected) >= config.max_components:
                break
            selected.append(entry.component_id)
            seen.add(entry.component_id)

    # 兜底策略：如果没有任何组件被选中，选择成本最低的组件（仅在允许可选时）
    if not selected and manifest.components and config.allow_optional:
        best = min(manifest.components, key=_manifest_sort_key)
        selected.append(best.component_id)

    return selected


def _manifest_sort_key(entry: ComponentManifestEntry) -> tuple[int, int]:
    """排序优先级：成本 -> 是否 required -> 是否默认"""
    cost_rank = _COST_ORDER.get(entry.cost, 1)
    required_rank = 0 if entry.required else 1
    default_rank = 0 if entry.default_selected else 1
    return cost_rank, required_rank, default_rank
