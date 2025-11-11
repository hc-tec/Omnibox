"""
组件能力表注册器，与前端对齐组件输入输出要求。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ComponentDefinition:
    """组件能力表中的单个组件定义。"""

    id: str
    requirements: List[str]
    optional_fields: List[str] = field(default_factory=list)
    options: Dict[str, Dict[str, object]] = field(default_factory=dict)
    interactions: List[str] = field(default_factory=list)
    layout_defaults: Dict[str, object] = field(default_factory=dict)
    description: Optional[str] = None

    def is_compatible(self, available_fields: List[str]) -> bool:
        """检查可用语义标签是否满足组件的必需字段。"""
        available = set(available_fields)
        return all(req in available for req in self.requirements)


class ComponentRegistry:
    """组件能力注册器，提供能力查询与匹配工具。"""

    def __init__(self, components: Optional[List[ComponentDefinition]] = None):
        self._components = {c.id: c for c in (components or default_components())}

    def get(self, component_id: str) -> Optional[ComponentDefinition]:
        return self._components.get(component_id)

    def all(self) -> List[ComponentDefinition]:
        return list(self._components.values())

    def find_compatible(self, available_fields: List[str]) -> List[ComponentDefinition]:
        """根据可用字段返回可兼容的组件列表。"""
        return [
            component
            for component in self._components.values()
            if component.is_compatible(available_fields)
    ]


def default_components() -> List[ComponentDefinition]:
    """返回内置组件集合定义。"""
    return [
        ComponentDefinition(
            id="ListPanel",
            requirements=["title", "link"],
            optional_fields=["description", "pubDate", "author"],
            options={"show_description": {"type": "boolean", "default": True}},
            interactions=["open_link"],
            layout_defaults={
                "layout_size": "third",
                "span": 12,
                "min_height": 320,
            },
            description="适用于文本类数据源的通用列表组件。",
        ),
        ComponentDefinition(
            id="LineChart",
            requirements=["timestamp", "value"],
            optional_fields=["series", "category"],
            options={"area_style": {"type": "boolean", "default": False}},
            interactions=["filter", "compare"],
            layout_defaults={
                "layout_size": "half",
                "span": 12,
                "min_height": 280,
            },
            description="用于展示时间序列数据的折线图组件。",
        ),
        ComponentDefinition(
            id="StatisticCard",
            requirements=["title", "value"],
            optional_fields=["trend", "unit"],
            options={},
            interactions=[],
            layout_defaults={
                "layout_size": "quarter",
                "span": 6,
                "min_height": 160,
            },
            description="用于突出单个统计指标的概览卡片。",
        ),
        ComponentDefinition(
            id="MediaCardGrid",
            requirements=["title", "cover_url"],
            optional_fields=["link", "author", "summary", "duration", "view_count", "like_count", "badges"],
            options={
                "columns": {"type": "number", "default": 3},
                "max_items": {"type": "number", "default": 6},
            },
            interactions=["open_link"],
            layout_defaults={
                "layout_size": "half",
                "span": 6,
                "min_height": 260,
            },
            description="适用于视频或短内容的卡片网格展示组件。",
        ),
        ComponentDefinition(
            id="FallbackRichText",
            requirements=["title"],
            optional_fields=["description"],
            options={},
            interactions=[],
            layout_defaults={
                "layout_size": "full",
                "span": 12,
                "min_height": 200,
            },
            description="当无其它组件匹配时的富文本兜底渲染组件。",
        ),
    ]
