# 专属研究视图完整实施方案

## 目标

直接实现专属研究视图（方案C），提供沉浸式的深度研究体验。

---

## 整体架构设计

### 视图结构

```
┌─────────────────────────────────────────────────────────────┐
│ 顶部导航栏                                                    │
│ [← 返回主界面] [研究标题] [导出报告] [分享]                   │
├──────────────────┬──────────────────────────────────────────┤
│                  │                                          │
│  左侧面板 (30%)  │  右侧面板 (70%)                           │
│                  │                                          │
│  研究上下文区     │  数据可视化区                             │
│  ┌────────────┐ │  ┌──────────────┐                        │
│  │研究目标     │ │  │  Panel卡片    │                        │
│  └────────────┘ │  └──────────────┘                        │
│  ┌────────────┐ │  ┌──────────────┐                        │
│  │执行步骤     │ │  │  Panel卡片    │                        │
│  │ ✅ 步骤1    │ │  └──────────────┘                        │
│  │ 🔄 步骤2    │ │                                          │
│  └────────────┘ │                                          │
│  ┌────────────┐ │                                          │
│  │AI分析结果   │ │                                          │
│  └────────────┘ │                                          │
│                  │                                          │
├──────────────────┴──────────────────────────────────────────┤
│ 底部交互区（可选）                                            │
│ [追问输入框] [发送]                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 功能清单（按优先级）

### P0（MVP - 必须实现）

#### 后端
- [x] 新增 WebSocket 消息类型（PanelMessage、AnalysisMessage等）
- [x] 改造 `_handle_complex_research` 为流式生成器
- [x] 新增 `/api/v1/research/stream` WebSocket 端点
- [x] 实时推送研究进度、数据、分析结果

#### 前端
- [x] 创建研究视图路由 `/research/:taskId`
- [x] 实现 ResearchView 主容器组件
- [x] 实现左侧研究上下文面板
  - [x] 研究目标展示
  - [x] 执行步骤列表（实时更新）
  - [x] AI分析结果展示
- [x] 实现右侧数据可视化面板
  - [x] Panel 卡片动态渲染
  - [x] 响应式布局
- [x] 实现顶部导航栏
  - [x] 返回主界面按钮
  - [x] 研究标题展示
- [x] WebSocket 连接管理
- [x] 视图状态管理（researchViewStore）

### P1（增强功能）

#### 后端
- [ ] 研究任务持久化（存储到数据库）
- [ ] 历史研究列表 API
- [ ] 导出报告 API（Markdown/PDF）

#### 前端
- [ ] 追问对话功能（底部输入框）
- [ ] 导出报告功能
- [ ] 分享研究功能（生成公开链接）
- [ ] 历史研究列表页面
- [ ] Panel 卡片全屏查看

### P2（高级功能）

- [ ] 研究模板系统
- [ ] 数据对比模式（分栏对比）
- [ ] 协作研究（多人实时）
- [ ] 版本管理（研究历史）
- [ ] 自定义研究流程

---

## 技术实现细节

### 一、后端实现

#### 1. 新增消息类型定义

**文件**：`api/schemas/stream_messages.py`（扩展现有）

```python
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ResearchMessageType(str, Enum):
    """研究消息类型"""
    RESEARCH_START = "research_start"      # 研究开始
    RESEARCH_STEP = "research_step"        # 步骤更新
    RESEARCH_PANEL = "research_panel"      # Panel数据推送
    RESEARCH_ANALYSIS = "research_analysis"  # 分析结果
    RESEARCH_COMPLETE = "research_complete"  # 研究完成
    RESEARCH_ERROR = "research_error"      # 错误


class ResearchStartMessage(BaseModel):
    """研究开始消息"""
    type: str = "research_start"
    stream_id: str
    task_id: str
    query: str
    plan: Dict[str, Any]  # 查询计划


