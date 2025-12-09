# Phase 3: 工作台 UI 设计方案

**创建日期**: 2025-12-09
**状态**: ✅ 已完成
**目标**: 实现三栏式工作台界面，支持工作流可视化、数据产物管理、实时交互

---

## 一、现状分析

### 1.1 现有可复用组件

| 组件 | 位置 | 复用策略 |
|------|------|---------|
| **PanelBoard** | `features/panel/components/` | ✅ 主画布 CSS Grid 布局 |
| **DynamicBlockRenderer** | `features/panel/components/` | ✅ 数据产物可视化渲染 |
| **ResearchContextPanel** | `features/research/components/` | 🔄 参考结构，重写为工作流面板 |
| **ResearchDataPanel** | `features/research/components/` | 🔄 参考结构，重写为数据产物面板 |
| **UI 组件库** | `components/ui/` | ✅ Card、Tabs、Progress、Badge 等 |
| **panelStore** | `store/` | ✅ 数据面板状态管理 |
| **researchViewStore** | `store/` | 🔄 参考结构，新建 workflowStore |

### 1.2 现有布局参考

**ResearchView 双栏布局**：
```
┌─────────────────┬────────────────────────────────┐
│  上下文面板      │           数据面板              │
│  (30%)          │           (70%)                │
│                 │                                │
│  - 任务信息      │  - PanelBoard 网格             │
│  - 步骤列表      │  - 分析结果                     │
│  - 进度显示      │                                │
└─────────────────┴────────────────────────────────┘
```

**目标三栏布局**：
```
┌────────────┬─────────────────────────┬─────────────┐
│  工作流面板  │        主画布            │  数据面板    │
│  (240px)   │       (flex-1)          │  (280px)   │
│            │                         │            │
│  - 工作流列表│  ┌─────────────────┐   │ - 产物列表   │
│  - 步骤树   │  │  数据可视化      │   │ - 预览      │
│  - 进度    │  │  (多视图切换)    │   │ - 操作按钮   │
│            │  └─────────────────┘   │            │
│            │  ┌─────────────────┐   │            │
│            │  │  对话交互区      │   │            │
│            │  └─────────────────┘   │            │
└────────────┴─────────────────────────┴─────────────┘
```

---

## 二、组件架构设计

### 2.1 目录结构

```
frontend/src/
├── views/
│   └── WorkspaceView.vue              # 工作台主视图（新增）
├── features/
│   └── workspace/                     # 工作台特性模块（新增）
│       ├── index.ts                   # 模块导出
│       ├── WorkspaceLayout.vue        # 三栏布局容器
│       ├── components/
│       │   ├── workflow/              # 工作流面板组件
│       │   │   ├── WorkflowPanel.vue          # 工作流面板容器
│       │   │   ├── WorkflowList.vue           # 工作流列表
│       │   │   ├── WorkflowStepTree.vue       # 步骤树
│       │   │   ├── WorkflowStepItem.vue       # 步骤项
│       │   │   └── WorkflowProgress.vue       # 进度指示器
│       │   ├── canvas/                # 主画布组件
│       │   │   ├── MainCanvas.vue             # 主画布容器
│       │   │   ├── CanvasViewSwitcher.vue     # 视图切换器
│       │   │   └── ChatInteractionArea.vue    # 对话交互区
│       │   └── artifact/              # 数据产物面板组件
│       │       ├── ArtifactPanel.vue          # 数据面板容器
│       │       ├── ArtifactList.vue           # 产物列表
│       │       ├── ArtifactPreview.vue        # 产物预览
│       │       └── ArtifactActions.vue        # 产物操作按钮
│       ├── stores/
│       │   └── workspaceStore.ts      # 工作台状态管理
│       ├── composables/
│       │   ├── useWorkflowExecution.ts # 工作流执行逻辑
│       │   └── useArtifactActions.ts  # 产物操作逻辑
│       ├── services/
│       │   └── workspaceApi.ts        # 工作台 API
│       └── types/
│           └── workspace.ts           # 工作台类型定义
├── store/
│   └── workspaceStore.ts              # 全局工作台状态（可选）
└── types/
    └── workflow.ts                    # 已有，Phase 2 创建
```

