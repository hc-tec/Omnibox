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
            optional_fields=["description", "pubDate", "author", "hot"],
            options={
                "variant": {"type": "string", "default": "standard"},  # 'minimal' | 'standard'
                "show_description": {"type": "boolean", "default": True},
                "show_metadata": {"type": "boolean", "default": True},
                "show_categories": {"type": "boolean", "default": True},
                "show_rank": {"type": "boolean", "default": False},
                "compact": {"type": "boolean", "default": False},
                "max_items": {"type": "number", "default": 10},
            },
            interactions=["open_link", "refresh"],
            layout_defaults={
                "layout_size": "third",
                "span": 12,
                "min_height": 320,
            },
            description="适用于文本类数据源的通用列表组件。支持标准模式（资讯）和极简模式（热榜）。",
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
            id="BarChart",
            requirements=["category", "value"],
            optional_fields=["series"],
            options={
                "horizontal": {"type": "boolean", "default": False},
                "stacked": {"type": "boolean", "default": False},
            },
            interactions=["filter", "sort"],
            layout_defaults={
                "layout_size": "half",
                "span": 12,
                "min_height": 280,
            },
            description="用于比较不同维度数值的柱状图组件。",
        ),
        ComponentDefinition(
            id="PieChart",
            requirements=["name", "value"],
            optional_fields=["percentage"],
            options={
                "rose_type": {"type": "string", "default": ""},  # '' | 'radius' | 'area'
                "show_label": {"type": "boolean", "default": True},
                "radius": {"type": "string", "default": "50%"},  # '50%' or ['40%', '70%']
            },
            interactions=["filter"],
            layout_defaults={
                "layout_size": "half",
                "span": 6,
                "min_height": 280,
            },
            description="饼图/环形图组件，支持南丁格尔图和可滚动图例。",
        ),
        ComponentDefinition(
            id="Table",
            requirements=["rows"],
            optional_fields=["headers"],
            options={
                "enable_pagination": {"type": "boolean", "default": True},
                "page_size": {"type": "number", "default": 10},
                "enable_sorting": {"type": "boolean", "default": True},
            },
            interactions=["sort", "paginate"],
            layout_defaults={
                "layout_size": "full",
                "span": 12,
                "min_height": 320,
            },
            description="表格组件，支持排序、分页、自动列检测。",
        ),
        ComponentDefinition(
            id="ImageGallery",
            requirements=["url"],
            optional_fields=["title", "description"],
            options={
                "columns": {"type": "number", "default": 3},
            },
            interactions=["open_lightbox"],
            layout_defaults={
                "layout_size": "full",
                "span": 12,
                "min_height": 280,
            },
            description="图片画廊组件，支持网格布局和 Lightbox 灯箱预览。",
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
        # 新增原子化组件
        ComponentDefinition(
            id="CountCard",
            requirements=["value"],
            optional_fields=["title", "unit", "description"],
            options={
                "color": {"type": "string", "default": "default"},
            },
            interactions=[],
            layout_defaults={
                "layout_size": "quarter",
                "span": 4,
                "min_height": 140,
            },
            description="单一数字指标展示，适合突出展示播放量、粉丝数等大数字。",
        ),
        ComponentDefinition(
            id="ProgressBar",
            requirements=["value"],
            optional_fields=["label", "max", "description"],
            options={
                "color": {"type": "string", "default": "primary"},
                "show_percentage": {"type": "boolean", "default": True},
            },
            interactions=[],
            layout_defaults={
                "layout_size": "third",
                "span": 6,
                "min_height": 120,
            },
            description="进度条展示，适合展示完成度、占比等指标。",
        ),
        ComponentDefinition(
            id="QuoteCard",
            requirements=["content"],
            optional_fields=["author", "source", "timestamp"],
            options={
                "compact": {"type": "boolean", "default": False},
            },
            interactions=[],
            layout_defaults={
                "layout_size": "third",
                "span": 6,
                "min_height": 160,
            },
            description="引用卡片，适合展示精选评论、金句、摘要等文本内容。",
        ),
        ComponentDefinition(
            id="ComparisonCard",
            requirements=["left_value", "right_value"],
            optional_fields=["left_label", "right_label", "left_unit", "right_unit"],
            options={
                "show_diff": {"type": "boolean", "default": True},
            },
            interactions=[],
            layout_defaults={
                "layout_size": "third",
                "span": 6,
                "min_height": 160,
            },
            description="对比卡片，适合展示同比环比、两个指标的并排对比。",
        ),
        ComponentDefinition(
            id="AuthorCard",
            requirements=["name"],
            optional_fields=["avatar", "bio", "verified", "followers", "following", "posts", "link"],
            options={},
            interactions=["open_link"],
            layout_defaults={
                "layout_size": "third",
                "span": 6,
                "min_height": 140,
            },
            description="作者/账号卡片，适合展示UP主、博主等用户信息。",
        ),
        ComponentDefinition(
            id="TagCloud",
            requirements=["name", "count"],
            optional_fields=[],
            options={
                "max_tags": {"type": "number", "default": 30},
                "show_count": {"type": "boolean", "default": False},
            },
            interactions=[],
            layout_defaults={
                "layout_size": "third",
                "span": 6,
                "min_height": 220,
            },
            description="标签云，适合展示分类/标签的频率分布。",
        ),
        ComponentDefinition(
            id="TimelineCard",
            requirements=["title", "timestamp"],
            optional_fields=["description", "status", "type", "link"],
            options={
                "max_items": {"type": "number", "default": 10},
                "show_description": {"type": "boolean", "default": True},
            },
            interactions=["open_link"],
            layout_defaults={
                "layout_size": "third",
                "span": 6,
                "min_height": 280,
            },
            description="时间线卡片，适合展示有序事件序列。",
        ),
        ComponentDefinition(
            id="HeatmapCalendar",
            requirements=["date", "value"],
            optional_fields=[],
            options={
                "weeks": {"type": "number", "default": 52},
                "show_stats": {"type": "boolean", "default": True},
                "value_unit": {"type": "string", "default": "次"},
            },
            interactions=[],
            layout_defaults={
                "layout_size": "full",
                "span": 12,
                "min_height": 220,
            },
            description="热力日历，适合展示时间段内的活动密度分布。",
        ),
    ]