class ResearchStepMessage(BaseModel):
    """研究步骤消息"""
    type: str = "research_step"
    stream_id: str
    task_id: str

    step_id: str
    step_type: str  # "planning" | "data_fetch" | "analysis"
    action: str  # 步骤描述
    status: str  # "processing" | "success" | "error"
    result_summary: Optional[str] = None
    execution_time: Optional[float] = None


class ResearchPanelMessage(BaseModel):
    """Panel数据推送消息"""
    type: str = "research_panel"
    stream_id: str
    task_id: str

    # 子查询信息
    sub_query: str
    data_source: Optional[str] = None
    item_count: int

    # Panel 数据
    panel_payload: Dict[str, Any]  # PanelPayload
    data_blocks: Dict[str, Any]  # DataBlock映射


class ResearchAnalysisMessage(BaseModel):
    """分析结果消息"""
    type: str = "research_analysis"
    stream_id: str
    task_id: str

    query: str
    summary: str
    item_count: int
    execution_time: float


class ResearchCompleteMessage(BaseModel):
    """研究完成消息"""
    type: str = "research_complete"
    stream_id: str
    task_id: str

    success: bool
    message: str
    total_time: float
    metadata: Dict[str, Any]
```

#### 2. 改造为流式生成器

**文件**：`services/chat_service.py`

新增方法：`_handle_complex_research_streaming`

```python
def _handle_complex_research_streaming(
    self,
    task_id: str,
    user_query: str,
    filter_datasource: Optional[str],
    use_cache: bool,
    intent_confidence: float,
    llm_logs: Optional[List[Dict[str, Any]]],
) -> Generator[Dict[str, Any], None, None]:
    """
    处理复杂研究意图（流式版本）

    Yields:
        ResearchMessage 消息字典
    """
    import time
    import uuid

    stream_id = str(uuid.uuid4())
    start_time = time.time()

    try:
        # 步骤1：LLM 规划
        yield {
            "type": "research_start",
            "stream_id": stream_id,
            "task_id": task_id,
            "query": user_query,
            "plan": {},
        }

        yield {
            "type": "research_step",
            "stream_id": stream_id,
            "task_id": task_id,
            "step_id": "planning",
            "step_type": "planning",
            "action": "LLM 正在规划研究方案",
            "status": "processing",
        }

        query_plan = self._llm_query_planner.plan(user_query)

        yield {
            "type": "research_step",
            "stream_id": stream_id,
            "task_id": task_id,
            "step_id": "planning",
            "step_type": "planning",
            "action": "LLM 规划完成",
            "status": "success",
            "result_summary": f"{len(query_plan.sub_queries)} 个子任务：{query_plan.reasoning}",
            "execution_time": 0.5,
        }

        # 步骤2：执行数据获取子查询
        data_sub_queries = [sq for sq in query_plan.sub_queries if sq.task_type == "data_fetch"]
        analysis_sub_queries = [sq for sq in query_plan.sub_queries if sq.task_type == "analysis"]

        success_results = []
        aggregated_datasets = []

        for idx, sub_query in enumerate(data_sub_queries, 1):
            step_id = f"fetch-{idx}"

            # 推送开始消息
            yield {
                "type": "research_step",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": step_id,
                "step_type": "data_fetch",
                "action": f"获取数据：{sub_query.query}",
                "status": "processing",
            }

            # 执行查询
            step_start = time.time()

            query_result = self.data_query_service.query(
                user_query=sub_query.query,
                filter_datasource=sub_query.datasource,
                use_cache=use_cache,
                prefer_single_route=self._should_force_single_route(sub_query.datasource),
            )

            execution_time = time.time() - step_start

            if query_result.status == "success":
                # 构建 Panel 数据
                datasets = query_result.datasets or []
                aggregated_datasets.extend(datasets)

                panel_result = self._build_panel(datasets, sub_query.query)

                # 推送 Panel 数据
                yield {
                    "type": "research_panel",
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "sub_query": sub_query.query,
                    "data_source": sub_query.datasource,
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
                    "task_id": task_id,
                    "step_id": step_id,
                    "step_type": "data_fetch",
                    "action": f"获取数据：{sub_query.query}",
                    "status": "success",
                    "result_summary": f"获取 {len(query_result.items)} 条数据",
                    "execution_time": execution_time,
                }

                success_results.append({
                    "sub_query": sub_query,
                    "result": query_result,
                    "execution_time": execution_time,
                })
            else:
                # 推送失败消息
                yield {
                    "type": "research_step",
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "step_type": "data_fetch",
                    "action": f"获取数据：{sub_query.query}",
                    "status": "error",
                    "result_summary": query_result.reasoning or "数据获取失败",
                    "execution_time": execution_time,
                }

        # 步骤3：执行分析子查询
        for idx, sub_query in enumerate(analysis_sub_queries, 1):
            step_id = f"analysis-{idx}"

            yield {
                "type": "research_step",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": step_id,
                "step_type": "analysis",
                "action": f"AI 分析：{sub_query.query}",
                "status": "processing",
            }

            step_start = time.time()

            # 执行分析
            analysis_summaries = self._run_analysis_sub_queries(
                [sub_query],
                aggregated_datasets
            )

            execution_time = time.time() - step_start

            if analysis_summaries:
                summary_data = analysis_summaries[0]

                # 推送分析结果
                yield {
                    "type": "research_analysis",
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "query": summary_data["query"],
                    "summary": summary_data["summary"],
                    "item_count": summary_data.get("item_count", 0),
                    "execution_time": execution_time,
                }

                # 推送成功消息
                yield {
                    "type": "research_step",
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "step_type": "analysis",
                    "action": f"AI 分析：{sub_query.query}",
                    "status": "success",
                    "result_summary": "分析完成",
                    "execution_time": execution_time,
                }

        # 步骤4：推送完成消息
        total_time = time.time() - start_time

        yield {
            "type": "research_complete",
            "stream_id": stream_id,
            "task_id": task_id,
            "success": True,
            "message": f"研究完成：{len(success_results)} 组数据，{len(analysis_sub_queries)} 项分析",
            "total_time": total_time,
            "metadata": {
                "query_plan": {
                    "reasoning": query_plan.reasoning,
                    "sub_query_count": len(query_plan.sub_queries),
                },
                "success_count": len(success_results),
                "failure_count": len(data_sub_queries) - len(success_results),
            }
        }

    except Exception as exc:
        logger.error("复杂研究流式处理失败: %s", exc, exc_info=True)
        yield {
            "type": "research_error",
            "stream_id": stream_id,
            "task_id": task_id,
            "error_code": "RESEARCH_ERROR",
            "error_message": str(exc),
        }
