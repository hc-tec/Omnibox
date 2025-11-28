from __future__ import annotations

"""工具：读取 data_store 中的数据集元数据（Schema/画像），不暴露原始记录。"""

from typing import Any, Dict, List, Optional

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool


def register_dataset_inspector_tool(registry: ToolRegistry) -> None:
    """
    注册 inspect_dataset 工具。

    Planner/Reflector 可通过该工具了解数据结构，而无需传递原始数据给 LLM。
    """

    @tool(
        registry,
        plugin_id="inspect_dataset",
        description="读取 data_store 中的数据集 Schema、字段画像等元信息，不返回原始记录。",
        schema={
            "type": "object",
            "properties": {
                "data_id": {"type": "string", "description": "DataStasher 保存的数据 ID"},
                "dataset_index": {
                    "type": "integer",
                    "description": "目标数据集索引（默认为 0）",
                    "minimum": 0,
                },
            },
            "required": ["data_id"],
        },
        execution_mode="lightweight",
    )
    def inspect_dataset(call: ToolCall, context: ToolExecutionContext) -> ToolExecutionPayload:
        data_id = call.args.get("data_id")
        if not data_id:
            raise ValueError("inspect_dataset 需要 data_id 参数")

        dataset_index = call.args.get("dataset_index", 0) or 0
        try:
            dataset_index = int(dataset_index)
        except (TypeError, ValueError):
            dataset_index = 0

        data_store = (context.extras or {}).get("data_store")
        if data_store is None:
            return ToolExecutionPayload(
                call=call,
                raw_output={"type": "dataset_inspection", "error": "data_store_unavailable"},
                status="error",
                error_message="data_store 不可用",
            )

        package = data_store.load(data_id)
        datasets_meta = _extract_metadata(package)
        if not datasets_meta:
            return ToolExecutionPayload(
                call=call,
                raw_output={"type": "dataset_inspection", "error": "datasets_not_available"},
                status="error",
                error_message="数据集中不包含可用的 schema 元信息",
            )

        if dataset_index < 0 or dataset_index >= len(datasets_meta):
            error_msg = f"dataset_index {dataset_index} 超出范围（共有 {len(datasets_meta)} 组数据）"
            return ToolExecutionPayload(
                call=call,
                raw_output={"type": "dataset_inspection", "error": error_msg},
                status="error",
                error_message=error_msg,
            )

        metadata = _sanitize_metadata(datasets_meta[dataset_index])
        raw_output = {
            "type": "dataset_inspection",
            "data_id": data_id,
            "dataset_index": dataset_index,
            "route": metadata.get("route"),
            "generated_path": metadata.get("route") or metadata.get("generated_path"),
            "schema": metadata.get("schema"),
            "schema_id": metadata.get("schema_id"),
            "profile": metadata.get("profile"),
            "available_components": metadata.get("available_components"),
            "adapter_notes": metadata.get("adapter_notes"),
            "record_count": (metadata.get("profile") or {}).get("record_count")
            if isinstance(metadata.get("profile"), dict)
            else None,
        }
        return ToolExecutionPayload(call=call, raw_output=raw_output, status="success")


def _extract_metadata(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        datasets = payload.get("datasets")
        if isinstance(datasets, list):
            return [dataset for dataset in datasets if isinstance(dataset, dict)]
    return []


def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    # 删除 items/payload 等可能包含原始数据的字段
    filtered = {
        key: value
        for key, value in metadata.items()
        if key not in {"items", "payload", "records"}
    }
    return filtered
