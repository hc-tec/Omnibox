"""
面向不同 RSSHub 路由的自定义适配器，允许按数据源裁剪结构并规划 UIBlock。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import unescape
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from api.schemas.panel import ComponentInteraction, LayoutHint, SourceInfo


@dataclass
class AdapterBlockPlan:
    component_id: str
    props: Dict[str, Any]
    options: Dict[str, Any] = field(default_factory=dict)
    interactions: List[ComponentInteraction] = field(default_factory=list)
    title: Optional[str] = None
    layout_hint: Optional[LayoutHint] = None
    confidence: float = 0.6


@dataclass
class RouteAdapterResult:
    records: List[Dict[str, Any]]
    block_plans: List[AdapterBlockPlan] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


RouteAdapter = Callable[[SourceInfo, Sequence[Dict[str, Any]]], RouteAdapterResult]


def _default_adapter(source_info: SourceInfo, records: Sequence[Dict[str, Any]]) -> RouteAdapterResult:
    trimmed = list(records)
    return RouteAdapterResult(records=trimmed)


class RouteAdapterRegistry:
    def __init__(self):
        self._routes: List[Tuple[str, RouteAdapter]] = []

    def register(self, route: str, adapter: RouteAdapter) -> None:
        normalized = self._normalize(route)
        for idx, (existing_route, _) in enumerate(self._routes):
            if existing_route == normalized:
                self._routes[idx] = (normalized, adapter)
                break
        else:
            self._routes.append((normalized, adapter))
            self._routes.sort(key=lambda item: len(item[0]), reverse=True)

    def get(self, route: str) -> RouteAdapter:
        if not route:
            return _default_adapter

        target = self._normalize(route)
        for registered, adapter in self._routes:
            if target == registered:
                return adapter
            if self._is_prefix_match(target, registered):
                return adapter
        return _default_adapter

    def clear(self) -> None:
        self._routes.clear()

    @staticmethod
    def _normalize(route: str) -> str:
        route = (route or "").strip()
        if not route.startswith("/"):
            route = f"/{route}"
        if route != "/" and route.endswith("/"):
            return route.rstrip("/")
        return route or "/"

    @staticmethod
    def _is_prefix_match(target: str, registered: str) -> bool:
        if not registered:
            return False
        if target.startswith(registered):
            remainder = target[len(registered) :]
            if not remainder:
                return True
            if registered.endswith("/"):
                return True
            return remainder.startswith("/")
        return False


_registry = RouteAdapterRegistry()


def register_route_adapter(route: str, adapter: RouteAdapter) -> None:
    """注册指定 RSSHub 路由的适配函数。"""
    _registry.register(route, adapter)


def get_route_adapter(route: str) -> RouteAdapter:
    return _registry.get(route)


def clear_route_adapters() -> None:
    _registry.clear()


def route_adapter(*routes: str) -> Callable[[RouteAdapter], RouteAdapter]:
    """使用装饰器语法批量登记路由适配器。"""

    if not routes:
        raise ValueError("At least one route must be provided for registration.")

    def decorator(func: RouteAdapter) -> RouteAdapter:
        for route in routes:
            register_route_adapter(route, func)
        return func

    return decorator


def _strip_html(value: Optional[str]) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return unescape(text).strip()


def _short_text(value: Optional[str], limit: int = 220) -> str:
    text = _strip_html(value)
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return f"{text[: limit - 3].rstrip()}..."


def _safe_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return int(value)
    except (ValueError, TypeError):
        return None


def _collect_feed_items(records: Sequence[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    feed_title = ""
    feed_stats: Dict[str, Any] = {}
    items: List[Dict[str, Any]] = []

    for record in records:
        if not isinstance(record, dict):
            continue

        feed_title = feed_title or record.get("title") or record.get("feedTitle") or ""
        feed_stats.setdefault("feed_link", record.get("home_page_url") or record.get("link"))
        feed_stats.setdefault("language", record.get("language"))

        possible_items: Iterable[Any] = []
        if isinstance(record.get("items"), list):
            possible_items = record["items"]
        elif isinstance(record.get("item"), list):
            possible_items = record["item"]
        else:
            possible_items = [record]

        for raw_item in possible_items:
            if isinstance(raw_item, dict):
                items.append(dict(raw_item))

    feed_stats["total_items"] = len(items)
    return feed_title, items, feed_stats


def _build_list_records(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in items:
        title = item.get("title") or item.get("name")
        link = (
            item.get("url")
            or item.get("link")
            or item.get("guid")
            or item.get("id")
        )

        if not title and not link:
            continue

        summary = (
            item.get("summary")
            or item.get("summary_text")
            or item.get("description")
            or item.get("content_text")
            or item.get("content")
            or item.get("content_html")
        )

        published = (
            item.get("date_published")
            or item.get("pubDate")
            or item.get("published")
            or item.get("updated")
            or item.get("lastBuildDate")
        )

        authors = []
        raw_authors = item.get("authors") or item.get("author")
        if isinstance(raw_authors, list):
            authors = [author.get("name") for author in raw_authors if isinstance(author, dict) and author.get("name")]
        elif isinstance(raw_authors, dict):
            name = raw_authors.get("name") or raw_authors.get("nickname")
            if name:
                authors = [name]
        elif isinstance(raw_authors, str):
            authors = [raw_authors]

        categories = []
        raw_categories = item.get("tags") or item.get("category") or item.get("categories")
        if isinstance(raw_categories, list):
            categories = [
                tag.get("name") if isinstance(tag, dict) else str(tag)
                for tag in raw_categories
            ]
        elif isinstance(raw_categories, str):
            categories = [raw_categories]

        normalized.append(
            {
                "id": item.get("id") or link or title,
                "title": title,
                "link": link,
                "summary": _short_text(summary),
                "published_at": published,
                "author": ", ".join(filter(None, authors)) or None,
                "categories": categories or None,
                "raw_excerpt_length": len(summary) if isinstance(summary, str) else 0,
            }
        )

    return normalized


def _build_list_plan(title: str, component_confidence: float = 0.75) -> AdapterBlockPlan:
    return AdapterBlockPlan(
        component_id="ListPanel",
        props={
            "title_field": "title",
            "link_field": "link",
            "description_field": "summary",
            "pub_date_field": "published_at",
        },
        options={"show_description": True, "span": 12},
        interactions=[
            ComponentInteraction(type="open_link", label="Open Link"),
        ],
        title=title or None,
        layout_hint=LayoutHint(span=12, min_height=320),
        confidence=component_confidence,
    )


@route_adapter("/hupu", "/hupu/bbs", "/hupu/all")
def hupu_board_list_adapter(source_info: SourceInfo, records: Sequence[Dict[str, Any]]) -> RouteAdapterResult:
    feed_title, items, feed_stats = _collect_feed_items(records)
    normalized_items = _build_list_records(items)

    stats = {
        "datasource": source_info.datasource,
        "route": source_info.route,
        "feed_title": feed_title,
        "total_items": feed_stats.get("total_items", len(normalized_items)),
        "language": feed_stats.get("language"),
    }

    return RouteAdapterResult(
        records=normalized_items,
        block_plans=[_build_list_plan(feed_title)],
        stats=stats,
    )


@route_adapter("/bilibili", "/bilibili/user/video", "/bilibili/user/dynamic")
def bilibili_feed_adapter(source_info: SourceInfo, records: Sequence[Dict[str, Any]]) -> RouteAdapterResult:
    feed_title, items, feed_stats = _collect_feed_items(records)
    normalized_items = _build_list_records(items)

    for item in normalized_items:
        item["source"] = "bilibili"

    stats = {
        "datasource": source_info.datasource or "bilibili",
        "route": source_info.route,
        "feed_title": feed_title,
        "total_items": feed_stats.get("total_items", len(normalized_items)),
    }

    return RouteAdapterResult(
        records=normalized_items,
        block_plans=[_build_list_plan(feed_title, component_confidence=0.7)],
        stats=stats,
    )


@route_adapter("/github/trending")
def github_trending_adapter(source_info: SourceInfo, records: Sequence[Dict[str, Any]]) -> RouteAdapterResult:
    feed_title, items, feed_stats = _collect_feed_items(records)

    normalized_items: List[Dict[str, Any]] = []
    top_stars = 0
    language_counter: Dict[str, int] = {}

    for item in items:
        extra = item.get("extra") or {}
        title = item.get("title") or extra.get("repo")
        if not title:
            continue

        link = item.get("url") or extra.get("url")
        description = item.get("description") or item.get("content_text") or item.get("content_html")
        language = extra.get("language") or item.get("language")
        stars = _safe_int(extra.get("stars") or extra.get("star") or item.get("star"))
        stars_today = _safe_int(extra.get("stars_today") or extra.get("star_today"))
        forks = _safe_int(extra.get("forks") or item.get("forks"))

        if language:
            language_counter[language] = language_counter.get(language, 0) + 1

        if stars:
            top_stars = max(top_stars, stars)

        normalized_items.append(
            {
                "id": item.get("id") or link or title,
                "title": title,
                "link": link,
                "summary": _short_text(description, limit=180),
                "published_at": item.get("date_published") or item.get("published"),
                "language": language,
                "stars": stars,
                "stars_today": stars_today,
                "forks": forks,
                "author": (title.split("/", 1)[0].strip() if "/" in title else None),
                "raw_excerpt_length": len(description) if isinstance(description, str) else 0,
            }
        )

    stats = {
        "datasource": source_info.datasource or "github",
        "route": source_info.route,
        "total_items": len(normalized_items),
        "top_language": max(language_counter, key=language_counter.get) if language_counter else None,
        "top_stars": top_stars,
    }

    return RouteAdapterResult(
        records=normalized_items,
        block_plans=[_build_list_plan(feed_title or "GitHub Trending", component_confidence=0.74)],
        stats=stats,
    )


@route_adapter("/github/issue")
def github_issue_adapter(source_info: SourceInfo, records: Sequence[Dict[str, Any]]) -> RouteAdapterResult:
    feed_title, items, feed_stats = _collect_feed_items(records)
    normalized_items = _build_list_records(items)

    stats = {
        "datasource": source_info.datasource or "github",
        "route": source_info.route,
        "total_items": feed_stats.get("total_items", len(normalized_items)),
    }

    return RouteAdapterResult(
        records=normalized_items,
        block_plans=[_build_list_plan(feed_title or "GitHub Issues", component_confidence=0.66)],
        stats=stats,
    )


@route_adapter("/sspai")
def sspai_feed_adapter(source_info: SourceInfo, records: Sequence[Dict[str, Any]]) -> RouteAdapterResult:
    feed_title, items, feed_stats = _collect_feed_items(records)
    normalized_items = _build_list_records(items)

    stats = {
        "datasource": source_info.datasource,
        "route": source_info.route,
        "total_items": feed_stats.get("total_items", len(normalized_items)),
    }

    return RouteAdapterResult(
        records=normalized_items,
        block_plans=[_build_list_plan(feed_title, component_confidence=0.68)],
        stats=stats,
    )


__all__ = [
    "AdapterBlockPlan",
    "RouteAdapterResult",
    "RouteAdapter",
    "register_route_adapter",
    "route_adapter",
    "get_route_adapter",
    "clear_route_adapters",
]
