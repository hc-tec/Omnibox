"""
Helpers to serialize panel generation outputs into structured metadata.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from services.panel.panel_generator import PanelGenerationResult
from services.panel.runtime import PanelRuntime
from services.panel.panel_spec import DisplaySchema, PanelDSL, PanelNode, DataBinding
from services.panel.view_model_builder import GeneratedViewModel
from api.schemas.panel import UIBlock


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
            "contract_id": vm.contract_id,
        }
        for key, vm in result.view_models.items()
    }
    dsl_dump = result.panel_dsl.model_dump() if result.panel_dsl else None

    rendered_preview = None
    degraded_components = []
    if result.panel_dsl:
        try:
            rendered_blocks = panel_runtime.render_dsl(
                result.panel_dsl,
                result.data_envelopes,
                result.view_models,
            )
            rendered_preview = [
                block.model_dump()
                for block in rendered_blocks
            ]
            degraded_components = _collect_degraded_blocks(rendered_blocks)
        except Exception as exc:  # pragma: no cover - 只做诊断
            rendered_preview = {"error": str(exc)}
            degraded_components = [{"error": str(exc)}]

    contracts_applied = [
        {
            "component_id": vm.component_id,
            "contract_id": vm.contract_id,
            "view_model_id": key,
            "title": vm.props.get("title"),
        }
        for key, vm in result.view_models.items()
        if vm.contract_id
    ]

    return {
        "data_envelopes": envelopes_dump,
        "display_schemas": display_schemas_dump,
        "view_models": view_models_dump,
        "panel_dsl": dsl_dump,
        "rendered_preview": rendered_preview,
        "degraded_components": degraded_components,
        "contracts_applied": contracts_applied,
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
            "contract_id": vm.contract_id,
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

    degraded_components: List[Dict[str, Any]] = []
    try:
        rendered_blocks = PanelRuntime().render_dsl(panel_dsl, {}, view_models)
        rendered_preview = [
            block.model_dump()
            for block in rendered_blocks
        ]
        degraded_components = _collect_degraded_blocks(rendered_blocks)
    except Exception as exc:  # pragma: no cover
        rendered_preview = {"error": str(exc)}
        degraded_components = [{"error": str(exc)}]

    contracts_applied = [
        {
            "component_id": vm.component_id,
            "contract_id": vm.contract_id,
            "view_model_id": key,
            "title": vm.props.get("title"),
        }
        for key, vm in view_models.items()
        if vm.contract_id
    ]

    return {
        "data_envelopes": envelopes_dump,
        "display_schemas": display_schemas_dump,
        "view_models": view_models_dump,
        "panel_dsl": panel_dsl.model_dump(),
        "rendered_preview": rendered_preview,
        "degraded_components": degraded_components,
        "contracts_applied": contracts_applied,
    }


def _collect_degraded_blocks(blocks: Iterable[UIBlock]) -> List[Dict[str, Any]]:
    degraded: List[Dict[str, Any]] = []

    def _walk(node: UIBlock) -> None:
        if node.options.get("degraded"):
            message = None
            if node.data:
                items = node.data.get("items") or []
                if items and isinstance(items[0], dict):
                    message = items[0].get("content")
            degraded.append(
                {
                    "block_id": node.id,
                    "title": node.title,
                    "rendered_component": node.component,
                    "original_component": node.options.get("original_component"),
                    "message": message,
                }
            )
        if node.children:
            for child in node.children:
                _walk(child)

    for block in blocks:
        _walk(block)
    return degraded
