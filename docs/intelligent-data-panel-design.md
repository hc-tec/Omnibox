# 智能数据面板后端设计方案

> 面向实现团队的完整设计文档。任何代码实现都必须对齐本文细节，禁止擅自增删字段或改变语义。

---

## 1. 核心背景

我们要构建一个 **智慧数据面板**：

- 用户通过自然语言查询，系统自动调用 RSSHub 获取多源数据。
- 返回给前端的不只是数据，还要包含“如何展示”的完整语义（组件类型、字段映射、布局建议、交互配置等）。
- 面板需要支持动态插入、替换、清空等行为，未来还要扩展交互组件（按钮、筛选、操作）。
- 必须提供可降级的 Mock 模式，保障开发体验；生产模式要严格依赖真实链路。

---

## 2. 需求全量清单

| 编号 | 需求描述 | 细节要求 |
| ---- | -------- | -------- |
| R1 | **多块展示** | 单次查询可拆解成多个数据块，每块可映射 1+ 组件。 |
| R2 | **动态布局** | 支持 append（顶部追加）、replace（清空后替换）、insert（指定位置插入，预留扩展）。 |
| R3 | **组件建议** | 必须返回 `component_id`、字段映射、配置、置信度、交互等信息，前端只负责渲染。 |
| R4 | **Schema 摘要** | 后端提取 SchemaSummary（字段→类型→样本→统计），禁止把全量数据直接塞给 LLM。 |
| R5 | **截断策略** | 列表取前/后样本 + 代表性记录；数值提供统计；时间序列均匀抽样。 |
| R6 | **配置优先级** | 用户偏好 > LLM/规则建议 > 默认配置。所有 props/options 必须显式返回。 |
| R7 | **交互描述** | `interactions` 字段描述按钮/筛选操作（type/label/payload）。 |
| R8 | **Mock/生产模式** | `CHAT_SERVICE_MODE` 控制（auto/mock/production），Mock 必须稳定返回示例数据。 |
| R9 | **接口一致性** | REST 与 WS 的数据模型必须一致，所有字段需要在文档中定义。 |
| R10 | **Complete 保证** | WebSocket 必须在任何情况下以 `complete` 消息结束（包含 success=false 的错误）。 |
| R11 | **布局树** | 返回 `LayoutTree`（Row/Column/Grid/Cell），支持 span/优先级/响应式标记。 |
| R12 | **数据引用** | 大数据放在 `data_blocks` 中，`UIBlock` 引用 `data_ref`；小数据可直接内嵌。 |
| R13 | **Schema 共享** | `SchemaSummary` 可复用，避免重复生成。 |
| R14 | **组件能力表** | 需要与前端约定标准 JSON（组件 ID、输入要求、默认配置、交互能力）；后端严格按此生成建议。 |
| R15 | **清空动作** | 支持用户指令“清空面板再生成新的”，需返回 `mode=replace` 并附上新布局。 |
| R16 | **多阶段查询** | pipeline 支持顺序依赖的子查询（例如先拉标题，再拉趋势）。 |
| R17 | **错误提示** | 任何失败都要返回人类可读的 `message/reason`。 |
| R18 | **服务模式曝光** | 健康检查与接口 metadata 必须返回当前 `service_mode`。 |
| R19 | **交互预留** | 数据块需能描述未来扩展的操作（如按钮触发的二次查询）。 |
| R20 | **性能约束** | LLM 输入需控制 token（默认 ≤ 1k tokens/块），支持自定义阈值。 |

---

## 3. 处理流程总览

```
用户查询
  ↓ IntentService（判断 data_query/chitchat/operation）
  ↓ Query Pipeline（拆解多个 SubQuery & 处理模式）
  ↓ RAG/规则定位 RSSHub 路由
  ↓ DataExecutor 并发获取数据 → DataBlocks
  ↓ Schema 摘要 + 样本抽样（控制 token）
  ↓ 组件建议引擎（规则 → LLM） → ViewDescriptors
  ↓ 布局引擎（考虑 mode、优先级、span 等）
  ↓ 输出 LayoutTree + UIBlocks + DataBlocks + Metadata
  ↓ REST / WebSocket 返回，前端渲染
```

---

## 4. 主要模块设计

### 4.1 IntentService & Query Pipeline
- IntentService 输出：
  ```jsonc
  {"intent": "data_query", "confidence": 0.83, "reasoning": "..."}
  ```
- Pipeline 将 Query 拆解为 `SubQuery`：
  ```jsonc
  {
    "mode": "append",                   // append / replace / insert
    "sub_queries": [
      {
        "id": "sq-1",
        "description": "获取虎扑热帖",
        "datasource": "hupu",
        "route_id": "hupu_bbs",
        "params": {"id": "bxj", "order": "hot"},
        "priority": 1
      },
      ...
    ]
  }
  ```
- 支持依赖关系；失败时需说明原因并继续其他块。

