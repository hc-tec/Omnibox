<template>
  <div class="layout-board">
    <section
      v-for="node in layout.nodes"
      :key="node.id"
      class="layout-row"
      :style="getRowStyle(node)"
    >
      <DynamicBlockRenderer
        v-for="childId in node.children"
        :key="childId"
        :block-id="childId"
        :block-map="blockMap"
        :data-blocks="dataBlocks"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { LayoutTree, UIBlock, DataBlock } from "../../../shared/types/panel";
import DynamicBlockRenderer from "./blocks/DynamicBlockRenderer.vue";

const props = defineProps<{
  layout: LayoutTree;
  blocks: UIBlock[];
  dataBlocks: Record<string, DataBlock>;
}>();

const blockMap = computed(() => {
  const map = new Map<string, UIBlock>();
  props.blocks.forEach((block) => map.set(block.id, block));
  return map;
});

function getRowStyle(node: LayoutTree["nodes"][number]) {
  const gap = 16;
  return {
    gap: `${gap}px`,
  };
}
</script>

<style scoped>
.layout-board {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-right: 6px;
  overflow-y: auto;
}

.layout-row {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  align-items: stretch;
}
</style>
