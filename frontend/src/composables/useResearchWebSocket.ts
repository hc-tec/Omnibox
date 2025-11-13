/**
 * 研究模式 WebSocket 管理
 */

import { ref, onUnmounted } from "vue";
import { useResearchViewStore } from "@/store/researchViewStore";
import { useResearchStore } from "@/features/research/stores/researchStore";
import { resolveHttpBase, resolveWsBase } from "@/shared/networkBase";
import type {
  ResearchAnalysis,
  ResearchPanel,
  ResearchStep,
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
const envWsBase = import.meta.env.VITE_RESEARCH_WS_BASE as string | undefined;

const ws = ref<WebSocket | null>(null);
  const isConnecting = ref(false);
  const isConnected = ref(false);
  const error = ref<string | null>(null);
  const reconnectAttempts = ref(0);
  const currentTaskId = ref(taskId);
const wsBaseUrl = ref(
  resolveWsBase(url ?? envWsBase, "/api/v1/chat/research-stream", API_BASE)
);
  let reconnectTimer: number | null = null;

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
          viewStore.handleResearchComplete({
            success: message.success,
            total_time: message.total_time,
            message: message.message,
            summary: message.summary,
          });
          break;
        case "research_error":
          viewStore.handleResearchError({
            error_code: message.error_code,
            error_message: message.error_message,
          });
          error.value = `[${message.error_code}] ${message.error_message}`;
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

  onUnmounted(() => {
    disconnect();
  });

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
