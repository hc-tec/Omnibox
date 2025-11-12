# LangGraph Agents 前端实现方案

## 技术约束

**必须遵循**：
- ✅ Vue 3 + TypeScript + Composition API
- ✅ shadcn-vue（UI 组件）
- ✅ Pinia（状态管理）
- ✅ Tailwind CSS（样式）
- ❌ **禁止使用 React 语法或其他框架**

---

## 设计理念

基于 `docs/langgraph-agents-frontend-design.md`：

**三位一体设计**：
1. **Omnibox**：全局命令输入（支持模式选择）
2. **Live Cards**：实时展示研究过程（动态卡片）
3. **Action Inbox**：异步处理人机交互（侧边栏）

---

## 实现计划

### 阶段 1：基础架构（核心）

#### 1.1 创建类型定义

**文件**: `frontend/src/features/research/types/researchTypes.ts`

```typescript
/**
 * 研究类型定义
 */

/** 查询模式 */
export type QueryMode = 'auto' | 'simple' | 'research';

/** 研究任务状态 */
export type ResearchTaskStatus =
  | 'idle'          // 空闲
  | 'processing'    // 处理中
  | 'human_in_loop' // 等待人工输入
  | 'completed'     // 完成
  | 'error';        // 错误

/** LangGraph 节点名称 */
export type LangGraphNode =
  | 'router'
  | 'simple_chat'
  | 'planner'
  | 'tool_executor'
  | 'data_stasher'
  | 'reflector'
  | 'synthesizer'
  | 'wait_for_human';

/** 执行步骤 */
export interface ExecutionStep {
  step_id: number;
  node: LangGraphNode;
  action: string;
  status: 'success' | 'error' | 'in_progress';
  timestamp: string;
}

/** 研究任务 */
export interface ResearchTask {
  task_id: string;
  query: string;
  mode: QueryMode;
  status: ResearchTaskStatus;
  execution_steps: ExecutionStep[];
  final_report?: string;
  human_request?: {
    message: string;
    timestamp: string;
  };
  error?: string;
  created_at: string;
  updated_at: string;
}

/** API 响应 */
export interface ResearchResponse {
  success: boolean;
  message: string;
  metadata?: {
    mode: string;
    total_steps: number;
    execution_steps: ExecutionStep[];
    data_stash_count?: number;
  };
}

/** WebSocket 消息 */
export interface ResearchWebSocketMessage {
  type: 'step' | 'human_in_loop' | 'complete' | 'error';
  task_id: string;
  data?: any;
}
```

#### 1.2 创建 Pinia Store

**文件**: `frontend/src/features/research/stores/researchStore.ts`

