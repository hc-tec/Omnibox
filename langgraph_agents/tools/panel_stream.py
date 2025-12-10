from __future__ import annotations

"""LangGraph 工具：在研究过程中推送实时数据卡片预览。"""

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

# 常量定义
MAX_PREVIEW_ITEMS = 20  # 单张预览卡片最多显示的记录数
MAX_PREVIEW_FIELDS = 3  # 每条记录最多保留的字段数，避免 payload 过大
MAX_TABLE_COLUMNS = 8  # Table 视图最大列数，避免超宽

from services.panel.panel_spec_builder import build_panel_spec_from_dataset

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool
from .data_ref_resolver import create_resolver_from_context, ResolvedData
from .data_payload_utils import unwrap_payload, extract_records, build_source_metadata, select_non_empty
from ..component_contracts import get_contract_by_id, ComponentContract

logger = logging.getLogger(__name__)


def register_panel_stream_tool(registry: ToolRegistry) -> None:
    """注册 emit_panel_preview 工具，用于基于契约生成面板并推送到前端。"""

    @tool(
        registry,
        plugin_id="emit_panel_preview",
        description="将已有数据引用按组件契约生成面板并推送（契约化视图适配 + 推送，一体化，无需额外 LLM）",
        schema={
            "type": "object",
            "properties": {
                "source_ref": {
                    "type": ["string", "integer"],
                    "description": "数据引用（data_id 或 $step.N），指向需要渲染的记录",
                },
                "contract_id": {
                    "type": "string",
                    "description": "组件契约 ID（如 Table-contract-v1），用于生成 panel_spec；未提供时按 metadata/默认推断",
                },
                "field_mapping": {
                    "type": "object",
                    "description": "字段映射：contract 字段 -> 数据字段名（未提供时默认使用同名字段）",
                    "additionalProperties": {"type": "string"},
                },
                "options": {
                    "type": "object",
                    "description": "展示选项（component_props/layout_hint/title 等）",
                    "additionalProperties": True,
                },
                "max_items": {
                    "type": "integer",
                    "description": "单张卡片包含的最大记录数（默认 6 条）",
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["source_ref"],
        },
    )
    def emit_panel_preview(call: ToolCall, context: ToolExecutionContext) -> ToolExecutionPayload:
        extras = context.extras or {}
        emitter = extras.get("emit_panel_preview")
        data_store = extras.get("data_store")

        if emitter is None:
            logger.warning("emit_panel_preview 工具未注入回调，跳过实时卡片推送")
            return ToolExecutionPayload(
                call=call,
                raw_output={"type": "panel_preview", "skipped": True, "reason": "callback_not_available"},
                status="success",
            )

        source_ref = call.args.get("source_ref")
        contract_id = call.args.get("contract_id")
        field_mapping = call.args.get("field_mapping") or {}
        options = call.args.get("options") or {}

        try:
            max_items = int(call.args.get("max_items", 6) or 6)
        except (TypeError, ValueError):
            max_items = 6
        max_items = max(1, min(max_items, MAX_PREVIEW_ITEMS))

        if data_store is None:
            return _error_payload(call, "data_store_unavailable", "数据存储不可用，无法加载数据引用")

        if source_ref is None:
            return _error_payload(call, "missing_source_ref", "source_ref 不能为空")

        try:
            preview_payload, panel_spec_bundle = _build_panel_from_source_ref(
                source_ref=source_ref,
                context=context,
                data_store=data_store,
                contract_id=contract_id,
                field_mapping=field_mapping,
                options=options,
                max_items=max_items,
            )
        except ValueError as exc:
            return _error_payload(call, "data_ref_resolve_failed", str(exc))
        except MissingFieldsError as exc:
            return _error_payload(call, "missing_fields", f"缺少字段: {', '.join(exc.missing)}")
        except RecordsNotAvailableError:
            return _error_payload(call, "records_not_available", "数据为空或无法解析 items")
        except Exception as exc:
            logger.exception("emit_panel_preview 适配失败")
            return _error_payload(call, "panel_adapt_failed", str(exc))

        emitter(preview_payload)

        panel_spec_raw = panel_spec_bundle["panel_spec"] if panel_spec_bundle else None
        panel_payload_raw = panel_spec_bundle["panel_payload"] if panel_spec_bundle else None
        contracts_applied = (
            panel_spec_bundle.get("contracts_applied")
            or (panel_spec_raw or {}).get("contracts_applied")
            or []
        )
        applied_contract = contracts_applied[0] if contracts_applied else {}

        return ToolExecutionPayload(
            call=call,
            raw_output={
                "type": "panel_preview",
                "count": len(preview_payload.get("previews", [])),
                "panel_spec": panel_spec_raw,
                "panel_payload": panel_payload_raw,
                "contract_id": applied_contract.get("contract_id"),
                "component_id": applied_contract.get("component_id"),
            },
            status="success",
        )


def _trim_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """仅保留前N个字段，避免 payload 过大。"""
    if not isinstance(record, dict):
        return {"value": record}
    trimmed = list(record.items())[:MAX_PREVIEW_FIELDS]
    return {key: value for key, value in trimmed}


def _build_panel_from_source_ref(
    source_ref: Any,
    context: ToolExecutionContext,
    data_store,
    *,
    contract_id: Optional[str],
    field_mapping: Dict[str, str],
    options: Dict[str, Any],
    max_items: int,
) -> (Dict[str, Any], Dict[str, Any]):
    resolver = create_resolver_from_context(context)
    if resolver is None:
        raise ValueError("无法解析数据引用：缺少 data_store")

    resolved: ResolvedData = resolver.resolve(source_ref, require_success=True)
    envelope = resolved.data
    if not isinstance(envelope, dict):
        raise ValueError("source_ref 指向的内容不是 dict，无法渲染")

    dataset_payload, payload_ref = unwrap_payload(envelope, data_store)
    if not isinstance(dataset_payload, dict):
        raise ValueError("无法解析数据内容，缺少 payload 结构")

    # 兼容内容分析类输出：将 analysis/analysis_result 下的 items 提升为顶层 items，便于面板渲染
    analysis_block = dataset_payload.get("analysis") or dataset_payload.get("analysis_result")
    if isinstance(analysis_block, dict):
        if "items" in analysis_block and "items" not in dataset_payload:
            items = analysis_block.get("items") or []
            if isinstance(items, list):
                dataset_payload["items"] = items
        if analysis_block.get("summary") and "summary" not in dataset_payload:
            dataset_payload["summary"] = analysis_block.get("summary")
        if analysis_block.get("title") and "title" not in dataset_payload:
            dataset_payload["title"] = analysis_block.get("title")
        # 记录分析任务元信息
        if dataset_payload.get("task"):
            metadata = dataset_payload.setdefault("metadata", {})
            metadata.setdefault("analysis_task", dataset_payload.get("task"))

    source_metadata = build_source_metadata(dataset_payload, resolved.source_data_id, resolved.source_step_id, payload_ref)
    envelope_meta = envelope.get("metadata") or {}
    stats = dict(envelope_meta)
    stats.setdefault("instruction", envelope_meta.get("instruction"))
    stats.update({k: v for k, v in source_metadata.items() if v is not None})

    # 生成 route：优先来源于元数据（真实 generated_path），若仍缺再兜底
    route = select_non_empty(
        stats.get("generated_path"),
        dataset_payload.get("generated_path"),
        dataset_payload.get("route"),
        envelope.get("generated_path"),
        stats.get("route"),
    ) or "custom/panel"
    if isinstance(stats, dict):
        stats.setdefault("generated_path", route)
        stats.setdefault("route", route)

    source_records = extract_records(dataset_payload)
    if not source_records:
        raise RecordsNotAvailableError()

    # 推断契约（优先参数，其次 payload metadata，再兜底 ListPanel）
    contract = _resolve_contract(contract_id, dataset_payload)
    if not contract:
        raise ValueError(f"未知的契约 ID: {contract_id}")

    mapped_items = _apply_field_mapping(source_records, field_mapping, contract)
    dataset_copy = dict(dataset_payload)
    dataset_copy["items"] = mapped_items

    metadata = dict(dataset_copy.get("metadata") or {})
    metadata["component_id"] = contract.component_id
    metadata["contract_id"] = contract.contract_id
    metadata["contract_version"] = contract.contract_id

    component_props = options.get("component_props") or options.get("props") or dataset_payload.get("component_props")
    if component_props:
        metadata["component_props"] = component_props
    layout_hint = options.get("layout_hint") or dataset_payload.get("layout_hint")
    if layout_hint:
        metadata["layout_hint"] = layout_hint
    metadata.setdefault("generated_path", route)
    metadata.setdefault("route", route)
    if options.get("title"):
        dataset_copy["title"] = options["title"]
    if options.get("summary"):
        dataset_copy["summary"] = options["summary"]
    dataset_copy.setdefault("generated_path", route)
    dataset_copy.setdefault("route", route)
    dataset_copy["metadata"] = metadata

    datasource = stats.get("source_datasource") or stats.get("datasource") or dataset_copy.get("source") or "rsshub"

    panel_bundle = build_panel_spec_from_dataset(
        dataset_copy,
        data_id=resolved.source_data_id,
        max_items=max_items,
    )

    preview_items = [_trim_record(record) for record in mapped_items[:max_items]]
    preview_payload = {
        "previews": [
            {
                "preview_id": f"{resolved.source_data_id or source_ref}-{uuid4().hex[:6]}",
                "title": dataset_copy.get("feed_title") or envelope_meta.get("instruction") or "数据预览",
                "items": preview_items,
                "generated_path": route,
                "source": datasource,
            }
        ],
        "panel_payload": panel_bundle["panel_payload"],
        "panel_spec": panel_bundle["panel_spec"],
        "panel_data_blocks": panel_bundle["panel_spec"]["data_envelopes"],
        "panel_bundle": panel_bundle,
        "contracts_applied": panel_bundle.get("contracts_applied"),
        "source_query": envelope_meta.get("instruction") or dataset_copy.get("feed_title") or route,
        "stats": stats,
    }
    return preview_payload, panel_bundle


def _apply_field_mapping(
    records: List[Dict[str, Any]],
    field_mapping: Dict[str, str],
    contract: ComponentContract,
) -> List[Dict[str, Any]]:
    required_fields = contract.required_fields or []
    # Table 需要 columns + rows 结构，与契约字段定义保持一致
    if contract.component_id == "Table":
        return _build_table_records(records, field_mapping)

    if contract.component_id == "ListPanel":
        return _build_listpanel_records(records, field_mapping, required_fields)

    if not field_mapping:
        # 默认直接复用原字段，后续契约校验交给 panel_spec_builder
        return records

    mapped: List[Dict[str, Any]] = []
    missing_fields: List[str] = []
    for record in records:
        if not isinstance(record, dict):
            missing_fields.extend(required_fields)
            continue
        new_record: Dict[str, Any] = {}
        for target_field, source_field in field_mapping.items():
            new_record[target_field] = record.get(source_field)
        mapped.append(new_record)

    if required_fields:
        for field in required_fields:
            if any(rec.get(field) is None for rec in mapped):
                missing_fields.append(field)

    if missing_fields:
        raise MissingFieldsError(missing_fields)
    return mapped


def _build_table_records(records: List[Dict[str, Any]], field_mapping: Dict[str, str]) -> List[Dict[str, Any]]:
    if not records:
        raise RecordsNotAvailableError()

    def _is_table_payload(record: Dict[str, Any]) -> bool:
        return isinstance(record, dict) and isinstance(record.get("columns"), list) and isinstance(record.get("rows"), list)

    first_record = records[0] if isinstance(records[0], dict) else {}
    mapping_columns = field_mapping.get("columns")
    mapping_rows_key = field_mapping.get("rows")
    records_to_use = records

    # 如果 rows 映射指向嵌套数组，优先展开该数组作为表格行
    if isinstance(mapping_rows_key, str):
        nested_rows = first_record.get(mapping_rows_key)
        if isinstance(nested_rows, list) and any(isinstance(row, dict) for row in nested_rows):
            records_to_use = [row for row in nested_rows if isinstance(row, dict)]
            first_record = records_to_use[0] if records_to_use else first_record

    # 如果 data_operator 已经生成符合 Table 契约的结构，则直接规范化后透传，避免将 columns/rows 误当作普通字段
    if _is_table_payload(first_record):
        raw_columns = first_record.get("columns") or []
        raw_rows = first_record.get("rows") or []

        normalized_columns = []
        for idx, col in enumerate(raw_columns[:MAX_TABLE_COLUMNS], start=1):
            if not isinstance(col, dict):
                continue
            key = col.get("key") or col.get("field") or col.get("id") or col.get("name") or f"col_{idx}"
            label = col.get("label") or col.get("title") or col.get("name") or key
            normalized_columns.append(
                {
                    "key": key,
                    "label": label,
                    "sortable": col.get("sortable", True),
                    "type": col.get("type"),
                    "align": col.get("align"),
                    "width": col.get("width"),
                }
            )

        normalized_rows = [row for row in raw_rows if isinstance(row, dict)][:MAX_PREVIEW_ITEMS]

        if not normalized_columns:
            # 如果 columns 缺失但 rows 存在，尝试从首行推断列
            sample_row = normalized_rows[0] if normalized_rows else {}
            for idx, key in enumerate(sample_row.keys()):
                if idx >= MAX_TABLE_COLUMNS:
                    break
                normalized_columns.append({"key": key, "label": key, "sortable": True})

        if not normalized_columns:
            raise MissingFieldsError(["columns"])
        if not normalized_rows:
            raise RecordsNotAvailableError()

        return [{"columns": normalized_columns, "rows": normalized_rows}]

    columns_fields: List[str] = []
    if isinstance(mapping_columns, list):
        columns_fields = [
            str(col) for col in mapping_columns if isinstance(col, (str, int))
        ][:MAX_TABLE_COLUMNS]
    elif isinstance(mapping_columns, str):
        nested_columns = first_record.get(mapping_columns)
        if isinstance(nested_columns, list):
            columns_fields = [
                str(col) for col in nested_columns if isinstance(col, (str, int))
            ][:MAX_TABLE_COLUMNS]

    if not columns_fields and field_mapping:
        columns_fields = [
            str(key) for key in field_mapping.keys() if key not in {"columns", "rows"}
        ][:MAX_TABLE_COLUMNS]

    if not columns_fields:
        columns_fields = list(first_record.keys()) if isinstance(first_record, dict) else []
    columns_fields = columns_fields[:MAX_TABLE_COLUMNS]
    if not columns_fields:
        raise MissingFieldsError(["columns", "rows"])

    columns = [{"key": field, "label": field} for field in columns_fields]
    rows: List[Dict[str, Any]] = []
    for record in records_to_use:
        if not isinstance(record, dict):
            continue
        row: Dict[str, Any] = {}
        for field in columns_fields:
            source_field = field_mapping.get(field, field)
            value = None
            if isinstance(source_field, list):
                for candidate in source_field:
                    if isinstance(candidate, str) and candidate in record:
                        value = record.get(candidate)
                        break
            else:
                value = record.get(source_field)
            row[field] = value
        rows.append(row)

    rows = rows[:MAX_PREVIEW_ITEMS]
    if not rows:
        raise RecordsNotAvailableError()

    return [{"columns": columns, "rows": rows}]


def _build_listpanel_records(
    records: List[Dict[str, Any]],
    field_mapping: Dict[str, str],
    required_fields: List[str],
) -> List[Dict[str, Any]]:
    mapped: List[Dict[str, Any]] = []
    for idx, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        new_record = dict(record)
        # 字段映射：如 field_mapping={"title":"title","summary":"summary"}
        for target_field, source_field in field_mapping.items():
            if target_field in record:
                continue
            if source_field in record:
                new_record[target_field] = record.get(source_field)
        # 缺失标题时兜底
        new_record.setdefault("title", record.get("title") or record.get("name") or f"记录{idx}")
        # 情感/类别字段如果是字符串，转为单元素列表以满足 categories 字段要求
        if isinstance(new_record.get("categories"), str):
            new_record["categories"] = [new_record["categories"]]
        if "sentiment" in new_record and "categories" not in new_record:
            if isinstance(new_record["sentiment"], list):
                new_record["categories"] = new_record["sentiment"]
            elif isinstance(new_record["sentiment"], str):
                new_record["categories"] = [new_record["sentiment"]]
        mapped.append(new_record)

    if required_fields:
        missing = []
        for field in required_fields:
            if any(rec.get(field) is None for rec in mapped):
                missing.append(field)
        if missing:
            raise MissingFieldsError(missing)
    return mapped


def _resolve_contract(contract_id: Optional[str], dataset_payload: Dict[str, Any]) -> Optional[ComponentContract]:
    if contract_id:
        c = get_contract_by_id(contract_id)
        if c:
            return c
    metadata = dataset_payload.get("metadata") or {}
    cid = metadata.get("contract_id")
    if cid:
        c = get_contract_by_id(cid)
        if c:
            return c
    component_id = metadata.get("component_id")
    if component_id:
        return get_contract_by_id(f"{component_id}-contract-v3") or get_contract_by_id(f"{component_id}-contract-v2")
    # 默认退回 ListPanel 合同
    return get_contract_by_id("ListPanel-contract-v3")


def _error_payload(call: ToolCall, error_code: str, message: str) -> ToolExecutionPayload:
    return ToolExecutionPayload(
        call=call,
        status="error",
        error_message=message,
        raw_output={
            "type": "panel_preview",
            "error_code": error_code,
            "error_message": message,
        },
    )


class MissingFieldsError(RuntimeError):
    def __init__(self, missing: List[str]):
        super().__init__("missing required fields")
        self.missing = missing


class RecordsNotAvailableError(RuntimeError):
    """数据为空或无法解析 items。"""