### 2.2 组件层次

```
WorkspaceView
└── WorkspaceLayout (三栏容器)
    ├── WorkflowPanel (左侧 240px)
    │   ├── WorkflowList
    │   │   └── WorkflowListItem (每个工作流)
    │   └── WorkflowStepTree (当前工作流的步骤)
    │       └── WorkflowStepItem (每个步骤)
    │           └── WorkflowProgress (进度指示)
    │
    ├── MainCanvas (中间 flex-1)
    │   ├── CanvasViewSwitcher (视图标签页)
    │   │   └── Tabs (图表/表格/文本/原始)
    │   ├── PanelBoard (复用现有)
    │   │   └── DynamicBlockRenderer (复用现有)
    │   └── ChatInteractionArea (底部)
    │       └── 输入框 + 发送按钮
    │
    └── ArtifactPanel (右侧 280px)
        ├── ArtifactList
        │   └── ArtifactListItem (每个产物)
        ├── ArtifactPreview (选中产物预览)
        └── ArtifactActions (操作按钮组)
```

---

## 三、状态管理设计

### 3.1 workspaceStore

**文件**: `frontend/src/features/workspace/stores/workspaceStore.ts`

```typescript
import { defineStore } from 'pinia'
import type {
  Workflow, WorkflowRun, WorkflowStep,
  RunStatus, ProgressEvent
} from '@/types/workflow'
import type { DataArtifact } from '@/types/artifact'

interface WorkspaceState {
  // 工作流管理
  workflows: Workflow[]
  currentWorkflowId: string | null
  currentRunId: string | null

  // 执行状态
  currentRun: WorkflowRun | null
  stepStatuses: Record<number, RunStatus>  // step_id → status

  // 数据产物
  artifacts: DataArtifact[]
  selectedArtifactId: string | null

  // 画布状态
  canvasView: 'chart' | 'table' | 'text' | 'raw'
  currentStepOutput: any  // 当前步骤的输出数据

  // UI 状态
  leftPanelCollapsed: boolean
  rightPanelCollapsed: boolean

  // WebSocket
  wsConnected: boolean
  progressEvents: ProgressEvent[]
}

// Actions
- loadWorkflows(): 加载工作流列表
- selectWorkflow(workflowId): 选择工作流
- startRun(variableValues): 启动执行
- pauseRun(): 暂停执行
- resumeRun(): 恢复执行
- cancelRun(): 取消执行
- handleProgressEvent(event): 处理进度事件
- selectArtifact(artifactId): 选择产物
- setCanvasView(view): 切换画布视图
- toggleLeftPanel(): 折叠/展开左侧面板
- toggleRightPanel(): 折叠/展开右侧面板
```

### 3.2 与后端 API 集成

```typescript
// workspaceApi.ts

// 工作流 CRUD
GET    /api/v1/workflows                → listWorkflows()
GET    /api/v1/workflows/:id            → getWorkflow(id)
POST   /api/v1/workflows                → createWorkflow(data)
PUT    /api/v1/workflows/:id            → updateWorkflow(id, data)
DELETE /api/v1/workflows/:id            → deleteWorkflow(id)

// 执行管理
POST   /api/v1/workflows/:id/run        → startRun(id, variables)
POST   /api/v1/runs/:runId/pause        → pauseRun(runId)
POST   /api/v1/runs/:runId/resume       → resumeRun(runId)
POST   /api/v1/runs/:runId/cancel       → cancelRun(runId)
GET    /api/v1/runs/:runId              → getRunStatus(runId)

// 数据产物
GET    /api/v1/artifacts                → listArtifacts(workflowId?, runId?)
GET    /api/v1/artifacts/:id            → getArtifact(id)
GET    /api/v1/artifacts/:id/data       → getArtifactData(id)

// WebSocket 进度推送
WS     /api/v1/ws/workflow/:runId       → 实时进度事件
```

