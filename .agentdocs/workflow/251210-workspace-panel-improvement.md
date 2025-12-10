# 工作台面板展示改进

> 任务目标：将工作台从"数据产物为主角"改进为 **Manus 风格流式时间线视图**，中心区域直接展示思考内容、工具调用、面板结果（从上到下依次排列），无需二级跳转。

## ⚠️ 重大需求调整（2025-12-10）

**用户反馈**：当前界面需要二级跳转才能查看面板信息，不够直观。参考 Manus，中心区域应该直接展示：
1. 思考内容（Agent 推理过程）
2. 调用的工具（工具名称、参数、状态）
3. 面板内容（可视化结果）

**新设计方向**：Manus 风格流式时间线视图

---

## 现状分析

### 现有可复用代码

| 模块 | 文件路径 | 复用价值 |
|------|---------|---------|
| **ResearchContextPanel** | `frontend/src/features/research/components/ResearchContextPanel.vue` | 步骤展示组件，可复用其设计模式 |
| **PanelBoard** | `frontend/src/features/panel/components/PanelBoard.vue` | 面板渲染组件，已在 MainCanvas 中使用 |
| **sessionStore** | `frontend/src/features/workspace/stores/sessionStore.ts` | Session 状态管理，已有 `loadRecordedSteps()` |
| **sessionApi** | `frontend/src/features/workspace/services/sessionApi.ts` | Session API，已有 `getRecordedSteps()` |
| **panel_stream.py** | `langgraph_agents/tools/panel_stream.py` | `emit_panel_preview` 工具，已正确推送面板数据 |

### 当前问题

1. **画布中央空空如也**
   - `MainCanvas.vue` 依赖 `currentStepOutput` 或 `selectedArtifact`
   - `panel_previews` 数据在 `ChatInteractionArea.vue:182-193` 已处理，但只更新到 `currentStepOutput`
   - 问题：没有持久化存储面板列表，只保留最后一个

2. **数据产物被当成主角**
   - `ArtifactPanel.vue` 在右侧，有 Pin 功能
   - 实际上数据产物应该是调试/参考面板，不需要 Pin

3. **步骤信息没有展示**
   - `sessionStore.ts` 有 `stepsCount` 和 `loadRecordedSteps()`
   - 但前端没有组件展示步骤详情

4. **Pin 功能放错对象**
   - `ArtifactPanel.vue:184-200` 对数据产物提供 Pin
   - 应该对面板提供 Pin，而非数据产物

---

## 改造方案

### 布局调整

**现有布局**：
```
┌─────────────────────────────────────────────────────────┐
│ WorkflowPanel │      MainCanvas      │  ArtifactPanel   │
│   (左侧)      │      (中央画布)       │   (数据产物)     │
└─────────────────────────────────────────────────────────┘
```

**目标布局**：
```
┌─────────────────────────────────────────────────────────┐
│ WorkflowPanel │    MainCanvas(面板)   │  ContextPanel   │
│   (左侧)      │    Pin按钮在此        │  - 步骤信息     │
│               │                       │  - 思考信息     │
│               │                       │  - 数据产物     │
└─────────────────────────────────────────────────────────┘
```

### 阶段拆分

#### Phase 1: 面板存储与展示

**目标**：让 `emit_panel_preview` 产出的面板在画布中央正确展示

**改造点**：

1. **workspaceStore.ts** - 新增面板列表状态
   ```typescript
   // 新增状态
   panelPreviews: [] as PanelPreview[],
   selectedPanelId: null as string | null,

   // 新增方法
   addPanelPreview(preview: PanelPreview): void
   selectPanel(panelId: string): void
   ```

2. **ChatInteractionArea.vue** - 修改面板处理逻辑
   ```typescript
   // 现有代码 L182-193 改为：
   if (result.panel_previews && result.panel_previews.length > 0) {
     for (const preview of result.panel_previews) {
       store.addPanelPreview(preview)  // 改为添加而非覆盖
     }
     // 自动选中最新面板
     store.selectPanel(result.panel_previews[result.panel_previews.length - 1].id)
   }
   ```

