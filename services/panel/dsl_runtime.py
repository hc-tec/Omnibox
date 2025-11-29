"""
Panel DSL parser and validation helpers.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

from services.panel.panel_spec import (
    PanelDSL,
    PanelNode,
    PanelSpecError,
    validate_panel_dsl,
)


class PanelDSLValidationError(RuntimeError):
    """Raised when DSL payload references未知组件或存在安全问题。"""

    def __init__(self, message: str, payload: Optional[Dict] = None):
        super().__init__(message)
        self.payload = payload or {}


class PanelDSLParser:
    """
    负责解析/校验 Panel DSL 的轻量封装。
    """

    def __init__(self, allowed_components: Optional[Iterable[str]] = None):
        self.allowed_components: Optional[Set[str]] = (
            set(allowed_components) if allowed_components else None
        )

    def parse(self, payload: Dict) -> PanelDSL:
        """校验原始 DSL 字典并返回 typed 对象。"""

        try:
            dsl = validate_panel_dsl(payload)
        except PanelSpecError as exc:  # pragma: no cover - 复用上层错误处理
            raise PanelDSLValidationError("Invalid DSL payload", payload=payload) from exc

        if self.allowed_components:
            illegal = [
                node.component
                for node in dsl.iter_nodes()
                if node.component not in self.allowed_components
            ]
            if illegal:
                raise PanelDSLValidationError(
                    f"Components not allowed: {', '.join(sorted(set(illegal)))}",
                    payload={"illegal_components": illegal},
                )

        return dsl

    @staticmethod
    def iter_data_bindings(dsl: PanelDSL) -> List[PanelNode]:
        """返回所有有 data_binding 的节点，便于运行时构建 ViewModel。"""

        return [node for node in dsl.iter_nodes() if node.data_binding is not None]
