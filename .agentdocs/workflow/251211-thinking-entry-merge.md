# 思考卡片合并方案设计

## 问题描述

当前时间线中，同一个 step 的"思考前"和"思考后"消息被显示为两个独立的思考卡片，导致界面冗余：

```
● 思考中               ← 第一条消息 (status=processing)
  分析执行策略
  详细推理: 生成执行摘要并规划下一步…

● 思考中               ← 第二条消息 (status=success)
  计划调用工具: fetch_public_data
  详细推理: 用户查询"B站热搜前三条"...TODO清单...
```

**期望效果**：同一个 step 的消息应该合并到同一张卡片，实时更新状态。

## 根因分析

### 后端消息流

`research_agent.py` 对每个 step 发送两次 `_emit_reasoning`：

```python
# 1. 规划前（line 553-561）
_emit_reasoning(runtime, {
    "step_id": next_step,         # 如：1
    "decision": "PLANNING",
    "reasoning": "生成执行摘要并规划下一步…",
    "status": "processing",
})

# 2. 规划后（line 609-617）
_emit_reasoning(runtime, {
    "step_id": next_step,         # 如：1（同一个 step_id）
    "decision": decision,         # 如：CONTINUE
    "reasoning": reasoning,       # 详细推理
    "tool_call": {...},
})
```

### WebSocket 消息格式

`session_controller.py` 将消息转换为 `ResearchStepMessage`（line 629-641）：

```python
ResearchStepMessage(
    step_id=f"think_{step_id}",   # 如："think_1"
    step_type="planning",
    action=action,                 # 如："分析执行策略" 或 "计划调用工具: xxx"
    status=status,                 # "processing" 或 "success"
    reasoning=reasoning,
    details={...},
)
```

**关键点**：后端已通过 `step_id` 标识同一个 step，但 `action` 不同。

### 前端处理逻辑

`useSessionWebSocket.ts` 中 `handleStepMessage`（line 301-304）：

```typescript
// 如果是 planning 类型（Agent 思考），添加为思考条目
if (stepType === 'planning') {
  workspaceStore.addThinkingEntry(action, reasoning)
  return
}
```

**问题**：没有传递 `step_id`，无法识别是同一个 step 的更新。

### addThinkingEntry 去重逻辑

`workspaceStore.ts`（line 612-627）：

```typescript
function addThinkingEntry(content: string, reasoning?: string): string {
  // 去重：检查最后一条是否是相同的思考条目
  const lastEntry = timelineEntries.value[timelineEntries.value.length - 1]
  if (lastEntry?.type === 'thinking' && lastEntry.thinking?.content === content) {
    // 更新 reasoning
    if (reasoning && reasoning !== lastEntry.thinking.reasoning) {
      lastEntry.thinking.reasoning = reasoning
    }
    return lastEntry.id
  }
  // 创建新条目
  return addTimelineEntry({...})
}
```

**问题**：基于 `content`（action）去重，但同一 step 的两条消息 `action` 不同：
- 第一条：`action="分析执行策略"`
- 第二条：`action="计划调用工具: fetch_public_data"`

因此被当作两个不同的条目创建。

## 解决方案

### 方案概述

利用后端已有的 `step_id` 字段，在前端实现基于 `step_id` 的思考卡片合并与状态更新。

### 数据结构改动

#### 1. 扩展 TimelineEntry.thinking 接口

**文件**：`frontend/src/features/workspace/types/workspace.ts`

```typescript
/** 思考信息（Agent 推理过程） */
thinking?: {
  step_id?: string              // 新增：步骤标识，用于合并同一 step 的消息
  content: string
  reasoning?: string
  status?: 'processing' | 'success' | 'error'  // 新增：思考状态
}
```

#### 2. 改造 addThinkingEntry 方法

**文件**：`frontend/src/features/workspace/stores/workspaceStore.ts`

```typescript
/**
 * 添加/更新思考条目（基于 step_id 合并）
 */
function addThinkingEntry(
  content: string,
  reasoning?: string,
  stepId?: string,
  status?: 'processing' | 'success' | 'error'
): string {
  // 如果有 step_id，查找已存在的同 step 条目
  if (stepId) {
    const existingEntry = timelineEntries.value.find(
      e => e.type === 'thinking' && e.thinking?.step_id === stepId
    )
    if (existingEntry?.thinking) {
      // 更新现有条目
      existingEntry.thinking.content = content
      existingEntry.thinking.status = status
      if (reasoning) {
        existingEntry.thinking.reasoning = reasoning
      }
      return existingEntry.id
    }
  }

  // 无 step_id 时，保持原有基于 content 的去重逻辑
  const lastEntry = timelineEntries.value[timelineEntries.value.length - 1]
  if (!stepId && lastEntry?.type === 'thinking' && lastEntry.thinking?.content === content) {
    if (reasoning && reasoning !== lastEntry.thinking.reasoning) {
      lastEntry.thinking.reasoning = reasoning
    }
    return lastEntry.id
  }

  // 创建新条目
  return addTimelineEntry({
    type: 'thinking',
    thinking: { step_id: stepId, content, reasoning, status },
  })
}
```

