# 智能数据面板前端设计方案

> 面向 Electron + Shadcn UI 的实现指南。任何 UI 开发均应对齐本文细节，确保与后端协议无缝衔接。

---

## 1. 技术栈与结构约束

| 层级 | 技术/库                    | 说明 |
| ---- |-------------------------| ---- |
| Shell | Electron 27+            | 主进程/渲染进程分离，支持多窗口；需启用 contextIsolation。|
| UI Framework | Vue3 + TypeScript       | 使用函数式组件、Hooks；严格类型定义。|
| UI 组件库 | Shadcn UI               | 通过 `shadcn/ui` 生成组件；禁止修改核心实现，所有定制写在扩展层。|
| 状态管理 | Zustand 或 Redux Toolkit | 统一管理布局栈、数据引用、用户偏好。|
| 网络/协议 | Axios/Fetch + WebSocket | REST `/api/v1/chat` 与 WS `/api/v1/chat/stream`；需统一封装。|
| 数据层缓存 | IndexedDB/LocalStorage  | 缓存 `data_blocks`、用户偏好、历史布局。|

> 目录建议（可按实际项目调整）：
>
> ```
> src/
> ├─ main/            # Electron 主进程
> ├─ preload/         # 预加载脚本（安全桥）
> ├─ renderer/
> │  ├─ app/          # App Shell
> │  ├─ components/   # 自定义组件，与 Shadcn 原子组件组合
> │  ├─ features/     # 面板、布局、数据服务
> │  ├─ lib/
> │  ├─ store/
> │  ├─ utils/
> │  └─ styles/
> └─ shared/          # 通用类型、协议定义（同步后端）
> ```

---

## 2. 组件能力表（前端实现须与后端共享）

前端需维护 `components.json`（或 TypeScript 模块），供后端和本地组件解析。示例：

```jsonc
{
  "components": [
    {
      "id": "ListPanel",
      "tag": "list",
      "props": {
        "titleField": { "type": "string", "required": true },
        "linkField": { "type": "string", "required": true },
        "descriptionField": { "type": "string", "required": false }
      },
      "options": {
        "showDescription": { "type": "boolean", "default": true },
        "maxItems": { "type": "number", "default": 20 }
      },
      "interactions": ["open_link", "refresh"],
      "layoutDefaults": { "span": 12, "minHeight": 320 },
      "categories": ["list", "text"]
    },
    {
      "id": "LineChart",
      "tag": "chart",
      "props": {
        "xField": { "type": "string", "required": true },
        "yField": { "type": "string", "required": true },
        "seriesField": { "type": "string", "required": false }
      },
      "options": {
        "areaStyle": { "type": "boolean", "default": false },
        "smooth": { "type": "boolean", "default": false }
      },
      "interactions": ["filter", "compare"],
      "layoutDefaults": { "span": 12, "minHeight": 300 },
      "categories": ["chart", "numeric"]
    }
  ]
}
```

**要求：**
- 所有组件实现必须读取能力表，校验后端传入的 `props/options` 是否满足定义。
- 能力表更新时需同步给后端（或后端通过接口动态获取）。
- 若后端返回未知组件 ID，需要提供 fallback 渲染（展示错误占位）。

---

## 3. 面板渲染流程

1. **数据获取层**
   - 封装 REST 客户端：`POST /api/v1/chat`。
   - 封装 WS 客户端：`ws://host/api/v1/chat/stream`。
   - 统一处理 metadata（`service_mode`、`cache_hit`、`component_confidence`）。

2. **状态管理**
   - `layoutStore`：存储当前布局树（mode、history_token、node 列表）。
   - `blockStore`：存储 UIBlock（props/options/interactions）以及 `data_ref` 对应的数据引用。
   - `dataStore`：缓存 `data_blocks`。
   - `preferenceStore`：用户偏好（主题、布局密度、默认组件等）。

