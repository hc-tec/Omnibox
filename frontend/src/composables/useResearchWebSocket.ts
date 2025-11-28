/**
 * 研究模式 WebSocket 管理
 */

import { ref } from "vue";
import { useResearchViewStore } from "@/store/researchViewStore";
import { useResearchStore } from "@/features/research/stores/researchStore";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { resolveHttpBase, resolveWsBase } from "@/shared/networkBase";
import type {
  ResearchAnalysis,
  ResearchPanel,
  ResearchStep,
  ResearchStepType,
  ResearchStepStatus,
} from "@/store/researchViewStore";

interface ResearchWebSocketOptions {
  /** 研究任务 ID */
  taskId: string;
  /** WebSocket 基础地址，支持相对路径 */
  url?: string;
  /** 是否自动重连 */
  autoReconnect?: boolean;
  /** 重连延迟（毫秒） */
  reconnectDelay?: number;
  /** 最大重连次数 */
  maxReconnectAttempts?: number;
}

const API_BASE = resolveHttpBase(import.meta.env.VITE_API_BASE, "/api/v1");
type StreamStageType = "intent" | "rag" | "fetch" | "summary";

interface StageStreamMessage {
  type: "stage";
  stage: StreamStageType;
  message: string;
  progress?: number;
  timestamp: string;
}

interface DataStreamMessage {
  type: "data";
  stage?: string;
  data?: Record<string, any>;
  timestamp: string;
}

interface GraphNodeStreamMessage {
  type: "graph_node";
  node_id: string;
  node_type: string;
  status: "pending" | "running" | "success" | "error" | "skipped";
  description?: string;
  input_refs?: string[];
  summary?: Record<string, any>;
  error?: string;
  timestamp: string;
  stream_id: string;
}

interface CompleteStreamMessage {
  type: "complete";
  success: boolean;
  message: string;
  total_time?: number;
  timestamp: string;
  stream_id: string;
}

interface ErrorStreamMessage {
  type: "error";
  error_code: string;
  error_message: string;
  timestamp: string;
  stream_id: string;
}

interface LLMCallStreamMessage {
  type: "llm_call";
  call_id: string;
  role: string;
  status: "started" | "completed" | "failed";
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  prompt_preview?: string;
  response_preview?: string;
  model?: string;
  timestamp: string;
}

const STAGE_STEP_META: Record<StreamStageType, { stepType: ResearchStepType; label: string }> = {
  intent: { stepType: "planning", label: "识别查询意图" },
  rag: { stepType: "data_fetch", label: "检索候选数据源" },
  fetch: { stepType: "data_fetch", label: "获取数据并执行工具" },
  summary: { stepType: "analysis", label: "生成总结与洞察" },
};

const STAGE_PROGRESS_HINT: Record<StreamStageType, number> = {
  intent: 15,
  rag: 35,
  fetch: 65,
  summary: 90,
};

const NODE_TYPE_META: Record<string, { stepType: ResearchStepType; label: string }> = {
  router: { stepType: "planning", label: "路由判定" },
  research_agent: { stepType: "analysis", label: "Research Agent 推理" },
  simple_chat: { stepType: "analysis", label: "简单回答" },
  tool_executor: { stepType: "data_fetch", label: "执行工具" },
  data_stasher: { stepType: "data_fetch", label: "数据暂存与摘要" },
  wait_for_human: { stepType: "analysis", label: "等待人工输入" },
};

const LLM_ROLE_META: Record<string, { stepType: ResearchStepType; label: string }> = {
  router: { stepType: "planning", label: "Router 决策" },
  planner: { stepType: "planning", label: "Planner 规划" },
  reflector: { stepType: "analysis", label: "Reflector 反思" },
  synthesizer: { stepType: "analysis", label: "Synthesizer 总结" },
  research_agent: { stepType: "analysis", label: "Research Agent 推理" },
  tool_executor: { stepType: "data_fetch", label: "Tool Executor 调度" },
  data_stasher: { stepType: "data_fetch", label: "DataStasher 摘要" },
  entity_resolver: { stepType: "planning", label: "实体解析" },
  query_parser: { stepType: "planning", label: "查询解析" },
  other: { stepType: "analysis", label: "LLM 调用" },
};