### 4.2 DataExecutor / DataBlock
- 并发拉取数据，遵守缓存/降级策略。
- DataBlock 结构：
  ```jsonc
  {
    "id": "data_block_hupu",
    "source_info": {
      "datasource": "hupu",
      "route": "/bbs/:id",
      "params": {"id": "bxj"},
      "fetched_at": "2025-10-31T10:00:00Z",
      "request_id": "req-123"
    },
    "records": [...],            // 精简列表，默认 ≤ 20 条
    "stats": {"total": 120, "range": ["2025-10-30", "2025-10-31"]},
    "schema_summary": {...},     // 详见下一节
    "full_data_ref": "data_store/hupu/bxj.json"
  }
  ```
- `records` 卡控大小，可支持 offset/limit。

### 4.3 Schema 摘要（SchemaSummary）
- 字段类型推断：标题、摘要、链接、时间戳、分类、数值、布尔、地理位置等。
- 样本策略：
  - 列表：前 3 + 随机 1 条。
  - 时间序列：按区间均匀取 5 个点。
  - 数值：min/max/avg/median/std。
- SchemaSummary 示例：
  ```jsonc
  {
    "fields": [
      {"name": "title", "type": "text", "sample": ["...", "..."]},
      {"name": "link", "type": "url", "sample": ["https://..."]},
      {"name": "pubDate", "type": "datetime", "sample": ["2025-10-31T09:00:00Z"]}
    ],
    "stats": {"total": 20, "time_range": ["2025-10-30", "2025-10-31"]},
    "schema_digest": "List(title/link/pubDate)"
  }
  ```
- LLM 输入仅可包含 SchemaSummary + 样本，不得传原始记录。

### 4.4 组件能力表（与前端共享）
- 参照以下结构定义：
  ```jsonc
  {
    "components": [
      {
        "id": "ListPanel",
        "requirements": ["title", "link"],
        "optional_fields": ["description", "pubDate", "author"],
        "options": {"show_description": {"type": "boolean", "default": true}},
        "interactions": ["open_link"],
        "layout_defaults": {"span": 12, "min_height": 320}
      },
      {
        "id": "LineChart",
        "requirements": ["timestamp", "value"],
        "optional_fields": ["series", "category"],
        "options": {"area_style": {"type": "boolean", "default": false}},
        "interactions": ["filter", "compare"],
        "layout_defaults": {"span": 12, "min_height": 280}
      }
    ]
  }
  ```
- 后端规则/LLM 必须只选择在能力表中存在的组件 ID；未匹配时返回默认 Fallback 组件。

### 4.5 组件建议引擎
- 输入：SchemaSummary、DataBlock stats、用户偏好、组件能力表。
- 流程：
  1. 规则匹配 → 得出候选组件。
  2. 候选冲突或不确定 → 调用 LLM（提示中包含 SchemaSummary + 能力表 + 用户偏好），要求 LLM 输出组件推荐 JSON。
  3. 生成 `ViewDescriptor`：
     ```jsonc
     {
       "id": "view-1",
       "component_id": "ListPanel",
       "confidence": 0.92,
       "data_ref": "data_block_hupu",
       "props": {"title_field": "title", "link_field": "link"},
       "options": {"show_description": true},
       "interactions": [{"type": "action", "label": "刷新", "payload": {...}}],
       "layout_hint": {"span": 12, "order": 1}
     }
     ```
- 一个 DataBlock 可拆出多个 ViewDescriptor，必须对总数设上限（默认 ≤ 4）。

### 4.6 布局引擎
- 结合 mode（append/replace/insert）和历史布局，生成 LayoutTree。
- 样例：
  ```jsonc
  {
    "mode": "append",
    "nodes": [
      {"type": "row", "id": "row-1", "children": ["block-list-1"]},
      {"type": "row", "id": "row-2", "children": ["block-chart-1"]}
    ],
    "history_token": "layout-uuid-123"
  }
  ```
- append 时：新块排在最上方，旧块以 `position="below"` 标记；replace 时旧块不返回。

### 4.7 输出结构（REST）

```jsonc
{
  "success": true,
  "message": "生成 2 个展示块",
  "data": {
    "mode": "append",
    "layout": {
      "nodes": [...],
      "history_token": "layout-uuid-123"
    },
    "blocks": [
      {
        "id": "block-list-1",
        "component": "ListPanel",
        "data_ref": "data_block_hupu",
        "data": {
          "items": [...],
          "schema": {...},
          "stats": {...}
        },
        "props": {...},
        "options": {...},
        "interactions": [...],
        "confidence": 0.92
      },
      ...
    ]
  },
  "data_blocks": {
    "data_block_hupu": {...},
    "data_block_hupu_trend": {...}
  },
  "metadata": {
    "intent": "data_query",
    "service_mode": "auto",
    "source": "local",
    "cache_hit": "rss_cache",
    "component_confidence": {
      "block-list-1": 0.92,
      "block-chart-1": 0.78
    },
    "debug": {...}    // 可选：耗时、降级信息
  }
}
```

### 4.8 WebSocket 消息序列

1. `stage` intent
2. `data` intent_result
3. `stage` rag （仅 data_query）
4. `data` rag_status
5. `stage` fetch
6. `data` fetch_summary
7. `stage` summary
8. `data` final_layout
9. `complete`

