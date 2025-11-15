# 统一工作区架构设计方案

**创建日期**：2025-11-15
**状态**：设计方案（待评审）
**优先级**：P1（架构优化，影响用户体验）

---

## 背景与问题分析

### 当前架构的"割裂"问题

#### 问题 1：研究卡片与普通面板完全分离

**现象**：
- 研究查询：生成研究卡片 → 用户点击 → 跳转到专属研究视图
- 普通查询：直接在主界面底部显示面板，无卡片、无历史记录

**问题**：
1. **无统一历史记录** - 普通查询没有任何记录，用户无法回溯
2. **交互模式不一致** - 研究模式有卡片可点击，普通模式只能看当前结果
3. **信息孤岛** - 两种模式的数据分别存储，无法统一管理

#### 问题 2：用户无法感知查询进度

**现象**：
- 用户点击提交 → 等待 3-5 秒 → 突然出现结果面板
- 期间没有任何视觉反馈，用户不知道发生了什么

**问题**：
1. **违反 0.1s 响应法则** - 用户操作后超过 100ms 才有反馈，体验差
2. **无进度可视化** - 后端正在执行 RAG、LLM、数据获取，但前端看不到
3. **无法判断是否卡死** - 用户不知道是系统在处理还是出错了

#### 问题 3：普通查询缺少身份信息

**现象**：
- 研究卡片有明确的查询文本、时间戳、模式标识、触发来源
- 普通查询结果只是一堆面板，看不出这是对哪个问题的回答

**问题**：
1. **上下文丢失** - 多次查询后，用户忘记了每个结果对应什么问题
2. **无法追溯** - 关闭窗口后，无法找回之前的查询结果
3. **无法分享** - 无法将某个查询结果截图/分享给他人（缺少关键上下文）

### 行业对比分析

| 产品 | 查询历史 | 进度反馈 | 身份信息 | 交互模式 |
|------|---------|---------|---------|---------|
| **Notion** | 所有块都有编辑历史 | 加载时显示骨架屏 | 块标题 + 时间戳 | 统一工作区，所有内容都是可点击块 |
| **Linear** | 所有 Issue 都有 Activity 记录 | 实时同步状态 | Issue 标题 + 编号 + 状态 | 统一列表，所有 Issue 都是卡片 |
| **Figma** | 文件历史 + 版本控制 | 加载时显示占位符 | 文件名 + 最后修改时间 | 统一画布，所有元素都可选中 |
| **Omnibox（当前）** | ❌ 普通查询无历史 | ❌ 无进度反馈 | ❌ 普通查询无身份 | ❌ 两种交互模式分离 |

**结论**：现代知识工作工具都采用"统一工作区"模式，所有交互对象都有一致的表现形式和管理方式。

---

## 解决方案：统一卡片工作区

### 核心设计理念

**"所有查询都是卡片，所有卡片都有生命周期"**

- ✅ **统一表现形式** - 研究查询和普通查询都生成卡片
- ✅ **统一生命周期** - 所有卡片都经历 `pending → processing → completed` 流程
- ✅ **统一交互模式** - 所有卡片都可点击、删除、展开详情
- ✅ **统一历史记录** - 所有查询都保存在工作区，可随时回溯

### 架构设计图

```
用户输入查询
     ↓
立即生成卡片（0.1s 内）
     │
     ├─ 卡片 Header（身份信息）
     │   ├─ 查询文本："科技美学最近在 B 站有什么新视频？"
     │   ├─ 时间戳：2025-11-15 14:32
     │   ├─ 模式标识：普通查询 / 研究模式
     │   └─ 触发来源：手动输入 / 快捷键 / API
     │
     ├─ 卡片 Body（内容区域）
     │   ├─ pending 状态：骨架屏（灰色占位块）
     │   ├─ processing 状态：实时进度（RAG → LLM → 数据获取）
     │   └─ completed 状态：实际数据面板（列表/图表/统计卡）
     │
     └─ 卡片 Footer（操作区域）
         ├─ 刷新按钮（复用元数据，快速刷新）
         ├─ 展开详情（跳转到专属视图）
         └─ 删除按钮
```

### 卡片生命周期状态机

```
┌─────────┐   用户提交查询   ┌────────────┐   开始执行   ┌─────────────┐   执行完成   ┌───────────┐
│  (无)   │ ──────────────→ │  pending   │ ──────────→ │ processing  │ ──────────→ │ completed │
└─────────┘                 └────────────┘             └─────────────┘             └───────────┘
                                   │                          │                           │
                                   │                          │ 执行失败                  │
                                   │                          ↓                           │
                                   │                    ┌─────────┐                       │
                                   │ 提交失败（罕见）   │  error  │                       │
                                   └──────────────────→ └─────────┘                       │
                                                              ↑                           │
                                                              │                           │
                                                              └───────────────────────────┘
                                                                    用户点击重试

状态说明：
- pending：卡片已创建，等待后端开始处理（持续时间：< 100ms）
- processing：后端正在执行（RAG/LLM/数据获取），前端显示实时进度（持续时间：3-10s）
- completed：执行成功，显示最终结果（持久状态）
- error：执行失败，显示错误信息 + 重试按钮（持久状态，可转回 processing）
```

### 不同查询模式的卡片差异

