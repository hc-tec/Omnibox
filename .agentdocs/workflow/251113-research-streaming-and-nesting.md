# 研究模式实时推送与数据归属可视化方案

## 问题背景

### 问题1：缺少实时性
**现状**：
- `mode="research"` (LLM Query Planner) 一次性返回 ChatResponse
- 用户看不到中间过程（获取数据、AI分析）
- 输入框被阻塞，无法发起新查询

**用户期望**：
- 像 `mode="langgraph"` 一样实时看到研究进度
- 输入框不阻塞，支持多任务并行

### 问题2：数据归属不清晰
**现状**：
```
用户输入："查看 up主15616847 的视频并分析方向"

[研究卡片区域]
🔍 正在研究...
  ✅ 获取B站视频数据
  🤖 AI分析中...

[Panel 区域 - 独立展示]
┌──────────────┐
│  视频列表     │  ← 用户不知道这个卡片从哪来的
└──────────────┘
```

**用户困惑**：
1. Panel 中的卡片是独立查询还是研究产物？
2. 多个研究并行时，哪些卡片属于哪个研究？
3. 研究完成后，如何回溯数据来源？

---

## 完整解决方案

### 架构设计

#### 方案A：嵌套容器（推荐 - MVP）

**设计理念**：研究卡片**内嵌**数据卡片，形成父子关系

```
┌──────────────────────────────────────────────────────┐
│ 研究卡片：查看 up主15616847 的视频并分析方向          │
├──────────────────────────────────────────────────────┤
│ 📋 研究进度                                           │
│ ✅ 获取B站视频数据 (23条)                             │
│ ✅ AI分析视频方向                                     │
│                                                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
│ 📊 研究产出的数据卡片：                               │
│ ┌──────────────┐  ┌──────────────┐                  │
│ │  视频列表     │  │  播放统计     │                  │
│ │  [23条]      │  │  [图表]      │                  │
│ └──────────────┘  └──────────────┘                  │
│                                                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
│ 🤖 AI 分析结果：                                      │
│ 该UP主近期专注于前端技术教程，视频涵盖Vue3和React...  │
│                                                       │
│ [折叠] [移除]                                         │
└──────────────────────────────────────────────────────┘
```

**优点**：
- ✅ 数据归属关系清晰（父子嵌套）
- ✅ 支持折叠（节省空间）
- ✅ 易于实现（复用现有 Panel 组件）
- ✅ 符合用户心智模型

**缺点**：
- ⚠️ 研究卡片会比较大（包含数据卡片）
- ⚠️ 折叠后无法单独查看数据卡片

---

#### 方案B：视觉连接线（备选）

**设计理念**：研究卡片和数据卡片独立，通过视觉连接

```
[研究卡片区域]          [Panel 区域]
┌────────────┐          ┌──────────────┐
│ 研究中...   │ ········▶│  视频列表     │
│ ✅ 数据获取 │   虚线    │  [23条]      │
│ 🤖 分析中   │          └──────────────┘
└────────────┘          ┌──────────────┐
                   ·····▶│  播放统计     │
                         └──────────────┘
```

**优点**：
- ✅ 数据卡片独立，可单独操作
- ✅ 节省空间

**缺点**：
- ❌ 视觉连接复杂，实现成本高
- ❌ 多任务时连接线会混乱
- ❌ 响应式布局困难

---

#### 方案C：专属研究视图（长期方案）

**设计理念**：研究任务进入全屏专属视图

```
┌──────────────────────────────────────────────────────┐
│ ← 返回主界面    研究视图：up主视频分析                 │
├───────────────────┬──────────────────────────────────┤
│ 左侧：研究流程     │ 右侧：数据面板                     │
│                   │                                   │
│ 📋 研究步骤        │ ┌──────────────┐                 │
│ ✅ 1. 获取数据     │ │  视频列表     │                 │
│ 🤖 2. AI分析      │ │  [23条]      │                 │
│ ✅ 3. 生成报告     │ └──────────────┘                 │
│                   │ ┌──────────────┐                 │
│ 📊 分析结果        │ │  播放统计     │                 │
│ [展开查看详情]     │ └──────────────┘                 │
│                   │                                   │
│ [导出报告]         │                                   │
└───────────────────┴──────────────────────────────────┘
```

**优点**：
- ✅ 沉浸式体验，专注研究任务
- ✅ 数据归属关系极其清晰
- ✅ 支持导出、分享等高级功能