**错误或校验失败**：
```jsonc
{"type": "error", "error_code": "VALIDATION_ERROR", ...}
{"type": "complete", "success": false, "message": "..."}
```

---

## 5. 模式控制

- `CHAT_SERVICE_MODE`：
  - `auto`：首选真实服务，失败自动回退 Mock。
  - `mock`：始终使用 Mock（开发/CI）。
  - `production`：禁止回退，失败需要人工排查。
- 健康检查 `/api/v1/health` 必须返回：
  ```jsonc
  {
    "status": "healthy",
    "version": "1.0.0",
    "mode": "mock",
    "services": {
      "chat_service": "mock",
      "rsshub": "mock",
      "rag": "mock",
      "cache": "mock"
    }
  }
  ```

---

## 6. Schema & 接口定义摘要

| 名称 | 结构要点 |
| ---- | -------- |
| DataBlock | `id`, `source_info`, `records`, `stats`, `schema_summary`, `full_data_ref` |
| SchemaSummary | `fields`（name/type/sample）、`stats`、`schema_digest` |
| ViewDescriptor | `component_id`, `data_ref`, `props`, `options`, `interactions`, `confidence`, `layout_hint` |
| UIBlock | `id`, `component`, `data`（嵌小数据）+ `data_ref`, `props`, `options`, `interactions`, `confidence` |
| LayoutTree | `mode`, `nodes`, `history_token` |
| WebSocketMessage | `type`（stage/data/error/complete）、`stream_id`, 具体字段 |

All structures 必须定义成 Pydantic Model 并复用。

---

## 7. 测试策略

1. **单元测试**
   - SchemaSummary 推断、样本截断、统计值计算。
   - 组件规则匹配/LLM fallback。
   - 布局合成逻辑。
2. **集成测试**
   - REST `/api/v1/chat`（`CHAT_SERVICE_MODE=mock`）。
   - WebSocket `/api/v1/chat/stream`（验证完整消息序列）。
3. **性能测试**
   - Schema 注入 token 控制。
   - 多子查询并发、降级策略。
4. **回归测试**
   - Mock → production 模式切换。
   - 清空后生成、组件组合、错误路径。

---

## 8. 前后端协作要点

1. 前端提供组件能力表与数据驱动规范；后端严格对齐。
2. `UIBlock`、`LayoutTree`、`DataBlock`、`SchemaSummary` 需要固化 JSON Schema。
3. 前端实现布局栈管理（append/replace/insert）、历史记录、交互事件。
4. Mock 数据和真实数据字段必须一致（组件、props、options、interactions 全部定义）。

---

## 9.  后续扩展

- 记忆用户偏好（组件位置、主题、排序）并反馈给建议引擎。
- 提供 diff/patch 更新，避免每次整体刷新面板。
- 操作类组件（Button/Action）与后端流程联动。
- 更细粒度的 LLM 反馈体系（组件效果收集 → Prompt 优化）。

---

## 10. 附录：示例响应

```jsonc
{
  "success": true,
  "message": "生成 2 个展示块（append）",
  "data": {
    "mode": "append",
    "layout": {
      "nodes": [
        {"type": "row", "id": "row-top", "children": ["block-list-1"]},
        {"type": "row", "id": "row-bottom", "children": ["block-chart-1"]}
      ],
      "history_token": "layout-uuid-123"
    },
    "blocks": [
      {
        "id": "block-list-1",
        "component": "ListPanel",
        "title": "虎扑步行街热帖",
        "data_ref": "data_block_hupu",
        "data": {
          "items": [
            {"title": "步行街话题 A", "link": "https://...", "description": "...", "pubDate": "..."},
            {"title": "步行街话题 B", "link": "https://...", "description": "...", "pubDate": "..."}
          ],
          "schema": {...},
          "stats": {"total": 20}
        },
        "props": {"title_field": "title", "link_field": "link", "description_field": "description"},
        "options": {"show_description": true},
        "interactions": [
          {"type": "action", "label": "刷新", "payload": {"query": "刷新虎扑"}}
        ],
        "confidence": 0.92
      },
      {
        "id": "block-chart-1",
        "component": "LineChart",
        "title": "热度趋势",
        "data_ref": "data_block_hupu_trend",
        "data": {
          "items": [
            {"timestamp": "2025-10-30", "value": 120},
            {"timestamp": "2025-10-31", "value": 135}
          ],
          "schema": {...},
          "stats": {"min": 100, "max": 150}
        },
        "props": {"x_field": "timestamp", "y_field": "value"},
        "options": {"area_style": true},
        "confidence": 0.78
      }
    ]
  },
  "data_blocks": {
    "data_block_hupu": {...},
    "data_block_hupu_trend": {...}
  },
  "metadata": {
    "intent": "data_query",
    "source": "local",
    "cache_hit": "rss_cache",
    "service_mode": "production",
    "component_confidence": {
      "block-list-1": 0.92,
      "block-chart-1": 0.78
    }
  }
}
```
*** End Patch
