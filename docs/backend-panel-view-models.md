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

## 5. BarChart@v1 —— 柱状图

### 5.1 Record 结构

```jsonc
{
  "id": "python-stars",
  "x": "Python",
  "y": 1234,
  "series": null,
  "color": "#3776ab",
  "tooltip": "Python: 1,234 stars"
}
```

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `id` | `str` | 唯一标识，建议使用 `series + x` 组合 |
| `x` | `str` | 横轴类目（如语言名称、用户名、标题） |
| `y` | `float` | 纵轴数值（如 Star 数、热度、回复数） |
| `series` | `Optional[str]` | 多序列分组名称，缺省视为单序列 |
| `color` | `Optional[str]` | 自定义柱子颜色（十六进制，如 `"#3776ab"`） |
| `tooltip` | `Optional[str]` | 自定义提示文本 |

### 5.2 推荐 props

```python
AdapterBlockPlan(
    component_id="BarChart",
    props={
        "x_field": "x",
        "y_field": "y",
        "series_field": "series",
    },
    options={
        "horizontal": False,  # False=垂直柱状图，True=横向柱状图
        "stacked": False,  # 是否堆叠
        "show_values": True,  # 是否在柱子上显示数值
        "span": 12,
    },
)
```

### 5.3 典型应用场景

- **排行榜**：GitHub Trending 按 Star 数排行、B 站热搜按热度排行
- **对比数据**：不同语言的项目数量、不同分类的内容数量
- **统计数据**：每日新增、每月汇总等

### 5.4 与 LineChart 的区别

| 维度 | BarChart | LineChart |
|------|----------|-----------|
| X 轴类型 | 离散类目（字符串） | 连续数值或时间 |
| 典型场景 | 对比、排行 | 趋势、变化 |
| 数据顺序 | 通常按 Y 值排序 | 通常按 X 值排序 |

---

## 6. Table@v1 —— 表格

### 6.1 数据结构

Table 组件采用 `TableViewModel` 结构，包含列定义（columns）和行数据（rows）。

```jsonc
{
  "columns": [
    {
      "key": "name",
      "label": "项目名称",
      "type": "text",
      "sortable": true,
      "align": "left",
      "width": 0.3
    },
    {
      "key": "stars",
      "label": "Stars",
      "type": "number",
      "sortable": true,
      "align": "right",
      "width": 0.2
    },
    {
      "key": "language",
      "label": "语言",
      "type": "tag",
      "sortable": false,
      "align": "center",
      "width": 0.2
    },
    {
      "key": "updated_at",
      "label": "更新时间",
      "type": "date",
      "sortable": true,
      "align": "left",
      "width": 0.3
    }
  ],
  "rows": [
    {
      "name": "octocat/hello-world",
      "stars": 12345,
      "language": "Python",
      "updated_at": "2024-01-15T10:30:00Z"
    },
    {
      "name": "user/awesome-project",
      "stars": 9876,
      "language": "JavaScript",
      "updated_at": "2024-01-14T08:20:00Z"
    }
  ]
}
```

### 6.2 TableColumn 字段说明

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `key` | `str` | 列对应的字段名（必填） |
| `label` | `str` | 列标题（必填） |
| `type` | `Optional[str]` | 列类型：`"text" \| "number" \| "date" \| "currency" \| "tag"` |
| `sortable` | `bool` | 是否可排序（默认 `false`） |
| `align` | `Optional[str]` | 对齐方式：`"left" \| "center" \| "right"` |
| `width` | `Optional[float]` | 相对宽度，0.0 ~ 1.0 之间的值 |

### 6.3 TableViewModel 字段说明

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `columns` | `List[TableColumn]` | 列定义列表（必填） |
| `rows` | `List[Dict[str, Any]]` | 行数据列表（必填） |

### 6.4 适配器返回格式

由于 Table 的数据结构特殊，适配器返回时需要将 `TableViewModel` 包装在 `records` 列表中：

```python
from services.panel.view_models import TableViewModel, TableColumn

table_model = TableViewModel(
    columns=[
        TableColumn(key="name", label="项目名称", type="text", sortable=True, align="left", width=0.4),
        TableColumn(key="stars", label="Stars", type="number", sortable=True, align="right", width=0.2),
        TableColumn(key="language", label="语言", type="tag", align="center", width=0.2),
        TableColumn(key="updated_at", label="更新时间", type="date", sortable=True, width=0.2),
    ],
    rows=[
        {"name": "octocat/hello-world", "stars": 12345, "language": "Python", "updated_at": "2024-01-15T10:30:00Z"},
        {"name": "user/awesome", "stars": 9876, "language": "JavaScript", "updated_at": "2024-01-14T08:20:00Z"},
    ]
)

# 验证并返回
validated = validate_records("Table", [table_model.model_dump()])

return RouteAdapterResult(
    records=validated,
    block_plans=[
        AdapterBlockPlan(
            component_id="Table",
            props={},  # Table 不需要字段映射，数据自包含
            options={"span": 12},
        )
    ],
    stats={"total_rows": len(table_model.rows)},
)
```

### 6.5 推荐 props

```python
AdapterBlockPlan(
    component_id="Table",
    props={},  # Table 组件不需要字段映射，列定义已在 columns 中
    options={
        "span": 12,
        "pagination": True,  # 是否启用分页（可选）
        "page_size": 20,  # 每页行数（可选）
    },
)
```

### 6.6 典型应用场景

- **GitHub Issues / Pull Requests**：展示标题、状态、作者、时间等多维度信息
- **股票行情数据**：展示代码、名称、价格、涨跌幅等
- **配置表/参数列表**：展示多字段结构化配置
- **对比数据**：对比多个项目/产品的详细参数

