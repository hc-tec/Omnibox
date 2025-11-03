"""
Adapter通用工具函数

提供HTML清理、文本处理、类型转换等基础功能，供各个adapter复用。
"""

from __future__ import annotations

from html import unescape
import re
from typing import Any, Optional, List


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
