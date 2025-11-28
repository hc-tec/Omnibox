from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from api.schemas.panel import ComponentInteraction, LayoutHint, SourceInfo

from services.panel.view_models import validate_records
from ..dataset_schema import DatasetSchemaDescriptor, DatasetSchemaField
from .registry import (
    AdapterBlockPlan,
    AdapterExecutionContext,
    ComponentManifestEntry,
    RouteAdapterManifest,
    RouteAdapterResult,
    route_adapter,
)
from .utils import short_text, early_return_if_no_match


GENERIC_LIST_SCHEMA = DatasetSchemaDescriptor(
    schema_id="generic.list_panel.v1",
    display_name="通用列表数据",
    description="标题/链接/摘要/时间结构",
    primary_key="id",
    time_field="published_at",
    fields=[
        DatasetSchemaField(name="id", type="string", description="唯一 ID", required=True, sortable=True),
        DatasetSchemaField(name="title", type="string", description="标题", required=True, filterable=True),
        DatasetSchemaField(name="link", type="string", description="原文链接"),
        DatasetSchemaField(name="summary", type="string", description="简短摘要"),
        DatasetSchemaField(name="published_at", type="datetime", description="发布时间", sortable=True),
    ],
    tags=["rss", "list"],
)


GENERIC_LIST_MANIFEST = RouteAdapterManifest(
    components=[
        ComponentManifestEntry(
            component_id="ListPanel",
            description="通用内容列表（标题 + 摘要）",
            cost="low",
            default_selected=True,
            required=True,
        )
    ],
    notes="适用于结构稳定但暂未深度定制的 RSS 路由。",
    schema=GENERIC_LIST_SCHEMA,
)


@route_adapter('/github/issue', manifest=GENERIC_LIST_MANIFEST)
def github_issue_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    return _build_simple_list(source_info, records, context=context, confidence=0.66)


@route_adapter('/sspai', manifest=GENERIC_LIST_MANIFEST)
def sspai_feed_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    return _build_simple_list(source_info, records, context=context, confidence=0.68)


def _build_simple_list(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    *,
    confidence: float,
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    payload = records[0] if records else {}
    raw_items = payload.get('items') or payload.get('item') or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    stats = {
        'datasource': source_info.datasource,
        'route': source_info.route,
        'feed_title': payload.get('title'),
        'total_items': len(raw_items),
        'api_endpoint': source_info.route,
        'metrics': {},
    }

    early = early_return_if_no_match(context, ['ListPanel'], stats)
    if early:
        return early

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
    stats['total_items'] = len(validated)

    block_plan = AdapterBlockPlan(
        component_id='ListPanel',
        props={
            'title_field': 'title',
            'link_field': 'link',
            'description_field': 'summary',
            'pub_date_field': 'published_at',
        },
        options={'show_description': True, 'span': 12, 'layout_size': 'full'},
        interactions=[ComponentInteraction(type='open_link', label='Open Link')],
        title=payload.get('title') or source_info.route,
        layout_hint=LayoutHint(layout_size='full', span=12, min_height=320),
        confidence=confidence,
    )

    return RouteAdapterResult(records=validated, block_plans=[block_plan], stats=stats)
