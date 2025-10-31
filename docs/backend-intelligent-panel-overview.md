# 后端智能数据面板联调指南

面向前端同学梳理当前后端实现现状，帮助理解接口结构、字段语义与行为约束，降低联调中的踩坑风险。

---

## 1. 架构总览

```
用户请求
  → ChatController / ChatStream (FastAPI)
  → ChatService（意图识别 + 数据查询 + 面板组装）
        ├─ IntentService：规则结合关键词识别 data_query / chitchat
        ├─ DataQueryService：调用 RAGInAction + DataExecutor，返回 FeedItem 列表
        └─ PanelGenerator：将数据块生成 UIBlock & LayoutTree
              ├─ DataBlockBuilder：裁剪记录、生成 SchemaSummary
              ├─ ComponentSuggester：基于 Schema 推荐组件
              └─ LayoutEngine：生成布局节点（span / min_height / order 等）
  → REST / WebSocket 返回统一的 JSON 结构
```

### 关键模块
- **ComponentRegistry** (`services/panel/component_registry.py`)  
  描述与前端约定的组件能力表。每个组件包含必需字段、可选字段、默认布局（`span`/`min_height`）和交互能力。

- **ComponentSuggester** (`services/panel/component_suggester.py`)  
  根据 SchemaSummary 推断字段语义（title/link/value/时间等），匹配合适组件；若多个组件合规，使用普通规则先行排序，可扩展 LLM。

- **LayoutEngine** (`services/panel/layout_engine.py`)  
  根据每个 UIBlock 的 `layout_hint` 或默认配置，生成 LayoutTree 节点，包含 `span`、`min_height`、`order`、`priority` 等。

- **PanelGenerator** (`services/panel/panel_generator.py`)  
  组装 DataBlock → ViewDescriptor → UIBlock → LayoutTree。返回的 PanelPayload 与 DataBlocks 将直接给前端使用。

---

## 2. 接口返回结构

### REST `/api/v1/chat`
```jsonc
{
  "success": true,
  "message": "已获取「虎扑步行街」共20条（本地服务）",
  "data": {                      // PanelPayload
    "mode": "append",
    "layout": {
      "nodes": [
        {"type": "row", "id": "row-1", "children": ["block-list-1"], "props": {"span": 12, "min_height": 320}}
      ],
      "history_token": null
    },
    "blocks": [
      {
        "id": "block-list-1",
        "component": "ListPanel",
        "title": "虎扑步行街热帖",
        "data_ref": "data_block_hupu",
        "data": {
          "items": [...],        // 裁剪后的原始记录
          "schema": {
            "fields": [
              {"name": "title", "type": "string", "semantic": ["title"], "sample": ["示例标题"], "stats": null},
              {"name": "url", "type": "string", "semantic": ["url"], "sample": ["https://example.com"], "stats": null},
              {"name": "publishedAt", "type": "string", "semantic": ["datetime"], "sample": ["2024-01-01T10:00:00Z"], "stats": {"min": "2024-01-01T10:00:00+00:00", "max": "2024-01-03T09:00:00+00:00", "count": 3}}
            ],
            "stats": {"total": 20, "time_range": ["2024-01-01T10:00:00+00:00", "2024-01-03T09:00:00+00:00"]},
            "schema_digest": "List(publishedAt:string/title:string/url:string)"
          },
          "stats": {...}
        },
        "props": {"title_field": "title", "link_field": "link"},
        "options": {"show_description": true, "span": 12},
        "interactions": [{"type": "open_link", "label": "打开链接"}],
        "confidence": 0.92
      }
    ]
  },
  "data_blocks": {
    "data_block_hupu": {
      "id": "...",
      "source_info": {...},
      "records": [...],          // 最多20条
      "stats": {"total": 120, ...},
      "schema_summary": {...},
      "full_data_ref": null
    }
  },
  "metadata": {
    "intent_type": "data_query",
    "intent_confidence": 0.92,
    "generated_path": "/hupu/bbs/bxj",
    "source": "local",
    "cache_hit": "rss_cache",
    "feed_title": "虎扑步行街",
    "component_confidence": {"block-list-1": 0.92},
    "debug": {
      "blocks": [
        {
          "data_block_id": "data_block_hupu",
          "available_semantic": {"title": ["title"], "url": ["url"], "publishedAt": ["datetime"]},
          "descriptor_ids": ["data_block_hupu-view-1"]
        }
      ]
    }
  }
}
```

