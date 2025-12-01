# 组件契约手册（Contract Registry v0.1）

> 本文是 LangGraph Planner 与数据算子(data_operator/schema_coder)之间共享的**唯一组件契约来源**。所有“面板该长什么样”的决策都必须引用这里的契约，不得再通过规则引擎或隐式 heuristics 猜测组件。

## 1. 契约形态

- `component_id`：前端 `componentManifest.ts` 中的组件 ID（如 `StatisticCard`、`ListPanel`）。
- `contract_id`：`{component_id}-contract-v{n}`，用于版本演进。
- `data_contract`：ViewModel 数据结构定义（字段名、类型、必填项、上限）。
- `props_contract`：需要传入 `UIBlock.props` 的字段及默认值规则。
- `layout_hint`：推荐 `span`、`min_height`、`append_mode` 等布局建议。
- `pipeline_guidance`：如何用内置 `pipeline` / `builtin` 变换构造数据（Planner 会把它注入 SchemaCoder）。
- `sample_view_model`：沙箱执行器应产出的 `view_model` JSON 片段，可复制到 few-shot。

> 🎯 **强约束**：data_operator 的输出必须与 `data_contract` 完全一致；PanelRuntime 只做渲染映射，不负责补字段。

## 2. 通用命名规范

- `items` 数组上限：表格/列表默认 50，StatisticCard 默认 4，MediaCardGrid 默认 9。超出必须在 metadata 中标注 `items_truncated`.
- `_field` 后缀的 props 表示“记录中对应字段的键名”，例如 `title_field="metric_title"`。
- 数值字段必须为 `number` 或可被 `coerce_number` 转换的字符串；不得返回 `Decimal`/`Fraction` 等自定义类型。
- 所有 `*_at` 字段使用 ISO 字符串；`categories`/`badges` 等是字符串数组。

## 3. 组件契约清单

### 3.1 StatisticCard Contract

- `contract_id`: `StatisticCard-contract-v2`
- 适用：用户明确要求“数字卡片/指标/统计值/only count”等。
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "metric_title": "string (必填)",
        "metric_value": "number (必填)",
        "metric_trend": "\"up\" | \"down\" | \"flat\" | null",
        "metric_delta_text": "string 可选，示例 “较上周 +12%”",
        "metric_unit": "string 可选，示例 “条”",
        "description": "string 可选，补充说明"
      }
    ]
  }
  ```
- `props_contract`
  ```jsonc
  {
    "title_field": "metric_title",
    "value_field": "metric_value",
    "trend_field": "metric_trend",
    "title": "面板标题（Planner 提供，有则覆盖）"
  }
  ```
- `layout_hint`: `span=6`, `min_height=160`, `mode="append"`.
- `pipeline_guidance`
  1. 若指令是“统计数量”，先 `aggregate_numeric(field="...") -> count`。
  2. 生成 `items=[{"metric_title": "...", "metric_value": count}]`。
  3. 可选 `rename_fields` 将业务字段映射至 `metric_*`。
- `sample_view_model`
  ```json
  {
    "component_id": "StatisticCard",
    "data": {
      "items": [
        {
          "metric_title": "B站热搜数量",
          "metric_value": 10,
          "description": "当前共有 10 条热搜数据"
        }
      ]
    },
    "props": {
      "title_field": "metric_title",
      "value_field": "metric_value",
      "trend_field": "metric_trend",
      "title": "B站热搜数量"
    }
  }
  ```

### 3.2 ListPanel Contract

- `contract_id`: `ListPanel-contract-v4`
- 使用场景：新闻/热搜/帖子/任意记录型结果。支持标准模式（资讯）和极简模式（热榜/排行榜）。
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "id": "string (可选，没填则 fallback 到 link/title)",
        "title": "string 必填",
        "link": "string | null",
        "summary": "string | null",
        "author": "string | null",
        "published_at": "ISO string | null",
        "categories": "string[] | null",
        "hot": "number | string | null (热度值，极简模式下显示)"
      }
    ],
    "stats": {
      "description": "string | null",
      "item_count": "number"
    }
  }
  ```