---

## 四、核心组件设计

### 4.1 WorkspaceLayout（三栏布局容器）

```vue
<template>
  <div class="workspace-layout">
    <!-- 左侧工作流面板 -->
    <aside
      class="workflow-panel"
      :class="{ collapsed: leftPanelCollapsed }"
    >
      <WorkflowPanel />
    </aside>

    <!-- 中间主画布 -->
    <main class="main-canvas">
      <MainCanvas />
    </main>

    <!-- 右侧数据面板 -->
    <aside
      class="artifact-panel"
      :class="{ collapsed: rightPanelCollapsed }"
    >
      <ArtifactPanel />
    </aside>
  </div>
</template>

<style>
.workspace-layout {
  display: flex;
  height: 100vh;
  background: var(--background);
}

.workflow-panel {
  width: 240px;
  border-right: 1px solid var(--border);
  transition: width 0.2s ease;
}

.workflow-panel.collapsed {
  width: 48px;
}

.main-canvas {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.artifact-panel {
  width: 280px;
  border-left: 1px solid var(--border);
  transition: width 0.2s ease;
}

.artifact-panel.collapsed {
  width: 48px;
}
</style>
```

### 4.2 WorkflowPanel（工作流面板）

```vue
<template>
  <div class="workflow-panel-content">
    <!-- 头部：标题 + 新建按钮 -->
    <header class="panel-header">
      <h3>工作流</h3>
      <Button variant="ghost" size="icon-sm" @click="createWorkflow">
        <Plus class="w-4 h-4" />
      </Button>
    </header>

    <!-- 工作流列表 -->
    <WorkflowList
      :workflows="workflows"
      :selected-id="currentWorkflowId"
      @select="selectWorkflow"
    />

    <!-- 分隔线 -->
    <Separator />

    <!-- 当前工作流的步骤树 -->
    <div v-if="currentWorkflow" class="step-section">
      <h4 class="section-title">{{ currentWorkflow.name }}</h4>
      <WorkflowStepTree
        :steps="currentWorkflow.steps"
        :step-statuses="stepStatuses"
        :current-step-id="currentRun?.current_step_id"
        @step-click="onStepClick"
      />
    </div>

    <!-- 执行控制 -->
    <div v-if="currentWorkflow" class="execution-controls">
      <Button
        v-if="!currentRun || currentRun.status === 'completed'"
        @click="startRun"
        class="w-full"
      >
        <Play class="w-4 h-4 mr-2" />
        执行
      </Button>
      <Button
        v-else-if="currentRun.status === 'running'"
        variant="secondary"
        @click="pauseRun"
        class="w-full"
      >
        <Pause class="w-4 h-4 mr-2" />
        暂停
      </Button>
      <Button
        v-else-if="currentRun.status === 'paused'"
        @click="resumeRun"
        class="w-full"
      >
        <Play class="w-4 h-4 mr-2" />
        继续
      </Button>
    </div>
  </div>
</template>
```

### 4.3 WorkflowStepTree（步骤树）

```vue
<template>
  <div class="step-tree">
    <div
      v-for="step in steps"
      :key="step.step_id"
      class="step-item"
      :class="getStepClass(step)"
      @click="$emit('step-click', step)"
    >
      <!-- 步骤图标 -->
      <div class="step-icon">
        <component :is="getStepIcon(step)" class="w-4 h-4" />
      </div>

      <!-- 步骤信息 -->
      <div class="step-info">
        <span class="step-name">{{ step.name }}</span>
        <span class="step-type">{{ step.step_type }}</span>
      </div>

      <!-- 状态指示 -->
      <div class="step-status">
        <CheckCircle v-if="stepStatuses[step.step_id] === 'completed'"
                     class="w-4 h-4 text-green-500" />
        <Loader2 v-else-if="step.step_id === currentStepId"
                 class="w-4 h-4 text-blue-500 animate-spin" />
        <Circle v-else class="w-4 h-4 text-muted-foreground" />
      </div>
    </div>

    <!-- 依赖连接线 -->
    <svg class="dependency-lines">
      <!-- 根据 depends_on 绘制连线 -->
    </svg>
  </div>
</template>
```

