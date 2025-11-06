# 智能面板组件视图模型（Contract-First 指南）

本文档描述后端产出的视图模型格式，是前后端共同遵守的契约。所有适配器实现、前端组件开发都必须以此为准；若契约发生变化，必须先更新本文档再改动代码。

---

## 1. 总体原则

1. **契约优先**：先定义模型，再实现适配器或组件。任何字段的新增、删除或重命名都要在这里记录。  
2. **统一命名**：字段命名使用 `snake_case`，字符串采用 UTF-8。  
3. **版本标识**：不同版本的契约通过 `ComponentId@vN` 表示，本文描述的均为 `@v1`。若未来需要破坏性调整，请发布 `@v2` 并保留旧版处理逻辑。  
4. **严格校验**：后端使用 `services/panel/view_models.py` 中的 Pydantic 模型验证，前端应生成一致的 TypeScript/Zod 类型。  
5. **样例驱动**：每个视图模型都提供完整示例以及推荐的 `AdapterBlockPlan.props` 映射。

---

## 2. ListPanel@v1 —— 列表类信息

### 2.1 Record 结构

```jsonc
{
  "id": "https://bbs.hupu.com/1.html",
  "title": "Sample Thread One",
  "link": "https://bbs.hupu.com/1.html",
  "summary": "Preview One",
  "published_at": "2024-01-01T00:00:00Z",
  "author": "AuthorA",
  "categories": ["tag-a", "tag-b"]
}
```

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `id` | `str` | 全局唯一标识，可使用链接或标题 |
| `title` | `str` | 展示标题（必填） |
| `link` | `Optional[str]` | 跳转地址 |
| `summary` | `Optional[str]` | 简要描述（建议去除 HTML） |
| `published_at` | `Optional[str]` | ISO8601 时间 |
| `author` | `Optional[str]` | 作者/发布者 |
| `categories` | `Optional[List[str]]` | 标签集合 |

### 2.2 推荐 props

```python
AdapterBlockPlan(
    component_id="ListPanel",
    props={
        "title_field": "title",
        "link_field": "link",
        "description_field": "summary",
        "pub_date_field": "published_at",
    },
    options={"show_description": True, "span": 12},
)
```

---

## 3. StatisticCard@v1 —— 指标卡片

### 3.1 Record 结构

```jsonc
{
  "id": "github-stars-total",
  "metric_title": "Stars",
  "metric_value": 1234,
  "metric_unit": null,
  "metric_delta_text": "+56 vs yesterday",
  "metric_delta_value": 56,
  "metric_trend": "up",
  "description": "Top project: octocat/hello-world"
}
```

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `id` | `str` | 唯一标识 |
| `metric_title` | `str` | 指标名称 |
| `metric_value` | `float` | 指标数值 |
| `metric_unit` | `Optional[str]` | 单位，如 `"次/天"`、`"%"` |
| `metric_delta_text` | `Optional[str]` | 人类可读的变化信息，例如 `"+5.6% vs last week"` |
| `metric_delta_value` | `Optional[float]` | 变化的原始数值 |
| `metric_trend` | `Optional[str]` | `"up" \| "down" \| "flat"` |
| `description` | `Optional[str]` | 补充说明 |

### 3.2 推荐 props

```python
AdapterBlockPlan(
    component_id="StatisticCard",
    props={
        "title_field": "metric_title",
        "value_field": "metric_value",
        "trend_field": "metric_trend",
    },
    options={"span": 6},
)
```

---

## 4. LineChart@v1 —— 折线图/面积图

### 4.1 Record 结构

```jsonc
{
  "id": "python-2024-01-01",
  "x": "2024-01-01",
  "y": 120.5,
  "series": "Python",
  "tooltip": "Python • 120.5"
}
```

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `id` | `str` | 唯一标识（建议使用 `series + x` 组合） |
| `x` | `str \| number` | 横轴值，时间建议使用 ISO8601 字符串 |
| `y` | `float` | 纵轴数值 |
| `series` | `Optional[str]` | 多序列名称，缺省视为单序列 |
| `tooltip` | `Optional[str]` | 自定义提示文本 |

### 4.2 推荐 props

```python
AdapterBlockPlan(
    component_id="LineChart",
    props={
        "x_field": "x",
        "y_field": "y",
        "series_field": "series",
    },
    options={"area_style": False, "span": 12},
)
```

---

## 5. FallbackRichText@v1 —— 兜底渲染

### 5.1 Record 结构

```jsonc
{
  "id": "fallback-rsshub",
  "title": "原始数据（调试用）",
  "content": "```json\n{... 原始 JSON ...}\n```"
}
```

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `id` | `str` | 唯一标识，推荐 `fallback-<route>` |
| `title` | `Optional[str]` | 兜底标题 |
| `content` | `str` | Markdown/HTML 文本 |

### 5.2 推荐 props

```python
AdapterBlockPlan(
    component_id="FallbackRichText",
    props={
        "title_field": "title",
        "description_field": "content",
    },
    options={"span": 12},
)
```

> 当无法结构化处理 payload 时，应返回 `FallbackRichText`，同时在 `stats` 中标记原因（如 `{"reason": "unsupported payload structure"}`）。

---

## 6. 验证与测试建议

1. 使用 `validate_records(component_id, records)` 进行 Pydantic 校验，出现 `ContractViolation` 视为适配器实现错误。  
2. 单元测试应覆盖：字段映射、`AdapterBlockPlan` props、stats、`requested_components` 下的行为等。  
3. 对多组件输出（如 List + LineChart），需分别调用 `validate_records` 保证两个契约同时成立。  
4. 若需要为前端生成样例，可将 Record 示例保存在 `tests/fixtures/panel/`，确保与本文件保持一致。

---

## 7. 变更流程

1. **提出需求**：明确新组件或字段的用途与展示方式。  
2. **更新本文档**：新增/修改条目，并说明版本号变化。  
3. **同步前端**：更新 `componentManifest.ts` 与 TypeScript 类型。  
4. **实现后端**：调整 `services/panel/view_models.py`、路由适配器及测试。  
5. **验证**：通过后端单测和前端 Storybook/Mock 校验。  
6. **发布**：在提交信息中说明契约变更点，便于后续追溯。

> 契约既是文档也是约束。请在编写适配器、组件、测试前先阅读本文件，确保面板渲染所见即所得。***