```typescript
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { ResearchTask, QueryMode, ResearchWebSocketMessage } from '../types/researchTypes';

export const useResearchStore = defineStore('research', () => {
  // 状态
  const tasks = ref<Map<string, ResearchTask>>(new Map());
  const activeTaskId = ref<string | null>(null);
  const queryMode = ref<QueryMode>('auto');

  // 计算属性
  const activeTasks = computed(() =>
    Array.from(tasks.value.values()).filter(
      t => t.status === 'processing' || t.status === 'human_in_loop'
    )
  );

  const completedTasks = computed(() =>
    Array.from(tasks.value.values()).filter(
      t => t.status === 'completed'
    )
  );

  const pendingHumanTasks = computed(() =>
    Array.from(tasks.value.values()).filter(
      t => t.status === 'human_in_loop'
    )
  );

  const pendingCount = computed(() => pendingHumanTasks.value.length);

  // Actions
  function createTask(query: string, mode: QueryMode): string {
    const taskId = `task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const task: ResearchTask = {
      task_id: taskId,
      query,
      mode,
      status: 'processing',
      execution_steps: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    tasks.value.set(taskId, task);
    activeTaskId.value = taskId;
    return taskId;
  }

  function updateTaskStep(taskId: string, step: any) {
    const task = tasks.value.get(taskId);
    if (task) {
      task.execution_steps.push(step);
      task.updated_at = new Date().toISOString();
    }
  }

  function setTaskHumanRequest(taskId: string, message: string) {
    const task = tasks.value.get(taskId);
    if (task) {
      task.status = 'human_in_loop';
      task.human_request = {
        message,
        timestamp: new Date().toISOString(),
      };
      task.updated_at = new Date().toISOString();
    }
  }

  function completeTask(taskId: string, report: string) {
    const task = tasks.value.get(taskId);
    if (task) {
      task.status = 'completed';
      task.final_report = report;
      task.updated_at = new Date().toISOString();
    }
  }

  function setTaskError(taskId: string, error: string) {
    const task = tasks.value.get(taskId);
    if (task) {
      task.status = 'error';
      task.error = error;
      task.updated_at = new Date().toISOString();
    }
  }

  function deleteTask(taskId: string) {
    tasks.value.delete(taskId);
    if (activeTaskId.value === taskId) {
      activeTaskId.value = null;
    }
  }

  function clearCompletedTasks() {
    completedTasks.value.forEach(task => {
      tasks.value.delete(task.task_id);
    });
  }

  return {
    // State
    tasks,
    activeTaskId,
    queryMode,
    // Computed
    activeTasks,
    completedTasks,
    pendingHumanTasks,
    pendingCount,
    // Actions
    createTask,
    updateTaskStep,
    setTaskHumanRequest,
    completeTask,
    setTaskError,
    deleteTask,
    clearCompletedTasks,
  };
});
```

---

### 阶段 2：核心组件实现

#### 2.1 Live Card 组件（研究进度卡片）

**文件**: `frontend/src/features/research/components/ResearchLiveCard.vue`

```vue
<template>
  <Card class="research-live-card" :class="statusClass">
    <CardHeader>
      <div class="flex items-center justify-between">
        <CardTitle class="text-sm flex items-center gap-2">
          <component :is="statusIcon" class="h-4 w-4" />
          {{ task.query }}
        </CardTitle>
        <Badge :variant="badgeVariant">{{ statusText }}</Badge>
      </div>
    </CardHeader>

    <CardContent>
      <!-- 处理中：显示执行步骤 -->
      <div v-if="task.status === 'processing'" class="space-y-2">
        <div
          v-for="step in task.execution_steps"
          :key="step.step_id"
          class="flex items-center gap-2 text-sm"
        >
          <CheckCircle v-if="step.status === 'success'" class="h-4 w-4 text-green-500" />
          <Loader v-else class="h-4 w-4 animate-spin text-blue-500" />
          <span>{{ step.action }}</span>
        </div>
      </div>

      <!-- 等待人工输入：显示提示 -->
      <div v-else-if="task.status === 'human_in_loop'" class="space-y-3">
        <Alert>
          <AlertCircle class="h-4 w-4" />
          <AlertTitle>需要您的输入</AlertTitle>
          <AlertDescription>
            {{ task.human_request?.message }}
          </AlertDescription>
        </Alert>
        <p class="text-xs text-muted-foreground">
          请在右下角的 "行动收件箱" 中回复
        </p>
      </div>

      <!-- 完成：显示最终报告 -->
      <div v-else-if="task.status === 'completed'" class="prose prose-sm max-w-none">
        <p>{{ task.final_report }}</p>
      </div>

      <!-- 错误：显示错误信息 -->
      <div v-else-if="task.status === 'error'">
        <Alert variant="destructive">
          <AlertCircle class="h-4 w-4" />
          <AlertTitle>错误</AlertTitle>
          <AlertDescription>
            {{ task.error }}
          </AlertDescription>
        </Alert>
      </div>
    </CardContent>

    <CardFooter v-if="task.status === 'completed'" class="justify-between">
      <span class="text-xs text-muted-foreground">
        {{ task.execution_steps.length }} 步骤完成
      </span>
      <Button variant="ghost" size="sm" @click="$emit('delete', task.task_id)">
        删除
      </Button>
    </CardFooter>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { CheckCircle, Loader, AlertCircle, Brain, Sparkles } from 'lucide-vue-next';
import type { ResearchTask } from '../types/researchTypes';

interface Props {
  task: ResearchTask;
}

const props = defineProps<Props>();

defineEmits<{
  delete: [taskId: string];
}>();

const statusIcon = computed(() => {
  switch (props.task.status) {
    case 'processing':
      return Loader;
    case 'human_in_loop':
      return Brain;
    case 'completed':
      return CheckCircle;
    case 'error':
      return AlertCircle;
    default:
      return Sparkles;
  }
});