3. **MainCanvas.vue** - 优先展示面板
   ```typescript
   // panelData computed 修改：优先使用 selectedPanel
   const panelData = computed(() => {
     const panel = selectedPanel.value
     if (panel?.layout) {
       return { layout: panel.layout, blocks: panel.blocks, dataBlocks: panel.dataBlocks }
     }
     // 兜底：使用 currentStepOutput 或 selectedArtifact
     ...
   })
   ```

#### Phase 2: 右侧面板重构

**目标**：将右侧从"数据产物面板"改为"上下文面板"，包含步骤、思考、数据产物

**改造点**：

1. **新建 ContextPanel.vue** - 替换 ArtifactPanel
   ```
   ContextPanel
   ├── 步骤信息（复用 ResearchContextPanel 的设计）
   │   ├── 进度条
   │   └── 步骤列表
   ├── 思考信息（新增）
   │   └── Agent 推理过程
   └── 数据产物（简化版 ArtifactPanel）
       └── 移除 Pin 功能
   ```

2. **WorkspaceLayout.vue** - 替换右侧面板
   ```vue
   <!-- 原来 -->
   <ArtifactPanel @collapse="toggleRightPanel" />

   <!-- 改为 -->
   <ContextPanel @collapse="toggleRightPanel" />
   ```

#### Phase 3: Pin 功能迁移

**目标**：Pin 功能从数据产物迁移到面板

**改造点**：

1. **MainCanvas.vue** - 在面板区域添加 Pin 按钮
   ```vue
   <template>
     <div v-if="selectedPanel" class="panel-header">
       <button @click="handlePinPanel">
         <Pin /> Pin 到仪表盘
       </button>
     </div>
     <PanelBoard ... />
   </template>
   ```

2. **dashboardStore.ts** - 修改 `pinArtifact` 为 `pinPanel`
   ```typescript
   // 需要检查现有实现是否支持面板数据结构
   ```

---

## 接口设计

### 新增前端类型

```typescript
// frontend/src/features/workspace/types/workspace.ts

/** 面板预览（来自 emit_panel_preview） */
export interface PanelPreview {
  id: string                    // 唯一标识
  title: string                 // 面板标题
  layout: LayoutTree            // 布局信息
  blocks: UIBlock[]             // UI 块
  dataBlocks: Record<string, DataBlock>  // 数据块
  createdAt: string             // 创建时间
  sourceQuery?: string          // 触发查询
}

/** 执行步骤（复用 RecordedStepInfo） */
export interface ExecutionStep {
  step_id: number
  tool_id: string
  tool_name: string
  summary: string
  status: 'pending' | 'processing' | 'success' | 'error'
  executed_at: string
}

/** 思考信息 */
export interface ThinkingInfo {
  step_id: string
  content: string               // 推理内容
  timestamp: string
}
```

### 后端接口（无需修改）

现有 `SessionChatResponse` 已包含：
- `panel_previews: List[Dict[str, Any]]` - 面板预览
- `execution_steps: List[Dict[str, Any]]` - 执行步骤

---

## 数据模型

### workspaceStore 状态扩展

```typescript
interface WorkspaceState {
  // 现有状态（保留）
  artifacts: Artifact[]
  selectedArtifactId: string | null
  currentStepOutput: StepOutput | null

  // 新增状态
  panelPreviews: PanelPreview[]      // 面板列表
  selectedPanelId: string | null      // 当前选中面板
  executionSteps: ExecutionStep[]     // 执行步骤
  thinkingHistory: ThinkingInfo[]     // 思考历史
}
```

---

## 迁移计划

### Step 1: 状态扩展（无破坏性）
- 在 workspaceStore 中添加新状态字段
- 添加新的 actions
- 不影响现有功能

### Step 2: 面板展示改进
- 修改 ChatInteractionArea 的面板处理逻辑
- 修改 MainCanvas 的 panelData computed
- 测试：执行查询后面板正确展示

### Step 3: 右侧面板重构
- 创建 ContextPanel 组件
- 复用 ResearchContextPanel 的步骤展示逻辑
- 将 ArtifactPanel 的内容作为子面板
- 替换 WorkspaceLayout 中的引用
- 测试：步骤和数据产物正确展示

### Step 4: Pin 功能迁移
- 在 MainCanvas 添加面板 Pin 功能
- 移除 ArtifactPanel 的 Pin 功能
- 测试：面板可以 Pin 到仪表盘

---

## 测试策略

### 手动测试用例

