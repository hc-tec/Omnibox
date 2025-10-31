<template>
  <article
    class="panel-block"
    :style="styleVars"
    :class="[{ 'is-unknown': !resolved.ability }, resolved.ability?.tag ?? 'unknown']"
  >
    <header class="panel-block__header">
      <h3>{{ resolved.block.title ?? resolved.block.component }}</h3>
      <span v-if="resolved.block.confidence !== undefined" class="confidence">
        置信度 {{ (resolved.block.confidence * 100).toFixed(0) }}%
      </span>
    </header>

    <section class="panel-block__body">
      <component
        :is="resolvedComponent"
        :block="resolved.block"
        :ability="resolved.ability"
        :data="resolved.data"
        :data-block="resolved.dataBlock"
        :interactions="resolved.interactions"
      />
    </section>

    <footer v-if="resolved.warnings.length > 0" class="panel-block__footer">
      <p v-for="warning in resolved.warnings" :key="warning">{{ warning }}</p>
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { UIBlock, DataBlock } from "../../../shared/types/panel";
import { resolveBlock } from "../../../../utils/panelHelpers";
import ListPanelBlock from "./ListPanelBlock.vue";
import LineChartBlock from "./LineChartBlock.vue";
import StatisticCardBlock from "./StatisticCardBlock.vue";
import FallbackBlock from "./FallbackRichTextBlock.vue";

const props = defineProps<{
  blockId: string;
  blockMap: Map<string, UIBlock>;
  dataBlocks: Record<string, DataBlock>;
}>();

const resolved = computed(() => {
  const block = props.blockMap.get(props.blockId);
  if (!block) {
    return {
      ability: null,
      block: {
        id: props.blockId,
        component: "Unknown",
        props: {},
        options: {},
      } as UIBlock,
      data: null,
      dataBlock: null,
      interactions: [],
      warnings: [`无法找到 block: ${props.blockId}`],
    };
  }
  return resolveBlock(block, props.dataBlocks);
});

const resolvedComponent = computed(() => {
  switch (resolved.value.block.component) {
    case "ListPanel":
      return ListPanelBlock;
    case "LineChart":
      return LineChartBlock;
    case "StatisticCard":
      return StatisticCardBlock;
    case "FallbackRichText":
    default:
      return FallbackBlock;
  }
});

const styleVars = computed(() => {
  const span = resolved.value.block.options?.span ?? resolved.value.ability?.layoutDefaults.span ?? 12;
  const minHeight =
    resolved.value.block.options?.min_height ??
    resolved.value.ability?.layoutDefaults.minHeight ??
    resolved.value.block.options?.minHeight ??
    220;
  return {
    gridColumn: `span ${Math.min(Number(span) || 12, 12)}`,
    minHeight: `${minHeight}px`,
  };
});
</script>

<style scoped>
.panel-block {
  display: flex;
  flex-direction: column;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid rgba(226, 232, 240, 0.8);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
  padding: 16px;
  min-height: 220px;
  transition: transform 0.25s ease;
}

.panel-block:hover {
  transform: translateY(-2px);
}

.panel-block__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}

.panel-block__header h3 {
  margin: 0;
  font-size: 17px;
  color: #0f172a;
  font-weight: 600;
}

.confidence {
  font-size: 12px;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.12);
  padding: 2px 8px;
  border-radius: 999px;
}

.panel-block__body {
  flex: 1;
  overflow: hidden;
}

.panel-block__footer {
  margin-top: 12px;
  font-size: 12px;
  color: #b91c1c;
  background: rgba(254, 226, 226, 0.65);
  padding: 8px;
  border-radius: 8px;
}

.panel-block__footer p {
  margin: 0;
}
</style>
