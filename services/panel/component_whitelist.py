"""
Component whitelist helpers for Panel DSL validation.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Iterable, Set, Optional

from services.panel.component_registry import default_components

# 预留的容器/布局组件，暂未在 component_registry 中建模
CONTAINER_COMPONENTS: Set[str] = {
    "TabGroup",
    "Accordion",
    "Section",
    "MultiColumn",
    "Stack",
    "Column",
    "Row",
}


def _base_component_ids() -> Set[str]:
    """从 ComponentRegistry 默认定义中获取组件 ID 集合。"""

    return {definition.id for definition in default_components()}


def _load_frontend_manifest_component_ids(manifest_path: Optional[Path] = None) -> Set[str]:
    """
    解析前端 componentManifest.ts 中声明的组件 ID。

    若文件不存在或解析失败，返回空集合。
    """

    if manifest_path is None:
        manifest_path = (
            Path(__file__)
            .resolve()
            .parents[3]
            / "frontend"
            / "src"
            / "shared"
            / "componentManifest.ts"
        )

    try:
        content = manifest_path.read_text(encoding="utf8")
    except FileNotFoundError:
        return set()
    except OSError:
        return set()

    pattern = re.compile(r'id:\s*"(?P<component>[A-Za-z0-9_]+)"')
    return set(pattern.findall(content))


def build_component_whitelist(
    extra_components: Iterable[str] | None = None,
    *,
    manifest_path: Optional[Path] = None,
) -> Set[str]:
    """
    构建 DSL 允许使用的组件列表。

    包含默认数据类组件 + 预留容器组件，可额外传入扩展组件。
    """

    allowed = set(_base_component_ids())
    allowed.update(CONTAINER_COMPONENTS)
    allowed.update(_load_frontend_manifest_component_ids(manifest_path))
    if extra_components:
        allowed.update(extra_components)
    return allowed


@lru_cache(maxsize=1)
def get_default_component_whitelist() -> Set[str]:
    """缓存的默认白名单集合，用于 PanelRuntime 默认配置。"""

    return build_component_whitelist()