#### 3. 修改 handleStepMessage

**文件**：`frontend/src/features/workspace/composables/useSessionWebSocket.ts`

```typescript
function handleStepMessage(message: StreamMessage): void {
  const stepId = message.step_id || `step-${Date.now()}`
  const action = message.action || '执行步骤'
  const statusRaw = message.status || 'success'
  const stepType = message.step_type || 'tool_call'
  const reasoning = message.reasoning
  // ...

  // 转换 status
  const thinkingStatus: 'processing' | 'success' | 'error' =
    statusRaw === 'processing' ? 'processing' :
    statusRaw === 'error' ? 'error' : 'success'

  // 如果是 planning 类型（Agent 思考），基于 step_id 合并
  if (stepType === 'planning') {
    workspaceStore.addThinkingEntry(action, reasoning, stepId, thinkingStatus)
    return
  }
  // ...
}
```

#### 4. 更新 ThinkingEntry 组件

**文件**：`frontend/src/features/workspace/components/timeline/entries/ThinkingEntry.vue`

```vue
<script setup lang="ts">
const { entry, isActive = false } = defineProps<{
  entry: TimelineEntry
  isActive?: boolean
}>()

// 基于 status 判断是否显示 shimmer（processing 状态）
const isProcessing = computed(() => entry.thinking?.status === 'processing')
const shimmerClass = computed(() => (isActive || isProcessing.value ? 'shimmer-text' : ''))
</script>

<template>
  <div class="bg-muted/30 rounded-lg overflow-hidden">
    <div class="flex items-center gap-1.5 px-3 py-2 cursor-pointer hover:bg-muted/50">
      <Brain class="h-3.5 w-3.5 text-muted-foreground" />
      <span class="text-xs font-medium text-muted-foreground" :class="shimmerClass">
        {{ isProcessing ? '思考中' : '思考完成' }}
      </span>
      <!-- ... -->
    </div>
    <!-- ... -->
  </div>
</template>
```

### 消息流示意

```
后端 Step 1:
  ├─ emit_reasoning({step_id: 1, status: "processing", action: "分析执行策略"})
  │     ↓
  │   ResearchStepMessage(step_id="think_1", status="processing", action="分析执行策略")
  │     ↓
  │   前端: addThinkingEntry("分析执行策略", "...", "think_1", "processing")
  │     ↓
  │   创建新条目: {id: "entry-1", thinking: {step_id: "think_1", content: "分析执行策略", status: "processing"}}
  │
  └─ emit_reasoning({step_id: 1, status: "success", action: "计划调用工具: fetch_public_data"})
        ↓
      ResearchStepMessage(step_id="think_1", status="success", action="计划调用工具: fetch_public_data")
        ↓
      前端: addThinkingEntry("计划调用工具: fetch_public_data", "...", "think_1", "success")
        ↓
      找到已有条目（step_id="think_1"），更新内容和状态
        ↓
      更新条目: {id: "entry-1", thinking: {step_id: "think_1", content: "计划调用工具: fetch_public_data", status: "success"}}
```

### 预期效果

改造后，时间线中同一个 step 只显示一张卡片，实时更新：

```
● 思考中 (shimmer动画)     ← 初始状态
  分析执行策略
  详细推理: 生成执行摘要并规划下一步…
      ↓ 更新
● 思考完成                  ← 最终状态
  计划调用工具: fetch_public_data
  详细推理: 用户查询"B站热搜前三条"...TODO清单...
```

## 改动清单

| 文件 | 改动 |
|------|------|
| `types/workspace.ts` | 扩展 `thinking` 接口，增加 `step_id`、`status` 字段 |
| `stores/workspaceStore.ts` | 改造 `addThinkingEntry`，支持基于 `step_id` 合并 |
| `composables/useSessionWebSocket.ts` | 传递 `step_id` 和 `status` 到 `addThinkingEntry` |
| `components/timeline/entries/ThinkingEntry.vue` | 基于 `status` 显示不同 UI 状态 |

## 兼容性

- 后端无需改动，已有 `step_id` 字段
- 前端改动向后兼容，无 `step_id` 时保持原有逻辑

## TODO

- [x] 扩展 TimelineEntry.thinking 接口
- [x] 改造 addThinkingEntry 方法
- [x] 修改 handleStepMessage 传递 step_id 和 status
- [x] 更新 ThinkingEntry 组件 UI
- [x] 端到端测试验证

## 验证结果（2025-12-11）

测试查询："B站热搜前三条"

**改进效果**：
- 每个 step 的"思考前"和"思考后"消息成功合并到同一张卡片
- 状态从"思考中"(shimmer 动画) 实时更新到"思考完成"
- 详细推理内容正确显示
- 时间线条目数量明显减少（从原来的每步 2 张卡片减少到 1 张）