1. **面板展示测试**
   - 输入：`获取B站热搜`
   - 预期：画布中央展示面板（列表卡片形式）
   - 验证：`emit_panel_preview` 的输出正确渲染

2. **步骤信息测试**
   - 输入：任意查询
   - 预期：右侧面板显示执行步骤（规划 → 数据获取 → 面板生成）
   - 验证：步骤状态实时更新

3. **数据产物测试**
   - 输入：任意查询
   - 预期：右侧面板的"数据产物"区域显示中间数据
   - 验证：数据产物无 Pin 按钮

4. **Pin 功能测试**
   - 操作：点击面板的 Pin 按钮
   - 预期：面板被添加到仪表盘
   - 验证：仪表盘正确显示 Pin 的面板

### Playwright 自动化测试

```typescript
// 待实现
test('workspace panel display', async ({ page }) => {
  await page.goto('/workspace')
  await page.fill('textarea', '获取B站热搜')
  await page.press('textarea', 'Enter')

  // 等待面板渲染
  await expect(page.locator('.panel-board')).toBeVisible()

  // 验证步骤面板
  await expect(page.locator('.context-panel .execution-steps')).toBeVisible()
})
```

---

## TODO

- [x] Phase 1: 面板存储与展示
  - [x] workspaceStore 添加 panelPreviews 状态
  - [x] ChatInteractionArea 修改面板处理逻辑
  - [x] MainCanvas 优先展示 selectedPanel

- [x] Phase 2: 右侧面板重构
  - [x] 创建 ContextPanel.vue（使用 shadcn/ui Tabs、Badge、Button 组件）
  - [x] 集成步骤信息展示（从 sessionStore.recordedSteps）
  - [x] 集成面板列表展示（从 workspaceStore.panelPreviews）
  - [x] 集成数据产物展示（简化版，无 Pin 功能）
  - [x] WorkspaceLayout 替换引用（ArtifactPanel → ContextPanel）

- [x] Phase 3: Pin 功能迁移
  - [x] MainCanvas 添加面板 Pin 按钮（使用 shadcn Button）
  - [x] 检查 dashboardStore.pinArtifact：不支持面板数据，需要后端新增 API
  - [ ] **后续任务**：实现后端 `POST /api/dashboard/pin/panel` 接口

---

## 后续工作

### 后端 API 扩展（待实现）

需要新增面板 Pin API，支持将面板预览数据直接存储为仪表盘卡片：

```python
# api/routes/dashboard.py

@router.post("/pin/panel")
async def pin_panel(request: PinPanelRequest) -> DashboardCard:
    """
    Pin 面板到仪表盘

    面板数据来自 emit_panel_preview，包含完整的布局和数据块信息
    """
    # 使用 card_type = 'custom'
    # source_config 存储面板数据（layout, blocks, dataBlocks）
    pass
```

```typescript
// frontend/src/features/dashboard/types/dashboard.ts

export interface PinPanelRequest {
  title: string
  layout: LayoutTree
  blocks: UIBlock[]
  dataBlocks: Record<string, DataBlock>
  description?: string
  refresh_interval?: RefreshIntervalValue
}
```

---

---

## Phase 4: Manus 风格流式时间线视图（新增）

### 设计目标

将中心画布从"选择-查看"模式改为 **流式时间线视图**：
- 所有内容（思考、工具调用、面板）在中心区域**从上到下依次展示**
- 用户无需点击右侧面板即可看到所有信息
- 类似聊天界面，但展示的是 Agent 执行过程

### 目标布局