const GRAPH_STATUS_MAP: Record<string, ResearchStepStatus> = {
  pending: "pending",
  running: "processing",
  success: "success",
  error: "error",
  skipped: "success",
};

function isKnownStage(stage: unknown): stage is StreamStageType {
  return stage === "intent" || stage === "rag" || stage === "fetch" || stage === "summary";
}

function mapGraphNodeStatus(status: string): ResearchStepStatus {
  return GRAPH_STATUS_MAP[status] ?? "processing";
}

export function useResearchWebSocket(options: ResearchWebSocketOptions) {
const {
  taskId,
  url,
  autoReconnect = true,
  reconnectDelay = 3000,
  maxReconnectAttempts = 5,
} = options;

const viewStore = useResearchViewStore();
const researchTaskStore = useResearchStore();
const workspaceStore = useWorkspaceStore();
const envWsBase = import.meta.env.VITE_WS_BASE as string | undefined;

const ws = ref<WebSocket | null>(null);
  const isConnecting = ref(false);
  const isConnected = ref(false);
  const error = ref<string | null>(null);
  const reconnectAttempts = ref(0);
  const currentTaskId = ref(taskId);
// 统一使用 /api/v1/chat/stream 端点
const wsBaseUrl = ref(
  resolveWsBase(url ?? envWsBase, "/api/v1/chat/stream", API_BASE)
);
  let reconnectTimer: number | null = null;
  let activeStageStep: ResearchStep | null = null;

  function finalizeActiveStage(status: ResearchStepStatus, timestamp: string) {
    if (!activeStageStep) return;
    const updatedStep: ResearchStep = {
      ...activeStageStep,
      status,
      timestamp,
    };
    viewStore.handleResearchStep(updatedStep);
    if (status !== "processing") {
      activeStageStep = null;
    } else {
      activeStageStep = updatedStep;
    }
  }

  function beginStageStep(message: StageStreamMessage) {
    const meta = STAGE_STEP_META[message.stage];
    const newStep: ResearchStep = {
      step_id: `stage-${message.stage}`,
      step_type: meta.stepType,
      action: message.message || meta.label,
      status: "processing",
      details: {
        stage: message.stage,
        progress: message.progress ?? null,
      },
      timestamp: message.timestamp,
    };
    activeStageStep = newStep;
    viewStore.handleResearchStep(newStep);
    viewStore.ensurePlan(meta.label);
  }

  function handleStageStreamMessage(message: StageStreamMessage) {
    if (!isKnownStage(message.stage)) {
      return;
    }

    const stageId = `stage-${message.stage}`;
    if (activeStageStep && activeStageStep.step_id !== stageId) {
      finalizeActiveStage("success", message.timestamp);
    }

    if (activeStageStep && activeStageStep.step_id === stageId) {
      activeStageStep = {
        ...activeStageStep,
        action: message.message || activeStageStep.action,
        details: {
          ...(activeStageStep.details || {}),
          stage: message.stage,
          progress: message.progress ?? activeStageStep.details?.progress,
        },
        status: "processing",
        timestamp: message.timestamp,
      };
      viewStore.handleResearchStep(activeStageStep);
      return;
    }

    beginStageStep(message);
  }

  function updateStageDetails(stage: StreamStageType, details: Record<string, any>, timestamp: string) {
    const stageId = `stage-${stage}`;
    if (activeStageStep && activeStageStep.step_id === stageId) {
      activeStageStep = {
        ...activeStageStep,
        details: {
          ...(activeStageStep.details || {}),
          ...details,
        },
        timestamp,
      };
      viewStore.handleResearchStep(activeStageStep);
      return;
    }

    const meta = STAGE_STEP_META[stage];
    const newStep: ResearchStep = {
      step_id: stageId,
      step_type: meta.stepType,
      action: meta.label,
      status: "processing",
      details,
      timestamp,
    };
    activeStageStep = newStep;
    viewStore.handleResearchStep(newStep);
    viewStore.ensurePlan(meta.label);
  }

  function handleGraphNodeEvent(message: GraphNodeStreamMessage) {
    const meta = NODE_TYPE_META[message.node_type] ?? { stepType: "analysis" as ResearchStepType, label: message.node_type };
    const nodeStep: ResearchStep = {
      step_id: `node-${message.node_id}`,
      step_type: meta.stepType,
      action: message.description || meta.label,
      status: mapGraphNodeStatus(message.status),
      details: {
        summary: message.summary,
        error: message.error,
      },
      timestamp: message.timestamp,
    };
    viewStore.handleResearchStep(nodeStep);
  }

  function pushSummaryArtifacts(message: DataStreamMessage) {
    const summaryData = message.data || {};
    const payload = summaryData.data;
    if (payload) {
      viewStore.handleResearchPanel({
        step_id: `summary-${Date.now()}`,
        step_index: undefined,
        source_query: summaryData.metadata?.query || store.state.query || "研究结果",
        panel_payload: payload,
        data_blocks: summaryData.data_blocks ?? {},
        timestamp: message.timestamp,
      } as ResearchPanel);
    }

    const summaryText = summaryData.summary || summaryData.message || summaryData.metadata?.summary;
    if (summaryText) {
      viewStore.handleResearchAnalysis({
        step_id: `summary-analysis-${Date.now()}`,
        analysis_text: summaryText,
        is_complete: true,
        timestamp: message.timestamp,
      } as ResearchAnalysis);
    }
  }

  function handleTaskGraphData(message: DataStreamMessage) {
    if (message.stage && isKnownStage(message.stage)) {
      if (message.stage === "summary") {
        const summaryDetails = {
          success: message.data?.success,
          message: message.data?.message,
          block_count: Array.isArray(message.data?.data?.blocks)
            ? message.data.data.blocks.length
            : undefined,
        };
        updateStageDetails("summary", summaryDetails, message.timestamp);
        pushSummaryArtifacts(message);
      } else {
        updateStageDetails(message.stage, message.data || {}, message.timestamp);
      }
      return;
    }

    if (message.stage === "summary") {
      pushSummaryArtifacts(message);
    }
  }

  function handleLLMCallEvent(message: LLMCallStreamMessage) {
    const meta = LLM_ROLE_META[message.role] ?? LLM_ROLE_META.other;
    const statusMap: Record<string, ResearchStepStatus> = {
      started: "processing",
      completed: "success",
      failed: "error",
    };
    const llmStep: ResearchStep = {
      step_id: `llm-${message.call_id}`,
      step_type: meta.stepType,
      action: meta.label,
      status: statusMap[message.status] ?? "processing",
      details: {
        role: message.role,
        prompt_tokens: message.prompt_tokens,
        completion_tokens: message.completion_tokens,
        total_tokens: message.total_tokens,
        prompt_preview: message.prompt_preview,
        response_preview: message.response_preview,
        model: message.model,
      },
      timestamp: message.timestamp,
    };
    viewStore.handleResearchStep(llmStep);
  }

  function handleCompleteMessage(message: CompleteStreamMessage) {
    finalizeActiveStage(message.success ? "success" : "error", message.timestamp);
    viewStore.handleResearchComplete({
      success: message.success,
      total_time: message.total_time ?? 0,
      message: message.message,
      summary: message.message,
    });

    const taskIdentifier = currentTaskId.value;
    if (taskIdentifier) {
      const workspaceCard = workspaceStore.getCard(taskIdentifier);
      if (workspaceCard && workspaceCard.mode === "research") {
        if (message.success) {
          workspaceStore.updateCardStatus(taskIdentifier, "completed", {
            current_step: "研究完成",
            progress: 100,
          });
        } else {
          workspaceStore.updateCardStatus(taskIdentifier, "error", {
            error_message: message.message,
          });
        }
      }
    }
  }

  function handleErrorMessage(message: ErrorStreamMessage) {
    finalizeActiveStage("error", message.timestamp);
    viewStore.handleResearchError({
      error_code: message.error_code,
      error_message: message.error_message,
    });
    error.value = message.error_message;

    const taskIdentifier = currentTaskId.value;
    if (taskIdentifier) {
      const workspaceCard = workspaceStore.getCard(taskIdentifier);
      if (workspaceCard && workspaceCard.mode === "research") {
        workspaceStore.updateCardStatus(taskIdentifier, "error", {
          error_message: `[${message.error_code}] ${message.error_message}`,
        });
      }
    }
  }

  function buildWebSocketUrl(): string {
    const base = wsBaseUrl.value;
    const id = currentTaskId.value;
    if (!id) {
      return base;
    }
    const separator = base.includes("?") ? "&" : "?";
    return `${base}${separator}task_id=${encodeURIComponent(id)}`;
  }

  function connect() {
    if (isConnecting.value || isConnected.value) {
      console.warn("[useResearchWebSocket] Already connecting or connected");
      return;
    }
    if (!currentTaskId.value) {
      error.value = "缺少任务 ID，无法建立研究连接";
      return;
    }

    isConnecting.value = true;
    error.value = null;
    viewStore.setWebSocketConnecting(true);

    try {
      const socket = new WebSocket(buildWebSocketUrl());
      ws.value = socket;

      socket.addEventListener("open", handleOpen);
      socket.addEventListener("message", handleMessage);
      socket.addEventListener("error", handleError);
      socket.addEventListener("close", handleClose);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "连接失败";
      isConnecting.value = false;
      viewStore.setWebSocketConnecting(false);
      if (autoReconnect && reconnectAttempts.value < maxReconnectAttempts) {
        scheduleReconnect();
      }
    }
  }

  function disconnect() {
    if (ws.value) {
      ws.value.close();
      ws.value = null;
    }
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    isConnecting.value = false;
    isConnected.value = false;
    viewStore.setWebSocketConnected(false);
  }

  function sendResearchRequest(payload: {
    query: string;
    filter_datasource?: string | null;
    use_cache?: boolean;
    layout_snapshot?: any[] | null;
  }) {
    if (!ws.value || !isConnected.value) {
      error.value = "WebSocket 未连接";
      return;
    }
    if (!currentTaskId.value) {
      error.value = "缺少任务 ID";
      return;
    }

    const message = {
      ...payload,
      mode: "research",  // 添加 mode 参数，让后端识别为研究模式
      task_id: currentTaskId.value,
    };

    try {
      ws.value.send(JSON.stringify(message));
    } catch (err) {
      error.value = err instanceof Error ? err.message : "发送失败";
    }
  }

  function handleOpen() {
    isConnecting.value = false;
    isConnected.value = true;
    error.value = null;
    reconnectAttempts.value = 0;
    viewStore.setWebSocketConnected(true);
  }

  function handleMessage(event: MessageEvent) {
    try {
      const message = JSON.parse(event.data as string);
      switch (message.type) {
        case "stage":
          handleStageStreamMessage(message as StageStreamMessage);
          break;
        case "data":
          handleTaskGraphData(message as DataStreamMessage);
          break;
        case "graph_node":
          handleGraphNodeEvent(message as GraphNodeStreamMessage);
          break;
        case "llm_call":
          handleLLMCallEvent(message as LLMCallStreamMessage);
          break;
        case "complete":
          handleCompleteMessage(message as CompleteStreamMessage);
          break;
        case "error":
          handleErrorMessage(message as ErrorStreamMessage);
          break;
        case "research_start":
          viewStore.handleResearchStart({
            plan: message.plan,
          });
          break;
        case "research_step":
          viewStore.handleResearchStep({
            step_id: message.step_id,
            step_type: message.step_type,
            action: message.action,
            status: message.status,
            details: message.details,
            timestamp: message.timestamp,
          } as ResearchStep);

          // Phase 2: 更新 workspace 卡片进度
          const workspaceCard = workspaceStore.getCard(message.task_id || currentTaskId.value);
          if (workspaceCard && workspaceCard.mode === 'research') {
            // 计算进度：根据步骤状态推进
            // 简单策略：每个步骤推进 20%，最多到 90%（最后 10% 留给完成）
            const currentProgress = workspaceCard.progress || 10;
            const newProgress = message.status === 'success'
              ? Math.min(currentProgress + 20, 90)
              : currentProgress;

            workspaceStore.updateCardProgress(
              message.task_id || currentTaskId.value,
              newProgress,
              message.action || '正在研究...'
            );
          }
          break;
        case "research_panel":
          viewStore.handleResearchPanel({
            step_id: message.step_id,
            step_index: message.step_index,
            source_query: message.source_query,
            panel_payload: message.panel_payload,
            data_blocks: message.panel_data_blocks ?? {},
            timestamp: message.timestamp,
          } as ResearchPanel);
          break;
        case "research_analysis":
          viewStore.handleResearchAnalysis({
            step_id: message.step_id,
            step_index: message.step_index,
            analysis_text: message.analysis_text,
            is_complete: message.is_complete,
            timestamp: message.timestamp,
          } as ResearchAnalysis);
          break;
        case "research_complete":
          finalizeActiveStage(message.success ? "success" : "error", message.timestamp);
          viewStore.handleResearchComplete({
            success: message.success,
            total_time: message.total_time,
            message: message.message,
            summary: message.summary,
          });

          // Phase 2: 标记 workspace 卡片为完成
          const completedCard = workspaceStore.getCard(message.task_id || currentTaskId.value);
          if (completedCard && completedCard.mode === 'research') {
            if (message.success) {
              workspaceStore.updateCardStatus(
                message.task_id || currentTaskId.value,
                'completed',
                {
                  current_step: '研究完成',
                  progress: 100,
                }
              );
            } else {
              workspaceStore.updateCardStatus(
                message.task_id || currentTaskId.value,
                'error',
                {
                  error_message: message.message || '研究失败',
                }
              );
            }
          }
          break;
        case "research_error":
          finalizeActiveStage("error", message.timestamp);
          viewStore.handleResearchError({
            error_code: message.error_code,
            error_message: message.error_message,
          });
          error.value = `[${message.error_code}] ${message.error_message}`;

          // Phase 2: 标记 workspace 卡片为错误
          const errorCard = workspaceStore.getCard(message.task_id || currentTaskId.value);
          if (errorCard && errorCard.mode === 'research') {
            workspaceStore.updateCardStatus(
              message.task_id || currentTaskId.value,
              'error',
              {
                error_message: `[${message.error_code}] ${message.error_message}`,
              }
            );
          }
          break;
        default:
          console.warn("[useResearchWebSocket] Unknown message type:", message.type);
          break;
      }

      syncResearchTaskWithMessage(message);
    } catch (err) {
      console.error("[useResearchWebSocket] Message parsing failed:", err);
      error.value = "消息解析失败";
    }
  }

  function handleError(event: Event) {
    console.error("[useResearchWebSocket] WebSocket error:", event);
    error.value = "WebSocket 连接错误";
  }

  function handleClose(event: CloseEvent) {
    console.log(`[useResearchWebSocket] Connection closed (code: ${event.code}, reason: ${event.reason})`);
    isConnecting.value = false;
    isConnected.value = false;
    viewStore.setWebSocketConnected(false);

    if (event.code !== 1000 && autoReconnect && reconnectAttempts.value < maxReconnectAttempts) {
      scheduleReconnect();
    }
  }

  function scheduleReconnect() {
    reconnectAttempts.value += 1;
    const delay = reconnectDelay * reconnectAttempts.value;
    reconnectTimer = window.setTimeout(() => {
      connect();
    }, delay);
  }

  function syncResearchTaskWithMessage(message: any) {
    const taskIdentifier = currentTaskId.value;
    if (!taskIdentifier) return;

    if (message.type === "stage" && isKnownStage(message.stage)) {
      const query = viewStore.state.query || message.message || "";
      researchTaskStore.ensureTask(taskIdentifier, query);
      researchTaskStore.markTaskProcessing(taskIdentifier);
      researchTaskStore.updateTaskStep(taskIdentifier, {
        step_id: `stage-${message.stage}`,
        action: message.message,
        status: "processing",
        timestamp: message.timestamp,
      });
      const progressHint = STAGE_PROGRESS_HINT[message.stage];
      if (typeof progressHint === "number") {
        const workspaceCard = workspaceStore.getCard(taskIdentifier);
        if (workspaceCard && workspaceCard.mode === "research") {
          workspaceStore.updateCardProgress(
            taskIdentifier,
            progressHint,
            message.message || "研究进行中"
          );
        }
      }
      return;
    }

    if (message.type === "graph_node") {
      researchTaskStore.updateTaskStep(taskIdentifier, {
        step_id: `node-${message.node_id}`,
        action: message.description || message.node_id,
        status: mapGraphNodeStatus(message.status),
        timestamp: message.timestamp,
      });
      return;
    }

    if (message.type === "data" && message.stage === "summary" && message.data?.data) {
      researchTaskStore.appendPreview(taskIdentifier, {
        previews: [
          {
            title: message.data.metadata?.query || store.state.query || "研究结果",
            items: buildPreviewItems(message.data.data),
            generated_path: message.data.data?.layout?.mode,
            source: message.data.metadata?.source,
          },
        ],
      });
      return;
    }

    if (message.type === "complete") {
      researchTaskStore.completeTask(taskIdentifier, message.message, {
        task_id: taskIdentifier,
        total_time: message.total_time,
        success: message.success,
      } as any);
      return;
    }

    if (message.type === "error") {
      researchTaskStore.setTaskError(taskIdentifier, message.error_message);
      return;
    }

    if (message.type === "research_start") {
      const query = viewStore.state.query || message.query || "";
      researchTaskStore.ensureTask(taskIdentifier, query);
      researchTaskStore.markTaskProcessing(taskIdentifier);
      return;
    }

    if (message.type === "research_step") {
      researchTaskStore.updateTaskStep(taskIdentifier, {
        step_id: message.step_id,
        action: message.action,
        status: message.status,
        timestamp: message.timestamp,
      });
      if (message.status === "error" && message.details?.error) {
        researchTaskStore.setTaskError(taskIdentifier, message.details.error);
      }
      return;
    }

    if (message.type === "research_panel") {
      researchTaskStore.appendPreview(taskIdentifier, {
        preview_id: `${taskIdentifier}-${message.step_id}-${Date.now()}`,
        title: message.source_query,
        items: buildPreviewItems(message.panel_payload),
        generated_path: message.panel_payload?.layout?.nodes?.[0]?.id,
        source: message.panel_payload?.layout?.mode,
      });
      return;
    }

    if (message.type === "research_complete") {
      researchTaskStore.completeTask(
        taskIdentifier,
        message.summary || message.message || "研究完成",
        {
          task_id: taskIdentifier,
          mode: "research",
          total_time: message.total_time,
          success: message.success,
        } as any
      );
      return;
    }

    if (message.type === "research_error") {
      researchTaskStore.setTaskError(taskIdentifier, message.error_message);
    }
  }

  function buildPreviewItems(panelPayload: any): Record<string, unknown>[] {
    const components = panelPayload?.components;
    if (!components || typeof components !== "object") {
      return [
        {
          status: "updated",
        },
      ];
    }

    const entries: Record<string, unknown>[] = [];
    for (const value of Object.values(components) as Array<Record<string, any>>) {
      const items = Array.isArray(value?.items) ? value.items : [];
      for (const item of items) {
        if (entries.length >= 3) break;
        entries.push(item as Record<string, unknown>);
      }
      if (entries.length >= 3) break;
    }

    if (!entries.length) {
      entries.push({
        title: panelPayload?.layout?.mode ?? "Panel",
      });
    }

    return entries.slice(0, 3);
  }

  // 注意：不在这里调用 onUnmounted，因为此 composable 可能在非组件上下文中被调用
  // 连接的清理由以下方式处理：
  // 1. 组件主动调用 disconnect()
  // 2. 全局管理器的 disconnectAndCleanup()
  // 3. 浏览器关闭/刷新时自动清理

  return {
    isConnecting,
    isConnected,
    error,
    reconnectAttempts,
    connect,
    disconnect,
    sendResearchRequest,
  };
}
