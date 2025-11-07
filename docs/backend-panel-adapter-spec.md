# 后端面板路由适配器开发规范

> 目标：构建“契约优先”的数据面板后端链路。DataExecutor 负责返回 RSSHub 原始 JSON，路由适配器根据前端组件契约进行显式映射，Planner 根据 Manifest 先决策需要的组件，再按需生成数据，做到所见即所得且避免无用计算。

---

## 1. DataExecutor 输出约定

`integration.data_executor.DataExecutor.fetch_rss(path)` 返回 `FetchResult`：

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `status` | `"success" \| "error"` | 请求是否成功 |
| `items` | `List[Dict[str, Any]]` | 默认值为 `[payload]`，保留给历史消费者 |
| `payload` | `Dict[str, Any]` | RSSHub 原始 JSON；若响应非对象，则包装为 `{"value": ...}` |
| `feed_title` / `feed_link` / `feed_description` | `Optional[str]` | 直接透传 RSSHub 元数据 |
| `source` | `"local" \| "fallback"` | 使用的 RSSHub 基础地址 |
| `fetched_at` | `str` | ISO8601 时间戳 |
| `error_message` | `Optional[str]` | 失败时的错误说明 |

缓存层会持久化完整的 `FetchResult`，命中缓存时不会丢失任何字段。

---

## 2. 面板生成流水线

```
DataExecutor
   │
   ▼
DataQueryService  ──► PanelGenerator
                       │
                       ├─ DataBlockBuilder（路由适配器 + SchemaSummary）
                       └─ LayoutEngine / Component Planner
```

1. Chat/RAG 阶段先确定候选接口，并根据 Manifest + 用户意图选择要渲染的组件集合（`requested_components`）。  
2. 选定路由后构造 `PanelBlockInput(records=[payload])`，并附带 `requested_components`。  
3. `DataBlockBuilder` 根据路由查找适配器，传入 `AdapterExecutionContext`（含所需组件）后获取 `RouteAdapterResult`。  
4. `PanelGenerator` 将 `AdapterBlockPlan` 转换为前端 `UIBlock`，同时在未请求任何组件时跳过构建，避免回退到兜底渲染。

---

## 3. 路由适配器契约

### 3.1 注册与 Manifest

```python
from services.panel.adapters import (
    route_adapter,
    AdapterExecutionContext,
    RouteAdapterResult,
    RouteAdapterManifest,
    ComponentManifestEntry,
)

FOLLOWINGS_MANIFEST = RouteAdapterManifest(
    components=[
        ComponentManifestEntry(
            component_id="ListPanel",
            description="展示关注列表",
            cost="low",
            required=True,
            hints={"metrics": ["follower_count"]},
        ),
        ComponentManifestEntry(
            component_id="StatisticCard",
            description="关注总量卡片",
            cost="medium",
            default_selected=False,
        ),
    ],
    notes="基于 /bilibili/user/followings/:uid/:loginUid",
)

@route_adapter("/bilibili/user/followings", manifest=FOLLOWINGS_MANIFEST)
def bilibili_followings_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    ...
```

- **Manifest（路由能力描述）**：列出适配器可产出的组件、成本、默认是否启用、依赖提示等，供 Planner 快速评估。  
- `route_adapter` 支持注册多个前缀，内部会按最长前缀匹配；同一路由可多次注册以覆盖旧实现。  
- 适配器代码必须按数据域拆分，例如 `services/panel/adapters/bilibili/`、`.../github.py`，便于维护。

### 3.2 AdapterExecutionContext

`AdapterExecutionContext` 由 `DataBlockBuilder` 传入，当前包含：

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `requested_components` | `Optional[Sequence[str]]` | Planner 选择的组件列表；`None` 表示默认全部生成 |

适配器需使用 `context.wants(component_id)` 判断是否需要生成某一组件，避免无效计算。当列表为空时不得回退到兜底渲染。

### 3.3 RouteAdapterResult

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `records` | `List[Dict[str, Any]]` | 组件可直接使用的记录；对于多组件场景推荐共享同一份结构化数据 |
| `block_plans` | `List[AdapterBlockPlan]` | 组件规划列表，可为空（表示本次不渲染任何组件） |
| `stats` | `Dict[str, Any]` | 额外统计信息，将合并进 `DataBlock.stats` |

### 3.4 AdapterBlockPlan

| 字段 | 必填 | 说明 |
| ---- | ---- | ---- |
| `component_id` | ✅ | 前端组件 ID |
| `props` | ✅ | 组件属性与记录字段映射 |
| `options` | ❌ | 行为配置（如 `span`、`area_style` 等） |
| `interactions` | ❌ | 交互动作列表 (`ComponentInteraction`) |
| `title` | ❌ | Block 标题，缺省时前端回落到路由或数据源名称 |
| `layout_hint` | ❌ | `LayoutHint(span, min_height, priority…)` |
| `confidence` | ❌ | 推荐置信度，默认 0.6 |