- `props_contract`
  ```jsonc
  {
    "title_field": "title",
    "link_field": "link",
    "description_field": "summary",
    "author_field": "author",
    "pub_date_field": "published_at",
    "categories_field": "categories",
    "hot_field": "hot"
  }
  ```
- `options_contract`
  ```jsonc
  {
    "variant": "string, 'standard' | 'minimal', default 'standard'",
    "show_description": "boolean, default true (standard 模式)",
    "show_metadata": "boolean, default true (standard 模式)",
    "show_categories": "boolean, default true (standard 模式)",
    "show_rank": "boolean, default false (minimal 模式建议 true)",
    "compact": "boolean, default false",
    "max_items": "number, default 10"
  }
  ```
- `variant` 模式说明：
  - `standard`（默认）：标准资讯模式，显示标题、描述、作者、日期、分类等完整信息
  - `minimal`：极简模式，仅显示排名 + 标题 + 热度值，适用于热搜/排行榜场景
- `pipeline_guidance`
  - 若需 Top-N：`sort_by` → `head`.
  - 多平台合并时必须补 `platform` 字段，并在 `title` 中加入平台前缀或 `categories`.
- `sample_view_model`
  ```json
  {
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
          "categories": ["bilibili", "hot-search"]
        }
      ],
      "stats": {
        "item_count": 15
      }
    },
    "props": {
      "title_field": "title",
      "link_field": "link",
      "description_field": "summary",
      "pub_date_field": "published_at",
      "categories_field": "categories"
    },
    "options": {
      "max_items": 15
    }
  }
  ```

### 3.3 LineChart Contract

- `contract_id`: `LineChart-contract-v2`
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "x": "string | number | ISO string (必填)",
        "y": "number (必填)",
        "series": "string | null (多序列可选)"
      }
    ]
  }
  ```
- `props_contract`
  ```jsonc
  {
    "x_field": "x",
    "y_field": "y",
    "series_field": "series"
  }
  ```
- `layout_hint`: `span=12`, `min_height=280`.
- `pipeline_guidance`
  - 时间序列：`rename_fields` 统一成 `x`（时间）、`y`（值）、`series`（来源）。
  - 数值保证：`coerce_number` → `aggregate_numeric`(可按日/周分组) → `sort_by(x)`.
- `sample_view_model`
  ```json
  {
    "component_id": "LineChart",
    "data": {
      "items": [
        { "x": "2025-11-25", "y": 12000, "series": "播放量" },
        { "x": "2025-11-26", "y": 18500, "series": "播放量" }
      ]
    },
    "props": {
      "x_field": "x",
      "y_field": "y",
      "series_field": "series"
    }
  }
  ```

### 3.4 BarChart Contract

- `contract_id`: `BarChart-contract-v2`
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "category": "string (x 轴)",
        "value": "number",
        "series": "string | null"
      }
    ]
  }
  ```
- `props_contract`
  ```jsonc
  {
    "x_field": "category",
    "y_field": "value",
    "series_field": "series"
  }
  ```
- `pipeline_guidance`
  - 合并字段 `rename_fields({"作者": "category", "投稿量": "value"})`.
  - 若需要排序：`sort_by(field="value", order="desc") -> head(10)`.

### 3.5 PieChart Contract

