"""
High-level helpers orchestrating schema/view model/DSL pipeline.
"""

from __future__ import annotations

from typing import Dict, Iterable, List

from api.schemas.panel import UIBlock
from services.panel.panel_spec import (
    DisplaySchema,
    PanelDSL,
    StructuredDataEnvelope,
    validate_panel_dsl,
)
from services.panel.dsl_runtime import PanelDSLParser
from services.panel.dsl_renderer import PanelDSLRenderer
from services.panel.sandbox_executor import SandboxExecutor
from services.panel.view_model_builder import GeneratedViewModel, ViewModelBuilder


class PanelRuntime:
    """
    Facade 将 DisplaySchema → ViewModel → PanelDSL 渲染串接起来。
    """

    def __init__(
        self,
        *,
        view_model_builder: ViewModelBuilder | None = None,
        sandbox_executor: SandboxExecutor | None = None,
        allowed_components: Iterable[str] | None = None,
    ):
        self.view_model_builder = view_model_builder or ViewModelBuilder()
        self.sandbox_executor = sandbox_executor or SandboxExecutor()
        self.dsl_parser = PanelDSLParser(allowed_components=allowed_components)
        self.dsl_renderer = PanelDSLRenderer(self.sandbox_executor)

    def build_view_models(self, schemas: Iterable[DisplaySchema]) -> Dict[str, GeneratedViewModel]:
        registry: Dict[str, GeneratedViewModel] = {}
        for schema in schemas:
            vm = self.view_model_builder.build(schema)
            registry[vm.view_model_id] = vm
        return registry

    def render_dsl(
        self,
        dsl_payload: Dict,
        envelopes: Dict[str, StructuredDataEnvelope],
    ) -> List[UIBlock]:
        dsl = self.dsl_parser.parse(dsl_payload)
        return self.dsl_renderer.render(dsl, envelopes)
