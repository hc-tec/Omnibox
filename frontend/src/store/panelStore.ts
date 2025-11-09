import { defineStore } from "pinia";
import { ref, computed } from "vue";
import type {
  DataBlock,
  LayoutNode,
  PanelPayload,
  PanelResponse,
  StreamMessage,
  PanelStreamSummaryPayload,
  PanelStreamFetchPayload,
} from "../shared/types/panel";
import { requestPanel, PanelStreamClient } from "../services/panelApi";

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
}

const streamClient = new PanelStreamClient();

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
  });

  const hasPanel = computed(() => !!state.value.layout && state.value.blocks.length > 0);

  async function fetchPanel(query: string, filterDatasource?: string | null) {
    state.value.loading = true;
    try {
      const response = await requestPanel({
        query,
        filter_datasource: filterDatasource,
        use_cache: true,
      });
      if (response.success && response.data) {
        applyPanelPayload(response);
      }
      state.value.message = response.message;
      state.value.metadata = response.metadata;
    } finally {
      state.value.loading = false;
    }
  }

  function applyPanelPayload(response: PanelResponse) {
    if (!response.data) return;

    const mode = response.data.mode ?? response.data.layout.mode;

    console.log("[PanelStore] applyPanelPayload - mode:", mode);
    console.log("[PanelStore] 当前 blocks 数量:", state.value.blocks.length);
    console.log("[PanelStore] 新增 blocks 数量:", response.data.blocks.length);

    if (mode === "append") {
      // 追加模式：合并新数据到现有数据
      console.log("[PanelStore] 使用 append 模式");
      mergeLayoutNodes(response.data.layout);
      state.value.blocks = [...state.value.blocks, ...response.data.blocks];
      state.value.dataBlocks = {
        ...state.value.dataBlocks,
        ...(response.data_blocks ?? {}),
      };
      console.log("[PanelStore] append 后 blocks 数量:", state.value.blocks.length);
    } else if (mode === "insert") {
      // 插入模式：暂时当作追加处理
      console.log("[PanelStore] 使用 insert 模式");
      mergeLayoutNodes(response.data.layout);
      state.value.blocks = [...state.value.blocks, ...response.data.blocks];
      state.value.dataBlocks = {
        ...state.value.dataBlocks,
        ...(response.data_blocks ?? {}),
      };
      console.log("[PanelStore] insert 后 blocks 数量:", state.value.blocks.length);
    } else {
      // replace 模式：完全替换
      console.log("[PanelStore] 使用 replace 模式");
      state.value.layout = response.data.layout;
      state.value.blocks = response.data.blocks;
      state.value.dataBlocks = response.data_blocks ?? {};
      console.log("[PanelStore] replace 后 blocks 数量:", state.value.blocks.length);
    }
  }

  function mergeLayoutNodes(newLayout: PanelPayload["layout"]) {
    if (!state.value.layout) {
      // 如果没有现有布局，直接使用新布局
      console.log("[PanelStore] 首次创建布局，nodes:", newLayout.nodes.length);
      state.value.layout = newLayout;
      return;
    }

    // 合并布局节点，避免重复
    const existingNodeIds = new Set(state.value.layout.nodes.map((n) => n.id));
    const newNodes = newLayout.nodes.filter((n) => !existingNodeIds.has(n.id));

    console.log("[PanelStore] 合并布局节点:");
    console.log("  现有 nodes:", state.value.layout.nodes.length);
    console.log("  新增 nodes（总）:", newLayout.nodes.length);
    console.log("  新增 nodes（去重后）:", newNodes.length);
    console.log("  新节点 IDs:", newNodes.map((n) => n.id));

    state.value.layout = {
      ...newLayout,
      nodes: [...state.value.layout.nodes, ...newNodes],
    };

    console.log("  合并后 nodes:", state.value.layout.nodes.length);
  }

  function connectStream(query: string, filterDatasource?: string | null) {
    state.value.streamLoading = true;
    state.value.streamLog = [];
    state.value.fetchSnapshot = null;

    streamClient.connect(
      { query, filter_datasource: filterDatasource ?? null, use_cache: true },
      (message) => {
        state.value.streamLog.push(message);
        if (message.type === "data" && message.stage === "fetch") {
          state.value.fetchSnapshot = message.data as PanelStreamFetchPayload;
        }
        if (message.type === "data" && message.stage === "summary") {
          const summary = message.data as PanelStreamSummaryPayload;
          if (summary.success && summary.data) {
            // 使用统一的 payload 合并逻辑
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
        if (message.type === "complete") {
          state.value.streamLoading = false;
        }
        if (message.type === "error") {
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

  function getLayoutNodes(): LayoutNode[] {
    return state.value.layout?.nodes ?? [];
  }

  return {
    state,
    hasPanel,
    fetchPanel,
    connectStream,
    disconnectStream,
    getLayoutNodes,
  };
});