**缺点**：
- ❌ 实现成本极高
- ❌ 与现有交互模式差异大
- ❌ 不支持多任务并行查看

---

## 推荐方案：方案A（嵌套容器）+ WebSocket 实时推送

### 实现架构

```
┌─────────────────────────────────────────────────────┐
│                    前端架构                          │
├─────────────────────────────────────────────────────┤
│ 1. 用户输入 query + mode="research"                 │
│ 2. 创建本地研究卡片（status: processing）            │
│ 3. 建立 WebSocket 连接                              │
│ 4. 实时接收推送消息，更新研究卡片：                   │
│    - StageMessage: 更新进度条                        │
│    - DataMessage: 更新步骤状态                       │
│    - PanelMessage: 嵌入数据卡片（新增）              │
│    - AnalysisMessage: 显示AI分析结果（新增）         │
│    - CompleteMessage: 标记完成                      │
│ 5. 完成后保留研究卡片，支持折叠                      │
└─────────────────────────────────────────────────────┘
           ↓ WebSocket
┌─────────────────────────────────────────────────────┐
│                    后端架构                          │
├─────────────────────────────────────────────────────┤
│ 1. ChatService._handle_complex_research 改为生成器   │
│ 2. 每个子查询完成后 yield 消息：                     │
│    - 子查询开始: StageMessage("获取B站数据...")      │
│    - 子查询成功: PanelMessage(panel_data, blocks)   │
│    - 分析开始: StageMessage("AI分析中...")          │
│    - 分析完成: AnalysisMessage(summary)             │
│ 3. 所有任务完成后 yield CompleteMessage            │
└─────────────────────────────────────────────────────┘
```

---

## 技术实现

### 1. 后端：新增消息类型

**新增文件**: `api/schemas/stream_messages.py`（扩展现有）

```python
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# 新增消息类型
class PanelMessage(BaseModel):
    """Panel数据推送消息（研究产出的数据卡片）"""
    type: str = "panel"
    stream_id: str
    stage: str = "research_data"  # research_data | research_analysis

    # Panel 数据
    panel_payload: Dict[str, Any]  # PanelPayload
    data_blocks: Dict[str, Any]  # DataBlock映射

    # 元数据
    sub_query: str  # 子查询文本
    data_source: str  # 数据源（bilibili/github等）
    item_count: int  # 数据条数


class AnalysisMessage(BaseModel):
    """AI分析结果推送消息"""
    type: str = "analysis"
    stream_id: str
    stage: str = "research_analysis"

    # 分析结果
    query: str  # 分析查询
    summary: str  # 分析总结
    item_count: int  # 基于多少条数据分析
    execution_time: float  # 执行耗时


class ResearchStepMessage(BaseModel):
    """研究步骤状态更新消息"""
    type: str = "research_step"
    stream_id: str

    step_id: str
    step_type: str  # "data_fetch" | "analysis"
    action: str  # 步骤描述
    status: str  # "processing" | "success" | "error"
    result_summary: Optional[str] = None
    execution_time: Optional[float] = None
```

### 2. 后端：改造 _handle_complex_research 为生成器

**修改文件**: `services/chat_service.py`