```
┌─────────────────────────────────────────────────────────────┐
│ WorkflowPanel │         流式时间线视图                       │
│   (左侧)      │                                              │
│               │  ┌───────────────────────────────────────┐  │
│  工作流列表    │  │ 💭 思考: 分析用户查询，需要获取B站热搜  │  │
│               │  └───────────────────────────────────────┘  │
│               │  ┌───────────────────────────────────────┐  │
│               │  │ 🔧 fetch_public_data                   │  │
│               │  │    route: bilibili/hot-search          │  │
│               │  │    status: ✅ 成功 (30条数据)           │  │
│               │  └───────────────────────────────────────┘  │
│               │  ┌───────────────────────────────────────┐  │
│               │  │ 📊 面板: B站热搜榜                      │  │
│               │  │  ┌─────────────────────────────────┐  │  │
│               │  │  │ [完整的面板渲染内容]              │  │  │
│               │  │  │  - 列表项 1                      │  │  │
│               │  │  │  - 列表项 2                      │  │  │
│               │  │  │  ...                            │  │  │
│               │  │  └─────────────────────────────────┘  │  │
│               │  │  [Pin 到仪表盘] 按钮                   │  │
│               │  └───────────────────────────────────────┘  │
│               │                                              │
│               │  ┌───────────────────────────────────────┐  │
│               │  │ 输入框: 输入指令...                     │  │
│               │  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 时间线条目类型

```typescript
// 时间线条目类型定义
type TimelineEntryType = 'thinking' | 'tool_call' | 'panel' | 'error' | 'user_query'

interface TimelineEntry {
  id: string
  type: TimelineEntryType
  timestamp: string

  // 思考类型
  thinking?: {
    content: string
  }

  // 工具调用类型
  toolCall?: {
    tool_name: string
    tool_id: string
    parameters: Record<string, any>
    status: 'pending' | 'running' | 'success' | 'error'
    result_summary?: string
    data_id?: string  // 数据产物引用
    error?: string
  }

  // 面板类型
  panel?: {
    title: string
    layout: LayoutTree
    blocks: UIBlock[]
    dataBlocks: Record<string, DataBlock>
  }

  // 用户查询类型
  userQuery?: {
    query: string
  }
}
```

### 核心组件设计

#### 1. ExecutionTimeline.vue（新组件）

```vue
<!-- 流式时间线组件 -->
<template>
  <div class="execution-timeline">
    <div
      v-for="entry in timelineEntries"
      :key="entry.id"
      class="timeline-entry"
    >
      <!-- 用户查询 -->
      <UserQueryEntry v-if="entry.type === 'user_query'" :entry="entry" />

      <!-- 思考 -->
      <ThinkingEntry v-else-if="entry.type === 'thinking'" :entry="entry" />

      <!-- 工具调用 -->
      <ToolCallEntry v-else-if="entry.type === 'tool_call'" :entry="entry" />

      <!-- 面板 -->
      <PanelEntry v-else-if="entry.type === 'panel'" :entry="entry" />

      <!-- 错误 -->
      <ErrorEntry v-else-if="entry.type === 'error'" :entry="entry" />
    </div>

    <!-- 底部输入框 -->
    <ChatInput @submit="handleSubmit" />
  </div>
</template>
```

#### 2. ThinkingEntry.vue

```vue
<!-- 思考条目 -->
<template>
  <Card class="thinking-entry">
    <CardHeader class="flex-row items-center gap-2 py-2">
      <Brain class="h-4 w-4 text-purple-500" />
      <span class="text-sm font-medium">思考</span>
    </CardHeader>
    <CardContent class="py-2 text-sm text-muted-foreground">
      {{ entry.thinking.content }}
    </CardContent>
  </Card>
</template>
```

#### 3. ToolCallEntry.vue

```vue
<!-- 工具调用条目 -->
<template>
  <Card class="tool-call-entry">
    <CardHeader class="flex-row items-center gap-2 py-2">
      <Wrench class="h-4 w-4 text-blue-500" />
      <span class="text-sm font-medium">{{ entry.toolCall.tool_name }}</span>
      <Badge :variant="statusVariant">{{ statusText }}</Badge>
    </CardHeader>
    <CardContent v-if="entry.toolCall.result_summary" class="py-2 text-sm">
      {{ entry.toolCall.result_summary }}
    </CardContent>
  </Card>
</template>
```

#### 4. PanelEntry.vue（复用 PanelBoard）

```vue
<!-- 面板条目 - 完整渲染面板内容 -->
<template>
  <Card class="panel-entry">
    <CardHeader class="flex-row items-center justify-between py-2">
      <div class="flex items-center gap-2">
        <LayoutGrid class="h-4 w-4 text-green-500" />
        <span class="text-sm font-medium">{{ entry.panel.title }}</span>
      </div>
      <Button variant="outline" size="sm" @click="handlePin">
        <Pin class="h-3 w-3 mr-1" />
        Pin 到仪表盘
      </Button>
    </CardHeader>
    <CardContent class="py-2">
      <!-- 复用现有 PanelBoard 组件 -->
      <PanelBoard
        :layout="entry.panel.layout"
        :blocks="entry.panel.blocks"
        :data-blocks="entry.panel.dataBlocks"
      />
    </CardContent>
  </Card>
