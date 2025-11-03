from __future__ import annotations

from html import unescape
import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from api.schemas.panel import ComponentInteraction, LayoutHint, SourceInfo

from services.panel.view_models import validate_records
from .registry import AdapterBlockPlan, RouteAdapterResult


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return unescape(text).strip()


def short_text(value: str | None, limit: int = 220) -> str:
    text = strip_html(value)
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return f"{text[: limit - 3].rstrip()}..."


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return int(value)
    except (ValueError, TypeError):
        return None


def collect_feed_items(records: Sequence[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    feed_title = ""
    feed_stats: Dict[str, Any] = {}
    items: List[Dict[str, Any]] = []

    for record in records:
        if not isinstance(record, dict):
            continue

        feed_title = feed_title or record.get("title") or record.get("feedTitle") or ""
        feed_stats.setdefault("feed_link", record.get("home_page_url") or record.get("link"))
        feed_stats.setdefault("language", record.get("language"))

        candidate_sequences: Iterable[Any]
        if isinstance(record.get("items"), list):
            candidate_sequences = record["items"]
        elif isinstance(record.get("item"), list):
            candidate_sequences = record["item"]
        else:
            candidate_sequences = [record]

        for raw_item in candidate_sequences:
            if isinstance(raw_item, dict):
                items.append(dict(raw_item))

    feed_stats["total_items"] = len(items)
    return feed_title, items, feed_stats


def build_list_records(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
                "summary": short_text(summary),
                "published_at": published,
                "author": ", ".join(filter(None, authors)) or None,
                "categories": categories or None,
                "raw_excerpt_length": len(summary) if isinstance(summary, str) else 0,
            }
        )

    return normalized


def build_list_plan(title: str | None, confidence: float = 0.75) -> AdapterBlockPlan:
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
        confidence=confidence,
    )


def build_api_candidate(
    *,
    route: str,
    label: str,
    docs: str | None = None,
    confidence: float | None = None,
) -> Dict[str, Any]:
    candidate = {
        "route": route,
        "label": label,
    }
    if docs:
        candidate["docs"] = docs
    if confidence is not None:
        candidate["confidence"] = confidence
    return candidate


def list_panel_result(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    *,
    confidence: float = 0.75,
    api_endpoint: str | None = None,
    api_candidates: Sequence[Dict[str, Any]] | None = None,
) -> RouteAdapterResult:
    feed_title, items, feed_stats = collect_feed_items(records)
    normalized = validate_records("ListPanel", build_list_records(items))
    stats = {
        "datasource": source_info.datasource,
        "route": source_info.route,
        "feed_title": feed_title,
        "total_items": feed_stats.get("total_items", len(normalized)),
        "language": feed_stats.get("language"),
    }
    endpoint = api_endpoint or source_info.route
    if endpoint:
        stats["api_endpoint"] = endpoint
    if api_candidates:
        stats["api_candidates"] = list(api_candidates)

    return RouteAdapterResult(
        records=normalized,
        block_plans=[build_list_plan(feed_title, confidence=confidence)],
        stats=stats,
    )
