<template>
  <section v-if="gridItems.length" class="panel-board">
    <div ref="boardRef" class="grid-board" :style="gridStyle">
      <div
        v-for="item in gridItems"
        :key="item.i"
        class="grid-cell"
        :style="{
          gridColumn: `auto / span ${item.colSpan}`,
          gridRow: `span ${item.rowSpan}`,
          gridArea: `span ${item.rowSpan} / span ${item.colSpan}`,
          order: item.order,
        }"
      >
        <DynamicBlockRenderer
          :block-id="item.blockId"
          :block="item.block"
          :block-map="blockMap"
          :data-blocks="dataBlocks"
          @inspect-component="$emit('inspect-component', $event)"
        />
      </div>
    </div>
  </section>
  <div v-else class="panel-board panel-board-empty py-16 text-center text-muted-foreground">
    <slot />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type {
  LayoutSnapshotItem,
  LayoutTree,
  UIBlock,
  DataBlock,
  LayoutGridMeta,
} from "../../../shared/types/panel";
import DynamicBlockRenderer from "./blocks/DynamicBlockRenderer.vue";
import { usePanelStore } from "@/store/panelStore";
import { PANEL_SIZE_PRESETS, type PanelLayoutSize } from "@/shared/panelSizePresets";

const props = defineProps<{
  layout: LayoutTree;
  blocks: UIBlock[];
  dataBlocks: Record<string, DataBlock>;
}>();

const emit = defineEmits<{
  (event: "snapshot-change", snapshot: LayoutSnapshotItem[]): void;
  (event: "inspect-component", payload: { block: UIBlock; dataBlock: DataBlock | null }): void;
}>();

const panelStore = usePanelStore();
const boardRef = ref<HTMLElement | null>(null);
const boardWidth = ref(0);
const resizeObserver = ref<ResizeObserver | null>(null);

const sizePreset = computed(() => PANEL_SIZE_PRESETS[panelStore.state.sizePreset]);

const blockMap = computed(() => {
  const map = new Map<string, UIBlock>();
  props.blocks.forEach((block) => map.set(block.id, block));
  return map;
});

const layoutConfig = computed(() => sizePreset.value.layout);
const BASE_COLUMNS = 12;

const LAYOUT_SIZES: PanelLayoutSize[] = ["quarter", "third", "half", "full"];

const componentDefaultSize: Record<string, PanelLayoutSize> = {
  StatisticCard: "quarter",
  ListPanel: "third",
  Table: "half",
  LineChart: "half",
  BarChart: "half",
  PieChart: "third",
  ImageGallery: "half",
  MediaCardGrid: "half",
  FallbackRichText: "full",
};

const isLayoutSize = (value: unknown): value is PanelLayoutSize =>
  typeof value === "string" && LAYOUT_SIZES.includes(value as PanelLayoutSize);

const resolveLayoutSize = (block: UIBlock | null, gridMeta: Partial<LayoutGridMeta> & Record<string, unknown>) => {
  const candidate =
    (gridMeta?.size as string | undefined) ??
    (gridMeta?.layoutSize as string | undefined) ??
    (gridMeta?.layout_size as string | undefined) ??
    (block?.options?.layoutSize as string | undefined) ??
    (block?.options as Record<string, unknown> | undefined)?.layout_size ??
    (block?.options?.layout as { size?: string } | undefined)?.size ??
    (block?.props?.layoutSize as string | undefined) ??
    (block?.props as Record<string, unknown> | undefined)?.layout_size ??
    (block?.props?.layout as { size?: string } | undefined)?.size;

  if (isLayoutSize(candidate)) return candidate;

  const override = block?.component
    ? sizePreset.value.componentSizeOverrides?.[block.component] ?? componentDefaultSize[block.component]
    : undefined;
  if (override) return override;

  const spanValue =
    typeof gridMeta?.w === "number"
      ? gridMeta.w
      : typeof gridMeta?.span === "number"
        ? gridMeta.span
        : typeof gridMeta?.columns === "number"
          ? gridMeta.columns
          : undefined;

  if (spanValue != null) {
    if (spanValue >= 10) return "full";
    if (spanValue >= 7) return "half";
    if (spanValue >= 5) return "third";
  }

  return "quarter";
};

const layoutSpanFraction = (size: PanelLayoutSize) => layoutConfig.value.sizeSpan[size] ?? 0.34;