</template>
```

### 后端数据流适配

后端已有的 WebSocket 消息需要适配为时间线条目：

| 后端消息类型 | 时间线条目类型 |
|-------------|---------------|
| `thinking` | `thinking` |
| `tool_start` | `tool_call` (status: running) |
| `tool_end` | `tool_call` (status: success/error) |
| `panel_preview` | `panel` |
| `step_info` | 合并到对应 `tool_call` |

### 改造点

1. **MainCanvas.vue** - 替换为 ExecutionTimeline
   - 移除 currentViewMode 选择逻辑
   - 移除 selectedPanel 单选逻辑
   - 使用时间线列表展示所有内容

2. **workspaceStore.ts** - 新增时间线状态
   ```typescript
   timelineEntries: TimelineEntry[]
   addTimelineEntry(entry: TimelineEntry): void
   clearTimeline(): void
   ```

3. **ChatInteractionArea.vue** - 适配时间线
   - WebSocket 消息转换为 TimelineEntry
   - 用户输入添加 `user_query` 条目

4. **WorkspaceLayout.vue** - 简化布局
   - 可选：移除右侧 ContextPanel（或保留为可折叠的调试面板）
   - 中心区域全部给时间线

### TODO

- [x] Phase 4.1: 时间线数据结构
  - [x] workspaceStore 添加 timelineEntries
  - [x] 定义 TimelineEntry 类型

- [x] Phase 4.2: 基础时间线组件
  - [x] 创建 ExecutionTimeline.vue（Manus 风格：左侧连接线 + 圆点）
  - [x] 创建 ThinkingEntry.vue
  - [x] 创建 ToolCallEntry.vue
  - [x] 创建 PanelEntry.vue
  - [x] 创建 UserQueryEntry.vue
  - [x] 创建 ErrorEntry.vue
  - [x] 创建 MessageEntry.vue

- [x] Phase 4.3: 数据流集成
  - [x] ChatInteractionArea 消息转换
  - [x] 用户查询添加为时间线条目

- [x] Phase 4.4: 布局集成
  - [x] MainCanvas 替换为 ExecutionTimeline
  - [x] 调整 WorkspaceLayout 布局
  - [x] 移除右侧边栏"步骤"标签页（步骤信息已在时间线中展示）

- [x] Phase 4.5: UI 改进
  - [x] 时间线圆点颜色与工具状态一致（success=绿色, running=蓝色, error=红色）
  - [x] ToolCallEntry 改进 JSON 解析，展示 instruction 而非原始数据
  - [x] 面板导航功能：点击右侧面板列表跳转到时间线对应位置
  - [x] 修复 @keyframes CSS 错误（使用 hsl() 而非 @apply）
  - [x] 使用 shadcn 组件替换自建组件（Button, DropdownMenu）

---

## 更新记录

- 2025-12-10：创建任务文档
- 2025-12-10：完成 Phase 1 - 面板存储与展示
  - workspaceStore.ts: 添加 panelPreviews, selectedPanelId, selectedPanel, addPanelPreview, selectPanel, clearPanelPreviews
  - ChatInteractionArea.vue: 修改为使用 store.addPanelPreview() 和 store.selectPanel()
  - MainCanvas.vue: 添加 selectedPanel 优先级，更新 panelData computed
  - workspace.ts: 添加 PanelPreview 类型定义
- 2025-12-10：完成 Phase 2 - 右侧面板重构
  - 创建 ContextPanel.vue: 使用 shadcn/ui Tabs 组件实现三标签页（步骤、面板、产物）
  - WorkspaceLayout.vue: 将 ArtifactPanel 替换为 ContextPanel，更新图标为 Activity
- 2025-12-10：完成 Phase 3 - Pin 功能迁移（前端 UI）
  - MainCanvas.vue: 添加 Pin 按钮，显示面板标题和 LayoutGrid 图标
  - handlePinPanel: 临时实现，显示开发中提示
  - 后端 API 待实现：POST /api/dashboard/pin/panel
- 2025-12-10：**需求调整** - Manus 风格流式时间线视图
  - 用户反馈：需要一级直观展示，不要二级跳转
  - 新增 Phase 4 设计方案
- 2025-12-10：完成 Phase 4 - Manus 风格流式时间线视图
  - 创建 ExecutionTimeline.vue: Manus 风格左侧连接线 + 圆点设计
  - 创建 6 种时间线条目组件（UserQueryEntry, ThinkingEntry, ToolCallEntry, PanelEntry, ErrorEntry, MessageEntry）
  - MainCanvas.vue 替换为 ExecutionTimeline
  - 移除右侧边栏"步骤"标签页
- 2025-12-10：完成 Phase 4.5 - UI 改进
  - ToolCallEntry: 改进 data_operator 结果解析，展示 instruction 而非原始 JSON
  - ExecutionTimeline: 时间线圆点颜色与工具状态同步（success=绿/running=蓝/error=红）
  - 面板导航功能：点击右侧面板列表跳转到时间线对应位置（平滑滚动 + 高亮动画）
  - 修复 @keyframes CSS 错误：将 @apply 替换为 hsl(var(--primary) / 0.x) 语法
  - shadcn 组件统一：ChatInteractionArea 使用 shadcn Button，DashboardCard 使用 shadcn DropdownMenu
- 2025-12-10：**发现严重问题** - 当前 Workspace 使用同步 HTTP，用户需等待数分钟
  - 需要改为 WebSocket 流式架构，复用研究卡片的成熟方案
  - 新增 Phase 5: WebSocket 流式改造方案

---

## Phase 5: WebSocket 流式架构改造（待实现）

### 问题背景

当前 Workspace 的会话聊天使用同步 HTTP 调用：
- **前端**：`sessionApi.chat()` 调用 `POST /api/v1/sessions/{id}/chat`
- **后端**：`session_controller.session_chat()` 同步执行 LangGraph，等待全部完成后返回
- **用户体验**：需要等待 2-5 分钟，期间无任何反馈

研究卡片（Research Card）已有成熟的 WebSocket 流式方案，可以复用。

### 现有 WebSocket 架构分析

#### 后端架构

**WebSocket 端点**：`api/controllers/chat_stream.py:403-539`
```python
@router.websocket("/chat/stream")
async def chat_stream(websocket: WebSocket, chat_service: Any = Depends(get_chat_service)):
    """
    统一 WebSocket 流式对话接口

    消息格式:
    - 客户端发送: { "query": "...", "mode": "auto|simple|research", ... }
    - 服务端推送: stage, data, graph_node, llm_call, complete, error
    """
