from __future__ import annotations

from typing import Any, Dict, Sequence

from api.schemas.panel import ComponentInteraction, LayoutHint, SourceInfo

from services.panel.view_models import validate_records
from .registry import AdapterBlockPlan, RouteAdapterResult, route_adapter
from .utils import short_text


@route_adapter('/github/issue')
def github_issue_adapter(
    source_info: SourceInfo, records: Sequence[Dict[str, Any]]
) -> RouteAdapterResult:
    return _build_simple_list(source_info, records, confidence=0.66)


@route_adapter('/sspai')
def sspai_feed_adapter(
    source_info: SourceInfo, records: Sequence[Dict[str, Any]]
) -> RouteAdapterResult:
    return _build_simple_list(source_info, records, confidence=0.68)


def _build_simple_list(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    *,
    confidence: float,
) -> RouteAdapterResult:
    payload = records[0] if records else {}
    raw_items = payload.get('items') or payload.get('item') or []

    normalized: list[Dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = item.get('title') or ''
        link = item.get('link') or item.get('url')
        normalized.append(
            {
                'id': item.get('id') or link or title,
                'title': title,
                'link': link,
                'summary': short_text(item.get('description')),
                'published_at': item.get('pubDate') or item.get('date_published'),
            }
        )

    validated = validate_records('ListPanel', normalized)

    block_plan = AdapterBlockPlan(
        component_id='ListPanel',
        props={
            'title_field': 'title',
            'link_field': 'link',
            'description_field': 'summary',
            'pub_date_field': 'published_at',
        },
        options={'show_description': True, 'span': 12},
        interactions=[ComponentInteraction(type='open_link', label='Open Link')],
        title=payload.get('title') or source_info.route,
        layout_hint=LayoutHint(span=12, min_height=320),
        confidence=confidence,
    )

    stats = {
        'datasource': source_info.datasource,
        'route': source_info.route,
        'feed_title': payload.get('title'),
        'total_items': len(validated),
        'api_endpoint': source_info.route,
    }

    return RouteAdapterResult(records=validated, block_plans=[block_plan], stats=stats)