const statusText = computed(() => {
  switch (props.task.status) {
    case 'processing':
      return '处理中';
    case 'human_in_loop':
      return '等待回复';
    case 'completed':
      return '已完成';
    case 'error':
      return '错误';
    default:
      return '空闲';
  }
});

const badgeVariant = computed(() => {
  switch (props.task.status) {
    case 'processing':
      return 'default';
    case 'human_in_loop':
      return 'secondary';
    case 'completed':
      return 'outline';
    case 'error':
      return 'destructive';
    default:
      return 'outline';
  }
});

const statusClass = computed(() => ({
  'border-blue-500': props.task.status === 'processing',
  'border-yellow-500': props.task.status === 'human_in_loop',
  'border-green-500': props.task.status === 'completed',
  'border-red-500': props.task.status === 'error',
}));
</script>

<style scoped>
.research-live-card {
  @apply border-2 transition-colors;
}
</style>
```

#### 2.2 Action Inbox 组件（行动收件箱）

**文件**: `frontend/src/features/research/components/ActionInbox.vue`

```vue
<template>
  <!-- FAB 按钮（魔棒） -->
  <div class="fixed bottom-6 right-6 z-50">
    <Button
      size="icon"
      class="h-14 w-14 rounded-full shadow-lg relative"
      @click="toggleInbox"
    >
      <Wand2 class="h-6 w-6" />
      <Badge
        v-if="pendingCount > 0"
        class="absolute -top-1 -right-1 h-6 w-6 rounded-full p-0 flex items-center justify-center"
        variant="destructive"
      >
        {{ pendingCount }}
      </Badge>
    </Button>
  </div>

  <!-- 侧边栏 -->
  <Transition name="slide">
    <div
      v-if="isOpen"
      class="fixed top-0 right-0 h-screen w-96 bg-background border-l shadow-2xl z-40 flex flex-col"
    >
      <!-- Header -->
      <div class="p-4 border-b flex items-center justify-between">
        <h2 class="text-lg font-semibold flex items-center gap-2">
          <Inbox class="h-5 w-5" />
          行动收件箱
          <Badge v-if="pendingCount > 0" variant="secondary">
            {{ pendingCount }}
          </Badge>
        </h2>
        <Button variant="ghost" size="icon" @click="closeInbox">
          <X class="h-4 w-4" />
        </Button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto p-4 space-y-4">
        <div v-if="pendingTasks.length === 0" class="text-center py-8 text-muted-foreground">
          <CheckCircle class="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>太棒了！没有待处理的任务</p>
        </div>

        <Card v-for="task in pendingTasks" :key="task.task_id" class="border-yellow-500">
          <CardHeader>
            <CardTitle class="text-sm">{{ task.query }}</CardTitle>
          </CardHeader>
          <CardContent class="space-y-3">
            <Alert>
              <Brain class="h-4 w-4" />
              <AlertTitle>助手提问</AlertTitle>
              <AlertDescription>
                {{ task.human_request?.message }}
              </AlertDescription>
            </Alert>

            <Textarea
              v-model="responses[task.task_id]"
              placeholder="在此输入您的回复..."
              class="min-h-20"
            />
          </CardContent>
          <CardFooter class="justify-end gap-2">
            <Button variant="outline" size="sm" @click="skipTask(task.task_id)">
              跳过
            </Button>
            <Button
              size="sm"
              :disabled="!responses[task.task_id]"
              @click="submitResponse(task.task_id)"
            >
              回复
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  </Transition>

  <!-- 遮罩层 -->
  <Transition name="fade">
    <div
      v-if="isOpen"
      class="fixed inset-0 bg-black/20 z-30"
      @click="closeInbox"
    />
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Textarea } from '@/components/ui/textarea';
import { Wand2, Inbox, X, Brain, CheckCircle } from 'lucide-vue-next';
import { useResearchStore } from '../stores/researchStore';

const researchStore = useResearchStore();

const isOpen = ref(false);
const responses = ref<Record<string, string>>({});

const pendingTasks = computed(() => researchStore.pendingHumanTasks);
const pendingCount = computed(() => researchStore.pendingCount);

function toggleInbox() {
  isOpen.value = !isOpen.value;
}

function closeInbox() {
  isOpen.value = false;
}

