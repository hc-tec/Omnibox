# Backend Panel Adapter Specification

> This document defines the contract between the DataExecutor, route adapters, and frontend components. All adapter development must follow these rules.

## 1. DataExecutor Output

`DataExecutor.fetch_rss` returns a `FetchResult` with the following fields:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `status` | `"success" \| "error"` | Whether the fetch succeeded. |
| `items` | `List[Dict[str, Any]]` | Defaults to `[payload]`. Kept as a list for historical consumers, but no longer assumes the presence of `title/link/description`. |
| `payload` | `Dict[str, Any]` | The original RSSHub JSON. When the response is not a dict, this field contains `{"value": <raw_response>}`. |
| `feed_title` / `feed_link` / `feed_description` | `Optional[str]` | Copied from the RSSHub response when available. |
| `source` | `"local" \| "fallback"` | Indicates which RSSHub endpoint was used. |
| `error_message` | `Optional[str]` | Present only when `status == "error"`. |

The cache layer stores the full `FetchResult`, so cache hits expose the exact same `payload`.

## 2. DataQueryResult

Successful queries produce:

```python
DataQueryResult(
    status="success",
    items=fetch_result.items,        # defaults to [payload]
    payload=fetch_result.payload,    # original RSSHub JSON
    feed_title=fetch_result.feed_title,
    generated_path=generated_path,
    source=fetch_result.source,
    cache_hit=...,
)
```

Downstream stages always prefer `payload`; `items` only exists for legacy helpers (e.g., schema summariser) and now mirrors `[payload]`.

## 3. Route Adapter Contract

### 3.1 Registration

```python
from services.panel.adapters import route_adapter, RouteAdapterResult, AdapterBlockPlan

@route_adapter("/hupu/bbs", "/hupu/all")
def hupu_adapter(source_info, records):
    ...
```

- `records` is a list; the first element is the original payload dictionary. Additional items can be used for adapter-specific expansions.
- Adapters must return `RouteAdapterResult`:
  - `records`: transformed data ready for frontend components.
  - `block_plans`: one or more `AdapterBlockPlan` objects describing component usage.
  - `stats`: optional metrics merged into `DataBlock.stats`.

### 3.2 AdapterBlockPlan Fields

| Field | Required | Description |
| ----- | -------- | ----------- |
| `component_id` | ✅ | Frontend component identifier. |
| `props` | ✅ | Mapping from component props to fields inside `records`. |
| `options` | ❌ | Optional component configuration (e.g., `span`, flags). |
| `interactions` | ❌ | `ComponentInteraction` list describing available actions. |
| `title` | ❌ | Block title; defaults to route or datasource when omitted. |
| `layout_hint` | ❌ | Optional layout suggestion (`LayoutHint`). |
| `confidence` | ❌ | Recommendation confidence (0–1). Defaults to 0.6. |

## 4. Component Field Schemas

The adapter must ensure each record includes the fields required by the selected component. Refer to `frontend/src/shared/componentManifest.ts` for authoritative definitions.

### 4.1 ListPanel

| Prop | Required | Description |
| ---- | -------- | ----------- |
| `title_field` | Yes | Record field used as display title. |
| `link_field` | Yes | Record field used as hyperlink. |
| `description_field` | No | Field containing summary text. |
| `pub_date_field` | No | Field containing publication time. |

Example record:

```jsonc
{
  "title": "Sample Thread One",
  "link": "https://bbs.hupu.com/1.html",
  "summary": "Preview ...",
  "published_at": "2024-01-01T00:00:00Z",
  "author": "AuthorA",
  "categories": ["tag-a", "tag-b"]
}
```

### 4.2 StatisticCard

| Prop | Required | Description |
| ---- | -------- | ----------- |
| `title_field` | Yes | Metric name field. |
| `value_field` | Yes | Metric value field (prefer numeric). |
| `trend_field` | No | Optional trend indicator. |

Recommended record:

```jsonc
{
  "metric_title": "Daily Active Users",
  "metric_value": 12345,
  "metric_trend": "+5.6%"
}
```

### 4.3 LineChart

| Prop | Required | Description |
| ---- | -------- | ----------- |
| `x_field` | Yes | X-axis field (time/category). |
| `y_field` | Yes | Numeric measure. |
| `series_field` | No | Optional series grouping. |

Example record:

```jsonc
{
  "timestamp": "2024-01-01",
  "value": 120,
  "series": "New Users"
}
```

### 4.4 FallbackRichText

| Prop | Required | Description |
| ---- | -------- | ----------- |
| `title_field` | Yes | Field containing the heading. |
| `description_field` | No | Field containing raw text/HTML. |

## 5. Adapter Pipeline

1. `DataExecutor` fetches the RSSHub payload and returns `FetchResult`.
2. `DataQueryService` stores both `items` and `payload` in `DataQueryResult`.
3. `ChatService` wraps the payload inside `PanelBlockInput(records=[payload])`.
4. `DataBlockBuilder` resolves a route adapter via `get_route_adapter(route)`:
   - If registered, it uses the adapter’s `records` and `block_plans`.
   - Otherwise it falls back to `FallbackRichText`.
5. `PanelGenerator` materialises UI blocks based on the `AdapterBlockPlan` objects and passes the trimmed data to the frontend.

## 6. Single-Route Multi-Component Example

Adapters may produce multiple blocks from the same payload. For example, GitHub Trending can render both a list and a chart:

```python
@route_adapter("/github/trending")
def github_trending_adapter(source_info, records):
    feed = records[0]
    items = feed.get("items", [])

    normalized = []
    for rank, item in enumerate(items, start=1):
        extra = item.get("extra") or {}
        normalized.append(
            {
                "rank": rank,
                "title": item.get("title"),
                "link": item.get("url"),
                "summary": item.get("description"),
                "language": extra.get("language"),
                "stars": int(extra.get("stars", 0) or 0),
            }
        )

    return RouteAdapterResult(
        records=normalized,
        block_plans=[
            AdapterBlockPlan(
                component_id="ListPanel",
                props={
                    "title_field": "title",
                    "link_field": "link",
                    "description_field": "summary",
                },
                title=feed.get("title"),
            ),
            AdapterBlockPlan(
                component_id="LineChart",
                props={
                    "x_field": "rank",
                    "y_field": "stars",
                    "series_field": "language",
                },
                title=f"{feed.get('title')} Stars",
            ),
        ],
    )
```

A single normalised record structure satisfies both components. If two components require fundamentally different data, consider creating multiple data blocks or including supplementary datasets under `stats`.

## 7. Development Guidelines

- Never assume the presence of `title/link/description` in the payload; always inspect the actual RSSHub response before mapping fields.
- Prefer converting strings to numeric types within the adapter so components receive consistent data.
- Return multiple `AdapterBlockPlan` instances when a route should render more than one component.
- When a feed cannot be structured, let the adapter return an empty plan so `FallbackRichText` handles the rendering gracefully.
- Each new adapter should ship with unit tests that cover field mapping and component selection.
