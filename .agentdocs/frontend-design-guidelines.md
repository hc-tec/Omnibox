# 前端界面设计规范（当前版本）

> 适用范围：Electron + Vue 前端（`frontend/`），所有新 UI 需遵循本规范。  
> 目的：避免 AI / 开发者在实现界面时反复出现“阴影过重、忘记用 shadcn、列表过大”等问题。

---

## 1. 应用壳层与布局

1. **App Shell**：只有顶部拖拽条与底部命令胶囊，禁止再添加额外的边框/菜单栏。  
   - 背景使用 `var(--shell-surface)` 的浅玻璃效果 + 渐变光斑。  
   - 所有拖拽区域通过 `.drag-region`/`.no-drag` 控制，不得影响交互控件。
2. **Command Palette**：必须使用 `shadcn` Button/Card 样式。  
   - 默认状态为透明小胶囊，`focus/hover` 才展开（仍在原位），不可弹窗/遮挡画布。  
   - 交互事件：`CMD/CTRL + Space`，`CMD/CTRL + K`。
3. **画布 & Layout**：`PanelBoard` 采用 12 列 CSS Grid (`grid-auto-flow: dense`)，不再使用 `vue-grid-layout`。  
   - 组件高度由内容决定，若需要滚动，在组件内部设置 `max-h` + `overflow-auto`。  
   - 默认列宽由 `COMPONENT_SPAN_PRESET` 控制（List=5、MediaCard=6、StatCard=3...），后端仍可在 `layout.nodes[].props.grid.w` 覆盖。

## 2. 组件风格（全局）

1. **统一使用 shadcn Card / Badge / Button 等组件**。  
   - Tailwind 的 `bg-[var(--shell-surface)]/xx` + `border-border/xx` 组合构建玻璃效果。  
   - 阴影只能使用轻量级（`0 4px 12px rgba(8,12,20,0.12)`），Hover 时最多 `0 10px 22px`。
2. **标题与标签**：优先显示后端 `block.title`，否则用中文友好名（“洞察列表”“趋势图”等）。  
   - 绝不展示 `ListPanel` 这类内部组件名。
3. **列表默认尺寸**：  
   - 外层 `max-h` 260/380px + `overflow-auto`（统一 `list-scroll` 样式）。  
   - 默认只展示 6~8 项，可通过 options 控制。
4. **媒体类信息**：若数据含封面/播放量/时长，必须转换成卡片展示，而不是纯文字列表。

## 3. 新增组件：MediaCardGrid

1. **用途**：用于 B 站投稿、小红书笔记等带封面卡片。可嵌套在 ListPanel 旁或独立展示。  
2. **API**（见 `frontend/src/features/panel/components/blocks/MediaCardGridBlock.vue` 与 `services/panel/view_models.py`）：  
   - props：`title_field/link_field/cover_field/author_field/summary_field/duration_field/view_count_field/like_count_field/badges_field`。  
   - options：`columns`（1~4）、`max_items`、`span`、`compact`。  
   - 数据契约必需 `id/title/cover_url`，可选播放量、点赞、徽章等。
3. **前端实现**：  
   - 结构：Tailwind Grid + shadcn Card，封面区域 `aspect-video`，支持 hover 缩放。  
   - 统计信息采用辅助函数 `_parse_count/_format_duration`（后端已提供）。
4. **后端适配（Bilibili）**：  
   - `services/panel/adapters/bilibili/user_video.py` 默认输出 `MediaCardGrid + ListPanel`，并保留统计卡片/封面画廊。  
   - 所有 video record 写入统一字段（`cover_url/view_count/duration/badges`），`validate_records("MediaCardGrid"... )` 保障契约。

## 4. 阴影 / 背景使用指南

| 场景           | 背景/边框                                             | 阴影                           |
|----------------|--------------------------------------------------------|--------------------------------|
| 画布卡片       | `bg-[var(--shell-surface)]/30` + `border-border/55`    | `shadow-[0_6px_16px_rgba(6,12,24,0.12)]` |
| Hover          | `border-border`                                        | `shadow-[0_10px_22px_rgba(6,12,24,0.18)]` |
| 内嵌卡片（列表/媒体） | 同上，但 `rounded-2xl`，可用 `bg-background/60` 淡背景 | 仅在 Hover 时加小阴影           |
| 禁止样式       | 大面积纯白 #fff、`box-shadow: 0 35px 80px` 等重阴影    |                                  |

## 5. 数据契约 & 适配器约束

1. 所有适配器必须通过 `validate_records(component_id, records)` 进行契约校验，否则视为违反规范。  
2. 若使用 `MediaCardGrid`，必须在 manifest 中声明，并提供 `media_card_size_preset` / `ComponentManifest` / `component_registry` / `view_models` 等全部配置。  
3. 输出的 block plan 默认要给出合理 `layout_hint.span`，否则前端会退回 compact 预设，导致宽度不符合期望。

## 6. 代码组织要求

1. 新组件一律放在 `frontend/src/features/panel/components/blocks/`，使用 shadcn 组合 + Tailwind。  
2. `PanelBoard` 是唯一布局入口，禁止在组件内部使用 `position: absolute`/`vh` 抢占高度；需要滚动必须在组件内部实现。  
3. 所有新样式都写成 Tailwind 工具类或少量 CSS 变量，不得写大段自定义盒阴影。  
4. Backend 适配器更新时，必须同步更新 `.agentdocs` 的规范文档。

---

> 若未来再增加类似“小红书笔记卡片”“微博热词卡片”等，请复用 `MediaCardGrid` 的数据契约与 UI 结构，只需在后端填充对应字段即可。  
> 以上规范已在 2025/11/11 版本中落地，后续 PR 若不符合上述要求，需先更新 `.agentdocs`。 