### 4.4 MainCanvas（主画布）

```vue
<template>
  <div class="main-canvas-content">
    <!-- 视图切换标签 -->
    <header class="canvas-header">
      <Tabs v-model="canvasView">
        <TabsList>
          <TabsTrigger value="chart">图表</TabsTrigger>
          <TabsTrigger value="table">表格</TabsTrigger>
          <TabsTrigger value="text">文本</TabsTrigger>
          <TabsTrigger value="raw">原始</TabsTrigger>
        </TabsList>
      </Tabs>

      <!-- 当前步骤信息 -->
      <div v-if="currentStep" class="current-step-badge">
        <Badge variant="outline">
          {{ currentStep.name }}
        </Badge>
      </div>
    </header>

    <!-- 数据可视化区域 -->
    <div class="canvas-viewport">
      <PanelBoard
        v-if="currentOutput"
        :layout="currentOutput.layout"
        :blocks="currentOutput.blocks"
        :data-blocks="currentOutput.dataBlocks"
      />
      <div v-else class="empty-canvas">
        <Database class="w-12 h-12 text-muted-foreground" />
        <p>选择一个步骤或产物查看数据</p>
      </div>
    </div>

    <!-- 对话交互区 -->
    <ChatInteractionArea
      :workflow-id="currentWorkflowId"
      :run-id="currentRunId"
      @send="handleChatSend"
    />
  </div>
</template>
```

### 4.5 ArtifactPanel（数据产物面板）

```vue
<template>
  <div class="artifact-panel-content">
    <!-- 头部 -->
    <header class="panel-header">
      <h3>数据产物</h3>
      <Badge>{{ artifacts.length }}</Badge>
    </header>

    <!-- 产物列表 -->
    <div class="artifact-list">
      <ArtifactListItem
        v-for="artifact in artifacts"
        :key="artifact.artifact_id"
        :artifact="artifact"
        :selected="artifact.artifact_id === selectedArtifactId"
        @click="selectArtifact(artifact.artifact_id)"
        @drag-start="onDragStart(artifact)"
      />
    </div>

    <!-- 选中产物预览 -->
    <div v-if="selectedArtifact" class="artifact-preview">
      <Separator />
      <ArtifactPreview :artifact="selectedArtifact" />
    </div>

    <!-- 操作按钮 -->
    <div class="artifact-actions">
      <Button variant="outline" size="sm" @click="exportArtifact">
        <Download class="w-4 h-4 mr-1" />
        导出
      </Button>
      <Button variant="outline" size="sm" @click="pinToDashboard">
        <Pin class="w-4 h-4 mr-1" />
        Pin
      </Button>
    </div>
  </div>
</template>
```

### 4.6 ChatInteractionArea（对话交互区）

```vue
<template>
  <div class="chat-interaction">
    <div class="chat-input-container">
      <Textarea
        v-model="inputText"
        placeholder="输入指令，如：把叙事结构做成对比表格..."
        :rows="1"
        class="chat-input"
        @keydown.enter.exact.prevent="send"
      />
      <Button
        @click="send"
        :disabled="!inputText.trim() || loading"
        size="icon"
      >
        <Send v-if="!loading" class="w-4 h-4" />
        <Loader2 v-else class="w-4 h-4 animate-spin" />
      </Button>
    </div>

    <!-- 快捷操作 -->
    <div class="quick-actions">
      <Button variant="ghost" size="xs">生成摘要</Button>
      <Button variant="ghost" size="xs">对比分析</Button>
      <Button variant="ghost" size="xs">导出报告</Button>
    </div>
  </div>
</template>
```

---

## 五、路由配置

