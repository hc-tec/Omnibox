"""
Helpers to serialize panel generation outputs into structured metadata.
"""

from __future__ import annotations

from typing import Any, Dict

from services.panel.panel_generator import PanelGenerationResult
from services.panel.runtime import PanelRuntime
from services.panel.panel_spec import DisplaySchema, PanelDSL, PanelNode, DataBinding
from services.panel.view_model_builder import GeneratedViewModel


def build_panel_spec_metadata(result: PanelGenerationResult) -> Dict[str, Any]:
    """将 PanelGenerationResult 转换为元数据，供 ChatService 返回。"""

    panel_runtime = PanelRuntime()
    envelopes_dump = {
        key: envelope.model_dump()
        for key, envelope in result.data_envelopes.items()
    }
    display_schemas_dump = {
        key: schema.model_dump()
        for key, schema in result.display_schemas.items()
    }
    view_models_dump = {
        key: {
            "component_id": vm.component_id,
            "data": vm.data,
            "props": vm.props,
        }
        for key, vm in result.view_models.items()
    }
    dsl_dump = result.panel_dsl.model_dump() if result.panel_dsl else None

    rendered_preview = None
    if result.panel_dsl:
        try:
            rendered_preview = [
                block.model_dump()
                for block in panel_runtime.render_dsl(
                    result.panel_dsl,
                    result.data_envelopes,
                    result.view_models,
                )
            ]
        except Exception as exc:  # pragma: no cover - 只做诊断
            rendered_preview = {"error": str(exc)}

    return {
        "data_envelopes": envelopes_dump,
        "display_schemas": display_schemas_dump,
        "view_models": view_models_dump,
        "panel_dsl": dsl_dump,
        "rendered_preview": rendered_preview,
    }


def build_panel_spec_metadata_from_components(
    schemas: Dict[str, DisplaySchema],
    view_models: Dict[str, GeneratedViewModel],
) -> Dict[str, Any]:
    envelopes_dump = {}
    display_schemas_dump = {key: schema.model_dump() for key, schema in schemas.items()}
    view_models_dump = {
        key: {
            "component_id": vm.component_id,
            "data": vm.data,
            "props": vm.props,
        }
        for key, vm in view_models.items()
    }

    panel_dsl = PanelDSL(
        layout=[
            PanelNode(
                node=vm.component_id,
                props=vm.props,
                data_binding=DataBinding(view_model_id=vm.view_model_id),
                events={},
                children=[],
            )
            for vm in view_models.values()
        ]
    )

    try:
        rendered_preview = [
            block.model_dump()
            for block in PanelRuntime().render_dsl(panel_dsl, {}, view_models)
        ]
    except Exception as exc:  # pragma: no cover
        rendered_preview = {"error": str(exc)}

    return {
        "data_envelopes": envelopes_dump,
        "display_schemas": display_schemas_dump,
        "view_models": view_models_dump,
        "panel_dsl": panel_dsl.model_dump(),
        "rendered_preview": rendered_preview,
    }