```

**消息类型**（`api/schemas/stream_messages.py`）：
| 类型 | 用途 | 关键字段 |
|------|------|---------|
| `stage` | 阶段进度 | stage(intent/rag/fetch/summary), message, progress |
| `data` | 阶段数据 | stage, data |
| `graph_node` | Task Graph 节点状态 | node_id, node_type, status, summary |
| `llm_call` | LLM 调用事件 | call_id, role, status, tokens, preview |
| `complete` | 完成消息 | success, message, total_time |
| `error` | 错误消息 | error_code, error_message |
| `research_*` | 研究模式专用 | research_start/step/panel/analysis/complete/error |

**流式处理函数**：`stream_chat_processing()` (L51-401)
- 阶段1: 意图识别 (intent)
- 阶段2: RAG 检索 (rag)
- 阶段3: 数据获取 (fetch) - 使用线程+队列实现异步
- 阶段4: 结果总结 (summary)

#### 前端架构

**WebSocket 连接管理**：`frontend/src/composables/useResearchWebSocket.ts`
```typescript
export function useResearchWebSocket(options: ResearchWebSocketOptions) {
  // 连接状态
  const isConnecting = ref(false)
  const isConnected = ref(false)
  const error = ref<string | null>(null)

  // WebSocket URL: /api/v1/chat/stream?task_id=xxx
  const wsBaseUrl = resolveWsBase(url ?? envWsBase, "/api/v1/chat/stream", API_BASE)

  // 消息处理
  function handleMessage(event: MessageEvent) {
    const message = JSON.parse(event.data)
    switch (message.type) {
      case "stage": handleStageStreamMessage(message); break
      case "data": handleTaskGraphData(message); break
      case "graph_node": handleGraphNodeEvent(message); break
      case "complete": handleCompleteMessage(message); break
      case "error": handleErrorMessage(message); break
      // ... 研究模式消息
    }
  }

  // 发送请求
  function sendResearchRequest(payload: { query, filter_datasource?, use_cache?, layout_snapshot? }) {
    ws.value.send(JSON.stringify({ ...payload, mode: "research", task_id: currentTaskId.value }))
  }
}
```

**全局连接管理器**：`frontend/src/composables/useResearchWebSocketManager.ts`
```typescript
// 全局连接池：taskId -> WebSocket 连接实例
const activeConnections = ref<Map<string, ReturnType<typeof useResearchWebSocket>>>(new Map())
// 全局请求状态：taskId -> 是否已发送研究请求
const requestSent = ref<Map<string, boolean>>(new Map())