```

#### 3. 新增 WebSocket 端点

**新增文件**：`api/controllers/research_stream.py`

```python
"""
研究模式 WebSocket 流式控制器
专属研究视图的实时推送
"""

import logging
import asyncio
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from uuid import uuid4

from api.controllers.chat_controller import get_chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/research", tags=["research-stream"])


def generate_task_id() -> str:
    """生成研究任务ID"""
    return f"research-{uuid4().hex[:12]}"


@router.websocket("/stream")
async def research_stream_ws(
    websocket: WebSocket,
    chat_service: Any = Depends(get_chat_service)
):
    """
    研究模式 WebSocket 流式接口

    客户端发送：
    {
        "query": "用户查询",
        "filter_datasource": null,
        "use_cache": true,
        "task_id": "可选，前端生成的任务ID"
    }

    服务端推送：
    - research_start: 研究开始
    - research_step: 步骤更新
    - research_panel: Panel数据
    - research_analysis: 分析结果
    - research_complete: 研究完成
    - research_error: 错误
    """
    await websocket.accept()
    task_id = None

    try:
        # 接收请求
        request_data = await websocket.receive_json()
        user_query = request_data.get("query", "")
        filter_datasource = request_data.get("filter_datasource")
        use_cache = request_data.get("use_cache", True)
        task_id = request_data.get("task_id") or generate_task_id()

        logger.info(f"[{task_id}] 收到研究请求: {user_query}")

        # 验证查询
        if not user_query or not user_query.strip():
            await websocket.send_json({
                "type": "research_error",
                "task_id": task_id,
                "error_code": "VALIDATION_ERROR",
                "error_message": "查询不能为空",
            })
            await websocket.close()
            return

        # 检查是否有流式生成器方法
        if not hasattr(chat_service, '_handle_complex_research_streaming'):
            logger.error(f"[{task_id}] ChatService 缺少 _handle_complex_research_streaming 方法")
            await websocket.send_json({
                "type": "research_error",
                "task_id": task_id,
                "error_code": "METHOD_NOT_FOUND",
                "error_message": "研究流式处理方法未实现",
            })
            await websocket.close()
            return

        # 创建流式生成器
        message_generator = chat_service._handle_complex_research_streaming(
            task_id=task_id,
            user_query=user_query,
            filter_datasource=filter_datasource,
            use_cache=use_cache,
            intent_confidence=0.9,
            llm_logs=None,
        )

        # 逐个推送消息
        while True:
            try:
                message = await asyncio.to_thread(next, message_generator, None)
                if message is None:
                    break

                await websocket.send_json(message)
                logger.debug(f"[{task_id}] 推送消息: {message['type']}")

            except StopIteration:
                break
            except Exception as e:
                logger.error(f"[{task_id}] 消息推送失败: {e}", exc_info=True)
                break

        logger.info(f"[{task_id}] 研究流式处理完成")

    except WebSocketDisconnect:
        logger.info(f"[{task_id}] 客户端断开连接")
    except Exception as e:
        logger.error(f"[{task_id}] WebSocket 处理失败: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "research_error",
                "task_id": task_id or "unknown",
                "error_code": "INTERNAL_ERROR",
                "error_message": str(e),
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
            logger.info(f"[{task_id}] WebSocket 连接已关闭")
        except:
            pass
```

#### 4. 注册路由

**修改文件**：`api/app.py`

```python
# 导入新的研究流式路由
from api.controllers import research_stream

# 注册路由
app.include_router(research_stream.router)
```

---

### 二、前端实现

#### 1. 路由配置

**修改文件**：`frontend/src/router/index.ts`（如果没有则创建）

```typescript
import { createRouter, createWebHistory } from 'vue-router';
import ResearchView from '@/views/ResearchView.vue';
import MainView from '@/views/MainView.vue';  // 原来的 App.vue 内容

const routes = [
  {
    path: '/',
    name: 'Home',
    component: MainView,
  },
  {
    path: '/research/:taskId',
    name: 'Research',
    component: ResearchView,
    props: true,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
```

#### 2. 研究视图 Store

**新增文件**：`frontend/src/stores/researchViewStore.ts`

```typescript
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export interface ResearchStep {
  step_id: string;
  step_type: 'planning' | 'data_fetch' | 'analysis';
  action: string;
  status: 'processing' | 'success' | 'error';
  result_summary?: string;
  execution_time?: number;
}

export interface ResearchPanel {
  sub_query: string;
  data_source?: string;
  item_count: number;
  panel_payload: any;
  data_blocks: Record<string, any>;
}

export interface ResearchAnalysis {
  query: string;
  summary: string;
  item_count: number;
  execution_time: number;
}

export interface ResearchTask {
  task_id: string;
  query: string;
  status: 'idle' | 'planning' | 'processing' | 'completed' | 'error';

  // 研究计划
  plan?: {
    reasoning: string;
    sub_query_count: number;
  };

  // 执行步骤
  steps: ResearchStep[];

  // Panel 数据
  panels: ResearchPanel[];

  // 分析结果
  analyses: ResearchAnalysis[];

  // 元数据
  metadata?: {
    total_time?: number;
    success_count?: number;
    failure_count?: number;
  };

  // 错误信息
  error?: string;
}

export const useResearchViewStore = defineStore('researchView', () => {
  const currentTask = ref<ResearchTask | null>(null);

  // 创建新研究任务
  const createTask = (taskId: string, query: string) => {
    currentTask.value = {
      task_id: taskId,
      query,
      status: 'idle',
      steps: [],
      panels: [],
      analyses: [],
    };
  };

  // 更新研究计划
  const updatePlan = (plan: any) => {
    if (currentTask.value) {
      currentTask.value.plan = plan;
      currentTask.value.status = 'planning';
    }
  };

  // 更新步骤
  const updateStep = (step: ResearchStep) => {
    if (!currentTask.value) return;

    const index = currentTask.value.steps.findIndex(s => s.step_id === step.step_id);
    if (index >= 0) {
      currentTask.value.steps[index] = step;
    } else {
      currentTask.value.steps.push(step);
    }

    // 更新状态
    if (step.status === 'processing') {
      currentTask.value.status = 'processing';
    }
  };

  // 添加 Panel
  const addPanel = (panel: ResearchPanel) => {
    if (currentTask.value) {
      currentTask.value.panels.push(panel);
    }
  };

  // 添加分析结果
  const addAnalysis = (analysis: ResearchAnalysis) => {
    if (currentTask.value) {
      currentTask.value.analyses.push(analysis);
    }
  };

  // 完成研究
  const completeTask = (metadata: any) => {
    if (currentTask.value) {
      currentTask.value.status = 'completed';
      currentTask.value.metadata = metadata;
    }
  };

  // 错误处理
  const errorTask = (error: string) => {
    if (currentTask.value) {
      currentTask.value.status = 'error';
      currentTask.value.error = error;
    }
  };

  // 清空当前任务
  const clearTask = () => {
    currentTask.value = null;
  };

  // 计算属性
  const isProcessing = computed(() => {
    return currentTask.value?.status === 'processing' ||
           currentTask.value?.status === 'planning';
  });

  const hasData = computed(() => {
    return (currentTask.value?.panels.length || 0) > 0;
  });

  const hasAnalysis = computed(() => {
    return (currentTask.value?.analyses.length || 0) > 0;
  });

  return {
    currentTask,
    createTask,
    updatePlan,
    updateStep,
    addPanel,
    addAnalysis,
    completeTask,
    errorTask,
    clearTask,
    isProcessing,
    hasData,
    hasAnalysis,
  };
});
```

#### 3. WebSocket Composable

**新增文件**：`frontend/src/composables/useResearchWebSocket.ts`

```typescript
import { ref, onUnmounted } from 'vue';
import { useResearchViewStore } from '@/stores/researchViewStore';

export function useResearchWebSocket() {
  const researchStore = useResearchViewStore();
  const ws = ref<WebSocket | null>(null);
  const isConnected = ref(false);
  const error = ref<string | null>(null);

  const connect = (taskId: string, query: string) => {
    // WebSocket URL
    const wsUrl = `ws://localhost:8000/api/v1/research/stream`;

    console.log(`[Research WS] Connecting to ${wsUrl}`);
    ws.value = new WebSocket(wsUrl);

    ws.value.onopen = () => {
      console.log('[Research WS] Connected');
      isConnected.value = true;
      error.value = null;

      // 发送查询请求
      ws.value?.send(JSON.stringify({
        task_id: taskId,
        query,
        use_cache: true,
      }));
    };

    ws.value.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('[Research WS] Message:', message);

      switch (message.type) {
        case 'research_start':
          researchStore.updatePlan(message.plan);
          break;

        case 'research_step':
          researchStore.updateStep(message);
          break;

        case 'research_panel':
          researchStore.addPanel({
            sub_query: message.sub_query,
            data_source: message.data_source,
            item_count: message.item_count,
            panel_payload: message.panel_payload,
            data_blocks: message.data_blocks,
          });
          break;

        case 'research_analysis':
          researchStore.addAnalysis({
            query: message.query,
            summary: message.summary,
            item_count: message.item_count,
            execution_time: message.execution_time,
          });
          break;

        case 'research_complete':
          researchStore.completeTask(message.metadata);
          break;

        case 'research_error':
          researchStore.errorTask(message.error_message);
          error.value = message.error_message;
          break;
      }
    };

    ws.value.onerror = (event) => {
      console.error('[Research WS] Error:', event);
      error.value = '连接失败';
      researchStore.errorTask('WebSocket 连接失败');
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
      isConnected.value = false;
    }
  };

  onUnmounted(() => {
    disconnect();
  });

  return {
    connect,
    disconnect,
    isConnected,
    error,
  };
}
```

#### 4. 研究视图主组件

**新增文件**：`frontend/src/views/ResearchView.vue`

```vue
<template>
  <div class="research-view h-screen flex flex-col bg-background">
    <!-- 顶部导航栏 -->
    <ResearchTopBar
      :query="researchStore.currentTask?.query || ''"
      :is-processing="researchStore.isProcessing"
      @back="handleBack"
      @export="handleExport"
    />

    <!-- 主内容区 -->
    <div class="flex-1 flex overflow-hidden">
      <!-- 左侧：研究上下文面板 -->
      <div class="w-[30%] border-r border-border overflow-y-auto">
        <ResearchContextPanel
          :task="researchStore.currentTask"
        />
      </div>

      <!-- 右侧：数据可视化面板 -->
      <div class="flex-1 overflow-y-auto bg-muted/20 p-6">
        <ResearchDataPanel
          :panels="researchStore.currentTask?.panels || []"
        />
      </div>
    </div>

    <!-- 加载状态 -->
    <div
      v-if="!researchStore.currentTask"
      class="absolute inset-0 flex items-center justify-center bg-background/80"
    >
      <div class="text-center">
        <Loader class="h-8 w-8 animate-spin mx-auto mb-4" />
        <p class="text-muted-foreground">正在初始化研究...</p>
      </div>
    </div>

    <!-- 错误提示 -->
    <Alert v-if="wsError" variant="destructive" class="absolute bottom-4 right-4 w-96">
      <AlertCircle class="h-4 w-4" />
      <AlertTitle>连接错误</AlertTitle>
      <AlertDescription>{{ wsError }}</AlertDescription>
    </Alert>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useResearchViewStore } from '@/stores/researchViewStore';
import { useResearchWebSocket } from '@/composables/useResearchWebSocket';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Loader, AlertCircle } from 'lucide-vue-next';
import ResearchTopBar from '@/features/research/components/ResearchTopBar.vue';
import ResearchContextPanel from '@/features/research/components/ResearchContextPanel.vue';
import ResearchDataPanel from '@/features/research/components/ResearchDataPanel.vue';

