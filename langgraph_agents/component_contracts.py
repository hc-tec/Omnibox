"""
组件契约注册表（Phase 13 基线）

提供：
1. CONTRACTS: 组件契约结构化定义
2. COMPONENT_CONTRACTS_PROMPT: 注入到 ResearchAgent 提示词的摘要
3. 辅助函数：get_contract_by_id/component
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ComponentContract:
    component_id: str
    contract_id: str
    description: str
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    props_mapping: Dict[str, str] = field(default_factory=dict)
    layout_hint: Dict[str, int] = field(default_factory=dict)
    sample_view_model: Dict[str, object] = field(default_factory=dict)


CONTRACTS: Dict[str, ComponentContract] = {
    "StatisticCard": ComponentContract(
        component_id="StatisticCard",
        contract_id="StatisticCard-contract-v2",
        description="指标/数字卡片：展示单个或少量统计指标（如数量、增幅、趋势）。",
        required_fields=[
            "metric_title",
            "metric_value",
        ],
        optional_fields=[
            "metric_trend",
            "metric_delta_text",
            "metric_unit",
            "description",
        ],
        props_mapping={
            "title_field": "metric_title",
            "value_field": "metric_value",
            "trend_field": "metric_trend",
        },
        layout_hint={"span": 6, "min_height": 160},
        sample_view_model={
            "component_id": "StatisticCard",
            "data": {
                "items": [
                    {
                        "metric_title": "B站热搜数量",
                        "metric_value": 10,
                        "description": "当前共有 10 条热搜数据",
                    }
                ]
            },
            "props": {
                "title_field": "metric_title",
                "value_field": "metric_value",
                "trend_field": "metric_trend",
                "title": "B站热搜数量",
            },
        },
    ),
    "ListPanel": ComponentContract(
        component_id="ListPanel",
        contract_id="ListPanel-contract-v3",
        description="通用列表：文本/链接记录列表，支持摘要、作者、时间、分类。",
        required_fields=["title"],
        optional_fields=["link", "summary", "author", "published_at", "categories"],
        props_mapping={
            "title_field": "title",
            "link_field": "link",
            "description_field": "summary",
            "pub_date_field": "published_at",
            "author_field": "author",
            "categories_field": "categories",
        },
        layout_hint={"span": 12, "min_height": 320},
        sample_view_model={
            "component_id": "ListPanel",
            "data": {
                "items": [
                    {
                        "id": "record-1",
                        "title": "bilibili · 猫meme冲上热搜",
                        "link": "https://www.bilibili.com/read/cv123",
                        "summary": "视频播放量再创新高",
                        "author": "哔哩哔哩",
                        "published_at": "2025-11-30T02:00:00+08:00",
                        "categories": ["bilibili", "hot-search"],
                    }
                ],
                "stats": {"item_count": 15},
            },
            "props": {
                "title_field": "title",
                "link_field": "link",
                "description_field": "summary",
                "pub_date_field": "published_at",
                "categories_field": "categories",
            },
        },
    ),
    "LineChart": ComponentContract(
        component_id="LineChart",
        contract_id="LineChart-contract-v2",
        description="折线图：展示时间或序列趋势，支持多序列。",
        required_fields=["x", "y"],
        optional_fields=["series"],
        props_mapping={
            "x_field": "x",
            "y_field": "y",
            "series_field": "series",
        },
        layout_hint={"span": 12, "min_height": 280},
        sample_view_model={
            "component_id": "LineChart",
            "data": {
                "items": [
                    {"x": "2025-11-25", "y": 12000, "series": "播放量"},
                    {"x": "2025-11-26", "y": 18500, "series": "播放量"},
                ]
            },
            "props": {"x_field": "x", "y_field": "y", "series_field": "series"},
        },
    ),
    "BarChart": ComponentContract(
        component_id="BarChart",
        contract_id="BarChart-contract-v2",
        description="柱状图：分类-数值对，可选多序列或排序后 Top-N。",
        required_fields=["category", "value"],
        optional_fields=["series"],
        props_mapping={
            "x_field": "category",
            "y_field": "value",
            "series_field": "series",
        },
        layout_hint={"span": 12, "min_height": 280},
        sample_view_model={
            "component_id": "BarChart",
            "data": {
                "items": [
                    {"id": "bar-1", "category": "凌晨(0-6点)", "value": 5},
                    {"id": "bar-2", "category": "上午(6-12点)", "value": 12},
                    {"id": "bar-3", "category": "下午(12-18点)", "value": 8},
                    {"id": "bar-4", "category": "晚上(18-24点)", "value": 15},
                ]
            },
            "props": {
                "x_field": "category",
                "y_field": "value",
                "title": "时间段分布",
            },
        },
    ),
    "PieChart": ComponentContract(
        component_id="PieChart",
        contract_id="PieChart-contract-v1",
        description="饼图：占比/份额展示。",
        required_fields=["name", "value"],
        optional_fields=["percentage"],
        props_mapping={
            "name_field": "name",
            "value_field": "value",
        },
        layout_hint={"span": 12, "min_height": 280},
    ),
    "Table": ComponentContract(
        component_id="Table",
        contract_id="Table-contract-v1",
        description="结构化表格：具备 header + rows/cells。",
        required_fields=["columns", "rows"],
        optional_fields=[],
        props_mapping={},
        layout_hint={"span": 12, "min_height": 320},
    ),
    "MediaCardGrid": ComponentContract(
        component_id="MediaCardGrid",
        contract_id="MediaCardGrid-contract-v2",
        description="媒体卡片：展示封面、作者、互动指标等（常用于视频/图文）。",
        required_fields=["title"],
        optional_fields=[
            "link",
            "cover_url",
            "author",
            "duration",
            "view_count",
            "like_count",
            "badges",
        ],
        props_mapping={
            "title_field": "title",
            "link_field": "link",
            "cover_field": "cover_url",
            "author_field": "author",
            "duration_field": "duration",
            "view_count_field": "view_count",
            "like_count_field": "like_count",
            "badges_field": "badges",
        },
        layout_hint={"span": 6, "min_height": 260},
    ),
}


def get_contract_by_component(component_id: str) -> Optional[ComponentContract]:
    return CONTRACTS.get(component_id)


def get_contract_by_id(contract_id: str) -> Optional[ComponentContract]:
    for contract in CONTRACTS.values():
        if contract.contract_id == contract_id:
            return contract
    return None


def _contract_definition_dict(contract: ComponentContract) -> Dict[str, Any]:
    return {
        "component_id": contract.component_id,
        "contract_id": contract.contract_id,
        "description": contract.description,
        "required_fields": list(contract.required_fields),
        "optional_fields": list(contract.optional_fields),
        "props_mapping": dict(contract.props_mapping),
        "layout_hint": dict(contract.layout_hint),
        "sample_view_model": contract.sample_view_model,
    }


def resolve_contracts_for_step(
    working_memory: Dict[str, Any],
    step_id: int,
) -> List[Dict[str, Any]]:
    """
    根据 step_id 在 working_memory 中查找已登记的组件契约。

    返回的每个契约都会附带 definition 字段（包含契约约束）。
    """
    entry = working_memory.get("component_contracts") or {}
    registry = entry.get("contracts") or {}
    target_token = f"$step.{step_id}"
    matches: List[Dict[str, Any]] = []

    for record in registry.values():
        targets = record.get("targets") or []
        if isinstance(targets, str):
            targets = [targets]
        if target_token not in targets:
            continue
        resolved = dict(record)
        contract_id = resolved.get("contract_id")
        component_id = resolved.get("component_id")
        contract_def = None
        if contract_id:
            contract_def = get_contract_by_id(contract_id)
        if not contract_def and component_id:
            contract_def = get_contract_by_component(component_id)
        if contract_def:
            resolved["definition"] = _contract_definition_dict(contract_def)
        matches.append(resolved)

    return matches


def _build_prompt_summary() -> str:
    lines: List[str] = [
        "组件契约速览（引用 contract_id 并严格匹配字段）："
    ]
    for contract in CONTRACTS.values():
        optional = ", ".join(contract.optional_fields) if contract.optional_fields else "无"
        props = ", ".join(f"{k}->{v}" for k, v in contract.props_mapping.items()) or "无"
        lines.append(
            f"- {contract.component_id} ({contract.contract_id}): {contract.description} "
            f"| 必填字段: {', '.join(contract.required_fields)} | 可选: {optional} | props: {props}"
        )
    lines.append("完整契约定义详见 `.agentdocs/component_contracts.md`。")
    return "\n".join(lines)


COMPONENT_CONTRACTS_PROMPT = _build_prompt_summary()