```typescript
// router/index.ts 新增

{
  path: '/workspace',
  name: 'workspace',
  component: () => import('@/views/WorkspaceView.vue'),
  meta: { title: '工作台' }
},
{
  path: '/workspace/:workflowId',
  name: 'workspace-workflow',
  component: () => import('@/views/WorkspaceView.vue'),
  meta: { title: '工作台' }
},
{
  path: '/workspace/:workflowId/run/:runId',
  name: 'workspace-run',
  component: () => import('@/views/WorkspaceView.vue'),
  meta: { title: '工作台' }
}
```

---

## 六、WebSocket 进度推送

### 6.1 连接管理

```typescript
// composables/useWorkflowWebSocket.ts

export function useWorkflowWebSocket(runId: Ref<string | null>) {
  const store = useWorkspaceStore()
  const ws = ref<WebSocket | null>(null)

  const connect = () => {
    if (!runId.value) return

    ws.value = new WebSocket(
      `${WS_BASE_URL}/api/v1/ws/workflow/${runId.value}`
    )

    ws.value.onmessage = (event) => {
      const data: ProgressEvent = JSON.parse(event.data)
      store.handleProgressEvent(data)
    }
  }

  const disconnect = () => {
    ws.value?.close()
    ws.value = null
  }

  watch(runId, (newId, oldId) => {
    if (oldId) disconnect()
    if (newId) connect()
  })

  onUnmounted(disconnect)

  return { connect, disconnect }
}
```

### 6.2 进度事件处理

```typescript
// workspaceStore.ts

handleProgressEvent(event: ProgressEvent) {
  this.progressEvents.push(event)

  switch (event.event_type) {
    case 'started':
      this.currentRun!.status = 'running'
      break

    case 'step_started':
      this.stepStatuses[event.step_id!] = 'running'
      this.currentRun!.current_step_id = event.step_id
      break

    case 'step_completed':
      this.stepStatuses[event.step_id!] = 'completed'
      if (event.artifact_id) {
        this.loadArtifact(event.artifact_id)
      }
      break

    case 'completed':
      this.currentRun!.status = 'completed'
      break

    case 'failed':
      this.currentRun!.status = 'failed'
      this.currentRun!.error_message = event.message
      break

    case 'paused':
      this.currentRun!.status = 'paused'
      break
  }
}
```

---

## 七、实施计划

### 7.1 分阶段实施

| 阶段 | 内容 | 依赖 |
|------|------|------|
| 3.1 | 创建设计文档（本文档） | - |
| 3.2 | 三栏布局容器 + 路由配置 | - |
| 3.3 | 工作流面板（列表 + 步骤树） | Phase 2 API |
| 3.4 | 数据产物面板（列表 + 预览） | Phase 1 API |
| 3.5 | 主画布（多视图 + 复用 PanelBoard） | 现有组件 |
| 3.6 | 对话交互区 + WebSocket 集成 | 后端 API |

### 7.2 后端 API 需求

需要新增以下后端端点：

```python
# api/routers/workflow.py（新增）

@router.get("/workflows")
async def list_workflows() -> List[WorkflowResponse]

@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str) -> WorkflowResponse

@router.post("/workflows")
async def create_workflow(data: WorkflowCreate) -> WorkflowResponse

@router.post("/workflows/{workflow_id}/run")
async def start_run(workflow_id: str, variables: Dict) -> WorkflowRunResponse

@router.post("/runs/{run_id}/pause")
async def pause_run(run_id: str) -> WorkflowRunResponse

@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str) -> WorkflowRunResponse

@router.get("/artifacts")
async def list_artifacts(workflow_id: str = None) -> List[ArtifactResponse]

@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str) -> ArtifactResponse

# WebSocket 端点
@router.websocket("/ws/workflow/{run_id}")
async def workflow_progress_ws(websocket: WebSocket, run_id: str)
```

---

## 八、待确认问题

