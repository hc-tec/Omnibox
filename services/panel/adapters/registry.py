"""
Route Adapter 注册与执行框架

提供路由适配器的注册、查找和执行机制，支持：
- 前缀匹配路由注册
- 组件选择性生成（通过 AdapterExecutionContext）
- 向后兼容 2 参数和 3 参数的 adapter 函数
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import inspect
from functools import wraps
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence

from api.schemas.panel import ComponentInteraction, LayoutHint, SourceInfo


@dataclass
class AdapterBlockPlan:
    """
    组件渲染计划

    描述如何渲染一个前端组件，包括组件类型、数据绑定、交互配置等。
    Adapter 返回多个 BlockPlan 时，前端会按顺序渲染这些组件。

    支持嵌套：通过 children 字段可以构建组件树，例如 Card 包含多个 StatisticCard。
    """
    component_id: str  # 组件ID，如 "ListPanel", "LineChart", "Card"
    props: Dict[str, Any]  # 组件属性，如字段映射 {"title_field": "title"}
    options: Dict[str, Any] = field(default_factory=dict)  # 组件选项，如样式配置
    interactions: List[ComponentInteraction] = field(default_factory=list)  # 交互行为
    title: Optional[str] = None  # 组件标题
    layout_hint: Optional[LayoutHint] = None  # 布局提示
    confidence: float = 0.6  # 渲染置信度（0-1），前端可据此排序或过滤
    children: Optional[List[AdapterBlockPlan]] = None  # 子组件列表，用于容器组件（如 Card、Tabs）✨


@dataclass
class RouteAdapterResult:
    """
    Adapter 执行结果

    包含标准化后的数据记录、组件渲染计划和统计信息。
    """
    records: List[Dict[str, Any]]  # 标准化数据记录（已通过契约验证）
    block_plans: List[AdapterBlockPlan] = field(default_factory=list)  # 组件渲染计划
    stats: Dict[str, Any] = field(default_factory=dict)  # 统计信息（如数据源、总数等）


@dataclass(frozen=True)
class AdapterExecutionContext:
    """
    Adapter 执行上下文

    控制 adapter 的行为，目前主要用于指定需要生成哪些组件。
    """
    requested_components: Optional[Sequence[str]] = None  # 请求的组件列表，None 表示无限制

    def wants(self, component_id: str, *, default: bool = True) -> bool:
        """
        判断是否需要生成指定组件

        Args:
            component_id: 组件ID
            default: requested_components 为 None 时的默认返回值

        Returns:
            True 表示需要生成该组件，False 表示跳过

        处理三种情况：
        - requested_components=None: 无限制，返回 default（通常为 True）
        - requested_components=[]: 不生成任何组件，始终返回 False
        - requested_components=['ListPanel', ...]: 检查 component_id 是否在列表中
        """
        if self.requested_components is None:
            return default
        return component_id in self.requested_components


# Adapter 函数签名：接收源信息、原始记录、可选上下文，返回处理结果
RouteAdapter = Callable[
    [SourceInfo, Sequence[Dict[str, Any]], Optional[AdapterExecutionContext]],
    RouteAdapterResult,
]


@dataclass(frozen=True)
class ComponentManifestEntry:
    """
    组件清单条目。

    描述 adapter 支持的一个组件，包括描述、成本、默认选中状态等元信息。
    """
    component_id: str  # 组件ID
    description: Optional[str] = None  # 组件功能描述
    cost: Literal["low", "medium", "high"] = "medium"  # 生成成本（影响是否默认启用）
    default_selected: bool = True  # 是否默认选中
    required: bool = False  # 是否为必需组件（必需组件永远不会被跳过）
    hints: Dict[str, Any] = field(default_factory=dict)  # 额外提示（如依赖的统计指标、min_items 等）
    field_requirements: List[Dict[str, str]] = field(default_factory=list)  # 组件必需的字段声明（如 link, summary, published_at）


@dataclass(frozen=True)
class RouteAdapterManifest:

    """
    路由适配器清单

    声明 adapter 支持的所有组件及相关说明，供前端或调用方查询。
    """
    components: List[ComponentManifestEntry]  # 支持的组件列表
    notes: Optional[str] = None  # 适配器说明


def _default_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    """
    默认适配器：直接返回原始记录，不做任何处理

    当路由没有注册专用适配器时使用此兜底适配器。
    这通常意味着该路由缺少适配器实现，应该引起开发者注意。
    """
    return RouteAdapterResult(
        records=list(records),
        block_plans=[],  # 不提供任何组件计划
        stats={
            "using_default_adapter": True,
            "route": source_info.route if source_info else None,
            "warning": f"No adapter registered for route: {source_info.route if source_info else 'unknown'}",
        }
    )


class RouteAdapterRegistry:
    """
    路由适配器注册表

    管理所有路由到 adapter 的映射关系，支持：
    - 精确匹配：/github/trending/daily
    - 前缀匹配：/github/trending → 匹配 /github/trending/daily、/github/trending/weekly 等
    - 按路由长度排序，优先匹配更具体的路由
    """
    def __init__(self):
        self._routes: List[tuple[str, RouteAdapter]] = []  # (路由, adapter) 列表
        self._manifests: List[tuple[str, RouteAdapterManifest]] = []  # (路由, 清单) 列表

    def register(
        self,
        route: str,
        adapter: RouteAdapter,
        manifest: Optional[RouteAdapterManifest] = None,
    ) -> None:
        """
        注册路由适配器

        如果路由已存在则覆盖，注册后按路由长度降序排序（更具体的路由优先匹配）。
        """
        normalized = self._normalize(route)
        for idx, (existing_route, _) in enumerate(self._routes):
            if existing_route == normalized:
                self._routes[idx] = (normalized, adapter)
                break
        else:
            self._routes.append((normalized, adapter))
            self._routes.sort(key=lambda item: len(item[0]), reverse=True)

        if manifest is not None:
            manifest_copy = replace(manifest, components=list(manifest.components))
            for idx, (existing_route, _) in enumerate(self._manifests):
                if existing_route == normalized:
                    self._manifests[idx] = (normalized, manifest_copy)
                    break
            else:
                self._manifests.append((normalized, manifest_copy))
                self._manifests.sort(key=lambda item: len(item[0]), reverse=True)

    def get(self, route: str) -> RouteAdapter:
        """
        查找路由对应的适配器

        先尝试精确匹配，再尝试前缀匹配。找不到时返回默认适配器。
        """
        if not route:
            return _default_adapter

        target = self._normalize(route)
        for registered, adapter in self._routes:
            if target == registered:
                return adapter
            if self._is_prefix_match(target, registered):
                return adapter
        return _default_adapter

    def get_manifest(self, route: str) -> Optional[RouteAdapterManifest]:
        """查找路由对应的适配器清单"""
        if not route:
            return None
        target = self._normalize(route)
        for registered, manifest in self._manifests:
            if target == registered or self._is_prefix_match(target, registered):
                return manifest
        return None

    def clear(self) -> None:
        """清空所有注册的适配器和清单（主要用于测试）"""
        self._routes.clear()
        self._manifests.clear()

    @staticmethod
    def _normalize(route: str) -> str:
        """规范化路由：确保以 / 开头，去除尾部 /"""
        route = (route or "").strip()
        if not route.startswith("/"):
            route = f"/{route}"
        if route != "/" and route.endswith("/"):
            return route.rstrip("/")
        return route or "/"

    @staticmethod
    def _is_prefix_match(target: str, registered: str) -> bool:
        """
        判断是否为前缀匹配

        示例：
        - target=/github/trending/daily, registered=/github/trending → True
        - target=/github/trending, registered=/github/trending → True (精确匹配)
        - target=/githubx, registered=/github → False (不是路径前缀)
        """
        if not registered:
            return False
        if target.startswith(registered):
            remainder = target[len(registered) :]
            if not remainder:
                return True
            if registered.endswith("/"):
                return True
            return remainder.startswith("/")
        return False


_registry = RouteAdapterRegistry()

# ========== 模块级 API ==========

def register_route_adapter(
    route: str,
    adapter: RouteAdapter,
    manifest: Optional[RouteAdapterManifest] = None,
) -> None:
    """注册路由适配器到全局注册表"""
    _registry.register(route, adapter, manifest)


def get_route_adapter(route: str) -> RouteAdapter:
    """从全局注册表查找适配器"""
    return _registry.get(route)


def get_route_manifest(route: str) -> Optional[RouteAdapterManifest]:
    """从全局注册表查找适配器清单"""
    return _registry.get_manifest(route)


def clear_route_adapters() -> None:
    """清空全局注册表（主要用于测试）"""
    _registry.clear()


def route_adapter(
    *routes: str, manifest: Optional[RouteAdapterManifest] = None
) -> Callable[[Callable[..., RouteAdapterResult]], RouteAdapter]:
    """
    路由适配器装饰器

    用法：
        @route_adapter("/github/trending", "/github/trending/daily", manifest=MANIFEST)
        def github_adapter(source_info, records, context=None):
            return RouteAdapterResult(...)

    特性：
    - 支持注册多个路由到同一个 adapter
    - 自动检测函数签名，支持 2 参数（旧）和 3 参数（新）两种风格
    - 2 参数风格：def adapter(source_info, records)
    - 3 参数风格：def adapter(source_info, records, context=None)
    """
    if not routes:
        raise ValueError("At least one route must be provided for registration.")

    def decorator(func: Callable[..., RouteAdapterResult]) -> RouteAdapter:
        # 检查函数签名以支持向后兼容
        signature = inspect.signature(func)
        expects_context = len(signature.parameters) >= 3

        @wraps(func)
        def wrapper(
            source_info: SourceInfo,
            records: Sequence[Dict[str, Any]],
            context: Optional[AdapterExecutionContext] = None,
        ) -> RouteAdapterResult:
            # 根据原函数签名决定是否传递 context 参数
            if expects_context:
                return func(source_info, records, context)
            return func(source_info, records)

        # 注册所有路由
        for route in routes:
            register_route_adapter(route, wrapper, manifest)
        return wrapper  # type: ignore[return-value]

    return decorator