- `contract_id`: `PieChart-contract-v1`
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "name": "string",
        "value": "number",
        "percentage": "number | null"
      }
    ]
  }
  ```
- `props_contract`: `{ "name_field": "name", "value_field": "value" }`.
- `pipeline_guidance`: 先 `group_count` / `aggregate_numeric`，然后 `rename_fields`.

### 3.6 Table Contract

- `contract_id`: `Table-contract-v1`
- `data_contract`
  ```jsonc
  {
    "headers": [
      { "key": "string", "label": "string", "type": "string | number | datetime | badge" }
    ],
    "rows": [
      {
        "_row_id": "string",
        "cells": {
          "<header.key>": "string | number | boolean"
        }
      }
    ]
  }
  ```
- `props_contract`: `{ "columns": "headers", "data_field": "rows" }`（交由 PanelRuntime 绑定）。
- `pipeline_guidance`: 使用 `select_fields` 将记录扁平化，再构造 headers。

### 3.7 MediaCardGrid Contract

- `contract_id`: `MediaCardGrid-contract-v2`
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "title": "string",
        "link": "string | null",
        "cover_url": "string | null",
        "author": "string | null",
        "duration": "string | null",
        "view_count": "number | string",
        "like_count": "number | string",
        "badges": "string[] | null"
      }
    ]
  }
  ```
- `props_contract`
  ```jsonc
  {
    "title_field": "title",
    "link_field": "link",
    "cover_field": "cover_url",
    "author_field": "author",
    "duration_field": "duration",
    "view_count_field": "view_count",
    "like_count_field": "like_count",
    "badges_field": "badges"
  }
  ```
- `pipeline_guidance`: 图片/媒体场景需要 `rename_fields` + `coerce_number`；`max_items` 默认为 6。

### 3.8 FallbackRichText Contract（调试 / 降级）

- `contract_id`: `FallbackRichText-contract-v1`
- 数据结构：
  ```jsonc
  {
    "items": [
      { "metric_title": "string", "description": "string" }
    ],
    "error_detail": "string"
  }
  ```
- 仅在 panel 渲染失败时由 PanelRuntime 自动生成，Planner 不应主动使用。


### 3.9 CountCard Contract（单一数字指标）

- `contract_id`: `CountCard-contract-v1`
- 使用场景：突出展示单个大数字（播放量、粉丝数、热度值）
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "metric_title": "string | null",
        "metric_value": "number (必填)",
        "unit": "string | null",
        "description": "string | null"
      }
    ]
  }
  ```
- `props_contract`: `{ "title_field": "metric_title", "value_field": "metric_value", "unit_field": "unit", "description_field": "description" }`
- `options_defaults`: `{ "color": "default|primary|success|warning|error|info" }`
- `layout_hint`: `span=4`, `min_height=140`

### 3.10 ProgressBar Contract（进度条）

- `contract_id`: `ProgressBar-contract-v1`
- 使用场景：展示完成度、占比（任务进度、好评率）
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "label": "string | null",
        "value": "number (必填，当前值)",
        "max": "number (可选，默认100)",
        "description": "string | null"
      }
    ]
  }
  ```
- `props_contract`: `{ "label_field": "label", "value_field": "value", "max_field": "max", "description_field": "description" }`
- `options_defaults`: `{ "color": "primary", "show_percentage": true }`

### 3.11 QuoteCard Contract（引用卡片）

- `contract_id`: `QuoteCard-contract-v1`
- 使用场景：展示精选评论、金句、摘要
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "content": "string (必填，引用内容)",
        "author": "string | null",
        "source": "string | null (来源)",
        "timestamp": "ISO string | null"
      }
    ]
  }
  ```
- `props_contract`: `{ "content_field": "content", "author_field": "author", "source_field": "source", "timestamp_field": "timestamp" }`
- `options_defaults`: `{ "compact": false }`

### 3.12 ComparisonCard Contract（对比卡片）

- `contract_id`: `ComparisonCard-contract-v1`
- 使用场景：同比环比、两个指标的并排对比
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "left_label": "string | null",
        "left_value": "number (必填)",
        "left_unit": "string | null",
        "right_label": "string | null",
        "right_value": "number (必填)",
        "right_unit": "string | null"
      }
    ]
  }
  ```
- `props_contract`: `{ "left_label_field", "left_value_field", "left_unit_field", "right_label_field", "right_value_field", "right_unit_field" }`
- `options_defaults`: `{ "show_diff": true }`

