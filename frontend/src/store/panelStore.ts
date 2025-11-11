import { defineStore } from "pinia";
import { ref, computed, watch } from "vue";
import type {
  DataBlock,
  LayoutNode,
  LayoutSnapshotItem,
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
    layoutSnapshot?: LayoutSnapshotItem[] | null
  ) {
    state.value.loading = true;
    try {
      const response = await requestPanel({
        query,
        filter_datasource: filterDatasource,
        use_cache: true,
        layout_snapshot: layoutSnapshot ?? state.value.layoutSnapshot ?? null,
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

  function connectStream(query: string, filterDatasource?: string | null, layoutSnapshot?: LayoutSnapshotItem[] | null) {
    state.value.streamLoading = true;
    state.value.streamLog = [];
    state.value.fetchSnapshot = null;

    streamClient.connect(
      {
        query,
        filter_datasource: filterDatasource ?? null,
        use_cache: true,
        layout_snapshot: layoutSnapshot ?? state.value.layoutSnapshot ?? null,
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
  };
});
