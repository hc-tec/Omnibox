# LLM 调用追踪系统 - 集成使用指南

## 1. 概述

**目标**：实时追踪所有 LLM 调用，前端可视化展示，提升系统可观测性。

**核心功能**：
- 🔍 **实时追踪**：所有 LLM 调用（Planner、Reflector、Synthesizer、订阅解析等）实时推送到前端
- 📊 **统计分析**：Token 使用量、耗时、调用分布统计
- 🛠️ **开发者模式**：查看完整 prompt/response，调试系统行为
- ⏱️ **时间线可视化**：直观展示 LLM 调用顺序和耗时

## 2. 架构设计

```
后端层次：
  LLM Client (基础层)
    └─ 在 generate() 方法前后插入追踪点
    └─ 调用 tracker.start_call() / complete_call()

  LLMCallTracker (追踪层)
    └─ 收集 LLM 调用事件
    └─ 通过 callback 推送到 WebSocket

  ChatService / ResearchService (服务层)
    └─ 创建 LLMCallTracker 实例
    └─ 注入到 LangGraph Runtime
    └─ 通过 WebSocket 推送事件

前端层次：
  WebSocket 连接
    └─ 接收 llm_call 消息
    └─ 更新 Store 状态

  LLMCallTimeline 组件
    └─ 显示调用列表
    └─ 点击查看详情

  LLMCallInspector 弹窗
    └─ 显示完整 prompt/response
    └─ 支持复制、导出
```

## 3. 后端集成

### 3.1 核心文件

**已创建**：
- `api/schemas/llm_call_event.py` - LLMCallEvent 和 LLMCallTracker
- `api/schemas/stream_messages.py` - LLMCallMessage

**需要修改**：
- `query_processor/llm_client.py` - 注入追踪点
- `langgraph_agents/llm_client.py` - 注入追踪点
- `langgraph_agents/runtime.py` - 传递 tracker
- `services/chat_service.py` - 创建 tracker 并推送事件

### 3.2 LLM Client 集成示例

```python
# query_processor/llm_client.py

import time
import uuid
from typing import Optional
from api.schemas.llm_call_event import LLMCallTracker

class LLMClient:
    def __init__(self, ...):
        # 现有初始化代码
        ...
        self.tracker: Optional[LLMCallTracker] = None  # 新增

    def set_tracker(self, tracker: LLMCallTracker, role: str):
        """设置追踪器（由外部注入）。"""
        self.tracker = tracker
        self.role = role  # "query_parser", "entity_resolver" 等

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        """生成响应（已注入追踪）。"""
        call_id = f"llm-{uuid.uuid4().hex[:12]}"
        start_time = time.time()

        # 开始追踪
        if self.tracker:
            self.tracker.start_call(
                call_id=call_id,
                role=self.role,
                model=self.model_name,
                temperature=temperature,
            )

        try:
            # 原有调用逻辑
            response = self.client.chat.completions.create(...)

            # 完成追踪
            duration_ms = int((time.time() - start_time) * 1000)
            if self.tracker:
                self.tracker.complete_call(
                    call_id=call_id,
                    prompt=prompt,
                    response=content,
                    duration_ms=duration_ms,
                    prompt_tokens=response.usage.prompt_tokens if response.usage else None,
                    completion_tokens=response.usage.completion_tokens if response.usage else None,
                    total_tokens=response.usage.total_tokens if response.usage else None,
                )

            return content

        except Exception as e:
            # 失败追踪
            duration_ms = int((time.time() - start_time) * 1000)
            if self.tracker:
                self.tracker.fail_call(
                    call_id=call_id,
                    error_message=str(e),
                    duration_ms=duration_ms,
                )
            raise
```

### 3.3 LangGraph Runtime 集成示例

```python
# langgraph_agents/runtime.py

from typing import Optional
from api.schemas.llm_call_event import LLMCallTracker

@dataclass
class LangGraphRuntime:
    # 现有字段
    planner_llm: LLMClient
    reflector_llm: LLMClient
    synthesizer_llm: LLMClient
    ...

    # 新增字段
    llm_tracker: Optional[LLMCallTracker] = None

    def __post_init__(self):
        """运行时初始化后，注入追踪器。"""
        if self.llm_tracker:
            self.planner_llm.set_tracker(self.llm_tracker, "planner")
            self.reflector_llm.set_tracker(self.llm_tracker, "reflector")
            self.synthesizer_llm.set_tracker(self.llm_tracker, "synthesizer")
```

### 3.4 ChatService 集成示例