export function useResearchWebSocketManager(options: WebSocketManagerOptions) {
  // 获取或创建连接（复用已有连接）
  let connection = activeConnections.value.get(taskId)
  if (!connection) {
    connection = useResearchWebSocket(options)
    activeConnections.value.set(taskId, connection)
  }

  // 带去重保护的请求发送（幂等操作）
  function sendResearchRequestOnce(payload) { ... }

  // 断开连接并清理资源
  function disconnectAndCleanup() { ... }
}
```

### 改造方案

#### Phase 5.1: 后端扩展

**无需大改**，现有 `/api/v1/chat/stream` 已支持通用查询，只需：

1. **session_controller.py** - 新增 WebSocket 端点（可选）
   ```python
   @router.websocket("/{session_id}/stream")
   async def session_stream(session_id: str, websocket: WebSocket):
       """Session 专属 WebSocket 端点（可选，也可复用 /chat/stream）"""
       # 复用 chat_stream 的处理逻辑
       # 只需添加 session_id 参数传递
   ```

2. **chat_stream.py** - 支持 session_id 参数
   ```python
   # 在 request_data 中读取 session_id
   session_id = request_data.get("session_id")
   # 如果有 session_id，将结果保存到 session
   ```

#### Phase 5.2: 前端改造

1. **新建 useWorkspaceWebSocket.ts**（复用 useResearchWebSocket 模式）
   ```typescript
   export function useWorkspaceWebSocket(options: { sessionId: string }) {
     // 连接到 /api/v1/chat/stream?session_id=xxx
     // 消息处理 → 更新 workspaceStore.timelineEntries
   }
   ```

2. **ChatInteractionArea.vue** - 使用 WebSocket 替代同步 HTTP
   ```typescript
   // 现有代码（同步 HTTP）
   const result = await sessionApi.chat(sessionId, query)

   // 改为 WebSocket
   const { connect, sendResearchRequest, isConnected } = useWorkspaceWebSocket({ sessionId })
   await connect()
   sendResearchRequest({ query, session_id: sessionId })
   ```

3. **消息转换为时间线条目**
   ```typescript
   function handleWebSocketMessage(message: StreamMessage) {
     switch (message.type) {
       case 'stage':
         // 转为 ThinkingEntry
         workspaceStore.addTimelineEntry({
           type: 'thinking',
           thinking: { content: message.message }
         })
         break
       case 'graph_node':
         // 转为 ToolCallEntry
         workspaceStore.addTimelineEntry({
           type: 'tool_call',
           toolCall: { tool_name: message.node_id, status: message.status, ... }
         })
         break
       case 'data':
         if (message.stage === 'summary') {
           // 转为 PanelEntry
           workspaceStore.addTimelineEntry({
             type: 'panel',
             panel: { layout: message.data.data, ... }
           })
         }
         break
       case 'complete':
         // 完成状态
         break
       case 'error':
         // 转为 ErrorEntry
         workspaceStore.addTimelineEntry({
           type: 'error',
           error: { message: message.error_message }
         })
         break
     }
   }
   ```

#### Phase 5.3: 全局连接管理

复用 `useResearchWebSocketManager` 的模式：

```typescript
// useWorkspaceWebSocketManager.ts
const activeConnections = ref<Map<string, ReturnType<typeof useWorkspaceWebSocket>>>(new Map())

