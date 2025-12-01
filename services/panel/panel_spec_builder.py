from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from api.schemas.panel import LayoutNode, LayoutTree, PanelPayload, UIBlock
from services.panel.panel_spec import (
    DataBinding,
    DisplaySchema,
    EnvelopeCursor,
    PanelDSL,
    PanelNode,
    StructuredDataEnvelope,
    StructuredDataSchema,
)
from services.panel.runtime import PanelRuntime
from langgraph_agents.component_contracts import get_contract_by_id, get_contract_by_component, ComponentContract

_panel_runtime = PanelRuntime()
_DEFAULT_CONTRACT_KIND = {
    "StatisticCard": "metric_set",
    "ListPanel": "record_set",
    "MediaCardGrid": "record_set",
}


def _resolve_component_contract(metadata: Dict[str, Any]) -> Optional[ComponentContract]:
    contract_id = metadata.get("contract_id") or metadata.get("component_contract_id")
    component_id = metadata.get("component_id")
    contract: Optional[ComponentContract] = None
    if contract_id:
        contract = get_contract_by_id(contract_id)
    if not contract and component_id:
        contract = get_contract_by_component(component_id)
    return contract


def _infer_display_kind_for_contract(component_id: str) -> str:
    return _DEFAULT_CONTRACT_KIND.get(component_id, "custom")
_DEFAULT_CONTRACT_KIND = {
    "StatisticCard": "metric_set",
    "ListPanel": "record_set",
    "MediaCardGrid": "record_set",
}


def build_panel_spec_from_dataset(
    dataset: Dict[str, Any],
    *,
    data_id: Optional[str],
    max_items: int = 6,
) -> Dict[str, Any]:
    """
    将通用 dataset payload 转换为 panel_spec/panel_payload。
    """

    envelope = _build_envelope(dataset, data_id=data_id, max_items=max_items)
    display_schema = _build_display_schema(dataset, envelope.data_id, max_items)
    view_models = _panel_runtime.build_view_models([display_schema])
    panel_dsl = PanelDSL(
        layout=[
            PanelNode(
                node=vm.component_id,
                props=vm.props,
                data_binding=DataBinding(view_model_id=vm_id),
            )
            for vm_id, vm in view_models.items()
        ]
    )
    rendered_blocks = _panel_runtime.render_dsl(
        panel_dsl,
        {envelope.data_id: envelope},
        view_models,
    )
    panel_payload = _build_panel_payload(rendered_blocks)

    contracts_applied = [
        {
            "component_id": vm.component_id,
            "contract_id": vm.contract_id,
            "view_model_id": vm_id,
            "title": vm.props.get("title"),
        }
        for vm_id, vm in view_models.items()
        if vm.contract_id
    ]

    panel_spec = {
        "data_envelopes": {envelope.data_id: envelope.model_dump()},
        "display_schemas": {envelope.data_id: display_schema.model_dump()},
        "view_models": {
            vm_id: {
                "component_id": vm.component_id,
                "data": vm.data,
                "props": vm.props,
                "contract_id": vm.contract_id,
            }
            for vm_id, vm in view_models.items()
        },
        "panel_dsl": panel_dsl.model_dump(),
        "rendered_preview": [block.model_dump() for block in rendered_blocks],
        "degraded_components": [],
        "contracts_applied": contracts_applied,
    }
    return {
        "panel_spec": panel_spec,
        "panel_payload": panel_payload.model_dump(),
    }


def _build_envelope(dataset: Dict[str, Any], data_id: Optional[str], max_items: int) -> StructuredDataEnvelope:
    items = dataset.get("items") or []
    if not isinstance(items, list):
        items = [items]
    preview = items[:max_items]
    metadata = dict(dataset.get("metadata") or {})
    schema = StructuredDataSchema(
        type="record",
        description=metadata.get("instruction") or dataset.get("feed_title") or dataset.get("title") or "数据集",
    )
    cursor = EnvelopeCursor(
        total=len(items) if items else metadata.get("item_count"),
        sampled=len(preview),
    )
    summary = _normalize_summary(dataset.get("summary") or dataset.get("reasoning") or metadata.get("instruction"))
    envelope_id = data_id or dataset.get("generated_path") or f"dataset-{uuid4().hex[:8]}"
    return StructuredDataEnvelope(
        data_id=envelope_id,
        schema=schema,
        summary=summary,
        preview=preview,
        cursor=cursor,
        metadata=metadata,
    )


def _build_display_schema(dataset: Dict[str, Any], source_ref: str, max_items: int) -> DisplaySchema:
    metadata = dict(dataset.get("metadata") or {})
    items = dataset.get("items") or []
    if not isinstance(items, list):
        items = [items]

    contract = _resolve_component_contract(metadata)
    if contract:
        return _build_contract_display_schema(contract, dataset, metadata, source_ref, max_items)

    if _should_build_metric_set(dataset, metadata, items):
        metric_label, metric_value = _extract_metric(dataset, metadata, items)
        metrics = [
            {
                "label": metric_label,
                "value": metric_value,
                "unit": metadata.get("unit"),
                "delta": metadata.get("delta_text"),
                "trend": metadata.get("trend"),
            }
        ]
        summary = _normalize_summary(dataset.get("summary") or dataset.get("reasoning"))
        return DisplaySchema(
            kind="metric_set",
            title=metadata.get("instruction") or dataset.get("feed_title") or dataset.get("title") or "指标概览",
            summary=summary,
            fields={"metrics": metrics},
            source_refs=[source_ref],
        )

    record_items = items[:max_items]
    fields = {
        "items": record_items,
        "stats": dataset.get("stats") or metadata.get("stats") or {"item_count": len(items)},
    }
    summary = _normalize_summary(dataset.get("summary") or dataset.get("reasoning"))
    return DisplaySchema(
        kind="record_set",
        title=dataset.get("feed_title") or dataset.get("title") or "数据列表",
        summary=summary,
        fields=fields,
        source_refs=[source_ref],
    )


