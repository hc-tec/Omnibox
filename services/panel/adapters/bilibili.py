from __future__ import annotations

import re
from typing import Any, Dict, Optional, Sequence

from api.schemas.panel import ComponentInteraction, LayoutHint, SourceInfo

from services.panel.view_models import validate_records
from .registry import AdapterBlockPlan, RouteAdapterResult, route_adapter
from .utils import strip_html, ensure_list, short_text


@route_adapter('/bilibili', '/bilibili/user/video', '/bilibili/user/dynamic')
def bilibili_feed_adapter(
    source_info: SourceInfo, records: Sequence[Dict[str, Any]]
) -> RouteAdapterResult:
    payload = records[0] if records else {}
    raw_items = payload.get('items') or payload.get('item') or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    normalized: list[Dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        title = item.get('title') or item.get('name') or ''
        link = item.get('link') or item.get('url')
        summary = short_text(
            item.get('description')
            or item.get('summary')
            or item.get('content_html')
        )
        normalized.append(
            {
                'id': item.get('id') or link or title,
                'title': title,
                'link': link,
                'summary': summary,
                'published_at': item.get('pubDate') or item.get('date_published'),
                'author': item.get('author'),
                'categories': ensure_list(item.get('tags')),
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
        confidence=0.7,
    )

    stats = {
        'datasource': source_info.datasource or 'bilibili',
        'route': source_info.route,
        'feed_title': payload.get('title'),
        'total_items': len(validated),
        'api_endpoint': source_info.route or '/bilibili',
    }

    return RouteAdapterResult(records=validated, block_plans=[block_plan], stats=stats)


@route_adapter('/bilibili/user/followings')
def bilibili_followings_adapter(
    source_info: SourceInfo, records: Sequence[Dict[str, Any]]
) -> RouteAdapterResult:
    payload = records[0] if records else {}
    raw_items = payload.get('item') or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    normalized: list[Dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        title = item.get('title') or ''
        link = item.get('link')
        summary = short_text(item.get('description'))
        normalized.append(
            {
                'id': item.get('id') or link or title,
                'title': title,
                'link': link,
                'summary': summary,
                'published_at': item.get('pubDate'),
            }
        )

    validated = validate_records('ListPanel', normalized)
    follower_count = _extract_following_count(raw_items)

    block_plan = AdapterBlockPlan(
        component_id='ListPanel',
        props={
            'title_field': 'title',
            'link_field': 'link',
            'description_field': 'summary',
            'pub_date_field': 'published_at',
        },
        options={'show_description': True, 'span': 12},
        interactions=[ComponentInteraction(type='open_link', label='Open Profile')],
        title=payload.get('title') or 'Bilibili Followings',
        layout_hint=LayoutHint(span=12, min_height=320),
        confidence=0.72,
    )

    stats = {
        'datasource': source_info.datasource or 'bilibili',
        'route': source_info.route,
        'feed_title': payload.get('title'),
        'total_items': len(validated),
        'follower_count': follower_count,
        'api_endpoint': source_info.route or '/bilibili/user/followings',
    }

    return RouteAdapterResult(records=validated, block_plans=[block_plan], stats=stats)


def _extract_following_count(items: Sequence[Dict[str, Any]]) -> Optional[int]:
    pattern = re.compile(r'总计(\d+)')
    for item in items:
        description = item.get('description') or ''
        match = pattern.search(str(description))
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return None

