import { defineStore } from "pinia";
import { ref, computed, watch } from "vue";
import type {
  DataBlock,
  LayoutNode,
  LayoutSnapshotItem,
  LLMCallEvent,
  PanelPayload,
  PanelResponse,
  PanelStreamFetchPayload,
  PanelStreamSummaryPayload,
  StreamMessage,
  UIBlock,
} from "../shared/types/panel";
import { requestPanel, PanelStreamClient } from "../services/panelApi";
import type { PanelSizePreset } from "@/shared/panelSizePresets";
import { PANEL_SIZE_PRESETS } from "@/shared/panelSizePresets";

interface PanelState {
  layout: PanelPayload["layout"] | null;
  blocks: PanelPayload["blocks"];
  dataBlocks: Record<string, DataBlock>;
  metadata: PanelResponse["metadata"];
  message: string;
  loading: boolean;
  streamLoading: boolean;
  streamLog: StreamMessage[];
  fetchSnapshot: PanelStreamFetchPayload | null;
  layoutSnapshot: LayoutSnapshotItem[];
  sizePreset: PanelSizePreset;
  llmCalls: LLMCallEvent[];  // V5.0 可观测性：LLM 调用追踪
}

const streamClient = new PanelStreamClient();

function deriveLayoutSnapshot(layout: PanelPayload["layout"] | null, blocks: UIBlock[]): LayoutSnapshotItem[] {
  if (!layout) return [];
  const lookup = new Map(blocks.map((block) => [block.id, block]));
  const snapshots: LayoutSnapshotItem[] = [];
  layout.nodes.forEach((node, index) => {
    const blockId = node.children?.[0];
    if (!blockId) return;
    const block = lookup.get(blockId);
    const grid = (node.props as any)?.grid ?? {};
    snapshots.push({
      block_id: blockId,
      component: block?.component ?? "Unknown",
      x: grid.x ?? (index % 12),
      y: grid.y ?? Math.floor(index / 12),
      w: grid.w ?? 12,
      h: grid.h ?? 1,
    });
  });
  return snapshots;
}

