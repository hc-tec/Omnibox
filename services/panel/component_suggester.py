"""
组件推荐引擎：基于 Schema 语义为数据块挑选合适的前端组件。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from api.schemas.panel import ComponentInteraction, LayoutHint, SchemaFieldSummary, ViewDescriptor
from services.panel.component_registry import ComponentDefinition, ComponentRegistry


class ComponentSuggester:
    """根据字段语义推荐组件，支持按需扩展。"""

    def __init__(self, registry: Optional[ComponentRegistry] = None):
        self.registry = registry or ComponentRegistry()

    def suggest(
        self,
        data_block_id: str,
        schema_fields: List[SchemaFieldSummary],
        user_preferences: Optional[Dict[str, str]] = None,
    ) -> List[ViewDescriptor]:
        semantic_pool = sorted({tag for field in schema_fields for tag in field.semantic})
        semantic_index = self._build_semantic_index(schema_fields)
        field_map = {field.name: field for field in schema_fields}

        preferred = user_preferences.get("preferred_component") if user_preferences else None
        components = self._select_components(semantic_pool, preferred)

        suggestions: List[ViewDescriptor] = []
        for idx, component in enumerate(components, start=1):
            descriptor = self._build_descriptor(
                data_block_id=data_block_id,
                component=component,
                field_map=field_map,
                semantic_index=semantic_index,
                order=idx,
            )
            if descriptor:
                descriptor.id = f"{data_block_id}-view-{idx}"
                suggestions.append(descriptor)

        if not suggestions:
            fallback = self.registry.get("FallbackRichText")
            if fallback:
                descriptor = self._build_descriptor(
                    data_block_id=data_block_id,
                    component=fallback,
                    field_map=field_map,
                    semantic_index=semantic_index,
                    order=len(suggestions) + 1,
                )
                if descriptor:
                    descriptor.id = f"{data_block_id}-view-fallback"
                    suggestions.append(descriptor)

        return suggestions[:4]

    def _select_components(self, semantic_pool: List[str], preferred: Optional[str]) -> List[ComponentDefinition]:
        components: List[ComponentDefinition] = []
        if preferred:
            preferred_component = self.registry.get(preferred)
            if preferred_component and preferred_component.is_compatible(semantic_pool):
                components.append(preferred_component)

        for component in self.registry.all():
            if component in components:
                continue
            if component.is_compatible(semantic_pool):
                components.append(component)

        return components

    def _build_descriptor(
        self,
        data_block_id: str,
        component: ComponentDefinition,
        field_map: Dict[str, SchemaFieldSummary],
        semantic_index: Dict[str, List[SchemaFieldSummary]],
        order: int,
    ) -> Optional[ViewDescriptor]:
        resolver = COMPONENT_BUILDERS.get(component.id, build_richtext_descriptor)
        result = resolver(component, field_map, semantic_index)
        if not result:
            return None
        props, options, interactions, confidence = result
        layout_hint = LayoutHint(
            span=component.layout_defaults.get("span"),
            order=component.layout_defaults.get("order", order),
            priority=component.layout_defaults.get("priority"),
            min_height=component.layout_defaults.get("min_height"),
            responsive=component.layout_defaults.get("responsive"),
        )
        return ViewDescriptor(
            id=f"{data_block_id}-{component.id.lower()}",
            component_id=component.id,
            data_ref=data_block_id,
            confidence=confidence,
            props=props,
            options=options,
            interactions=interactions,
            layout_hint=layout_hint,
        )

    @staticmethod
    def _build_semantic_index(schema_fields: List[SchemaFieldSummary]) -> Dict[str, List[SchemaFieldSummary]]:
        index: Dict[str, List[SchemaFieldSummary]] = {}
        for field in schema_fields:
            for tag in field.semantic:
                index.setdefault(tag, []).append(field)
        return index


# 组件构造函数

def build_list_panel_descriptor(
    component: ComponentDefinition,
    field_map: Dict[str, SchemaFieldSummary],
    semantic_index: Dict[str, List[SchemaFieldSummary]],
):
    title_field = pick_semantic_field(["title"], semantic_index, field_map)
    link_field = pick_semantic_field(["url", "link"], semantic_index, field_map)
    if not title_field or not link_field:
        return None

    description_field = pick_semantic_field(["summary", "description"], semantic_index, field_map)
    datetime_field = pick_semantic_field(["datetime"], semantic_index, field_map)

    props = {
        "title_field": title_field.name,
        "link_field": link_field.name,
    }
    if description_field:
        props["description_field"] = description_field.name
    if datetime_field:
        props["pub_date_field"] = datetime_field.name

    options = {
        "show_description": True,
        "span": component.layout_defaults.get("span", 12),
    }
    interactions = [ComponentInteraction(type="open_link", label="打开链接")]

    confidence = 0.75
    if description_field:
        confidence += 0.05
    if datetime_field:
        confidence += 0.05

    return props, options, interactions, min(confidence, 0.95)


def build_line_chart_descriptor(
    component: ComponentDefinition,
    field_map: Dict[str, SchemaFieldSummary],
    semantic_index: Dict[str, List[SchemaFieldSummary]],
):
    x_field = pick_semantic_field(["datetime", "identifier"], semantic_index, field_map)
    y_field = pick_semantic_field(["value"], semantic_index, field_map, type_whitelist={"number"})
    if not x_field or not y_field:
        return None

    series_field = pick_semantic_field(["category", "series"], semantic_index, field_map)
    props = {
        "x_field": x_field.name,
        "y_field": y_field.name,
    }
    if series_field:
        props["series_field"] = series_field.name

    options = {
        "area_style": False,
        "span": component.layout_defaults.get("span", 12),
    }
    interactions = [
        ComponentInteraction(type="filter", label="筛选"),
        ComponentInteraction(type="compare", label="对比"),
    ]
    confidence = 0.8 + (0.05 if series_field else 0.0)
    return props, options, interactions, confidence


def build_statistic_card_descriptor(
    component: ComponentDefinition,
    field_map: Dict[str, SchemaFieldSummary],
    semantic_index: Dict[str, List[SchemaFieldSummary]],
):
    value_field = pick_semantic_field(["value"], semantic_index, field_map, type_whitelist={"number"})
    title_field = pick_semantic_field(["title"], semantic_index, field_map)
    if not value_field:
        return None

    props = {
        "value_field": value_field.name,
    }
    if title_field:
        props["title_field"] = title_field.name

    trend_field = pick_semantic_field(["trend"], semantic_index, field_map, type_whitelist={"number"})
    if trend_field:
        props["trend_field"] = trend_field.name

    options = {
        "span": component.layout_defaults.get("span", 6),
    }
    interactions: List[ComponentInteraction] = []
    confidence = 0.7 + (0.05 if title_field else 0.0) + (0.05 if trend_field else 0.0)
    return props, options, interactions, confidence


def build_richtext_descriptor(
    component: ComponentDefinition,
    field_map: Dict[str, SchemaFieldSummary],
    semantic_index: Dict[str, List[SchemaFieldSummary]],
):
    title_field = pick_semantic_field(["title", "identifier"], semantic_index, field_map) or next(iter(field_map.values()), None)
    props = {
        "title_field": title_field.name if title_field else next(iter(field_map.keys()), "title"),
    }
    description_field = pick_semantic_field(["summary", "description"], semantic_index, field_map)
    if description_field:
        props["description_field"] = description_field.name

    options = {
        "span": component.layout_defaults.get("span", 12),
    }
    return props, options, [], 0.5


COMPONENT_BUILDERS = {
    "ListPanel": build_list_panel_descriptor,
    "LineChart": build_line_chart_descriptor,
    "StatisticCard": build_statistic_card_descriptor,
    "FallbackRichText": build_richtext_descriptor,
}


def pick_semantic_field(
    preferred_tags: List[str],
    semantic_index: Dict[str, List[SchemaFieldSummary]],
    field_map: Dict[str, SchemaFieldSummary],
    type_whitelist: Optional[set[str]] = None,
) -> Optional[SchemaFieldSummary]:
    for tag in preferred_tags:
        candidates = semantic_index.get(tag)
        if not candidates:
            continue
        for candidate in candidates:
            if type_whitelist and candidate.type not in type_whitelist:
                continue
            return candidate
    for field in field_map.values():
        if type_whitelist and field.type not in type_whitelist:
            continue
        if any(tag in preferred_tags for tag in field.semantic):
            return field
    return None
