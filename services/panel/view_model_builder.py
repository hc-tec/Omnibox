"""
Utility to convert DisplaySchema instances into component-ready view models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from services.panel.panel_spec import DisplaySchema
from services.panel.view_models import (
    ensure_statistic_card,
    ensure_table,
    ensure_list_panel,
    ensure_fallback,
    validate_records,
)


@dataclass
class GeneratedViewModel:
    view_model_id: str
    component_id: str
    data: Dict[str, Any]
    props: Dict[str, Any]
    contract_id: Optional[str] = None


class ViewModelBuilder:
    """
    Convert DisplaySchema payloads into concrete component view models.
    """

    def build(self, schema: DisplaySchema) -> GeneratedViewModel:
        if schema.component_id:
            return self._handle_component_contract(schema)

        handler = getattr(self, f"_handle_{schema.kind}", None)
        if handler:
            return handler(schema)
        return self._handle_fallback(schema)

    def _handle_metric_set(self, schema: DisplaySchema) -> GeneratedViewModel:
        metrics = schema.fields.get("metrics") or []
        records: List[Dict[str, Any]] = []
        for idx, metric in enumerate(metrics, start=1):
            value = metric.get("value") if isinstance(metric, dict) else None
            if value is None:
                continue
            record = {
                "id": f"metric-{idx}",
                "metric_title": metric.get("label") or metric.get("title") or schema.title or "指标",
                "metric_value": value,
                "metric_unit": metric.get("unit"),
                "metric_delta_text": metric.get("delta"),
                "metric_trend": metric.get("trend"),
            }
            records.append(record)

        validated = ensure_statistic_card(records or [
            {
                "id": "metric-1",
                "metric_title": schema.title or "指标",
                "metric_value": 0,
                "metric_unit": "",
                "metric_delta_text": None,
                "metric_trend": None,
            }
        ])
        return GeneratedViewModel(
            view_model_id=f"vm-{uuid4().hex[:8]}",
            component_id="StatisticCard",
            data={"items": [record.model_dump() for record in validated]},
            props={"title": schema.title or "指标概览"},
            contract_id=schema.contract_id,
        )

    def _handle_comparison(self, schema: DisplaySchema) -> GeneratedViewModel:
        rows = schema.fields.get("rows") or []
        columns = schema.fields.get("columns") or []
        table_model = ensure_table([
            {
                "columns": columns,
                "rows": rows,
            }
        ])[0]

        return GeneratedViewModel(
            view_model_id=f"vm-{uuid4().hex[:8]}",
            component_id="Table",
            data={"columns": [col.model_dump() for col in table_model.columns], "rows": table_model.rows},
            props={"title": schema.title or "对比结果"},
            contract_id=schema.contract_id,
        )

    def _handle_cluster(self, schema: DisplaySchema) -> GeneratedViewModel:
        clusters = schema.fields.get("clusters") or []
        records: List[Dict[str, Any]] = []
        for idx, cluster in enumerate(clusters, start=1):
            record = {
                "id": f"cluster-{idx}",
                "title": cluster.get("name") or f"Cluster {idx}",
                "summary": cluster.get("summary"),
                "categories": cluster.get("keywords"),
            }
            records.append(record)

        validated = ensure_list_panel(records)
        return GeneratedViewModel(
            view_model_id=f"vm-{uuid4().hex[:8]}",
            component_id="ListPanel",
            data={"items": [item.model_dump() for item in validated]},
            props={"title": schema.title or "聚类结果"},
            contract_id=schema.contract_id,
        )

    def _handle_record_set(self, schema: DisplaySchema) -> GeneratedViewModel:
        items = schema.fields.get("items") or []
        normalized: List[Dict[str, Any]] = []
        for idx, item in enumerate(items[:20], start=1):
            record = dict(item)
            record.setdefault("id", record.get("link") or f"record-{idx}")
            record.setdefault("title", record.get("title") or schema.title or f"记录 {idx}")
            normalized.append(record)
        validated = ensure_list_panel(normalized)
        return GeneratedViewModel(
            view_model_id=f"vm-{uuid4().hex[:8]}",
            component_id="ListPanel",
            data={"items": [item.model_dump() for item in validated]},
            props={"title": schema.title or "数据列表"},
            contract_id=schema.contract_id,
        )

    def _handle_fallback(self, schema: DisplaySchema) -> GeneratedViewModel:
        record = {
            "title": schema.title or "洞察",
            "content": schema.summary or "暂无法渲染该洞察类型。",
        }
        validated = ensure_fallback([record])
        return GeneratedViewModel(
            view_model_id=f"vm-{uuid4().hex[:8]}",
            component_id="FallbackRichText",
            data={"items": [item.model_dump() for item in validated]},
            props={"title": schema.title or "洞察"},
            contract_id=schema.contract_id,
        )

    def _handle_component_contract(self, schema: DisplaySchema) -> GeneratedViewModel:
        component_id = schema.component_id or "FallbackRichText"
        raw_items = schema.fields.get("items") or []
        props = dict(schema.fields.get("props") or {})
        candidate_items: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw_items or [], start=1):
            record = dict(item)
            record.setdefault("id", f"{component_id}-record-{idx}")
            candidate_items.append(record)
        if not candidate_items:
            candidate_items = [{"id": f"{component_id}-record-1"}]
        mapping = (schema.contract_metadata or {}).get("props_mapping") or {}
        normalized_items: List[Dict[str, Any]] = []
        for record in candidate_items:
            normalized_item = dict(record)
            for key, source_field in mapping.items():
                if not key.endswith("_field"):
                    continue
                const_target = key.replace("_field", "")
                if normalized_item.get(const_target) is None and source_field in normalized_item:
                    normalized_item[const_target] = normalized_item[source_field]
            normalized_items.append(normalized_item)

        validated_items = validate_records(component_id, normalized_items)
        normalized = validated_items

        data: Dict[str, Any]
        if component_id == "Table":
            table_payload = normalized[0] if normalized else {"columns": [], "rows": []}
            data = table_payload
        else:
            data = {"items": normalized}

        props.setdefault("title", schema.title or "")

        return GeneratedViewModel(
            view_model_id=f"vm-{uuid4().hex[:8]}",
            component_id=component_id,
            data=data,
            props=props,
            contract_id=schema.contract_id,
        )