async function submitResponse(taskId: string) {
  const response = responses.value[taskId];
  if (!response) return;

  try {
    // TODO: 发送响应到后端
    // await api.submitHumanResponse(taskId, response);

    // 清空输入
    delete responses.value[taskId];

    // 更新任务状态（实际应由后端 WebSocket 推送）
    researchStore.completeTask(taskId, '继续处理中...');
  } catch (error) {
    console.error('提交响应失败:', error);
  }
}

function skipTask(taskId: string) {
  // 标记任务为跳过（可选实现）
  delete responses.value[taskId];
}
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}

.slide-enter-from {
  transform: translateX(100%);
}

.slide-leave-to {
  transform: translateX(100%);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
```

#### 2.3 研究模式选择器

**文件**: `frontend/src/features/research/components/QueryModeSelector.vue`

```vue
<template>
  <div class="flex items-center gap-2">
    <Label class="text-sm text-muted-foreground">模式:</Label>
    <RadioGroup v-model="selectedMode" class="flex gap-1">
      <div class="flex items-center space-x-1">
        <RadioGroupItem value="auto" id="mode-auto" />
        <Label for="mode-auto" class="text-sm cursor-pointer">自动</Label>
      </div>
      <div class="flex items-center space-x-1">
        <RadioGroupItem value="simple" id="mode-simple" />
        <Label for="mode-simple" class="text-sm cursor-pointer">简单</Label>
      </div>
      <div class="flex items-center space-x-1">
        <RadioGroupItem value="research" id="mode-research" />
        <Label for="mode-research" class="text-sm cursor-pointer">研究</Label>
      </div>
    </RadioGroup>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import type { QueryMode } from '../types/researchTypes';

interface Props {
  modelValue: QueryMode;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  'update:modelValue': [value: QueryMode];
}>();

const selectedMode = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});
</script>
```

---

### 阶段 3：API 服务层

**文件**: `frontend/src/features/research/services/researchApi.ts`

```typescript
import axios from 'axios';
import type { QueryMode, ResearchResponse } from '../types/researchTypes';

const API_BASE = '/api/v1';

export const researchApi = {
  /**
   * 发起研究查询
   */
  async submitQuery(query: string, mode: QueryMode): Promise<ResearchResponse> {
    const response = await axios.post<ResearchResponse>(`${API_BASE}/chat`, {
      query,
      mode,
    });
    return response.data;
  },

  /**
   * 提交人工响应
   */
  async submitHumanResponse(taskId: string, response: string): Promise<void> {
    await axios.post(`${API_BASE}/research/human-response`, {
      task_id: taskId,
      response,
    });
  },

  /**
   * 取消研究任务
   */
  async cancelTask(taskId: string): Promise<void> {
    await axios.post(`${API_BASE}/research/cancel`, {
      task_id: taskId,
    });
  },
};
```

---

### 阶段 4：集成到 App.vue

**文件**: `frontend/src/App.vue` (更新)

```vue
<template>
  <div class="app-container">
    <!-- 主面板区域 -->
    <div class="main-panel">
      <!-- Omnibox（查询输入框） -->
      <div class="omnibox-container">
        <QueryModeSelector v-model="queryMode" />
        <Textarea
          v-model="userQuery"
          placeholder="输入您的问题..."
          @keydown.enter.ctrl="handleSubmit"
        />
        <Button @click="handleSubmit" :disabled="!userQuery.trim()">
          生成面板
        </Button>
      </div>

      <!-- 研究任务卡片（Live Cards） -->
      <div class="research-cards-grid">
        <ResearchLiveCard
          v-for="task in activeTasks"
          :key="task.task_id"
          :task="task"
          @delete="handleDeleteTask"
        />
      </div>

      <!-- 原有的面板布局（保持不变） -->
      <div class="existing-panels">
        <!-- ... 原有代码 ... -->
      </div>
    </div>

    <!-- Action Inbox（行动收件箱） -->
    <ActionInbox />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import QueryModeSelector from '@/features/research/components/QueryModeSelector.vue';
import ResearchLiveCard from '@/features/research/components/ResearchLiveCard.vue';
import ActionInbox from '@/features/research/components/ActionInbox.vue';
import { useResearchStore } from '@/features/research/stores/researchStore';
import { researchApi } from '@/features/research/services/researchApi';
import type { QueryMode } from '@/features/research/types/researchTypes';

const researchStore = useResearchStore();

const userQuery = ref('');
const queryMode = ref<QueryMode>('auto');