```python
def _handle_complex_research_streaming(
    self,
    user_query: str,
    filter_datasource: Optional[str],
    use_cache: bool,
    intent_confidence: float,
    llm_logs: Optional[List[Dict[str, Any]]],
) -> Generator[Dict[str, Any], None, None]:
    """
    处理复杂研究意图（流式版本）

    Yields:
        流式消息字典
    """
    stream_id = str(uuid4())

    try:
        # 第一步：LLM 规划
        yield {
            "type": "research_step",
            "stream_id": stream_id,
            "step_id": "planning",
            "action": "LLM 正在规划研究方案...",
            "status": "processing",
        }

        query_plan = self._llm_query_planner.plan(user_query)

        yield {
            "type": "research_step",
            "stream_id": stream_id,
            "step_id": "planning",
            "action": f"规划完成：{len(query_plan.sub_queries)} 个子任务",
            "status": "success",
            "result_summary": query_plan.reasoning,
        }

        # 第二步：并行执行子查询（改为串行+实时推送）
        data_sub_queries = [sq for sq in query_plan.sub_queries if sq.task_type == "data_fetch"]
        analysis_sub_queries = [sq for sq in query_plan.sub_queries if sq.task_type == "analysis"]

        success_results = []
        aggregated_datasets = []

        for idx, sub_query in enumerate(data_sub_queries, 1):
            # 推送开始消息
            yield {
                "type": "research_step",
                "stream_id": stream_id,
                "step_id": f"fetch-{idx}",
                "step_type": "data_fetch",
                "action": f"获取数据：{sub_query.query}",
                "status": "processing",
            }

            # 执行查询
            import time
            start_time = time.time()

            query_result = self.data_query_service.query(
                user_query=sub_query.query,
                filter_datasource=sub_query.datasource,
                use_cache=use_cache,
                prefer_single_route=self._should_force_single_route(sub_query.datasource),
            )

            execution_time = time.time() - start_time

            if query_result.status == "success":
                # 构建 Panel 数据
                datasets = query_result.datasets or []
                aggregated_datasets.extend(datasets)

                panel_result = self._build_panel(datasets, user_query)

                # 推送数据卡片
                yield {
                    "type": "panel",
                    "stream_id": stream_id,
                    "stage": "research_data",
                    "sub_query": sub_query.query,
                    "data_source": sub_query.datasource or "unknown",
                    "item_count": len(query_result.items),
                    "panel_payload": panel_result.payload.model_dump(),
                    "data_blocks": {
                        k: v.model_dump() for k, v in panel_result.data_blocks.items()
                    },
                }

                # 推送成功消息
                yield {
                    "type": "research_step",
                    "stream_id": stream_id,
                    "step_id": f"fetch-{idx}",
                    "step_type": "data_fetch",
                    "action": f"获取数据：{sub_query.query}",
                    "status": "success",
                    "result_summary": f"获取 {len(query_result.items)} 条数据",
                    "execution_time": execution_time,
                }

                success_results.append(SubQueryResult(
                    sub_query=sub_query,
                    result=query_result,
                    execution_time=execution_time,
                ))
            else:
                # 推送失败消息
                yield {
                    "type": "research_step",
                    "stream_id": stream_id,
                    "step_id": f"fetch-{idx}",
                    "step_type": "data_fetch",
                    "action": f"获取数据：{sub_query.query}",
                    "status": "error",
                    "result_summary": query_result.reasoning,
                    "execution_time": execution_time,
                }

        # 第三步：执行分析子查询
        for idx, sub_query in enumerate(analysis_sub_queries, 1):
            yield {
                "type": "research_step",
                "stream_id": stream_id,
                "step_id": f"analysis-{idx}",
                "step_type": "analysis",
                "action": f"AI 分析：{sub_query.query}",
                "status": "processing",
            }

            start_time = time.time()

            # 执行分析
            analysis_summaries = self._run_analysis_sub_queries(
                [sub_query],
                aggregated_datasets
            )

            execution_time = time.time() - start_time

            if analysis_summaries:
                summary_data = analysis_summaries[0]

                # 推送分析结果
                yield {
                    "type": "analysis",
                    "stream_id": stream_id,
                    "stage": "research_analysis",
                    "query": summary_data["query"],
                    "summary": summary_data["summary"],
                    "item_count": summary_data.get("item_count", 0),
                    "execution_time": execution_time,
                }

                # 推送成功消息
                yield {
                    "type": "research_step",
                    "stream_id": stream_id,
                    "step_id": f"analysis-{idx}",
                    "step_type": "analysis",
                    "action": f"AI 分析：{sub_query.query}",
                    "status": "success",
                    "result_summary": "分析完成",
                    "execution_time": execution_time,
                }

        # 第四步：推送完成消息
        yield {
            "type": "complete",
            "stream_id": stream_id,
            "success": True,
            "message": f"研究完成：{len(success_results)} 组数据，{len(analysis_summaries)} 项分析",
            "metadata": {
                "query_plan": {
                    "reasoning": query_plan.reasoning,
                    "sub_query_count": len(query_plan.sub_queries),
                },
            }
        }

    except Exception as exc:
        logger.error("复杂研究流式处理失败: %s", exc, exc_info=True)
        yield {
            "type": "error",
            "stream_id": stream_id,
            "error_code": "RESEARCH_ERROR",
            "error_message": str(exc),
        }
```

### 3. 后端：新增 WebSocket 端点

**修改文件**: `api/controllers/chat_stream.py`