```python
# services/chat_service.py

from api.schemas.llm_call_event import LLMCallTracker, LLMCallEvent
from api.schemas.stream_messages import LLMCallMessage

class ChatService:
    async def stream_chat_research(
        self,
        stream_id: str,
        query: str,
        websocket: WebSocket,
        dev_mode: bool = False,
    ):
        """流式研究模式（集成 LLM 追踪）。"""

        # 1. 创建追踪器
        def push_llm_call_event(event: LLMCallEvent):
            """WebSocket 推送回调。"""
            message = LLMCallMessage(
                stream_id=stream_id,
                call_id=event.call_id,
                role=event.role,
                status=event.status,
                step_id=event.step_id,
                duration_ms=event.duration_ms,
                prompt_tokens=event.prompt_tokens,
                completion_tokens=event.completion_tokens,
                total_tokens=event.total_tokens,
                prompt_preview=event.prompt_preview,
                response_preview=event.response_preview,
                full_prompt=event.full_prompt if dev_mode else None,
                full_response=event.full_response if dev_mode else None,
                error_message=event.error_message,
                model=event.model,
                temperature=event.temperature,
                metadata=event.metadata,
            )
            await websocket.send_json(message.dict())

        tracker = LLMCallTracker(
            stream_id=stream_id,
            callback=push_llm_call_event,
            dev_mode=dev_mode,
        )

        # 2. 注入追踪器到 LangGraph Runtime
        runtime = self._build_langgraph_runtime(tracker=tracker)

        # 3. 执行查询（追踪自动工作）
        result = await runtime.execute(query)

        # 4. 推送统计信息（可选）
        stats = tracker.get_statistics()
        await websocket.send_json({
            "type": "llm_stats",
            "stream_id": stream_id,
            "stats": stats,
        })
```

## 4. 前端集成

### 4.1 Store 扩展

```typescript
// frontend/src/store/researchViewStore.ts

interface ResearchViewState {
  // 现有字段
  task_id: string | null
  steps: ResearchStep[]
  panels: PanelData[]

  // 新增字段
  llm_calls: LLMCallEvent[]  // LLM 调用列表
  llm_stats: {  // 统计信息
    total_calls: number
    total_tokens: number
    total_duration_ms: number
    by_role: Record<string, {count: number, tokens: number, duration_ms: number}>
  } | null
}

// 新增 action
function handleLLMCallMessage(message: LLMCallMessage) {
  state.llm_calls.push({
    call_id: message.call_id,
    role: message.role,
    status: message.status,
    step_id: message.step_id,
    duration_ms: message.duration_ms,
    prompt_tokens: message.prompt_tokens,
    completion_tokens: message.completion_tokens,
    total_tokens: message.total_tokens,
    prompt_preview: message.prompt_preview,
    response_preview: message.response_preview,
    full_prompt: message.full_prompt,
    full_response: message.full_response,
    error_message: message.error_message,
    model: message.model,
    temperature: message.temperature,
    timestamp: message.timestamp,
  })
}
```

### 4.2 WebSocket 消息处理

```typescript
// frontend/src/composables/useResearchWebSocket.ts

function handleMessage(message: any) {
  switch (message.type) {
    case 'research_start':
      // 现有处理
      break

    case 'llm_call':  // 新增
      viewStore.handleLLMCallMessage(message)
      break

    case 'llm_stats':  // 新增
      viewStore.setLLMStats(message.stats)
      break
  }
}
```

### 4.3 LLMCallTimeline 组件示例

```vue
<!-- frontend/src/features/research/components/LLMCallTimeline.vue -->
<template>
  <div class="llm-call-timeline">
    <div class="timeline-header">
      <h3>LLM 调用 ({{ calls.length }})</h3>
      <div class="stats">
        <span>{{ formatTokens(totalTokens) }} tokens</span>
        <span>{{ formatDuration(totalDuration) }}</span>
      </div>
    </div>

    <div class="timeline-list">
      <div
        v-for="call in calls"
        :key="call.call_id"
        class="call-item"
        :class="[`status-${call.status}`, `role-${call.role}`]"
        @click="inspectCall(call)"
      >
        <!-- 角色图标 -->
        <div class="icon">
          <Brain v-if="call.role === 'planner'" />
          <Eye v-if="call.role === 'reflector'" />
          <FileText v-if="call.role === 'synthesizer'" />
          <!-- 其他角色图标 -->
        </div>

        <!-- 调用信息 -->
        <div class="info">
          <div class="role">{{ roleLabel(call.role) }}</div>
          <div class="meta">
            <span v-if="call.total_tokens">{{ call.total_tokens }} tokens</span>
            <span v-if="call.duration_ms">{{ call.duration_ms }}ms</span>
            <span v-if="call.step_id">Step {{ call.step_id }}</span>
          </div>
        </div>

        <!-- 状态指示器 -->
        <div class="status">
          <Loader v-if="call.status === 'started'" class="animate-spin" />
          <CheckCircle v-if="call.status === 'completed'" />
          <XCircle v-if="call.status === 'failed'" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useResearchViewStore } from '@/store/researchViewStore'
import { Brain, Eye, FileText, Loader, CheckCircle, XCircle } from 'lucide-vue-next'

const store = useResearchViewStore()
const calls = computed(() => store.state.llm_calls)

const totalTokens = computed(() =>
  calls.value.reduce((sum, call) => sum + (call.total_tokens || 0), 0)
)

const totalDuration = computed(() =>
  calls.value.reduce((sum, call) => sum + (call.duration_ms || 0), 0)
)

function roleLabel(role: string): string {
  const labels = {
    planner: '规划器',
    reflector: '反思器',
    synthesizer: '综合器',
    data_stasher: '摘要生成',
    entity_resolver: '实体解析',
    query_parser: '查询解析',
  }
  return labels[role] || role
}

function inspectCall(call: LLMCallEvent) {
  // 打开详情弹窗
  store.openCallInspector(call)
}
</script>

<style scoped>
.llm-call-timeline {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 16px;
}

.call-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.call-item:hover {
  background: rgba(255, 255, 255, 0.1);
}

.status-started {
  border-left: 2px solid #3b82f6;
}

.status-completed {
  border-left: 2px solid #10b981;
}

.status-failed {
  border-left: 2px solid #ef4444;
}
</style>
```