| 特性 | 普通查询卡片 | 研究查询卡片 |
|------|-------------|-------------|
| **生成时机** | 提交后立即生成 | 提交后立即生成 |
| **Header 内容** | 查询文本 + 时间戳 + "普通查询" Badge | 查询文本 + 时间戳 + "研究模式" Badge |
| **Processing 内容** | 单一进度条（"正在查询..."） | 详细步骤列表（RAG → 规划 → 执行子查询 → 生成报告） |
| **Completed 内容** | 嵌入式面板（最多 3-5 个） | 面板预览 + "查看完整报告"按钮 |
| **点击行为** | 展开/折叠卡片（inline） | 跳转到专属研究视图 |
| **刷新逻辑** | 快速路径（0.5-1.5s，复用元数据） | 完整路径（3-10s，重新执行研究） |

---

## 即时反馈设计（0.1s 响应法则）

### 设计原则

**用户操作后 100 毫秒内必须有视觉反馈，否则会感知到延迟。**

参考资料：
- [Nielsen Norman Group - Response Times](https://www.nngroup.com/articles/response-times-3-important-limits/)
- [Google Web Vitals - First Input Delay](https://web.dev/fid/)

### 实施细节

#### 1. 点击提交 → 立即生成卡片（前端同步操作）

```typescript
async function handleCommandSubmit(payload: { query: string; mode: QueryMode }) {
  // Step 1: 立即生成卡片（0.05s 内完成）
  const taskId = generateUUID();
  const card = {
    id: taskId,
    query: payload.query,
    mode: payload.mode,
    status: 'pending',  // ← 关键：立即显示 pending 状态
    created_at: new Date().toISOString(),
    trigger_source: 'manual_input',
  };

  // Step 2: 添加到工作区（触发 Vue 响应式更新，0.02s 内渲染）
  workspaceStore.addCard(card);

  // Step 3: 异步提交到后端（不阻塞 UI）
  submitToBackend(taskId, payload).catch(error => {
    // 提交失败时更新卡片状态为 error
    workspaceStore.updateCardStatus(taskId, 'error', error.message);
  });
}
```

**效果**：用户点击后 < 100ms 即可看到新卡片出现在工作区顶部。

#### 2. Pending 状态骨架屏设计

```vue
<template>
  <div v-if="card.status === 'pending'" class="skeleton-container space-y-3 p-4">
    <!-- 标题骨架 -->
    <div class="h-5 w-3/4 animate-pulse rounded-lg bg-muted/50" />

    <!-- 内容骨架（3 行） -->
    <div class="space-y-2">
      <div class="h-4 w-full animate-pulse rounded bg-muted/30" />
      <div class="h-4 w-5/6 animate-pulse rounded bg-muted/30" />
      <div class="h-4 w-4/6 animate-pulse rounded bg-muted/30" />
    </div>

    <!-- 底部操作区骨架 -->
    <div class="flex gap-2">
      <div class="h-8 w-20 animate-pulse rounded-lg bg-muted/40" />
      <div class="h-8 w-16 animate-pulse rounded-lg bg-muted/40" />
    </div>
  </div>
</template>
```

**设计要点**：
- 使用 `animate-pulse` 提供"正在加载"的视觉暗示
- 骨架屏布局与实际内容布局一致，避免内容闪烁（Layout Shift）
- 使用渐变透明度（`bg-muted/50` → `bg-muted/30`）提供层次感

#### 3. Processing 状态实时进度更新

```typescript
// 后端通过 WebSocket 推送进度消息
interface ProgressMessage {
  task_id: string;
  type: 'progress';
  step: string;  // "RAG 检索中..." / "LLM 规划中..." / "获取数据中..."
  progress: number;  // 0-100
  timestamp: string;
}

// 前端接收并更新卡片
wsManager.onMessage((msg: ProgressMessage) => {
  workspaceStore.updateCardProgress(msg.task_id, {
    current_step: msg.step,
    progress: msg.progress,
  });
});
```

```vue
<template>
  <div v-if="card.status === 'processing'" class="processing-container space-y-3">
    <div class="flex items-center gap-2 text-sm">
      <Loader class="h-4 w-4 animate-spin text-blue-500" />
      <span class="text-muted-foreground">{{ card.current_step }}</span>
    </div>

    <!-- 进度条 -->
    <div class="h-1 w-full overflow-hidden rounded-full bg-muted">
      <div
        class="h-full bg-blue-500 transition-all duration-300"
        :style="{ width: `${card.progress}%` }"
      />
    </div>
  </div>
</template>
```

**关键设计**：
- 每个后端操作（RAG/LLM/数据获取）都推送进度消息
- 进度条平滑过渡（`transition-all duration-300`）
- 显示当前步骤文本，让用户知道系统在做什么

---

## 卡片身份信息设计

### Header 结构

```vue
<div class="card-header flex items-start justify-between p-4">
  <!-- 左侧：查询信息 -->
  <div class="flex-1 space-y-2">
    <!-- 查询文本（可折叠） -->
    <h3 class="text-sm font-semibold text-foreground line-clamp-2">
      {{ card.query }}
    </h3>

    <!-- 元信息标签 -->
    <div class="flex items-center gap-2 text-xs">
      <!-- 模式标识 -->
      <Badge :variant="card.mode === 'research' ? 'default' : 'secondary'">
        {{ card.mode === 'research' ? '研究模式' : '普通查询' }}
      </Badge>

      <!-- 相对时间戳 -->
      <span class="text-muted-foreground">
        {{ formatRelativeTime(card.created_at) }}
      </span>

      <!-- 触发来源（可选） -->
      <Badge v-if="card.trigger_source === 'api'" variant="outline" class="text-[10px]">
        API
      </Badge>
    </div>
  </div>

  <!-- 右侧：状态图标 -->
  <div class="flex-shrink-0">
    <div
      class="flex h-10 w-10 items-center justify-center rounded-xl transition-all"
      :class="statusIconClass"
    >
      <component :is="statusIcon" class="h-5 w-5" />
    </div>
  </div>
</div>
```

### 相对时间戳实现

```typescript
function formatRelativeTime(timestamp: string): string {
  const now = Date.now();
  const past = new Date(timestamp).getTime();
  const diffMs = now - past;

  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) return '刚刚';
  if (minutes < 60) return `${minutes} 分钟前`;
  if (hours < 24) return `${hours} 小时前`;
  if (days < 7) return `${days} 天前`;

  // 超过 7 天显示绝对时间
  return new Date(timestamp).toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// 每分钟更新一次（Vue 3 示例）
const relativeTime = ref(formatRelativeTime(card.created_at));
const timer = setInterval(() => {
  relativeTime.value = formatRelativeTime(card.created_at);
}, 60000);

onBeforeUnmount(() => clearInterval(timer));
```

---

## 后端支持架构

### 1. 快速刷新机制

#### 问题：用户刷新时不应重新执行 AI 推理

**现象**：
- 用户查询"科技美学最近的视频" → 后端执行 RAG（找到 route_id=123）+ LLM（生成参数）→ 返回结果
- 用户点击"刷新"按钮 → 后端再次执行 RAG + LLM → 浪费 3-5 秒

**期望**：
- 首次查询：完整路径（RAG + LLM + 数据获取）→ 3-5 秒
- 刷新操作：快速路径（复用 route_id，只重新获取数据）→ 0.5-1.5 秒

#### 解决方案：元数据保存与复用

**后端 API 响应增强**：

```python
# services/chat_service.py

class ChatResponse(BaseModel):
    # ... 现有字段 ...

    # 新增字段：刷新元数据
    refresh_metadata: Optional[Dict[str, Any]] = None
    """
    用于快速刷新的元数据，包含：
    - route_id: str - RAG 检索到的路由 ID
    - generated_path: str - LLM 生成的完整路径
    - query_plan: Optional[Dict] - 研究模式的查询计划
    - retrieved_tools: List[Dict] - RAG 检索到的候选工具
    """

# 生成响应时添加元数据
async def generate_response(query: str, mode: str = "auto") -> ChatResponse:
    # ... 执行 RAG + LLM ...

    response.refresh_metadata = {
        "route_id": primary_route.route_id,
        "generated_path": primary_route.path,
        "query_plan": query_plan if mode == "research" else None,
        "retrieved_tools": [
            {"route_id": r.route_id, "name": r.name, "score": r.score}
            for r in rag_result.routes[:5]  # 保存前 5 个候选路由
        ],
        "cache_key": rag_cache_key,  # 可选：用于缓存失效判断
    }

    return response
```

**前端存储元数据**：

```typescript
// stores/workspaceStore.ts

interface Card {
  id: string;
  query: string;
  mode: 'simple' | 'research';
  status: 'pending' | 'processing' | 'completed' | 'error';

  // ... 其他字段 ...

  // 新增：刷新元数据
  refresh_metadata?: {
    route_id: string;
    generated_path: string;
    query_plan?: any;
    retrieved_tools: Array<{ route_id: string; name: string; score: number }>;
  };
}

// 接收后端响应时保存元数据
function handleBackendResponse(taskId: string, response: ChatResponse) {
  const card = getCard(taskId);
  if (card) {
    card.status = 'completed';
    card.panels = response.blocks;
    card.refresh_metadata = response.refresh_metadata;  // ← 保存元数据
  }
}
```

**快速刷新 API 端点**：

```python
# api/controllers/chat.py

@router.post("/chat/refresh")
async def refresh_query(request: RefreshQueryRequest):
    """
    快速刷新查询结果（跳过 RAG 和 LLM，直接获取数据）

    Args:
        task_id: 原始任务 ID
        refresh_metadata: 前端提供的元数据（包含 route_id 和 generated_path）
    """
    metadata = request.refresh_metadata

    # 跳过 RAG 和 LLM，直接使用已知路由
    route = Route(
        route_id=metadata["route_id"],
        path=metadata["generated_path"],
        # ... 其他必要字段 ...
    )

    # 只执行数据获取
    datasets = await data_executor.execute([route])

    # 复用原有的 panel adapter 逻辑
    panels = await panel_adapter.adapt(datasets, query=original_query)

    return ChatResponse(
        message="数据已刷新",
        blocks=panels,
        refresh_metadata=metadata,  # 返回相同的元数据
        mode="refresh",  # 标记为刷新模式
    )
```

**性能对比**：

| 操作 | RAG | LLM | 数据获取 | 总耗时 |
|------|-----|-----|---------|--------|
| **首次查询** | ✅ 200-500ms | ✅ 1-2s | ✅ 0.5-1.5s | **3-5s** |
| **快速刷新** | ❌ 跳过 | ❌ 跳过 | ✅ 0.5-1.5s | **0.5-1.5s** |

**节省时间**：70-80%（从 3-5s 降低到 0.5-1.5s）

### 2. 交互式研究工作流

#### 问题：用户无法干预研究计划

**现象**：
- 研究模式自动生成查询计划 → 立即执行 → 用户无法修改
- 如果计划不合理（子查询太多/方向偏离），用户只能等待完成后重新查询

**期望**：
- 生成计划后，先展示给用户确认
- 用户可以修改子查询、删除不需要的步骤、调整优先级
- 确认后再执行

#### 解决方案：Human-in-the-Loop 工作流

**后端状态机扩展**：

```python
# services/chat_service.py

class ResearchStatus(str, Enum):
    PENDING = "pending"        # 等待开始
    PLANNING = "planning"      # LLM 正在生成计划
    PLAN_REVIEW = "plan_review"  # ← 新增：等待用户确认计划
    EXECUTING = "executing"    # 执行中
    COMPLETED = "completed"    # 已完成
    ERROR = "error"           # 出错

# WebSocket 消息类型扩展
class PlanReviewMessage(BaseModel):
    type: Literal["plan_review"] = "plan_review"
    task_id: str
    query_plan: Dict[str, Any]
    """
    {
      "main_query": "科技美学近期动态分析",
      "sub_queries": [
        {"id": "sq1", "query": "科技美学最近的视频", "priority": "high"},
        {"id": "sq2", "query": "科技美学的粉丝增长趋势", "priority": "medium"},
        {"id": "sq3", "query": "科技美学的评论热点话题", "priority": "low"}
      ],
      "estimated_time": "预计耗时 5-8 分钟"
    }
    """
    message: str = "研究计划已生成，请确认后执行"

# 用户响应消息（前端 → 后端）
class UserPlanResponseMessage(BaseModel):
    type: Literal["user_plan_response"] = "user_plan_response"
    task_id: str
    action: Literal["approve", "reject", "modify"]
    modified_plan: Optional[Dict[str, Any]] = None
    """
    用户确认/修改/取消研究计划的响应消息

    - action="approve": 用户确认计划，使用原始计划执行
    - action="modify": 用户修改了计划，使用 modified_plan 执行
    - action="reject": 用户取消计划，终止研究任务

    modified_plan 示例（仅当 action="modify" 时需要）：
    {
      "main_query": "科技美学近期动态分析",
      "sub_queries": [
        {"id": "sq1", "query": "科技美学最近的视频（用户修改后）", "priority": "high"},
        {"id": "sq2", "query": "新增的子查询", "priority": "medium"}
      ]
    }
    """

# 研究服务流程修改
async def execute_research(task_id: str, query: str) -> AsyncIterator[dict]:
    # Step 1: 生成计划
    yield {"type": "status", "status": "planning", "message": "正在生成研究计划..."}
    query_plan = await llm_planner.generate_plan(query)

    # Step 2: 等待用户确认
    yield {
        "type": "plan_review",
        "task_id": task_id,
        "query_plan": query_plan,
        "message": "研究计划已生成，请确认后执行"
    }

    # Step 3: 阻塞等待用户响应（使用 asyncio.Event + 超时控制）
    try:
        user_response = await wait_for_user_confirmation(task_id, timeout=300)  # 5 分钟超时
    except asyncio.TimeoutError:
        # 超时后自动取消任务
        yield {
            "type": "error",
            "task_id": task_id,
            "error": "等待用户确认超时（5 分钟），研究任务已取消"
        }
        return

    if user_response.action in ("approve", "modify"):
        # 使用用户确认的计划（可能已修改）
        final_plan = user_response.modified_plan if user_response.action == "modify" else query_plan
        yield {"type": "status", "status": "executing", "message": "开始执行研究..."}
        # ... 执行子查询 ...

    elif user_response.action == "reject":
        yield {
            "type": "error",
            "task_id": task_id,
            "error": "用户取消了研究任务"
        }
        return
```

**前端交互流程**：

```vue
<template>
  <div v-if="card.status === 'plan_review'" class="plan-review-container space-y-4">
    <!-- 计划预览 -->
    <div class="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
      <h4 class="text-sm font-semibold text-foreground mb-3">
        研究计划（预计耗时 {{ plan.estimated_time }}）
      </h4>

      <ul class="space-y-2">
        <li
          v-for="subQuery in plan.sub_queries"
          :key="subQuery.id"
          class="flex items-start gap-3"
        >
          <!-- 拖拽手柄（可调整顺序） -->
          <GripVertical class="h-4 w-4 text-muted-foreground cursor-move" />

          <!-- 子查询内容（可编辑） -->
          <input
            v-model="subQuery.query"
            class="flex-1 rounded border border-border/40 bg-background px-2 py-1 text-xs"
          />

          <!-- 优先级标签 -->
          <Badge :variant="getPriorityVariant(subQuery.priority)">
            {{ subQuery.priority }}
          </Badge>

          <!-- 删除按钮 -->
          <button @click="removeSubQuery(subQuery.id)" class="text-destructive">
            <X class="h-4 w-4" />
          </button>
        </li>
      </ul>

      <!-- 添加子查询按钮 -->
      <Button variant="outline" size="sm" class="mt-3" @click="addSubQuery">
        <Plus class="mr-1.5 h-3.5 w-3.5" />
        添加子查询
      </Button>
    </div>

    <!-- 操作按钮 -->
    <div class="flex gap-3">
      <Button @click="approvePlan" class="flex-1">
        <Check class="mr-1.5 h-4 w-4" />
        确认并开始研究
      </Button>
      <Button variant="outline" @click="rejectPlan">
        取消
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
function approvePlan() {
  // 发送用户确认消息到后端
  wsManager.sendMessage({
    type: 'user_plan_response',
    task_id: card.id,
    action: plan.value === originalPlan ? 'approve' : 'modify',
    modified_plan: plan.value !== originalPlan ? plan.value : undefined,
  });
}

function rejectPlan() {
  wsManager.sendMessage({
    type: 'user_plan_response',
    task_id: card.id,
    action: 'reject',
  });
}
</script>
```

**用户体验优化**：
- 默认计划已经合理，大多数情况下用户直接点击"确认"
- 高级用户可以调整子查询顺序、删除不需要的、添加新的
- 支持拖拽调整优先级
- 显示预计耗时，让用户有心理预期

---

## 实施路线图

### Phase 1: 基础卡片系统（3 天）

**目标**：所有查询都生成卡片，支持 pending/processing/completed 状态。

**任务清单**：
- [ ] 创建 `WorkspaceStore`（管理卡片列表）
- [ ] 实现 `QueryCard` 组件（Header/Body/Footer 结构）
- [ ] 实现即时卡片生成（提交后 < 100ms 显示）
- [ ] 实现骨架屏（pending 状态）
- [ ] 修改 `handleCommandSubmit` 逻辑（先生成卡片，再调用后端）
- [ ] 后端 API 返回 `task_id`（前端用于关联卡片）

**验证标准**：
- 用户提交查询后 < 100ms 看到新卡片
- 卡片显示查询文本、时间戳、模式标识
- 普通查询和研究查询都生成卡片

### Phase 2: 进度反馈与元数据（2 天）

**目标**：Processing 状态显示实时进度，completed 状态保存刷新元数据。

**任务清单**：
- [ ] 后端增加进度推送（WebSocket 消息：`progress`）
- [ ] 前端接收并更新卡片进度
- [ ] 实现进度条 UI
- [ ] 后端响应增加 `refresh_metadata` 字段
- [ ] 前端存储 `refresh_metadata`

**验证标准**：
- 查询执行时显示"RAG 检索中..." / "LLM 规划中..." / "获取数据中..."
- 进度条从 0% 平滑过渡到 100%
- completed 卡片包含 `refresh_metadata`

### Phase 3: 快速刷新功能（2 天）

**目标**：用户点击"刷新"按钮，0.5-1.5s 内更新数据（跳过 RAG/LLM）。

**任务清单**：
- [ ] 实现 `POST /api/v1/chat/refresh` 端点
- [ ] 后端跳过 RAG/LLM，直接使用 `refresh_metadata` 中的 route_id
- [ ] 前端添加"刷新"按钮到卡片 Footer
- [ ] 前端调用刷新 API 并更新卡片数据
- [ ] 添加刷新加载状态（转圈图标）

**验证标准**：
- 首次查询耗时 3-5s
- 刷新操作耗时 0.5-1.5s（节省 70-80% 时间）
- 刷新后数据更新，但元数据不变

### Phase 4: 交互式研究工作流（3 天）

**目标**：研究模式生成计划后，先展示给用户确认，允许修改。

**任务清单**：
- [ ] 后端增加 `plan_review` 状态和对应 WebSocket 消息
- [ ] 实现 `wait_for_user_confirmation`（asyncio.Event）
- [ ] 前端实现计划预览 UI（可编辑子查询、拖拽排序、删除/添加）
- [ ] 前端实现"确认"/"取消"按钮
- [ ] 前端发送 `user_response` 消息到后端
- [ ] 后端接收用户响应并继续/取消执行

**验证标准**：
- 研究模式生成计划后暂停，等待用户确认
- 用户可以修改子查询内容、调整顺序、删除不需要的
- 点击"确认"后继续执行，点击"取消"则任务终止
- 计划修改会影响实际执行的子查询

### Phase 5: 卡片持久化与历史记录（2 天）

**目标**：卡片数据保存到数据库，刷新页面后可恢复。

**任务清单**：
- [ ] 创建 `QueryCard` 数据库模型（SQLite）
- [ ] 卡片状态变化时自动保存到数据库
- [ ] 页面加载时从数据库恢复卡片列表
- [ ] 实现"清空历史"功能（删除所有已完成卡片）
- [ ] 实现"搜索历史"功能（按查询文本搜索）

**验证标准**：
- 关闭应用后重新打开，卡片列表仍然存在
- 可以回溯之前的查询结果
- 可以按查询文本搜索历史卡片

---

## 数据库 Schema 设计

### QueryCard 表

```sql
CREATE TABLE query_cards (
    id TEXT PRIMARY KEY,                    -- UUID
    query TEXT NOT NULL,                    -- 查询文本
    mode TEXT NOT NULL,                     -- 'simple' | 'research'
    status TEXT NOT NULL,                   -- 'pending' | 'processing' | 'completed' | 'error'
    trigger_source TEXT,                    -- 'manual_input' | 'shortcut' | 'api'

    -- 时间戳
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,                 -- 完成时间

    -- 结果数据（完整存储）
    panels JSON,                            -- 面板列表（完整数据，包括所有配置和数据项）
    error_message TEXT,                     -- 错误信息

    -- 刷新元数据（JSON）
    refresh_metadata JSON,                  -- 包含 route_id, generated_path, retrieved_tools 等

    -- 进度信息
    current_step TEXT,                      -- 当前步骤描述
    progress INTEGER DEFAULT 0,             -- 0-100

    -- 用户信息（预留，多用户支持时使用）
    user_id TEXT,

    -- 软删除
    is_deleted BOOLEAN DEFAULT FALSE,

    INDEX idx_created_at ON query_cards(created_at DESC),
    INDEX idx_user_status ON query_cards(user_id, status)
);
```

**设计决策**：

**为什么直接存储完整 `panels` JSON？**

1. **桌面应用场景** - 数据存储在用户本地 SQLite，不占用服务器资源
2. **简单可靠** - 避免复杂的引用机制和数据同步问题
3. **性能优先** - 查询历史记录时无需多表 JOIN，直接读取即可
4. **数据完整性** - 完整保留历史查询结果，用户可以随时回溯
5. **存储空间可接受** - 即使 90 天累积 270 MB，对于本地桌面应用也是可接受的

**数据量估算**（本地 SQLite）：

| 时间范围 | 查询次数 | 数据量 | 说明 |
|---------|---------|--------|------|
| 30 天 | 3000 | ~90 MB | 可接受 |
| 90 天 | 9000 | ~270 MB | 可接受 |
| 180 天 | 18000 | ~540 MB | 仍可接受（桌面应用） |

**对比服务器端应用**：
- 服务器端：需要优化存储（多用户共享资源）
- 桌面应用：存储空间充足，优先考虑简单性和性能

### 查询示例

```sql
-- 获取用户的最近 20 个卡片（包括进行中和已完成）
SELECT * FROM query_cards
WHERE user_id = ? AND is_deleted = FALSE
ORDER BY created_at DESC
LIMIT 20;

-- 搜索历史卡片
SELECT * FROM query_cards
WHERE user_id = ?
  AND is_deleted = FALSE
  AND query LIKE ?
ORDER BY created_at DESC;

-- 获取所有进行中的任务
SELECT * FROM query_cards
WHERE user_id = ?
  AND status IN ('pending', 'processing')
  AND is_deleted = FALSE;

-- 删除 90 天前的已完成任务（可选，用户可配置）
DELETE FROM query_cards
WHERE user_id = ?
  AND status = 'completed'
  AND completed_at < datetime('now', '-90 days');
```

**数据清理策略**（可选功能）：

桌面应用的数据清理策略应该简单、可配置：

1. **默认不自动清理** - 完整保留所有历史记录
2. **用户手动清理** - 提供"清空历史"按钮，用户主动触发
3. **可配置的自动清理** - 设置页面提供选项：
   - 不自动清理（默认）
   - 清理 30 天前的记录
   - 清理 90 天前的记录
   - 清理 180 天前的记录

**自动清理作业**（可选，默认禁用）：

```python
# services/maintenance/cleanup_old_cards.py

from datetime import datetime, timedelta
from services.database import get_db
from services.config import get_cleanup_config

async def cleanup_old_query_cards():
    """
    定时清理旧的查询卡片（可选功能，默认禁用）
    - 根据用户配置决定是否清理
    - 只清理已完成的卡片
    """
    config = get_cleanup_config()

    if not config.auto_cleanup_enabled:
        return  # 自动清理已禁用

    db = get_db()
    cutoff_date = datetime.now() - timedelta(days=config.retention_days)

    result = await db.execute(
        """
        DELETE FROM query_cards
        WHERE status = 'completed'
          AND completed_at < ?
        """,
        (cutoff_date,)
    )

    deleted_count = result.rowcount
    if deleted_count > 0:
        print(f"[Cleanup] Deleted {deleted_count} query cards older than {config.retention_days} days")

# 启动定时任务（仅在用户启用时注册）
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def register_cleanup_job():
    config = get_cleanup_config()
    if config.auto_cleanup_enabled:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(cleanup_old_query_cards, 'cron', hour=3, minute=0)
        scheduler.start()
```

**前端设置页面配置项**：

```vue
<template>
  <div class="settings-section">
    <h3>历史记录清理</h3>

    <div class="setting-item">
      <label>
        <input type="checkbox" v-model="autoCleanupEnabled" />
        自动清理历史记录
      </label>
    </div>

    <div v-if="autoCleanupEnabled" class="setting-item">
      <label>保留时间</label>
      <select v-model="retentionDays">
        <option value="30">30 天</option>
        <option value="90">90 天</option>
        <option value="180">180 天</option>
      </select>
    </div>

    <div class="setting-item">
      <button @click="manualCleanup">立即清空所有历史</button>
    </div>
  </div>
</template>
```

---

## 性能优化与注意事项

### 1. 卡片列表渲染优化

**问题**：如果有 100+ 历史卡片，全部渲染会导致页面卡顿。

**解决方案**：虚拟滚动（Virtual Scrolling）

```vue
<template>
  <RecycleScroller
    :items="cards"
    :item-size="120"
    key-field="id"
    class="workspace-scroller h-full"
  >
    <template #default="{ item }">
      <QueryCard :card="item" />
    </template>
  </RecycleScroller>
</template>

<script setup lang="ts">
import { RecycleScroller } from 'vue-virtual-scroller';
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
</script>
```

**依赖**：`npm install vue-virtual-scroller`

**效果**：只渲染可见区域的卡片，支持数千条历史记录。

### 2. WebSocket 消息频率限制

**问题**：后端频繁推送进度消息（如每 100ms 一次），前端渲染压力大。

**解决方案**：前端节流（Throttle）

```typescript
import { throttle } from 'lodash-es';

// 最多每 500ms 更新一次卡片进度
const updateCardProgress = throttle((taskId: string, progress: number) => {
  workspaceStore.updateCardProgress(taskId, progress);
}, 500);

wsManager.onMessage((msg) => {
  if (msg.type === 'progress') {
    updateCardProgress(msg.task_id, msg.progress);
  }
});
```

### 3. 元数据大小控制

**问题**：`refresh_metadata` 包含大量 RAG 检索结果，导致响应体过大。

**解决方案**：只保留必要字段

```python
# 不要保存完整的 RAG 结果（可能包含几十个候选路由）
response.refresh_metadata = {
    "route_id": primary_route.route_id,
    "generated_path": primary_route.path,
    # ❌ 不要保存：
    # "retrieved_tools": rag_result.routes  # 可能有 50+ 个

    # ✅ 只保存前 3 个（用于前端展示"AI 考虑了这些路由"）
    "retrieved_tools": [
        {"route_id": r.route_id, "name": r.name, "score": r.score}
        for r in rag_result.routes[:3]
    ],
}
```

---

## 前后端接口契约

### 1. 提交查询 API

**请求**：
```typescript
POST /api/v1/chat/submit
Content-Type: application/json

{
  "task_id": "uuid-generated-by-frontend",  // ← 前端生成 UUID
  "query": "科技美学最近在 B 站有什么新视频？",
  "mode": "auto"  // "auto" | "simple" | "research"
}
```

**响应**：
```json
{
  "task_id": "uuid-generated-by-frontend",
  "status": "processing",
  "message": "查询已提交，正在处理..."
}
```

**说明**：
- `task_id` 由前端生成（UUID），后端直接使用
- 后端立即返回（< 100ms），不阻塞等待结果
- 实际结果通过 WebSocket 推送

### 2. WebSocket 进度推送

**消息类型**：

```typescript
// 1. 进度更新
{
  "type": "progress",
  "task_id": "uuid",
  "step": "RAG 检索中...",
  "progress": 30
}

// 2. 状态变更
{
  "type": "status",
  "task_id": "uuid",
  "status": "processing"  // "pending" | "processing" | "completed" | "error"
}

// 3. 计划审核（研究模式）
{
  "type": "plan_review",
  "task_id": "uuid",
  "query_plan": {
    "main_query": "...",
    "sub_queries": [...]
  }
}

// 4. 结果完成
{
  "type": "result",
  "task_id": "uuid",
  "panels": [...],  // UIBlock[]
  "refresh_metadata": {...}
}

// 5. 错误
{
  "type": "error",
  "task_id": "uuid",
  "error": "执行失败: 网络超时"
}

// 6. 用户计划响应（前端 → 后端）
{
  "type": "user_plan_response",
  "task_id": "uuid",
  "action": "approve" | "modify" | "reject",
  "modified_plan": {  // 仅当 action="modify" 时需要
    "main_query": "...",
    "sub_queries": [...]
  }
}
```

**说明**：
- 消息 1-5 为后端 → 前端推送
- 消息 6 为前端 → 后端响应（仅用于交互式研究工作流）
- `plan_review` 推送后，后端进入阻塞等待状态（最多 5 分钟）
- 超时或用户取消后，任务自动转入 `error` 状态

### 3. 快速刷新 API

**请求**：
```typescript
POST /api/v1/chat/refresh
Content-Type: application/json

{
  "task_id": "original-task-id",
  "refresh_metadata": {
    "route_id": "bilibili_user-video",
    "generated_path": "/bilibili/user/video/12345"
  }
}
```

**响应**：
```json
{
  "task_id": "new-task-id",  // 新的任务 ID
  "panels": [...],           // 更新后的面板数据
  "refresh_metadata": {...}, // 返回相同的元数据
  "mode": "refresh"
}
```

---

## 风险与缓解措施

### 风险 1：快速刷新可能返回错误数据

**场景**：路由定义变更，旧的 `generated_path` 已失效。

**缓解措施**：
- 刷新 API 捕获 404 错误，自动回退到完整路径
- 前端显示"数据源已更新，正在重新查询..."
- 每次刷新时检查 route_id 是否仍然存在

### 风险 2：用户修改计划后执行失败

**场景**：用户添加了无法执行的子查询（如"帮我写一首诗"）。

**缓解措施**：
- 后端验证修改后的计划（确保所有子查询都是 `data_fetch` 类型）
- 如果包含不支持的查询，返回错误并要求用户修改
- 提供"智能建议"按钮，自动修正不合理的子查询

### 风险 3：历史卡片占用大量存储空间

**场景**：用户进行大量查询，数据库增长到几 GB。

**影响评估**：
- 桌面应用场景下，本地存储空间充足（180 天约 540 MB）
- SQLite 性能在 1 GB 以下数据量时表现良好
- 用户可以通过设置页面手动清理历史记录

**缓解措施**：
- ✅ **提供可选的自动清理功能**（默认禁用，用户可配置保留时间）
- ✅ **提供手动清理按钮**（"清空所有历史"）
- 可选：提供"导出历史"功能（JSON/CSV）
- 可选：显示数据库大小统计（如"历史记录占用 120 MB"）

---

## 实现细节补充

### `wait_for_user_confirmation` 实现

交互式研究工作流的核心是等待用户响应的机制。以下是完整实现：

```python
# services/research/user_confirmation.py

import asyncio
from typing import Dict, Optional
from pydantic import BaseModel

class UserPlanResponseMessage(BaseModel):
    """用户计划响应消息"""
    type: str = "user_plan_response"
    task_id: str
    action: str  # "approve" | "modify" | "reject"
    modified_plan: Optional[Dict] = None

# 全局存储：task_id → asyncio.Event
_pending_confirmations: Dict[str, asyncio.Event] = {}

# 全局存储：task_id → UserPlanResponseMessage
_user_responses: Dict[str, UserPlanResponseMessage] = {}

async def wait_for_user_confirmation(
    task_id: str,
    timeout: int = 300
) -> UserPlanResponseMessage:
    """
    等待用户确认计划（阻塞式）

    Args:
        task_id: 任务 ID
        timeout: 超时时间（秒），默认 5 分钟

    Returns:
        用户响应消息

    Raises:
        asyncio.TimeoutError: 超时未响应
    """
    # 创建事件对象
    event = asyncio.Event()
    _pending_confirmations[task_id] = event

    try:
        # 等待事件被触发（最多 timeout 秒）
        await asyncio.wait_for(event.wait(), timeout=timeout)

        # 事件被触发，获取用户响应
        response = _user_responses.pop(task_id)
        return response

    except asyncio.TimeoutError:
        # 超时，清理资源
        _pending_confirmations.pop(task_id, None)
        _user_responses.pop(task_id, None)
        raise

    finally:
        # 清理事件对象
        _pending_confirmations.pop(task_id, None)

def handle_user_plan_response(response: UserPlanResponseMessage):
    """
    处理用户响应消息（WebSocket 端点调用）

    Args:
        response: 用户响应消息
    """
    task_id = response.task_id

    # 存储用户响应
    _user_responses[task_id] = response

    # 触发事件，唤醒等待的协程
    event = _pending_confirmations.get(task_id)
    if event:
        event.set()
```

**WebSocket 端点集成**：

```python
# api/controllers/research_stream.py

from services.research.user_confirmation import handle_user_plan_response

@router.websocket("/ws/research/{task_id}")
async def research_websocket(websocket: WebSocket, task_id: str):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            # 处理用户计划响应
            if data.get("type") == "user_plan_response":
                response = UserPlanResponseMessage(**data)
                handle_user_plan_response(response)
                # 不需要回复，等待的协程会自动继续执行

            # 处理其他消息类型...

    except WebSocketDisconnect:
        pass
```

**完整流程图**：

```
┌─────────────┐
│ 后端生成计划│
└──────┬──────┘
       │
       ↓
┌─────────────────────────────┐
│ 推送 plan_review 消息       │ ← WebSocket
└──────┬──────────────────────┘
       │
       ↓
┌─────────────────────────────┐
│ 后端阻塞等待（300s 超时）   │ ← asyncio.Event.wait()
│ event = asyncio.Event()     │
└──────┬──────────────────────┘
       │
       │ ┌──────────────────────────┐
       │ │ 前端用户操作             │
       │ │ - 修改子查询             │
       │ │ - 点击"确认"或"取消"     │
       │ └──────┬───────────────────┘
       │        │
       │        ↓
       │ ┌──────────────────────────┐
       │ │ 前端发送响应消息         │ ← WebSocket
       │ │ type: user_plan_response │
       │ └──────┬───────────────────┘
       │        │
       ↓        ↓
┌─────────────────────────────┐
│ handle_user_plan_response   │
│ - 存储响应到 _user_responses│
│ - event.set() 触发事件      │
└──────┬──────────────────────┘
       │
       ↓
┌─────────────────────────────┐
│ wait_for_user_confirmation  │
│ - event.wait() 返回         │
│ - 获取 _user_responses[id]  │
│ - 返回用户响应              │
└──────┬──────────────────────┘
       │
       ↓
┌─────────────────────────────┐
│ 后端继续执行研究            │
│ - 使用用户确认的计划        │
│ - 执行子查询                │
└─────────────────────────────┘
```

**关键设计点**：

1. **全局状态管理** - 使用字典存储 `asyncio.Event` 和用户响应，支持多任务并发
2. **超时控制** - `asyncio.wait_for()` 提供超时保护，防止永久阻塞
3. **资源清理** - 超时或完成后自动清理事件对象，防止内存泄漏
4. **线程安全** - `asyncio.Event` 是协程安全的，无需额外锁
5. **解耦设计** - WebSocket 端点只负责调用 `handle_user_plan_response`，业务逻辑在 `wait_for_user_confirmation` 中

---

## 参考资料

### 设计灵感来源

- **Notion** - 统一工作区设计，所有内容都是可操作的块
- **Linear** - 实时状态更新，清晰的任务卡片
- **Figma** - 加载时的骨架屏设计
- **GitHub Actions** - 工作流步骤可视化
- **Claude.ai** - 对话历史管理

### 技术参考

- [Nielsen Norman Group - Response Times](https://www.nngroup.com/articles/response-times-3-important-limits/)
- [Google Web Vitals - FID](https://web.dev/fid/)
- [Vue Virtual Scroller](https://github.com/Akryum/vue-virtual-scroller)
- [AsyncIO Event](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event)

---

## 更新日志

- **2025-11-15 v1.2** - 简化数据库存储方案（基于桌面应用场景）：
  - ✅ **恢复完整存储**：`panels` 字段直接存储完整 JSON（无需复杂的引用机制）
  - ✅ **简化清理策略**：自动清理改为可选功能，默认禁用，用户可配置
  - ✅ **设计决策说明**：补充为什么桌面应用场景下完整存储更合理（简单、可靠、性能好）
- **2025-11-15 v1.1** - 修复 P0 问题（用户响应协议缺失）：
  - ✅ **P0 修复**：补充用户响应协议（`UserPlanResponseMessage` 定义、超时处理、前后端接口契约）
  - ✅ **补充**：`wait_for_user_confirmation` 完整实现细节（asyncio.Event + 全局状态管理 + 流程图）
- **2025-11-15 v1.0** - 创建文档，定义统一工作区架构、即时反馈设计、快速刷新机制、交互式研究工作流