| 问题 | 选项 A | 选项 B | 建议 |
|------|--------|--------|------|
| **对话区位置** | 主画布底部（固定） | 浮动输入框（可拖动） | A: 固定更直观 | A
| **产物预览方式** | 右侧面板内预览 | 中间画布预览 | B: 画布空间更大 | B
| **工作流列表位置** | 左侧面板顶部 | 独立页面选择 | A: 快速切换 | A
| **步骤依赖可视化** | 竖向列表 + 连线 | DAG 图形化 | A: 先简单实现 | A

---

## 九、TODO 清单

- [x] 用户确认设计方案 (2025-12-09)
- [x] Phase 3.1: 创建目录结构 (2025-12-09)
- [x] Phase 3.2: 实现 WorkspaceView + WorkspaceLayout (2025-12-09)
- [x] Phase 3.3: 实现 WorkflowPanel 组件 (2025-12-09)
- [x] Phase 3.4: 实现 ArtifactPanel 组件 (2025-12-09)
- [x] Phase 3.5: 实现 MainCanvas + 视图切换 (2025-12-09)
- [x] Phase 3.6: 实现 ChatInteractionArea (2025-12-09)
- [x] Phase 3.7: 后端 API schemas (2025-12-09)
- [x] Phase 3.8: 后端 API router (2025-12-09)
- [x] Phase 3.9: WebSocket 进度推送 (2025-12-09)
- [x] Phase 3.10: 前端 API 集成 (2025-12-09)

---

## 十、设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 对话区位置 | 主画布底部（固定） | 更直观，用户视线自然流动 |
| 产物预览方式 | 中间画布预览 | 画布空间更大，可充分展示数据 |
| 工作流列表位置 | 左侧面板顶部 | 快速切换，符合常见 IDE 布局 |
| 步骤依赖可视化 | 竖向列表 + 连线 | 先简单实现，后续可扩展为 DAG 图 |

---

## 十一、实施进度

### 已完成的前端组件

| 文件 | 说明 |
|------|------|
| `views/WorkspaceView.vue` | 工作台主视图 |
| `features/workspace/index.ts` | 模块导出 |
| `features/workspace/WorkspaceLayout.vue` | 三栏布局容器 |
| `features/workspace/stores/workspaceStore.ts` | Pinia 状态管理 |
| `features/workspace/types/workspace.ts` | TypeScript 类型定义 |
| `features/workspace/components/workflow/WorkflowPanel.vue` | 工作流面板 |
| `features/workspace/components/workflow/WorkflowListItem.vue` | 工作流列表项 |
| `features/workspace/components/workflow/WorkflowStepTree.vue` | 步骤树 |
| `features/workspace/components/canvas/MainCanvas.vue` | 主画布 |
| `features/workspace/components/canvas/CanvasEmptyState.vue` | 空状态 |
| `features/workspace/components/canvas/ChatInteractionArea.vue` | 对话交互区 |
| `features/workspace/components/artifact/ArtifactPanel.vue` | 数据产物面板 |
| `features/workspace/components/artifact/ArtifactListItem.vue` | 产物列表项 |
| `features/workspace/components/artifact/ArtifactPreview.vue` | 产物预览 |

### 路由配置

```
/workspace                    - 工作台主页
/workspace/:workflowId        - 指定工作流
/workspace/:workflowId/run/:runId - 指定执行实例
```

### 后端实现

1. **API Schemas** (`api/schemas/workflow.py`)
   - WorkflowCreate/Update/Response
   - RunCreate/Response
   - ArtifactSchema
   - ProgressEventSchema

2. **API Controller** (`api/controllers/workflow_controller.py`)
   - 工作流 CRUD：GET/POST/PATCH/DELETE /api/v1/workflows
   - 执行管理：POST runs, pause, resume, cancel
   - 产物查询：GET artifacts, artifact data
   - WebSocket：GET /stream 进度推送

3. **前端 API 集成** (`features/workspace/services/workspaceApi.ts`)
   - 所有 REST API 封装
   - WebSocket 连接管理 (connectProgressStream)
   - workspaceStore 已集成 API 调用