### 6.7 与 ListPanel 的区别

| 维度 | Table | ListPanel |
|------|-------|-----------|
| 数据结构 | 多列结构化数据 | 单一条目列表 |
| 展示形式 | 表格形式，列对齐 | 卡片/列表形式 |
| 典型场景 | 对比、详细参数展示 | 文章、帖子、视频列表 |
| 字段数量 | 通常 3-8 列 | 通常 2-4 个主要字段 |

---

## 7. PieChart@v1 —— 饼图

### 7.1 Record 结构

```jsonc
{
  "id": "python-projects",
  "name": "Python",
  "value": 1234,
  "color": "#3776ab",
  "tooltip": "Python: 1,234 projects (34.5%)"
}
```

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `id` | `str` | 唯一标识 |
| `name` | `str` | 分类名称（必填） |
| `value` | `float` | 数值（必填） |
| `color` | `Optional[str]` | 自定义扇区颜色（十六进制，如 `"#3776ab"`） |
| `tooltip` | `Optional[str]` | 自定义提示文本 |

### 7.2 推荐 props

```python
AdapterBlockPlan(
    component_id="PieChart",
    props={
        "name_field": "name",
        "value_field": "value",
    },
    options={
        "donut": False,  # False=饼图，True=环形图
        "show_legend": True,  # 是否显示图例
        "show_label": True,  # 是否显示标签
        "span": 12,
    },
)
```

### 7.3 典型应用场景

- **占比分析**：各编程语言项目占比、流量来源占比、用户地域分布
- **分类统计**：各分类文章数量、各标签使用频率
- **比例关系**：收入构成、时间分配、资源使用情况

### 7.4 与 BarChart 的区别

| 维度 | PieChart | BarChart |
|------|----------|----------|
| 展示重点 | 占比关系 | 数值对比 |
| 适用数据 | 总和为整体的部分数据 | 独立的类目数据 |
| 数据量 | 建议 2-8 个分类 | 可展示更多类目 |
| 典型问题 | "各部分占多少比例？" | "哪个类目数值最大？" |

---

## 8. ImageGallery@v1 —— 图片画廊

### 8.1 Record 结构

```jsonc
{
  "id": "image-1",
  "image_url": "https://example.com/image.jpg",
  "title": "图片标题",
  "description": "图片描述文本",
  "link": "https://example.com/detail",
  "thumbnail_url": "https://example.com/thumb.jpg"
}
```

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `id` | `str` | 唯一标识 |
| `image_url` | `str` | 图片完整 URL（必填） |
| `title` | `Optional[str]` | 图片标题 |
| `description` | `Optional[str]` | 图片描述 |
| `link` | `Optional[str]` | 点击跳转链接 |
| `thumbnail_url` | `Optional[str]` | 缩略图 URL（用于性能优化） |

### 8.2 推荐 props

```python
AdapterBlockPlan(
    component_id="ImageGallery",
    props={
        "image_field": "image_url",
        "title_field": "title",
        "link_field": "link",
    },
    options={
        "columns": 3,  # 网格列数 (2-4)
        "aspect_ratio": "16/9",  # 图片宽高比
        "show_title": True,  # 是否显示标题
        "span": 12,
    },
)
```

### 8.3 典型应用场景

- **视频封面**：B站视频、YouTube 视频列表
- **图集相册**：摄影作品、产品图集
- **商品展示**：电商商品图片、商品缩略图
- **截图展示**：应用截图、设计作品

### 8.4 与 ListPanel 的区别

| 维度 | ImageGallery | ListPanel |
|------|-------------|-----------|
| 展示重点 | 图片视觉 | 文字信息 |
| 布局方式 | 网格布局 | 列表布局 |
| 典型场景 | 视频、相册、商品 | 文章、帖子、动态 |
| 信息密度 | 低（突出视觉） | 高（突出文字） |

---

## 9. FallbackRichText@v1 —— 兜底渲染

### 9.1 Record 结构

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

### 9.2 推荐 props

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

## 10. 验证与测试建议

1. 使用 `validate_records(component_id, records)` 进行 Pydantic 校验，出现 `ContractViolation` 视为适配器实现错误。  
2. 单元测试应覆盖：字段映射、`AdapterBlockPlan` props、stats、`requested_components` 下的行为等。  
3. 对多组件输出（如 List + LineChart），需分别调用 `validate_records` 保证两个契约同时成立。  
4. 若需要为前端生成样例，可将 Record 示例保存在 `tests/fixtures/panel/`，确保与本文件保持一致。

---

## 11. 变更流程

1. **提出需求**：明确新组件或字段的用途与展示方式。  
2. **更新本文档**：新增/修改条目，并说明版本号变化。  
3. **同步前端**：更新 `componentManifest.ts` 与 TypeScript 类型。  
4. **实现后端**：调整 `services/panel/view_models.py`、路由适配器及测试。  
5. **验证**：通过后端单测和前端 Storybook/Mock 校验。  
6. **发布**：在提交信息中说明契约变更点，便于后续追溯。

> 契约既是文档也是约束。请在编写适配器、组件、测试前先阅读本文件，确保面板渲染所见即所得。***

## 附录：Stats / Metrics

- 后端适配器在 `stats` 中附带 `metrics` 字典，键使用 `snake_case`，例如 `follower_count`、`total_stars`；Planner 与前端根据这些指标决定是否展示 `StatisticCard` 等组件。
- `sample_titles` 便于调试，前端亦可用于兜底展示。