def _build_contract_display_schema(
    contract: ComponentContract,
    dataset: Dict[str, Any],
    metadata: Dict[str, Any],
    source_ref: str,
    max_items: int,
) -> DisplaySchema:
    items = dataset.get("items") or metadata.get("items") or []
    if not isinstance(items, list):
        items = [items]
    record_items = items[:max_items]
    props = dict(contract.props_mapping or {})
    component_props = metadata.get("component_props") or dataset.get("component_props") or {}
    props.update(component_props)
    layout_hint = metadata.get("layout_hint") or contract.layout_hint or {}
    fields = {
        "items": record_items,
        "props": props,
        "layout_hint": layout_hint,
    }
    summary = _normalize_summary(
        dataset.get("summary") or dataset.get("reasoning") or metadata.get("instruction")
    )
    # 标题优先级：feed_title > title > contract.description，避免使用过长的 instruction
    title = dataset.get("feed_title") or dataset.get("title") or contract.description or "数据分析"
    return DisplaySchema(
        kind=_infer_display_kind_for_contract(contract.component_id),
        component_id=contract.component_id,
        contract_id=contract.contract_id,
        contract_metadata={
            "layout_hint": layout_hint,
            "props_mapping": contract.props_mapping,
        },
        title=title,
        summary=summary,
        fields=fields,
        source_refs=[source_ref],
    )


def _should_build_metric_set(dataset: Dict[str, Any], metadata: Dict[str, Any], items: List[Any]) -> bool:
    if metadata.get("panel_hint") == "statistic_card":
        return True
    if isinstance(metadata.get("metric_value"), (int, float)):
        return True
    result = dataset.get("result")
    if isinstance(result, dict):
        metrics = result.get("metrics")
        if isinstance(metrics, list) and metrics:
            return True
        if any(isinstance(result.get(key), (int, float)) for key in ("total", "count", "value", "sum")):
            return True
    # 单条记录且包含指标字段（value/count等）时也视为指标卡
    if items:
        first = items[0] if isinstance(items[0], dict) else None
        if isinstance(first, dict):
            if any(isinstance(first.get(field), (int, float)) for field in ("value", "metric_value", "count", "total")):
                return True
    return False


def _extract_metric(dataset: Dict[str, Any], metadata: Dict[str, Any], items: List[Any]) -> tuple[str, float]:
    label = metadata.get("instruction") or dataset.get("feed_title") or dataset.get("title") or "数量"
    candidates: List[Optional[float]] = []
    metric_value = metadata.get("metric_value")
    if isinstance(metric_value, (int, float)):
        candidates.append(float(metric_value))
    for key in ("metric_value", "value", "total", "count", "sum", "item_count"):
        value = metadata.get(key)
        if isinstance(value, (int, float)):
            candidates.append(float(value))
    stats = metadata.get("stats") or {}
    if isinstance(stats, dict):
        for key in ("total", "count", "value", "sum"):
            value = stats.get(key)
            if isinstance(value, (int, float)):
                candidates.append(float(value))
    result = dataset.get("result")
    if isinstance(result, dict):
        if isinstance(result.get("metrics"), list) and result["metrics"]:
            first = result["metrics"][0]
            if isinstance(first, dict):
                label = first.get("label") or first.get("title") or label
                value = first.get("value")
                if isinstance(value, (int, float)):
                    candidates.append(float(value))
        for key in ("total", "count", "value", "sum"):
            value = result.get(key)
            if isinstance(value, (int, float)):
                candidates.append(float(value))
    if not candidates:
        if metadata.get("item_count") is not None:
            try:
                candidates.append(float(metadata["item_count"]))
            except (TypeError, ValueError):
                pass
        elif isinstance(items, list):
            candidates.append(float(len(items)))
    if not candidates and items:
        first = items[0]
        if isinstance(first, dict):
            for key in ("value", "count", "total"):
                val = first.get(key)
                if isinstance(val, (int, float)):
                    candidates.append(float(val))
                    break
    metric_value = candidates[0] if candidates else 0.0
    return label, metric_value


def _build_panel_payload(blocks: List[UIBlock]) -> PanelPayload:
    nodes = []
    for index, block in enumerate(blocks, start=1):
        node_id = f"row-{block.id}"
        props = {
            "span": block.options.get("span", 12),
            "min_height": block.options.get("min_height"),
            "layout_size": block.options.get("layout_size"),
        }
        nodes.append(
            LayoutNode(
                type="row",
                id=node_id,
                children=[block.id],
                props=props,
            )
        )
    layout = LayoutTree(mode="append", nodes=nodes, history_token=None)
    return PanelPayload(mode="append", layout=layout, blocks=blocks)


def _normalize_summary(summary_value: Any) -> Optional[str]:
    if summary_value is None:
        return None
    if isinstance(summary_value, dict):
        return json.dumps(summary_value, ensure_ascii=False)
    return str(summary_value)
