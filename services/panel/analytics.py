"""
数据分析模块（Analytics）

职责：
  分析 RSSHub 返回的 payload 数据，提取关键指标和摘要信息。

功能：
  1. 统一的 payload 摘要接口（summarize_payload）
  2. 路由特定的分析策略（如 bilibili, github, hupu 等）
  3. 提取 item_count, metrics, sample_titles 等元信息
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def summarize_payload(route: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分析 payload 数据并返回摘要信息。

    根据路由选择对应的分析策略：
      - /bilibili/user/followings: 关注列表专用分析
      - /bilibili/*: Bilibili 通用分析
      - /github/trending: GitHub 趋势分析
      - /hupu/*: 虎扑分析
      - 其他: 通用分析

    Args:
        route: 路由标识（如 "/github/trending/daily"）
        payload: RSSHub 返回的 JSON 数据

    Returns:
        包含以下字段的字典：
          - item_count: 数据项数量
          - sample_titles: 示例标题列表（最多 3 条）
          - metrics: 路由特定的指标字典
    """
    if not isinstance(payload, dict):
        return {"item_count": 0, "metrics": {}, "sample_titles": []}

    route = route or ""
    # 按路由匹配优先级选择分析策略（注意：具体路由优先于通配符）
    if route.startswith("/bilibili/user/followings"):
        return _summarize_bilibili_followings(payload)
    if route.startswith("/bilibili/"):
        return _summarize_generic_items(payload)
    if route.startswith("/github/trending"):
        return _summarize_github_trending(payload)
    if route.startswith("/hupu"):
        return _summarize_hupu(payload)
    return _summarize_generic_items(payload)


def _summarize_generic_items(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    通用的 payload 分析（默认策略）。

    适用于大多数 RSSHub 路由，提取 items/item 字段中的数据项。

    Args:
        payload: RSSHub 返回的 JSON 数据

    Returns:
        包含 item_count, sample_titles, metrics 的字典
    """
    items = payload.get("items") or payload.get("item") or []
    # 兼容单个对象的情况（某些路由返回单个 item 而非数组）
    if isinstance(items, dict):
        items = [items]
    item_count = len(items) if isinstance(items, list) else 0
    titles = _collect_titles(items)
    metrics = {"item_count": item_count}
    return {"item_count": item_count, "sample_titles": titles, "metrics": metrics}


def _summarize_bilibili_followings(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bilibili 关注列表专用分析。

    提取关注数、新增关注数、最近关注时间等指标。

    Args:
        payload: Bilibili 关注列表的 JSON 数据

    Returns:
        包含以下 metrics 的字典：
          - follower_count: 总关注数
          - new_followings: 新增关注数
          - hours_since_latest: 距离最近一次关注的小时数
    """
    items = payload.get("item") or payload.get("items") or []
    if isinstance(items, dict):
        items = [items]
    item_count = len(items) if isinstance(items, list) else 0
    follower_count = payload.get("count") or payload.get("total_followings")
    metrics = {
        "item_count": item_count,
        "follower_count": _safe_int(follower_count),
        "new_followings": item_count,
    }
    # 计算距离最近关注的时间（小时）
    latest_time = _parse_recent_time(items)
    if latest_time is not None:
        metrics["hours_since_latest"] = latest_time
    return {
        "item_count": item_count,
        "sample_titles": _collect_titles(items),
        "metrics": {k: v for k, v in metrics.items() if v is not None},
    }


def _summarize_github_trending(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    GitHub 趋势榜单专用分析。

    提取星标数、语言分布等指标。

    Args:
        payload: GitHub trending 的 JSON 数据

    Returns:
        包含以下 metrics 的字典：
          - total_stars: 所有仓库的总星标数
          - avg_stars: 平均星标数
          - language_diversity: 语言种类数
    """
    items = payload.get("items") or []
    metrics: Dict[str, Any] = {}
    languages: Dict[str, int] = {}  # 语言计数器
    total_stars = 0
    item_count = 0

    for item in items or []:
        if not isinstance(item, dict):
            continue
        item_count += 1
        extra = item.get("extra") or {}
        star_count = _safe_int(extra.get("stars") or item.get("stars"))
        if star_count is not None:
            total_stars += star_count
        language = extra.get("language") or item.get("language")
        if language:
            languages[language] = languages.get(language, 0) + 1

    if item_count:
        metrics["item_count"] = item_count
    if total_stars:
        metrics["total_stars"] = total_stars
        metrics["avg_stars"] = round(total_stars / item_count, 2) if item_count else None
    if languages:
        metrics["language_diversity"] = len(languages)

    return {
        "item_count": item_count,
        "sample_titles": _collect_titles(items),
        "metrics": {k: v for k, v in metrics.items() if v is not None},
    }


def _summarize_hupu(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    虎扑论坛专用分析。

    提取帖子作者信息等指标。

    Args:
        payload: 虎扑帖子的 JSON 数据

    Returns:
        包含以下 metrics 的字典：
          - author_ratio: 有作者信息的帖子占比
    """
    items = payload.get("items") or []
    item_count = len(items) if isinstance(items, list) else 0
    author_count = 0  # 统计有作者信息的帖子数
    for item in items or []:
        if isinstance(item, dict) and item.get("authors"):
            author_count += 1
    metrics = {
        "item_count": item_count,
        "author_ratio": round(author_count / item_count, 2) if item_count else None,
    }
    return {
        "item_count": item_count,
        "sample_titles": _collect_titles(items),
        "metrics": {k: v for k, v in metrics.items() if v is not None},
    }


def _collect_titles(items: Any, max_samples: int = 3) -> List[str]:
    """
    从数据项列表中提取示例标题。

    Args:
        items: 数据项列表
        max_samples: 最多提取的标题数（默认 3 条）

    Returns:
        标题字符串列表
    """
    titles: List[str] = []
    if not isinstance(items, list):
        return titles
    for item in items:
        if not isinstance(item, dict):
            continue
        # 优先提取 title，其次 name
        title = item.get("title") or item.get("name")
        if title:
            titles.append(str(title))
        if len(titles) >= max_samples:
            break
    return titles


def _parse_recent_time(items: Any) -> Optional[float]:
    """
    从数据项列表中解析最近的时间戳。

    Args:
        items: 数据项列表

    Returns:
        距离现在的小时数（浮点数）
        若无法解析任何时间，返回 None
    """
    latest = None
    now = datetime.utcnow()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        pub = item.get("pubDate") or item.get("date_published")
        if not pub:
            continue
        # 尝试解析 ISO 8601 格式
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except Exception:
            # 尝试解析 RFC 822 格式（RSS 常用）
            try:
                dt = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z")
            except Exception:
                continue
        # 计算时间差（小时）
        delta = (now - dt).total_seconds() / 3600
        if latest is None or delta < latest:
            latest = delta
    return latest


def _safe_int(value: Any) -> Optional[int]:
    """
    安全地将值转换为整数。

    处理规则：
      - None, "", False: 返回 None
      - 字符串: 移除逗号和空格后转换
      - 其他类型: 直接转换

    Args:
        value: 待转换的值

    Returns:
        整数或 None（转换失败时）
    """
    if value in (None, "", False):
        return None
    try:
        if isinstance(value, str):
            # 移除千分位逗号和空格（如 "1,234" -> "1234"）
            value = value.replace(",", "").strip()
        return int(value)
    except (TypeError, ValueError):
        return None
