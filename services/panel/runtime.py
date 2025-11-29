"""
High-level helpers orchestrating schema/view model/DSL pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from api.schemas.panel import UIBlock
from services.panel.panel_spec import (
    DisplaySchema,
    PanelDSL,
    StructuredDataEnvelope,
)
from services.panel.dsl_runtime import PanelDSLParser
from services.panel.dsl_renderer import PanelDSLRenderer
from services.panel.sandbox_executor import SandboxExecutor
from services.panel.view_model_builder import GeneratedViewModel, ViewModelBuilder
from services.panel.component_whitelist import get_default_component_whitelist


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
        enforce_component_whitelist: bool = True,
    ):
        self.view_model_builder = view_model_builder or ViewModelBuilder()
        self.sandbox_executor = sandbox_executor or SandboxExecutor()
        if enforce_component_whitelist:
            component_whitelist = (
                set(allowed_components) if allowed_components is not None else get_default_component_whitelist()
            )
        else:
            component_whitelist = None

        self.dsl_parser = PanelDSLParser(allowed_components=component_whitelist)
        self.dsl_renderer = PanelDSLRenderer(self.sandbox_executor)

    def build_view_models(self, schemas: Iterable[DisplaySchema]) -> Dict[str, GeneratedViewModel]:
        registry: Dict[str, GeneratedViewModel] = {}
        for schema in schemas:
            vm = self.view_model_builder.build(schema)
            registry[vm.view_model_id] = vm
        return registry

    def render_dsl(
        self,
        dsl_payload: PanelDSL | Dict[str, Any],
        envelopes: Dict[str, StructuredDataEnvelope],
        view_models: Dict[str, GeneratedViewModel] | None = None,
    ) -> List[UIBlock]:
        payload: Dict[str, Any]
        if isinstance(dsl_payload, PanelDSL):
            payload = dsl_payload.model_dump()
        else:
            payload = dsl_payload

        dsl = self.dsl_parser.parse(payload)
        return self.dsl_renderer.render(dsl, envelopes, view_models)