`stats` 必须包含 `api_endpoint`，以便前端溯源；根据需要追加特定指标，如 `follower_count`、`top_language` 等。

---

## 4. 组件视图模型（@v1）

适配器输出必须符合 `services/panel/view_models.py` 中的 Pydantic 模型，核心组件如下：

| 组件 | 关键字段 | 说明 |
| ---- | ---- | ---- |
| `ListPanel` | `id`, `title`, `link`, `summary`, `published_at`, `author`, `categories` | 用于文章/帖子列表 |
| `StatisticCard` | `metric_title`, `metric_value`, `metric_trend`, `metric_delta_text` | 指标卡片，可附带趋势信息 |
| `LineChart` | `x`, `y`, `series`, `tooltip` | 折线/面积图所需数据 |
| `FallbackRichText` | `title`, `content` | 兜底渲染，内容可为 Markdown/HTML |

详细字段说明与样例见 `docs/backend-panel-view-models.md`。若引入新组件必须先更新该文档，再调整代码。

---

## 5. Manifest + Planner 工作流

1. **读取 Manifest**：Planner 通过 `services.panel.adapters.get_route_manifest(route)` 获取路由能力列表与成本信息。  
2. **选择组件集合**：结合用户指令、布局限制、默认策略（如“每次最多展示 2 个组件”），输出 `requested_components`。  
3. **按需生成**：`PanelGenerator` 将 `requested_components` 注入 `AdapterExecutionContext`，适配器只生成被请求的组件；若结果为空且存在请求，则不会回退到兜底组件。  
4. **统计透出**：即使某组件被跳过，也应在 `stats` 中保留关键指标，便于后续计算或提示。  
5. **前端渲染**：UI 层仅渲染返回的 `AdapterBlockPlan`，无需额外判断哪些组件可用。  
6. **Planner 实现**：默认提供 `services.panel.component_planner.plan_components_for_route`，支持 `ComponentPlannerConfig(max_components=2, preferred_components=(), allow_optional=True)` 以及运行时 `PlannerContext(item_count, available_metrics, user_preferences)`。例如，当 item 数 <3 时自动跳过 `LineChart`，若组件 `hints.metrics` 与 `available_metrics` 不相交则不推荐对应指标卡片。可在 `ChatService` 构造器传入自定义配置。

---

## 6. 开发流程（最佳实践）

1. **确认契约**：审阅/更新 `backend-panel-view-models.md` 与前端 `componentManifest.ts`，明确所需字段。  
2. **设计 Manifest**：为新路由起草 `RouteAdapterManifest`，标注组件、成本、备注。  
3. **实现适配器**：根据 `AdapterExecutionContext` 判断是否生成每个组件；避免创建过度抽象的“万能解析器”。  
4. **补充统计**：在 `stats` 中写明 `api_endpoint` 以及业务关注的聚合指标。  
5. **撰写文档**：在 `docs/adapters/overview.md` 填写路由说明、字段映射、组件组合。  
6. **完善测试**：在 `tests/services/test_panel_adapters.py` 添加样例数据，覆盖 manifest 注册、`requested_components` 选择、stats 等逻辑。  
7. **前端同步**：新增字段或组件时及时通知前端，并更新 TypeScript 契约（`frontend/src/shared/types/panelContracts.ts`）。  
8. **验证**：运行 `python -m pytest tests/services/test_panel_adapters.py` 等相关测试，确保契约未被破坏。

---

## 7. 版本管理与兼容策略

- 任何不兼容变更（字段重命名、结构调整）必须升级组件版本号（如 `StatisticCard@v2`），并保留旧版处理。  
- Manifest 与契约文档需同步更新，提交说明中明确变更原因。  
- 建议在 CI 中加入 JSON Schema diff 或契约校验，阻止未审查的字段漂移。  
- 对于临时关闭的组件（Planner 不再请求），适配器应保持稳定输出，不影响已有功能。

---

## 8. 参考资源

- `services/panel/view_models.py`：Pydantic 视图模型与契约校验函数。  
- `services/panel/adapters/registry.py`：路由适配器注册、Manifest、执行上下文等基础设施。  
- `services/panel/adapters/*`：示例适配器与 Manifest。  
- `services/panel/data_block_builder.py`：`AdapterExecutionContext` 的使用方式。  
- `tests/services/test_panel_adapters.py`：针对适配器的单元测试与选择性渲染示例。  
- `frontend/src/shared/types/panelContracts.ts`：前端对组件数据结构的 TypeScript 定义。

> 完整遵守上述规范，即可在确保性能和契约一致性的前提下，逐步扩展智能面板的路由适配器矩阵。只要 Manifest 与测试同步更新，Planner 就能在生成阶段精准选择所需组件，避免“算了但不展示”的浪费。***
