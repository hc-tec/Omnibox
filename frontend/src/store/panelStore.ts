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
    state.value.layout = response.data.layout;
    state.value.blocks = response.data.blocks;
    state.value.dataBlocks = response.data_blocks ?? {};
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
            state.value.layout = summary.data.layout;
            state.value.blocks = summary.data.blocks;
            state.value.dataBlocks = summary.data_blocks ?? {};
            state.value.metadata = summary.metadata;
          }
          state.value.message = summary.message;
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
