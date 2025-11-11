"""
面板组件配置预设

提供不同尺寸的组件配置，供 AI planner 灵活选择。
"""

from typing import Dict, Any, Literal

SizePreset = Literal["compact", "normal", "large", "full"]


def list_panel_size_preset(
    size: SizePreset = "normal",
    show_description: bool = True,
    show_metadata: bool = True,
    show_categories: bool = True,
) -> Dict[str, Any]:
    """
    ListPanel 组件的尺寸预设配置

    参数:
        size: 尺寸预设
            - "compact": 紧凑模式（3-5条，占1/3-1/4行，隐藏元数据）
            - "normal": 标准模式（10条，占半行，显示基本信息）
            - "large": 大型模式（20条，占全行，显示所有信息）
            - "full": 完整模式（30-50条，占全行，显示所有信息）
        show_description: 是否显示描述
        show_metadata: 是否显示作者/时间等元数据
        show_categories: 是否显示分类标签

    返回:
        组件配置字典（用于 AdapterBlockPlan.options）
    """
    presets = {
        "compact": {
            "compact": True,
            "max_items": 5,
            "span": 4,
            "layout_size": "quarter",
            "show_description": False,
            "show_metadata": False,
            "show_categories": False,
        },
        "normal": {
            "compact": False,
            "max_items": 10,
            "span": 6,
            "layout_size": "third",
            "show_description": show_description,
            "show_metadata": show_metadata,
            "show_categories": show_categories,
        },
        "large": {
            "compact": False,
            "max_items": 20,
            "span": 12,
            "layout_size": "half",
            "show_description": show_description,
            "show_metadata": show_metadata,
            "show_categories": show_categories,
        },
        "full": {
            "compact": False,
            "max_items": 50,
            "span": 12,
            "layout_size": "full",
            "show_description": show_description,
            "show_metadata": show_metadata,
            "show_categories": show_categories,
        },
    }

    config = presets[size].copy()

    # 允许覆盖默认值
    if size == "compact":
        # 紧凑模式强制隐藏这些信息
        config["show_description"] = False
        config["show_metadata"] = False
        config["show_categories"] = False
    else:
        config["show_description"] = show_description
        config["show_metadata"] = show_metadata
        config["show_categories"] = show_categories

    return config


def chart_size_preset(size: SizePreset = "normal") -> Dict[str, Any]:
    """
    图表组件（BarChart, LineChart, PieChart）的尺寸预设

    参数:
        size: 尺寸预设
            - "compact": 紧凑模式（占1/3行，高度200px）
            - "normal": 标准模式（占半行，高度280px）
            - "large": 大型模式（占全行，高度320px）
            - "full": 完整模式（占全行，高度400px）

    返回:
        组件配置字典
    """
    presets = {
        "compact": {"span": 4, "layout_size": "third"},
        "normal": {"span": 6, "layout_size": "half"},
        "large": {"span": 12, "layout_size": "full"},
        "full": {"span": 12, "layout_size": "full"},
    }
    return presets[size]

def media_card_size_preset(size: SizePreset = "normal") -> Dict[str, Any]:
    """
    媒体/视频卡片组件的预设尺寸
    """
    presets = {
        "compact": {"span": 4, "layout_size": "third", "columns": 2, "max_items": 4},
        "normal": {"span": 6, "layout_size": "half", "columns": 3, "max_items": 6},
        "large": {"span": 8, "layout_size": "half", "columns": 4, "max_items": 9},
        "full": {"span": 12, "layout_size": "full", "columns": 4, "max_items": 12},
    }
    return presets[size].copy()


def statistic_card_size_preset(size: SizePreset = "normal") -> Dict[str, Any]:
    """
    指标卡片的尺寸预设

    参数:
        size: 尺寸预设
            - "compact": 紧凑模式（占1/6行，适合6个并排）
            - "normal": 标准模式（占1/4行，适合4个并排）
            - "large": 大型模式（占1/3行，适合3个并排）
            - "full": 完整模式（占半行，适合2个并排）

    返回:
        组件配置字典
    """
    presets = {
        "compact": {"span": 2, "layout_size": "quarter"},
        "normal": {"span": 3, "layout_size": "quarter"},
        "large": {"span": 4, "layout_size": "third"},
        "full": {"span": 6, "layout_size": "half"},
    }
    return presets[size]


# 预定义的配置组合示例

HOTLIST_COMPACT = {
    "name": "热榜紧凑模式",
    "description": "适合热搜榜单、排行榜，占用空间小",
    "config": list_panel_size_preset("compact"),
}

ARTICLE_LIST_NORMAL = {
    "name": "文章列表标准模式",
    "description": "适合文章、帖子列表，信息量适中",
    "config": list_panel_size_preset("normal", show_description=True, show_metadata=True),
}

VIDEO_LIST_LARGE = {
    "name": "视频列表大型模式",
    "description": "适合视频列表，显示完整信息",
    "config": list_panel_size_preset("large", show_description=True, show_categories=True),
}