### WebSocket `/api/v1/chat/stream`
- 按 `intent → rag → fetch → summary → complete` 顺序推送 `stage`/`data` 消息。
- `summary` 阶段的 `data` 字段与 REST `data` 结构一致，同时包含 `data_blocks`。
- `fetch` 阶段附带 `items_count`, `block_count`, `cache_hit`, `source` 等指标。
- 所有流在结束时必然发送 `complete`（成功或失败）。

---

## 3. 组件推荐细节

- 字段语义由 SchemaSummary 的 `fields[].semantic` 提供，后端通过可扩展规则自动识别 `title`、`url`、`datetime`、`image`、`value` 等标签。
- 当前内置组件：
  | 组件 ID | 必需字段 | 可选 | 默认布局 | 交互 | 说明 |
  | ------- | -------- | ---- | -------- | ---- | ---- |
  | ListPanel | `title`, `link` | description/pubDate/author | span=12, min_height=320 | open_link | 文本列表 |
  | LineChart | `timestamp`, `value` | series/category | span=12, min_height=280 | filter/compare | 趋势图 |
  | StatisticCard | `title`, `value` | trend/unit | span=6, min_height=160 | - | 数字概览 |
  | FallbackRichText | `title` | description | span=12, min_height=200 | - | 兜底展示 |

- 推荐规则优先级：  
  1. 用户偏好（`user_preferences.preferred_component`）  
  2. 兼容性 + 简单打分（含 `pubDate` 列的 ListPanel → 0.9 等）  
  3. 若无匹配，使用 `FallbackRichText`。

---

## 4. 布局与数据对应关系

- `PanelPayload.blocks[*].data_ref` 指向 `data_blocks` 中的对应数据块；前端渲染时以 `data_ref` + `data.items` 渲染。
- `LayoutTree.nodes[*].children` 列出同一行或同容器内的 block id，`props` 中提供布局信息：
  - `span`：栅格宽度（示例实现以 12 列为满宽）
  - `min_height`：最小高度，用于设定卡片高度基础值
  - `order` / `priority`：当后续支持排序或插入时提供优先级
  - `responsive`：预留前端响应式配置
- 每个 UIBlock 的 `props` 提供组件必需字段映射（如 `title_field`），值来自 Schema 字段 `name`；`semantic` 标签用于校验/兜底，`options` 给出组件可配置项（如 `show_description`）。

---

## 5. Mock 与生产差异

- 环境变量 `CHAT_SERVICE_MODE` 控制运行模式：
  - `mock`：返回内置示例数据，组件/布局结构与真实模式一致，便于前端初期调试。
  - `auto`：优先真实链路，失败回退 mock。
  - `production`：仅真实链路，失败需要人工排查。
- Mock 数据结构遵守真实接口契约：提供 `data_blocks`、`layout.nodes`、`props/options` 等字段，方便前端无痛切换。
- 真实模式中，`component_confidence` 提示每个 block 的推荐置信度，前端可根据阈值给出提示或高亮。

---

## 6. 常见约束与注意事项

1. **数据裁剪**：`DataBlock.records` 默认最多 20 条，超出需前端自行分页/懒加载。
2. **SchemaSummary**：仅提供字段列表、样本值和统计摘要，不会透出全部原始数据。
3. **交互字段**：`UIBlock.interactions` 暂包含 `type` / `label` / `payload`，前端需透传 `payload` 回后端再触发二次查询。
4. **必备字段**：布局渲染依赖 `data.blocks[*].component`、`props`、`options`、`layout.nodes`；缺失任意字段会导致渲染失败，请在调试时校验完整性。
5. **错误处理**：无论 REST 还是 WebSocket，失败响应会在 `metadata` 或 `complete` 消息中携带 `success=false` 与 `reasoning`，前端需要显式提示。

---

## 7. 联调建议

- 初期联调可直接请求 `/api/v1/chat`，检查返回的 PanelPayload 与 DataBlocks；确认字段映射后，再接入 WebSocket 流式体验。
- 若需要固定结构，可设置 `CHAT_SERVICE_MODE=mock`，后端会返回稳定的示例数据。
- 将布局与组件渲染逻辑做成可扩展：尊重 `span`、`min_height`，并保留对 `component_id` 扩展的兼容性，以便后端新增组件时无需大规模改动。
- 对于 `interactions`，建议抽象统一事件分发机制，避免各组件重复处理。

---

如后续前端遇到字段含义不清、组件能力扩充等问题，请优先对照本指南与 `services/panel` 目录实现，再与后端协同确认。祝开发顺利！md