```python
@router.websocket("/chat/research-stream")
async def research_stream(
    websocket: WebSocket,
    chat_service: Any = Depends(get_chat_service)
):
    """
    复杂研究模式的 WebSocket 流式接口

    实时推送研究进度、数据卡片、分析结果
    """
    await websocket.accept()
    stream_id = generate_stream_id()
    logger.info(f"[{stream_id}] 研究 WebSocket 连接已建立")

    try:
        # 接收请求
        request_data = await websocket.receive_json()
        user_query = request_data.get("query", "")
        filter_datasource = request_data.get("filter_datasource")
        use_cache = request_data.get("use_cache", True)

        logger.info(f"[{stream_id}] 收到研究查询: {user_query}")

        # 创建流式生成器
        message_generator = chat_service._handle_complex_research_streaming(
            user_query=user_query,
            filter_datasource=filter_datasource,
            use_cache=use_cache,
            intent_confidence=0.9,
            llm_logs=None,
        )

        # 逐个推送消息
        import asyncio
        while True:
            try:
                message = await asyncio.to_thread(next, message_generator, None)
                if message is None:
                    break

                await websocket.send_json(message)
                logger.debug(f"[{stream_id}] 推送消息: {message['type']}")

            except StopIteration:
                break
            except Exception as e:
                logger.error(f"[{stream_id}] 消息推送失败: {e}", exc_info=True)
                break

        logger.info(f"[{stream_id}] 研究流式处理完成")

    except WebSocketDisconnect:
        logger.info(f"[{stream_id}] 客户端断开连接")
    except Exception as e:
        logger.error(f"[{stream_id}] WebSocket 处理失败: {e}", exc_info=True)
    finally:
        try:
            await websocket.close()
        except:
            pass
```

### 4. 前端：新增研究卡片组件

**新增文件**: `frontend/src/features/research/components/ResearchCardV2.vue`

```vue
<template>
  <Card class="research-card" :class="{ 'collapsed': isCollapsed }">
    <CardHeader>
      <div class="flex items-center justify-between">
        <CardTitle class="text-sm flex items-center gap-2">
          <component :is="statusIcon" :class="iconClass" />
          {{ research.query }}
        </CardTitle>
        <div class="flex gap-2">
          <Badge :variant="badgeVariant">{{ statusText }}</Badge>
          <Button
            v-if="research.status === 'completed'"
            size="sm"
            variant="ghost"
            @click="toggleCollapse"
          >
            {{ isCollapsed ? '展开' : '折叠' }}
          </Button>
          <Button size="sm" variant="ghost" @click="$emit('remove', research.task_id)">
            移除
          </Button>
        </div>
      </div>
    </CardHeader>

    <CardContent v-if="!isCollapsed">
      <!-- 研究步骤 -->
      <div class="execution-steps space-y-2 mb-4">
        <div
          v-for="step in research.execution_steps"
          :key="step.step_id"
          class="flex items-center gap-2 text-sm"
        >
          <CheckCircle v-if="step.status === 'success'" class="h-4 w-4 text-green-500" />
          <XCircle v-else-if="step.status === 'error'" class="h-4 w-4 text-red-500" />
          <Loader v-else class="h-4 w-4 animate-spin text-blue-500" />
          <span class="text-muted-foreground">{{ step.action }}</span>
          <span v-if="step.result_summary" class="text-xs text-muted-foreground">
            ({{ step.result_summary }})
          </span>
        </div>
      </div>

      <!-- 嵌入的数据卡片 -->
      <div v-if="research.embedded_panels && research.embedded_panels.length > 0" class="mb-4">
        <div class="flex items-center gap-2 mb-3">
          <Database class="h-4 w-4 text-blue-500" />
          <h4 class="font-semibold text-sm">研究产出的数据卡片</h4>
        </div>

        <div class="space-y-3">
          <div
            v-for="(panel, idx) in research.embedded_panels"
            :key="`panel-${idx}`"
            class="border rounded-lg p-3 bg-muted/30"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="text-xs font-medium text-muted-foreground">
                来自：{{ panel.sub_query }}
              </span>
              <Badge variant="outline">{{ panel.item_count }} 条</Badge>
            </div>

            <!-- 渲染 mini Panel -->
            <div class="panel-preview">
              <DynamicBlockRenderer
                v-for="block in panel.blocks"
                :key="block.id"
                :block="block"
                :data-block="panel.data_blocks[block.data_ref]"
                size="compact"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- AI 分析结果 -->
      <div v-if="research.analysis_results && research.analysis_results.length > 0">
        <div class="flex items-center gap-2 mb-3">
          <Brain class="h-4 w-4 text-purple-500" />
          <h4 class="font-semibold text-sm">AI 分析结果</h4>
        </div>

        <div
          v-for="(analysis, idx) in research.analysis_results"
          :key="`analysis-${idx}`"
          class="rounded-lg border bg-card p-4 mb-3"
        >
          <h5 class="text-sm font-medium mb-2">{{ analysis.query }}</h5>
          <p class="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
            {{ analysis.summary }}
          </p>
          <div class="mt-2 text-xs text-muted-foreground">
            基于 {{ analysis.item_count }} 条数据分析
          </div>
        </div>
      </div>

      <!-- 元数据 -->
      <div
        v-if="research.metadata"
        class="mt-4 border-t pt-3 text-xs text-muted-foreground"
      >
        <div>总耗时：{{ research.metadata.total_time?.toFixed(2) }}s</div>
        <div>子任务：{{ research.metadata.total_steps }} 个</div>
      </div>
    </CardContent>

    <!-- 折叠状态的摘要 -->
    <CardContent v-else class="py-2">
      <div class="flex items-center justify-between text-sm text-muted-foreground">
        <span>{{ research.execution_steps.length }} 个步骤</span>
        <span>{{ research.metadata?.total_time?.toFixed(2) }}s</span>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { CheckCircle, XCircle, Loader, Brain, Database } from 'lucide-vue-next';
import DynamicBlockRenderer from '@/features/panel/components/blocks/DynamicBlockRenderer.vue';

interface Props {
  research: ResearchTask;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  remove: [taskId: string];
}>();

const isCollapsed = ref(false);

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value;
};

const statusIcon = computed(() => {
  switch (props.research.status) {
    case 'processing':
      return Loader;
    case 'completed':
      return CheckCircle;
    case 'error':
      return XCircle;
    default:
      return Loader;
  }
});

const iconClass = computed(() => ({
  'h-4 w-4': true,
  'animate-spin text-blue-500': props.research.status === 'processing',
  'text-green-500': props.research.status === 'completed',
  'text-red-500': props.research.status === 'error',
}));

const statusText = computed(() => {
  switch (props.research.status) {
    case 'processing':
      return '研究中';
    case 'completed':
      return '已完成';
    case 'error':
      return '错误';
    default:
      return '未知';
  }
});

const badgeVariant = computed((): 'default' | 'outline' | 'destructive' => {
  switch (props.research.status) {
    case 'processing':
      return 'default';
    case 'completed':
      return 'outline';
    case 'error':
      return 'destructive';
    default:
      return 'outline';
  }
});
</script>

<style scoped>
.research-card {
  transition: all 0.3s ease;
}

.research-card.collapsed {
  max-height: 120px;
}

.panel-preview {
  transform: scale(0.9);
  transform-origin: top left;
}
</style>
```

