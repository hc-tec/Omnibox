"""
Helpers to convert DataBlock objects into StructuredDataEnvelope payloads.
"""

from __future__ import annotations

from typing import Dict, List

from api.schemas.panel import DataBlock
from services.panel.panel_spec import (
    EnvelopeCursor,
    StructuredDataEnvelope,
    StructuredDataSchema,
)


def build_envelope_from_data_block(
    data_block: DataBlock,
    *,
    preview_limit: int = 8,
) -> StructuredDataEnvelope:
    """
    将 DataBlock 转换为 StructuredDataEnvelope，供 Sandbox/LLM 安全读取。

    - preview 仅包含少量裁剪后的记录
    - schema.type 当前根据 DataBlock 内容粗略设为 table，后续可扩展
    """

    preview_records: List[Dict] = list(data_block.records[:preview_limit])
    schema = StructuredDataSchema(
        type="table",
        description=data_block.schema_summary.schema_digest,
    )
    cursor = EnvelopeCursor(
        total=data_block.stats.get("total"),
        sampled=len(preview_records),
        next_token=data_block.stats.get("next_token"),
    )
    metadata = {
        "source_info": data_block.source_info.model_dump(),
        "stats": data_block.stats,
    }

    summary = metadata["source_info"].get("route") or metadata["source_info"].get("datasource")
    if data_block.stats.get("summary"):
        summary = data_block.stats["summary"]

    return StructuredDataEnvelope(
        data_id=data_block.id,
        schema=schema,
        summary=summary,
        preview=preview_records,
        cursor=cursor,
        metadata=metadata,
    )