## 5. 使用场景

### 场景 1：调试查询规划问题

**问题**：用户查询"B站影视飓风投稿视频中，标题包含'英雄联盟'的视频"，系统没有正确过滤。

**调试步骤**：
1. 开启开发者模式
2. 查看 LLM 调用时间线
3. 点击 Planner 的调用记录
4. 查看完整 prompt，检查：
   - `data_stash` 是否包含正确的数据摘要
   - `working_memory` 是否有轻量工具结果
   - 工具列表是否包含 `filter_data`
5. 查看完整 response，检查：
   - Planner 选择的工具是否正确
   - 参数是否正确（如 `conditions`）

### 场景 2：Token 使用优化

**问题**：发现某次查询消耗了 50,000+ tokens，成本过高。

**分析步骤**：
1. 查看 LLM 统计面板
2. 按角色查看 token 分布：
   - Planner: 5,000 tokens
   - Reflector: 4,000 tokens
   - Synthesizer: 40,000 tokens（异常！）
3. 点击 Synthesizer 调用查看详情
4. 发现 prompt 中包含了完整原始数据（应该只用 summary）
5. 修复代码，验证优化效果

### 场景 3：性能优化

**问题**：查询响应慢，需要定位瓶颈。

**分析步骤**：
1. 查看 LLM 调用时间线
2. 按耗时排序：
   - entity_resolver: 1,200ms
   - planner (step 1): 800ms
   - reflector (step 1): 600ms
   - planner (step 2): 750ms
   - ...
3. 发现 entity_resolver 耗时最长
4. 优化订阅解析缓存策略

## 6. 开发者模式

**启用方式**（前端）：
```typescript
// 在 WebSocket 请求中添加参数
const payload = {
  query: userQuery,
  mode: 'research',
  dev_mode: true,  // 启用开发者模式
}
```

**开发者模式特性**：
- ✅ 返回完整 prompt（不截断）
- ✅ 返回完整 response（不截断）
- ✅ 支持复制到剪贴板
- ✅ 支持导出为 JSON 文件
- ⚠️ 注意：开发者模式会增加 WebSocket 数据传输量

## 7. 实现状态

**已完成**：
- [x] 修改 `query_processor/llm_client.py` 注入追踪点 - 添加 set_tracker() 和 generate() 追踪
- [x] 修改 `langgraph_agents/runtime.py` 传递 tracker - 添加 llm_tracker 字段和 __post_init__ 自动注入
- [x] 修改 `langgraph_agents/factory.py` 传递 tracker - build_runtime() 支持 llm_tracker 参数
- [x] 修改 `langgraph_agents/sync_executor.py` 传递 tracker - SyncLangGraphExecutor 支持 llm_tracker
- [x] 修改 `services/chat_service.py` 创建 tracker 并推送 - chat() 和 _handle_data_query() 支持 llm_tracker
- [x] 修改 `api/controllers/chat_stream.py` 集成追踪 - stream_chat_processing() 创建 tracker 并 yield LLM 事件
- [x] 前端：扩展 Store 支持 `llm_calls` 状态 - panelStore.ts 添加 llmCalls 和 llmCallStats
- [x] 前端：创建 `LLMCallTimeline` 组件 - components/debug/LLMCallTimeline.vue

**待实施**：
- [ ] 前端：创建 `LLMCallInspector` 详情弹窗（可选，当前 LLMCallTimeline 已支持展开查看详情）

**实现效果**：
- ✅ 用户可以实时看到所有 LLM 调用（通过 WebSocket 推送 llm_call 消息）
- ✅ 前端 Store 自动收集并统计 LLM 调用
- ✅ LLMCallTimeline 组件支持查看调用列表、展开详情、Token 统计
- ✅ 已集成到 MainView.vue（开发者模式下可见）
- ✅ 所有后端测试通过

## 8. 使用方法

1. 启动应用后，在 MainView 右上角点击「开发模式」按钮开启开发者模式
2. 发送任意查询（会触发 LLM 调用）
3. 在 PanelWorkspace 下方会出现「LLM 调用追踪」面板
4. 点击面板标题可折叠/展开
5. 点击单条调用记录可查看详情（Prompt、Response、Token 统计等）
