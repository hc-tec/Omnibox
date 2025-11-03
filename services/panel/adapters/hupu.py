from __future__ import annotations

from typing import Any, Dict, Sequence

from api.schemas.panel import SourceInfo

from .common import list_panel_result
from .registry import RouteAdapterResult, route_adapter


@route_adapter("/hupu", "/hupu/bbs", "/hupu/all")
def hupu_board_list_adapter(
    source_info: SourceInfo, records: Sequence[Dict[str, Any]]
) -> RouteAdapterResult:
    return list_panel_result(source_info, records)
