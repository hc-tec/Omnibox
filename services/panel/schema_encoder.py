"""
Helpers to convert DataBlock objects to DisplaySchema instances.
"""

from __future__ import annotations

from typing import Dict, List

from api.schemas.panel import DataBlock
from services.panel.panel_spec import DisplaySchema


def build_display_schema_from_data_block(data_block: DataBlock) -> DisplaySchema:
    """
    将 DataBlock 的记录转换为 record_set DisplaySchema。
    """

    fields = {
        "items": data_block.records,
        "schema": data_block.schema_summary.model_dump(),
        "stats": data_block.stats,
    }

    return DisplaySchema(
        kind="record_set",
        title=data_block.source_info.route or data_block.source_info.datasource,
        summary=data_block.stats.get("summary"),
        fields=fields,
        source_refs=[data_block.id],
        warnings=[],
    )
