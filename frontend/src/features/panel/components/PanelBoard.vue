<template>
  <section class="panel-board" v-if="gridItems.length">
    <GridLayout
      :layout="gridItems"
      :col-num="12"
      :row-height="rowHeight"
      :is-draggable="false"
      :is-resizable="false"
      :vertical-compact="true"
      :margin="[gap, gap]"
    >
      <GridItem
        v-for="item in gridItems"
        :key="item.i"
        :i="item.i"
        :x="item.x"
        :y="item.y"
        :w="item.w"
        :h="item.h"
        :static="true"
      >
        <DynamicBlockRenderer
          :block-id="item.blockId"
          :block="item.block"
          :block-map="blockMap"
          :data-blocks="dataBlocks"
        />
      </GridItem>
    </GridLayout>
  </section>
  <div v-else class="panel-board-empty">
    <slot />
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from "vue";
import { GridLayout, GridItem } from "vue-grid-layout";
import type { LayoutSnapshotItem, LayoutTree, UIBlock, DataBlock } from "../../../shared/types/panel";
import DynamicBlockRenderer from "./blocks/DynamicBlockRenderer.vue";

const props = defineProps<{
  layout: LayoutTree;
  blocks: UIBlock[];
  dataBlocks: Record<string, DataBlock>;
}>();

const emit = defineEmits<{
  (event: "snapshot-change", snapshot: LayoutSnapshotItem[]): void;
}>();

const blockMap = computed(() => {
  const map = new Map<string, UIBlock>();
  props.blocks.forEach((block) => map.set(block.id, block));
  return map;
});

const rowHeight = 90;
const gap = 16;

const gridItems = computed(() =>
  props.layout.nodes.map((node, index) => {
    const blockId = node.children?.[0] ?? `unknown-${index}`;
    const block = blockMap.value.get(blockId) ?? null;
    const gridMeta = (node.props as any)?.grid ?? {};
    return {
      i: blockId,
      x: gridMeta.x ?? (index % 12),
      y: gridMeta.y ?? Math.floor(index / 12),
      w: gridMeta.w ?? 12,
      h: gridMeta.h ?? 1,
      blockId,
      block: block ?? undefined,
    };
  })
);

const snapshot = computed<LayoutSnapshotItem[]>(() =>
  gridItems.value.map((item) => ({
    block_id: item.blockId,
    component: item.block?.component ?? "Unknown",
    x: item.x,
    y: item.y,
    w: item.w,
    h: item.h,
  }))
);

watch(
  snapshot,
  (value) => {
    emit("snapshot-change", value);
  },
  { immediate: true, deep: true }
);
</script>

<style scoped>
.panel-board {
  flex: 1;
  overflow: auto;
  padding: 12px;
  border-radius: 16px;
  background: radial-gradient(circle, #ffffff 0%, #f8fafc 60%);
  border: 1px solid rgba(226, 232, 240, 0.7);
}

.panel-board :deep(.vue-grid-layout) {
  min-height: 100%;
}

.panel-board :deep(.vue-grid-item) {
  transition: transform 0.2s, box-shadow 0.2s;
}

.panel-board :deep(.vue-grid-layout) {
  position: relative;
  transition: height 200ms ease;
}

.panel-board :deep(.vue-grid-placeholder) {
  background: rgba(37, 99, 235, 0.15);
  border: 1px dashed rgba(37, 99, 235, 0.4);
}

.panel-board :deep(.vue-grid-item) {
  transition: left 200ms ease, top 200ms ease, width 200ms ease, height 200ms ease;
}

.panel-board :deep(.vue-grid-item.cssTransforms) {
  transition-property: transform, width, height;
}

.panel-board :deep(.vue-resizable-handle) {
  display: none;
}

.panel-board-empty {
  width: 100%;
  padding: 48px 0;
}
</style>
