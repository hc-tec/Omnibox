"""
Adapter通用工具函数

提供HTML清理、文本处理、类型转换等基础功能，供各个adapter复用。
"""

from __future__ import annotations

from html import unescape
import re
from typing import Any, Optional, List, Dict, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import AdapterExecutionContext, RouteAdapterResult


def strip_html(value: str | None) -> str:
    """
    清理HTML标签和实体编码

    - 移除所有HTML标签
    - 解码HTML实体（如 &nbsp;, &lt;, &gt;）
    - 合并连续空格
    """
    if not value:
        return ""
    # 移除所有HTML标签
    text = re.sub(r"<[^>]+>", " ", value)
    # 合并连续空格
    text = re.sub(r"\s+", " ", text)
    # 解码HTML实体
    return unescape(text).strip()


def short_text(value: str | None, limit: int = 220) -> str:
    """
    截断文本到指定长度，先清理HTML

    Args:
        value: 输入文本（可能包含HTML）
        limit: 最大长度（默认220字符）
    """
    text = strip_html(value)
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return f"{text[: limit - 3].rstrip()}..."


def safe_int(value: Any) -> int | None:
    """
    安全地转换为整数

    - 处理逗号分隔的数字（如 "1,234"）
    - 空值返回 None
    - 转换失败返回 None
    """
    if value in (None, ""):
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return int(value)
    except (ValueError, TypeError):
        return None


def ensure_list(value: Any) -> Optional[List[str]]:
    """
    规范化为字符串列表

    - 列表：转换每个元素为字符串
    - 单个字符串：包装为列表
    - 其他类型：返回 None
    """
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [value]
    return None


def first_author(authors: Any) -> str | None:
    """
    从多种格式中提取第一个作者名称

    支持的格式：
    - 列表：[{"name": "Alice"}, ...]
    - 字典：{"name": "Alice"}
    - 字符串："Alice"
    """
    if isinstance(authors, list) and authors:
        first = authors[0]
        if isinstance(first, dict):
            return first.get("name")
        if isinstance(first, str):
            return first
    if isinstance(authors, dict):
        return authors.get("name")
    if isinstance(authors, str):
        return authors
    return None


def should_skip_component(
    context: Optional["AdapterExecutionContext"],
    component_id: str,
    *,
    required: bool = False
) -> bool:
    """
    判断是否应该跳过某个组件的生成

    Args:
        context: 执行上下文，包含请求的组件列表
        component_id: 组件ID
        required: 是否为必需组件（必需组件永远不跳过）

    Returns:
        True表示应该跳过该组件，False表示应该生成

    使用示例：
        if should_skip_component(context, 'ListPanel', required=True):
            # 这个分支永远不会执行，因为ListPanel是必需的
            pass
    """
    if not context:
        return False  # 无context时不跳过任何组件
    if required:
        return False  # 必需组件永远不跳过
    return not context.wants(component_id)


def early_return_if_no_match(
    context: Optional["AdapterExecutionContext"],
    available_components: Sequence[str],
    stats: Dict[str, Any]
) -> Optional["RouteAdapterResult"]:
    """
    当所有可用组件都不在请求列表中时，提前返回空结果

    适用场景：
    - 用户只请求了该adapter不支持的组件
    - 避免不必要的数据处理

    Args:
        context: 执行上下文
        available_components: 该adapter支持的组件列表
        stats: 已构建的统计信息（会包含在返回结果中）

    Returns:
        如果需要提前返回则返回RouteAdapterResult，否则返回None继续执行

    使用示例：
        stats = {'datasource': 'github', 'route': '/github/trending'}
        early = early_return_if_no_match(context, ['ListPanel', 'LineChart'], stats)
        if early:
            return early  # 提前返回
        # 继续正常处理...
    """
    # 无context或requested_components为None时，表示无限制
    if not context or context.requested_components is None:
        return None

    # 检查是否有至少一个可用组件在请求列表中
    for component_id in available_components:
        if context.wants(component_id):
            return None  # 找到匹配组件，继续执行

    # 所有组件都不匹配（包括requested_components=[]的情况），提前返回空结果
    # 延迟导入避免循环依赖
    from .registry import RouteAdapterResult
    return RouteAdapterResult(records=[], block_plans=[], stats=stats)