### 5. 前端：WebSocket 连接管理

**修改文件**: `frontend/src/features/research/composables/useResearchWebSocket.ts`

```typescript
import { ref, onUnmounted } from 'vue';
import { useResearchStore } from '../stores/researchStore';

export function useResearchWebSocket() {
  const researchStore = useResearchStore();
  const ws = ref<WebSocket | null>(null);
  const isConnected = ref(false);

  const connect = (taskId: string, query: string) => {
    // 创建本地研究卡片
    researchStore.createResearchTask(taskId, query);

    // 建立 WebSocket 连接
    const wsUrl = `ws://localhost:8000/api/v1/chat/research-stream`;
    ws.value = new WebSocket(wsUrl);

    ws.value.onopen = () => {
      console.log('[Research WS] Connected');
      isConnected.value = true;

      // 发送查询请求
      ws.value?.send(JSON.stringify({
        query,
        use_cache: true,
      }));
    };

    ws.value.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('[Research WS] Message:', message);

      switch (message.type) {
        case 'research_step':
          researchStore.updateStep(taskId, message);
          break;

        case 'panel':
          // 嵌入数据卡片
          researchStore.embedPanel(taskId, {
            sub_query: message.sub_query,
            data_source: message.data_source,
            item_count: message.item_count,
            panel_payload: message.panel_payload,
            data_blocks: message.data_blocks,
            blocks: message.panel_payload.blocks,
          });
          break;

        case 'analysis':
          // 添加分析结果
          researchStore.addAnalysis(taskId, {
            query: message.query,
            summary: message.summary,
            item_count: message.item_count,
          });
          break;

        case 'complete':
          researchStore.completeTask(taskId, message);
          break;

        case 'error':
          researchStore.errorTask(taskId, message.error_message);
          break;
      }
    };

    ws.value.onerror = (error) => {
      console.error('[Research WS] Error:', error);
      researchStore.errorTask(taskId, '连接失败');
    };

    ws.value.onclose = () => {
      console.log('[Research WS] Disconnected');
      isConnected.value = false;
    };
  };

  const disconnect = () => {
    if (ws.value) {
      ws.value.close();
      ws.value = null;
    }
  };

  onUnmounted(() => {
    disconnect();
  });

  return {
    connect,
    disconnect,
    isConnected,
  };
}
```

---

## 实施计划

### 阶段1：WebSocket 实时推送（1-2天）
- [ ] 后端：新增消息类型（PanelMessage、AnalysisMessage等）
- [ ] 后端：改造 _handle_complex_research 为生成器
- [ ] 后端：新增 /chat/research-stream WebSocket 端点
- [ ] 前端：实现 useResearchWebSocket composable
- [ ] 测试：验证实时推送功能

### 阶段2：嵌套容器展示（1天）
- [ ] 前端：实现 ResearchCardV2 组件
- [ ] 前端：在研究卡片内嵌入 Panel 组件（mini版）
- [ ] 前端：实现折叠/展开功能
- [ ] 样式：优化嵌套布局

### 阶段3：多任务管理（0.5天）
- [ ] 前端：支持多个研究任务并行
- [ ] 前端：研究卡片排序（最新在前）
- [ ] 前端：已完成任务持久化（localStorage）

---

## 交互流程

```
用户输入："查看 up主15616847 的视频并分析方向"
    ↓