### 3.13 AuthorCard Contract（作者卡片）

- `contract_id`: `AuthorCard-contract-v1`
- 使用场景：展示UP主、博主等用户信息
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "name": "string (必填)",
        "avatar": "string | null (头像URL)",
        "bio": "string | null (简介)",
        "verified": "boolean | null (认证)",
        "followers": "number | null (粉丝数)",
        "following": "number | null (关注数)",
        "posts": "number | null (作品数)",
        "link": "string | null (主页链接)"
      }
    ]
  }
  ```
- `props_contract`: 所有字段对应 `*_field` 映射
- `layout_hint`: `span=6`, `min_height=140`

### 3.14 TagCloud Contract（标签云）

- `contract_id`: `TagCloud-contract-v1`
- 使用场景：展示分类/标签的频率分布
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "name": "string (必填，标签名)",
        "count": "number (必填，频次)"
      }
    ]
  }
  ```
- `props_contract`: `{ "name_field": "name", "count_field": "count" }`
- `options_defaults`: `{ "max_tags": 30, "show_count": false }`
- `pipeline_guidance`: 使用 `group_count` 按字段分组计数

### 3.15 TimelineCard Contract（时间线）

- `contract_id`: `TimelineCard-contract-v1`
- 使用场景：展示有序事件序列（动态历史、操作记录）
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "title": "string (必填)",
        "timestamp": "ISO string (必填)",
        "description": "string | null",
        "status": "string | null (completed|pending|error|active)",
        "type": "string | null (事件类型标签)",
        "link": "string | null"
      }
    ]
  }
  ```
- `props_contract`: 所有字段对应 `*_field` 映射
- `options_defaults`: `{ "max_items": 10, "show_description": true }`
- `layout_hint`: `span=6`, `min_height=280`

### 3.16 HeatmapCalendar Contract（热力日历）

- `contract_id`: `HeatmapCalendar-contract-v1`
- 使用场景：展示时间段内的活动密度（发布频率、提交记录）
- `data_contract`
  ```jsonc
  {
    "items": [
      {
        "date": "string (必填，YYYY-MM-DD格式)",
        "value": "number (必填，活动值)"
      }
    ]
  }
  ```
- `props_contract`: `{ "date_field": "date", "value_field": "value" }`
- `options_defaults`: `{ "weeks": 52, "show_stats": true, "value_unit": "次" }`
- `layout_hint`: `span=12`, `min_height=220`
- `pipeline_guidance`: 使用 `aggregate_by_date` 按日期聚合


## 4. 契约引用方式

1. **Planner**
   - 在 TODO 中写 `组件: StatisticCard (contract: StatisticCard-contract-v2)`。
   - 在 `tool_args` 内添加 `target_component_id`、`contract_id`。
2. **data_operator**
   - Prompt 中追加 `contract_definition`（上面 JSON）。
   - 输出 `metadata.component_id`、`metadata.contract_version`。
3. **PanelRuntime**
   - `panel_spec.data_envelopes[*].metadata.contract_id = ...`
   - `view_models[*].component_id = contract.component_id`。

## 5. 验证与版本策略

- 当组件 props 或数据结构发生变动，先在此文件新增 `contract-v{n+1}` 并注明差异。
- 调试脚本 `scripts/contract_validator.py` 将 `frontend/src/shared/componentManifest.ts` 与本文件做字段对比（TODO: TS-09）。
- 所有测试（TS-01~TS-20）必须引用契约 ID，而不是凭空硬编码字段。

---

> 更新记录：
> - v0.2（2025-12-02）——新增 8 个原子化组件契约（CountCard、ProgressBar、QuoteCard、ComparisonCard、AuthorCard、TagCloud、TimelineCard、HeatmapCalendar）
> - v0.1（2025-11-30）——整理现有 7 个核心组件 + 1 个降级组件的契约，提供 sample view_model 与 pipeline 指南，供 Phase 13 实施使用。