export function useWorkspaceWebSocketManager(options: { sessionId: string }) {
  // 获取或创建连接
  // 请求去重
  // 断开清理
}
```

### 数据流对比

**现有同步流程**：
```
User Input → ChatInteractionArea
           → sessionApi.chat() [HTTP POST]
           → session_controller.session_chat() [同步执行 2-5 分钟]
           → ChatResponse [全部数据一次返回]
           → workspaceStore.addTimelineEntry() [一次性添加所有条目]
```

**目标异步流程**：
```
User Input → ChatInteractionArea
           → useWorkspaceWebSocket.connect() [建立连接]
           → sendResearchRequest() [发送查询]
           → WebSocket 消息流 [实时推送]
              ├─ stage:intent → ThinkingEntry
              ├─ stage:rag → ThinkingEntry
              ├─ graph_node:running → ToolCallEntry(running)
              ├─ graph_node:success → ToolCallEntry(success)
              ├─ data:summary → PanelEntry
              └─ complete → 完成状态
           → workspaceStore.addTimelineEntry() [逐条添加]
```

### TODO

- [x] Phase 5.1: 后端扩展（✅ 2025-12-10 已完成）
  - [x] `session_controller.py` 新增 WebSocket 端点 `/{session_id}/stream`
  - [x] 使用 threading + Queue 模式处理异步回调
  - [x] 推送 stage, data, research_step, complete, error 消息

- [x] Phase 5.2: 前端 WebSocket 适配（✅ 2025-12-10 已完成）
  - [x] 创建 `useSessionWebSocket.ts`（连接管理、消息处理）
  - [x] `ChatInteractionArea.vue` 使用 WebSocket 替代 HTTP
  - [x] 消息转换为 TimelineEntry（thinking, tool_call, panel, error）

- [x] Phase 5.3: 单元测试（✅ 2025-12-10 已完成）
  - [x] 创建 `tests/api/test_session_stream.py`
  - [x] 11 个测试用例全部通过

- [x] Phase 5.4: 测试验证（✅ 2025-12-10 已完成）
  - [x] 修复 progress 值范围（0-1 浮点数）
  - [x] 修复类型错误（DataStashItem 接口）

**实现文件清单**：
- 后端：`api/controllers/session_controller.py` (新增 `session_stream` 和 `_stream_session_execution`)
- 前端：`frontend/src/features/workspace/composables/useSessionWebSocket.ts`（新建）
- 前端：`frontend/src/features/workspace/components/canvas/ChatInteractionArea.vue`（修改 handleSend）
- 测试：`tests/api/test_session_stream.py`（新建）

### 风险与注意事项

1. **Session 保存**：WebSocket 完成后需要保存结果到 Session，否则刷新丢失
2. **错误处理**：WebSocket 断开时的重连策略
3. **并发控制**：同一 Session 不能同时有多个 WebSocket 请求
4. **向后兼容**：保留同步 HTTP API 作为降级方案

## 工具生命周期流式事件（新增需求）

**痛点**：工具完成后才推送，导致时间线在末尾集中刷屏，执行中缺少“正在调用哪个工具”的实时反馈。

**方案**：
- 工具执行前推送 `tool_start`：携带 `step_id`、`tool_name`、`description`，状态 `processing`，前端立即呈现“运行中”动效。
- 工具完成仍用 `tool_result`，只更新状态，不在 summary 阶段重复回放。
- summary 阶段 data_stash 仅用于 artifacts/统计，不再生成时间线条目。

**落地点**：
- 后端：`langgraph_agents/agents/tool_executor.py` 触发 start 回调；`langgraph_agents/sync_executor.py`、`services/session/runtime_manager.py` 注入 `emit_tool_start`；`api/controllers/session_controller.py` 监听并推送 `research_step`。
- 前端：`frontend/src/features/workspace/composables/useSessionWebSocket.ts` 继续消费 `research_step`（running 态已有流光动效）。

### 待改进问题（2025-12-10）
1) **同一内容的 start/finish 未复用同一条时间线记录**：tool_start 和 tool_result 仍可能生成两个条目，需按 tool_id/tool_name 合并更新，确保只更新状态而非新增记录。
2) **动画对比度不足**：当前 shimmer 动效在深色背景下不明显，需要调整渐变强度/叠加描边或使用更亮的高光色，确保“运行中”提示易辨识。