const activeTasks = computed(() => researchStore.activeTasks);

async function handleSubmit() {
  if (!userQuery.value.trim()) return;

  const query = userQuery.value;
  const mode = queryMode.value;

  // 创建任务
  const taskId = researchStore.createTask(query, mode);

  // 清空输入框
  userQuery.value = '';

  try {
    // 发送请求
    const response = await researchApi.submitQuery(query, mode);

    // 处理响应
    if (response.success) {
      if (response.metadata?.mode === 'research') {
        // 研究模式：更新步骤
        response.metadata.execution_steps?.forEach(step => {
          researchStore.updateTaskStep(taskId, step);
        });
      }

      // 完成任务
      researchStore.completeTask(taskId, response.message);
    } else {
      researchStore.setTaskError(taskId, response.message);
    }
  } catch (error) {
    researchStore.setTaskError(
      taskId,
      `请求失败: ${error instanceof Error ? error.message : '未知错误'}`
    );
  }
}

function handleDeleteTask(taskId: string) {
  researchStore.deleteTask(taskId);
}
</script>

<style scoped>
.app-container {
  @apply h-screen flex flex-col p-4;
}

.omnibox-container {
  @apply mb-4 space-y-2;
}

.research-cards-grid {
  @apply grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4;
}
</style>
```

---

## 实施步骤

### 步骤 1：安装缺失的 UI 组件

```bash
cd frontend

# 安装 shadcn-vue 缺失的组件
npx shadcn-vue@latest add radio-group
npx shadcn-vue@latest add textarea
npx shadcn-vue@latest add label

# 安装 lucide-vue-next（图标库）
npm install lucide-vue-next
```

### 步骤 2：创建文件结构

```bash
mkdir -p src/features/research/{components,stores,services,types}

# 创建文件
touch src/features/research/types/researchTypes.ts
touch src/features/research/stores/researchStore.ts
touch src/features/research/components/ResearchLiveCard.vue
touch src/features/research/components/ActionInbox.vue
touch src/features/research/components/QueryModeSelector.vue
touch src/features/research/services/researchApi.ts
```

### 步骤 3：复制代码

将上述代码复制到对应文件中。

### 步骤 4：测试

```bash
# 启动开发服务器
npm run dev

# 测试功能
# 1. 输入查询
# 2. 选择"研究"模式
# 3. 查看 Live Card 实时更新
# 4. 测试 Action Inbox（如果有 HIL 场景）
```

---

## 可选增强

### WebSocket 实时推送（推荐）

如果需要真正的实时进度推送，需要：

1. **后端实现 WebSocket**（参考 `langgraph-agents-integration-plan.md` 阶段 4）
2. **前端添加 WebSocket 客户端**：

```typescript
// frontend/src/features/research/services/researchWebSocket.ts
export class ResearchWebSocket {
  private ws: WebSocket | null = null;

  connect(taskId: string, onMessage: (msg: ResearchWebSocketMessage) => void) {
    this.ws = new WebSocket(`ws://localhost:8000/api/v1/research/stream`);

    this.ws.onopen = () => {
      this.ws?.send(JSON.stringify({ task_id: taskId }));
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      onMessage(message);
    };
  }

  disconnect() {
    this.ws?.close();
    this.ws = null;
  }
}
```

---

## 总结

### 已实现
✅ 类型定义（researchTypes.ts）
✅ Pinia Store（状态管理）
✅ Live Card 组件（实时进度）
✅ Action Inbox 组件（异步交互）
✅ Query Mode Selector（模式选择）
✅ API 服务层
✅ App.vue 集成示例

### 技术栈验证
✅ Vue 3 + TypeScript + Composition API
✅ shadcn-vue（Card, Badge, Alert, Button, Textarea, RadioGroup）
✅ Pinia（状态管理）
✅ Tailwind CSS（样式）
✅ lucide-vue-next（图标）

### 下一步
1. 安装缺失的 UI 组件
2. 创建文件并复制代码
3. 测试基本功能
4. （可选）实现 WebSocket 实时推送

---

## 参考文档
- `docs/langgraph-agents-frontend-design.md` - 前端设计理念
- `.agentdocs/frontend-architecture.md` - 技术约束
- `.agentdocs/workflow/langgraph-agents-integration-usage.md` - 后端集成