const computeColSpan = (gridMeta: Partial<LayoutGridMeta>, size: PanelLayoutSize) => {
  if (typeof gridMeta.w === "number" && gridMeta.w > 0) {
    const normalized = gridMeta.w / BASE_COLUMNS;
    return Math.max(1, Math.round(normalized * currentColumns.value));
  }
  const fraction = layoutSpanFraction(size);
  return Math.max(1, Math.round(currentColumns.value * fraction));
};

const computeRowSpan = (gridMeta: Partial<LayoutGridMeta>, size: PanelLayoutSize) => {
  if (typeof gridMeta.h === "number" && gridMeta.h > 0) {
    return Math.max(1, Math.round(gridMeta.h));
  }
  if (size === "full") return 2;
  if (size === "quarter") return 1;
  return 1;
};

const currentColumns = ref(layoutConfig.value.minColumns);

const gridStyle = computed(() => ({
  display: "grid",
  gridTemplateColumns: `repeat(${currentColumns.value}, minmax(0, 1fr))`,
  gridAutoRows: `minmax(${Math.round(sizePreset.value.listRowHeight * 0.7)}px, auto)`,
  gridAutoFlow: "row dense",
  gap: "var(--panel-grid-gap, 24px)",
}));

const gridItems = computed(() =>
  props.layout.nodes
    .map((node, index) => {
      const blockId = node.children?.[0] ?? `unknown-${index}`;
      const block = blockMap.value.get(blockId) ?? null;
      const gridMeta = ((node.props as any)?.grid ?? {}) as Partial<LayoutGridMeta> & Record<string, unknown>;
      const layoutSize = resolveLayoutSize(block, gridMeta);
      const span = computeColSpan(gridMeta, layoutSize);
      const rowSpan = computeRowSpan(gridMeta, layoutSize);
      const width = typeof gridMeta.w === "number" ? gridMeta.w : Math.max(1, Math.round((span / currentColumns.value) * BASE_COLUMNS));
      const height = typeof gridMeta.h === "number" ? gridMeta.h : rowSpan;
      return {
        i: blockId,
        x: (gridMeta.x as number | undefined) ?? (index % currentColumns.value),
        y: (gridMeta.y as number | undefined) ?? Math.floor(index / currentColumns.value),
        blockId,
        block: block ?? undefined,
        order: gridMeta.order ?? index,
        colSpan: span,
        rowSpan,
        width,
        height,
      };
    })
    .sort((a, b) => (a.y === b.y ? a.x - b.x : a.y - b.y))
);

const snapshot = computed<LayoutSnapshotItem[]>(() =>
  gridItems.value.map((item) => ({
    block_id: item.blockId,
    component: item.block?.component ?? "Unknown",
    x: item.x,
    y: item.y,
    w: item.width,
    h: item.height,
  }))
);

watch(
  snapshot,
  (value) => {
    emit("snapshot-change", value);
  },
  { immediate: true, deep: true }
);

const updateBoardWidth = () => {
  const width = boardRef.value?.clientWidth ?? 0;
  boardWidth.value = width;
  const cfg = layoutConfig.value;
  if (width <= 0) {
    currentColumns.value = cfg.minColumns;
    return;
  }
  const maxColumns = cfg.maxColumns;
  const minColumns = cfg.minColumns;
  const desiredColumns = Math.floor(width / cfg.baseColumnWidth);
  currentColumns.value = Math.max(minColumns, Math.min(maxColumns, desiredColumns));
};

watch(
  layoutConfig,
  (cfg) => {
    currentColumns.value = cfg.minColumns;
    updateBoardWidth();
  },
  { immediate: true }
);

onMounted(() => {
  if (typeof ResizeObserver === "undefined") {
    updateBoardWidth();
    return;
  }
  resizeObserver.value = new ResizeObserver(() => updateBoardWidth());
  updateBoardWidth();
  if (boardRef.value) {
    resizeObserver.value.observe(boardRef.value);
  }
});

onBeforeUnmount(() => {
  resizeObserver.value?.disconnect();
});
</script>

<style scoped>
.grid-board {
  width: 100%;
}

.grid-cell {
  min-width: 0;
}

.grid-cell > :deep(*) {
  border-radius: var(--panel-card-radius, 18px);
  background: color-mix(in srgb, var(--shell-surface) 32%, transparent);
  border: 1px solid color-mix(in srgb, var(--border) 65%, transparent);
  overflow: hidden;
  animation: drop-in 320ms ease-out;
}

.grid-cell > :deep(*:hover) {
  border-color: color-mix(in srgb, var(--border) 90%, transparent);
}

@keyframes drop-in {
  from {
    opacity: 0;
    transform: translateY(24px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