3. **布局解析**
   - 将后端返回的 `LayoutTree` 转换为前端 `PanelLayout`。
   - 支持容器节点（Row/Column/Grid/Stack），子节点为 `UIBlock` ID。
   - 根据 `mode` 执行追加或替换：
     - append：新增 block 插入顶部，旧 block 下移。
     - replace：清空现有 state，重新渲染新布局。
     - insert（预留）：根据 `layout_hint.order` 或 `target` 插入。

4. **组件渲染器**
   - 实现 `ComponentRegistry`：`component_id → Vue Component` 映射。
   - 每个组件接受统一 props：
     ```ts
     interface DynamicComponentProps {
       blockId: string;
       data: any;
       props: Record<string, any>;
       options: Record<string, any>;
       interactions?: InteractionDefinition[];
       onInteraction?: (interaction: InteractionDefinition) => void;
     }
     ```
   - 组件内部使用 shadcn 原子组件组合 UI（List、Card、Chart 等）。
   - 交互通过 `onInteraction` 回调触发统一 Action 层。

5. **交互层**
   - 定义 Interaction 类型：`open_link`、`refresh`、`filter` 等。
   - 所有交互均需在前端有统一处理器，并可拓展。
   - 交互执行后需反馈结果或错误（Toast/Dialog）。

6. **数据校验**
   - 渲染前校验 `component_id` 、 props/options 类型、数据结构。
   - 错误时显示 fallback，并记录日志（Sentry/console）。

---

## 4. Electron Shell 规范

1. **主进程**：窗口管理、生命周期、IPC 安全；禁用不必要权限。
2. **预加载脚本**：暴露最小 API；使用 contextBridge，禁止直接暴露 Node API。
3. **日志与更新**：使用统一日志库（如 winston），支持自动更新（electron-updater）。
4. **开发与生产**：开发模式允许 DevTools，生产需关闭。

---

## 5. Shadcn UI 使用规范

1. 通过 `npx shadcn@latest add` 引入；禁止直接修改库文件。
2. 自定义组件放在 `components/custom`，组合 shadcn 原子组件。
3. 样式遵循 Tailwind + CSS Variable；统一主题管理。
4. Chart 组件可集成 `@ant-design/plots` 或 `recharts`，需封装统一接口。
5. 保持 UI 一致性：间距、字体、色彩与 shadcn 设计规范一致。

---

## 6. 与后端接口对齐

| 字段 | 前端职责 |
| ---- | -------- |
| `mode` | 调整布局（append/replace/insert）。|
| `layout.nodes` | 解析容器与子节点。|
| `blocks[].component` | 通过 ComponentRegistry 渲染对应组件。|
| `blocks[].data` / `data_ref` | 读取展示数据或从 `data_blocks` 查找。|
| `props/options` | 校验并传入组件，应用用户偏好。|
| `interactions` | 显示操作按钮，触发统一 handler。|
| `confidence` | 可用于显示置信度徽标。|
| `metadata` | 展示来源、缓存命中、模式等信息。|

---

## 7. WebSocket 流式处理

- 单例连接，支持重连。
- 根据 stage 更新 UI 提示，data 消息可用于预览。
- 收到 error 时展示提示并等待 complete。
- 按 stream_id 区分并发请求。

---

## 8. 用户偏好与缓存

- 偏好项：主题、布局密度、默认排序、组件折叠等。
- 持久化：IndexedDB/Electron Store。
- 可选同步到后端，便于跨设备使用。

---

## 9. QA & 测试

1. 单元测试：组件渲染器、LayoutTree 解析、交互 handler。
2. 集成测试：REST/WS 模拟，验证面板渲染、交互、模式切换。
3. 性能：大数据量渲染、频繁 WS 更新。
4. 可访问性：aria、键盘导航、主题对比度。

---

## 10. 未来扩展

- 面板布局拖拽、用户自定义顺序。
- 操作型组件（按钮触发写操作）。
- 组件动效，提升体验。
- 组件库扩展指南，便于新增组件。

---

严格按照上述规范开发，任何新增字段或行为需提前更新文档并评审。