export const usePanelStore = defineStore("panel", () => {
  const state = ref<PanelState>({
    layout: null,
    blocks: [],
    dataBlocks: {},
    metadata: {},
    message: "",
    loading: false,
    streamLoading: false,
    streamLog: [],
    fetchSnapshot: null,
    layoutSnapshot: [],
    sizePreset: "balanced",
    llmCalls: [],  // V5.0 可观测性
  });

  function applySizePresetStyles(preset: PanelSizePreset) {
    const cfg = PANEL_SIZE_PRESETS[preset];
    const root = document.documentElement;
    root.style.setProperty("--panel-grid-gap", `${cfg.gridGap}px`);
    root.style.setProperty("--panel-card-padding", `${cfg.cardPadding}px`);
    root.style.setProperty("--panel-card-radius", `${cfg.cardRadius}px`);
    root.style.setProperty("--panel-font-scale", `${cfg.fontScale}`);
    root.style.setProperty("--panel-heading-size", `${cfg.headingSize}px`);
    root.style.setProperty("--panel-meta-size", `${cfg.metaSize}px`);
    root.style.setProperty("--panel-spacing-scale", `${cfg.spacingScale}`);
  }

  watch(
    () => state.value.sizePreset,
    (preset) => applySizePresetStyles(preset),
    { immediate: true }
  );

  const hasPanel = computed(() => !!state.value.layout && state.value.blocks.length > 0);

  async function fetchPanel(
    query: string,
    filterDatasource?: string | null,
    layoutSnapshot?: LayoutSnapshotItem[] | null,
    mode?: string,
    clientTaskId?: string | null
  ): Promise<PanelResponse> {
    state.value.loading = true;
    try {
      const response = await requestPanel({
        query,
        filter_datasource: filterDatasource,
        use_cache: true,
        layout_snapshot: layoutSnapshot ?? state.value.layoutSnapshot ?? null,
        mode: mode as any,
        client_task_id: clientTaskId ?? null,
      });

      // 检测复杂任务：后端返回 requires_streaming=true 时自动切换到流式
      if (response.metadata?.requires_streaming) {
        console.log("[PanelStore] 检测到复杂任务，自动切换到流式接口");
        state.value.loading = false;
        // 返回一个 Promise，在流式完成时 resolve
        return new Promise((resolve) => {
          connectStreamWithCallback(
            query,
            filterDatasource,
            layoutSnapshot ?? state.value.layoutSnapshot ?? null,
            mode,
            (finalResponse) => resolve(finalResponse)
          );
        });
      }

      if (response.success && response.data) {
        applyPanelPayload(response);
      }
      state.value.message = response.message;
      state.value.metadata = response.metadata;
      return response;
    } finally {
      state.value.loading = false;
    }
  }

  // 带回调的流式连接（用于自动切换场景）
  function connectStreamWithCallback(
    query: string,
    filterDatasource?: string | null,
    layoutSnapshot?: LayoutSnapshotItem[] | null,
    mode?: string,
    onComplete?: (response: PanelResponse) => void
  ) {
    state.value.streamLoading = true;
    state.value.streamLog = [];
    state.value.fetchSnapshot = null;
    state.value.llmCalls = [];  // V5.0：清空 LLM 调用记录

    streamClient.connect(
      {
        query,
        filter_datasource: filterDatasource ?? null,
        use_cache: true,
        layout_snapshot: layoutSnapshot ?? state.value.layoutSnapshot ?? null,
        mode: mode as any,
      },
      (message) => {
        state.value.streamLog.push(message);
        if (message.type === "data" && message.stage === "fetch") {
          state.value.fetchSnapshot = message.data as PanelStreamFetchPayload;
        }
        if (message.type === "data" && message.stage === "summary") {
          const summary = message.data as PanelStreamSummaryPayload;
          if (summary.success && summary.data) {
            applyPanelPayload({
              success: summary.success,
              message: summary.message,
              data: summary.data,
              data_blocks: summary.data_blocks,
              metadata: summary.metadata,
            });
          }
          state.value.message = summary.message;
          state.value.metadata = summary.metadata;
        }
        // V5.0 可观测性：处理 LLM 调用事件
        if (message.type === "llm_call") {
          state.value.llmCalls.push({
            call_id: message.call_id,
            role: message.role,
            status: message.status,
            step_id: message.step_id,
            stream_id: message.stream_id,
            timestamp: message.timestamp,
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
            metadata: message.metadata,
          });
        }
        if (message.type === "complete" || message.type === "error") {
          state.value.streamLoading = false;
          // 调用回调返回最终响应
          if (onComplete) {
            onComplete({
              success: message.type === "complete" && (message as any).success !== false,
              message: state.value.message,
              data: state.value.layout ? {
                mode: state.value.layout.mode,
                layout: state.value.layout,
                blocks: state.value.blocks,
              } : null,
              data_blocks: state.value.dataBlocks,
              metadata: state.value.metadata,
            });
          }
        }
      },
      () => {
        state.value.streamLoading = false;
        if (onComplete) {
          onComplete({
            success: false,
            message: "流式连接错误",
            data: null,
            data_blocks: {},
            metadata: {},
          });
        }
      }
    );
  }

  function applyPanelPayload(response: PanelResponse) {
    if (!response.data) return;

    const mode = response.data.mode ?? response.data.layout.mode;

    if (mode === "append" || mode === "insert") {
      mergeLayoutNodes(response.data.layout);
      state.value.blocks = [...state.value.blocks, ...response.data.blocks];
      state.value.dataBlocks = {
        ...state.value.dataBlocks,
        ...(response.data_blocks ?? {}),
      };
    } else {
      state.value.layout = response.data.layout;
      state.value.blocks = response.data.blocks;
      state.value.dataBlocks = response.data_blocks ?? {};
    }

    state.value.layoutSnapshot = deriveLayoutSnapshot(state.value.layout, state.value.blocks);
  }

  function mergeLayoutNodes(newLayout: PanelPayload["layout"]) {
    if (!state.value.layout) {
      state.value.layout = newLayout;
      return;
    }
    const existingNodeIds = new Set(state.value.layout.nodes.map((n) => n.id));
    const newNodes = newLayout.nodes.filter((n) => !existingNodeIds.has(n.id));

    state.value.layout = {
      ...newLayout,
      nodes: [...state.value.layout.nodes, ...newNodes],
    };
  }

  function connectStream(query: string, filterDatasource?: string | null, layoutSnapshot?: LayoutSnapshotItem[] | null, mode?: string) {
    state.value.streamLoading = true;
    state.value.streamLog = [];
    state.value.fetchSnapshot = null;
    state.value.llmCalls = [];  // V5.0：清空 LLM 调用记录

    streamClient.connect(
      {
        query,
        filter_datasource: filterDatasource ?? null,
        use_cache: true,
        layout_snapshot: layoutSnapshot ?? state.value.layoutSnapshot ?? null,
        mode: mode as any,
      },
      (message) => {
        state.value.streamLog.push(message);
        if (message.type === "data" && message.stage === "fetch") {
          state.value.fetchSnapshot = message.data as PanelStreamFetchPayload;
        }
        if (message.type === "data" && message.stage === "summary") {
          const summary = message.data as PanelStreamSummaryPayload;
          if (summary.success && summary.data) {
            applyPanelPayload({
              success: summary.success,
              message: summary.message,
              data: summary.data,
              data_blocks: summary.data_blocks,
              metadata: summary.metadata,
            });
          }
          state.value.message = summary.message;
          state.value.metadata = summary.metadata;
        }
        // V5.0 可观测性：处理 LLM 调用事件
        if (message.type === "llm_call") {
          state.value.llmCalls.push({
            call_id: message.call_id,
            role: message.role,
            status: message.status,
            step_id: message.step_id,
            stream_id: message.stream_id,
            timestamp: message.timestamp,
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
            metadata: message.metadata,
          });
        }
        if (message.type === "complete" || message.type === "error") {
          state.value.streamLoading = false;
        }
      },
      () => {
        state.value.streamLoading = false;
      }
    );
  }

  function disconnectStream() {
    streamClient.disconnect();
    state.value.streamLoading = false;
  }

  function resetPanel() {
    state.value.layout = null;
    state.value.blocks = [];
    state.value.dataBlocks = {};
    state.value.metadata = {};
    state.value.message = "";
    state.value.layoutSnapshot = [];
    state.value.llmCalls = [];  // V5.0 可观测性
  }

  function getLayoutNodes(): LayoutNode[] {
    return state.value.layout?.nodes ?? [];
  }

  function setLayoutSnapshot(snapshot: LayoutSnapshotItem[]) {
    state.value.layoutSnapshot = snapshot ?? [];
  }

  function getLayoutSnapshot(): LayoutSnapshotItem[] {
    return state.value.layoutSnapshot ?? [];
  }

  function setSizePreset(preset: PanelSizePreset) {
    if (PANEL_SIZE_PRESETS[preset]) {
      state.value.sizePreset = preset;
    }
  }

  // V5.0 可观测性：LLM 调用统计
  const llmCallStats = computed(() => {
    const calls = state.value.llmCalls;
    const completed = calls.filter(c => c.status === "completed");
    const failed = calls.filter(c => c.status === "failed");
    const totalTokens = completed.reduce((sum, c) => sum + (c.total_tokens ?? 0), 0);
    const totalDuration = completed.reduce((sum, c) => sum + (c.duration_ms ?? 0), 0);
    return {
      total: calls.length,
      completed: completed.length,
      failed: failed.length,
      totalTokens,
      totalDuration,
    };
  });

  // V5.0 可观测性：清除 LLM 调用记录
  function clearLLMCalls() {
    state.value.llmCalls = [];
  }

  return {
    state,
    hasPanel,
    fetchPanel,
    connectStream,
    disconnectStream,
    resetPanel,
    getLayoutNodes,
    setLayoutSnapshot,
    getLayoutSnapshot,
    setSizePreset,
    llmCallStats,  // V5.0 可观测性
    clearLLMCalls,  // V5.0 可观测性
  };
});