前端：创建研究卡片（status: processing）
    ↓
前端：建立 WebSocket 连接
    ↓
后端：推送消息流
    ├─ StageMessage: "LLM 正在规划..."
    ├─ StageMessage: "获取B站视频数据..."
    ├─ PanelMessage: { 视频列表数据卡片 }  → 前端嵌入到研究卡片
    ├─ StageMessage: "AI 分析中..."
    ├─ AnalysisMessage: { 分析总结 }  → 前端嵌入到研究卡片
    └─ CompleteMessage: "研究完成"
    ↓
前端：更新研究卡片（status: completed）
    ↓
用户：可折叠、可移除、可回顾
```

---

## 优势总结

### 实时性
- ✅ 用户实时看到研究进度
- ✅ 输入框不阻塞，支持多任务并行
- ✅ 中间数据立即可见

### 数据归属
- ✅ 嵌套容器清晰展示父子关系
- ✅ 标注数据来源（sub_query + data_source）
- ✅ 支持多研究并行，不会混淆

### 用户体验
- ✅ 研究过程可视化
- ✅ 研究结果可回顾
- ✅ 支持折叠节省空间
- ✅ 支持手动移除

---

## 后续迭代方向

### 短期（1-2周）
1. 导出研究报告（PDF/Markdown）
2. 分享研究结果（生成链接）
3. 历史研究记录（持久化存储）

### 中期（1-2月）
1. 研究模板（预设常用研究类型）
2. 数据对比模式（多数据源并排对比）
3. 交互式分析（用户追问）

### 长期（3-6月）
1. 方案C：专属研究视图
2. 协作研究（多人共同研究）
3. AI助手自主研究（用户授权后自动执行）

---

## 风险与应对

### 风险1：WebSocket 连接不稳定
**应对**：
- 实现自动重连机制
- 降级方案：失败时回退到 HTTP 轮询

### 风险2：嵌入 Panel 性能问题
**应对**：
- 使用虚拟滚动（数据量大时）
- mini 模式渲染（简化版组件）
- 懒加载（折叠时不渲染）

### 风险3：研究卡片过多占用内存
**应对**：
- 限制最大保留数量（如20个）
- 自动清理旧任务（超过7天）
- 分页加载历史记录

---

## 开发优先级

**P0（必须）**：
1. WebSocket 实时推送
2. 基础研究卡片（不嵌入 Panel）
3. 分析结果展示

**P1（重要）**：
1. 嵌入 Panel 数据卡片
2. 折叠/展开功能
3. 多任务并行

**P2（优化）**：
1. 样式优化
2. 动画效果
3. 导出功能

---

## 总结

**推荐方案**：方案A（嵌套容器） + WebSocket 实时推送

**实施周期**：2-3天完成 MVP，1周完成完整版

**关键优势**：
- 解决实时性问题（WebSocket）
- 解决数据归属问题（嵌套容器）
- 用户体验显著提升
- 架构清晰，易于扩展