const router = useRouter();
const route = useRoute();
const researchStore = useResearchViewStore();
const { connect, disconnect, error: wsError } = useResearchWebSocket();

// 从路由参数获取任务信息
const taskId = route.params.taskId as string;
const query = route.query.query as string;

onMounted(() => {
  if (!taskId || !query) {
    console.error('Missing taskId or query');
    router.push('/');
    return;
  }

  // 创建研究任务
  researchStore.createTask(taskId, query);

  // 建立 WebSocket 连接
  connect(taskId, query);
});

onUnmounted(() => {
  disconnect();
  researchStore.clearTask();
});

const handleBack = () => {
  router.push('/');
};

const handleExport = () => {
  // TODO: 实现导出功能
  console.log('导出研究报告');
};
</script>

<style scoped>
.research-view {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>
```

---

## 文件清单

### 后端新增/修改文件

1. **新增**：`api/schemas/stream_messages.py`（扩展）
   - 新增研究消息类型定义

2. **修改**：`services/chat_service.py`
   - 新增 `_handle_complex_research_streaming` 方法

3. **新增**：`api/controllers/research_stream.py`
   - 研究 WebSocket 端点

4. **修改**：`api/app.py`
   - 注册新路由

### 前端新增文件

1. **新增**：`frontend/src/router/index.ts`
   - 路由配置

2. **新增**：`frontend/src/stores/researchViewStore.ts`
   - 研究视图状态管理

3. **新增**：`frontend/src/composables/useResearchWebSocket.ts`
   - WebSocket 连接管理

4. **新增**：`frontend/src/views/ResearchView.vue`
   - 研究视图主容器

5. **新增**：`frontend/src/features/research/components/ResearchTopBar.vue`
   - 顶部导航栏

6. **新增**：`frontend/src/features/research/components/ResearchContextPanel.vue`
   - 左侧上下文面板

7. **新增**：`frontend/src/features/research/components/ResearchDataPanel.vue`
   - 右侧数据面板

8. **修改**：`frontend/src/App.vue`
   - 改为使用 router-view

9. **修改**：`frontend/src/main.ts`
   - 注册 router

---

## 实施步骤

### 第1步：后端基础设施（Day 1上午）

1. ✅ 新增消息类型定义
2. ✅ 实现流式生成器方法
3. ✅ 创建 WebSocket 端点
4. ✅ 注册路由

### 第2步：前端路由和Store（Day 1下午）

1. ✅ 配置 Vue Router
2. ✅ 创建 researchViewStore
3. ✅ 实现 WebSocket composable

### 第3步：前端核心组件（Day 2上午）

1. ✅ 实现 ResearchView 主容器
2. ✅ 实现 ResearchTopBar
3. ✅ 实现基础的 ResearchContextPanel
4. ✅ 实现基础的 ResearchDataPanel

### 第4步：测试和调试（Day 2下午）

1. ✅ 端到端测试
2. ✅ WebSocket 连接测试
3. ✅ 实时推送测试
4. ✅ 视图切换测试

### 第5步：UI优化（Day 3）

1. ✅ 样式优化
2. ✅ 响应式布局
3. ✅ 加载状态
4. ✅ 错误处理

---

## 开发优先级

### P0（必须，Day 1-2）
- 后端流式生成器
- WebSocket 连接
- 研究视图基础布局
- 实时步骤更新
- Panel 数据展示
- 分析结果展示

### P1（Day 3-4）
- UI/UX 优化
- 错误处理
- 加载状态
- 返回主界面

### P2（Day 5+）
- 追问对话
- 导出报告
- 分享功能

---

## 注意事项

1. **WebSocket 连接管理**
   - 实现心跳机制
   - 实现自动重连
   - 处理异常断线

2. **状态管理**
   - 研究任务状态要完整
   - Panel 数据要正确传递
   - 避免内存泄漏

3. **性能优化**
   - Panel 数据懒加载
   - 虚拟滚动（如果Panel很多）
   - 防抖和节流

4. **用户体验**
   - 流畅的动画过渡
   - 清晰的加载状态
   - 友好的错误提示

---

## 测试计划

### 单元测试
- [ ] 后端流式生成器测试
- [ ] Store 状态管理测试
- [ ] WebSocket composable 测试

### 集成测试
- [ ] WebSocket 端到端测试
- [ ] 研究视图渲染测试
- [ ] 视图切换测试

### 手动测试场景
1. 启动研究 → 观察实时推送
2. 中途断开网络 → 观察错误处理
3. 返回主界面 → 观察状态清理
4. 刷新页面 → 观察恢复逻辑

---

## 下一步行动

现在开始按照优先级实施：

1. **后端 P0**（先做）
   - 新增消息类型
   - 实现流式生成器
   - 创建 WebSocket 端点

2. **前端 P0**（后做）
   - 配置路由
   - 创建 Store
   - 实现主要组件

准备好了吗？我们开始编写代码！
