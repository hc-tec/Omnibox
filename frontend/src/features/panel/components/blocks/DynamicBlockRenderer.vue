<template>
  <article
    class="panel-block"
    :style="styleVars"
    :class="[
      { 'is-unknown': !resolved.ability, 'dev-mode': devModeEnabled },
      resolved.ability?.tag ?? 'unknown'
    ]"
    @click="handleBlockClick"
  >
    <header class="panel-block__header">
      <h3>{{ displayTitle }}</h3>
      <div class="flex items-center gap-2">
        <span v-if="devModeEnabled" class="dev-indicator">
          🔧 DEV
        </span>
        <span v-if="resolved.block.confidence !== undefined" class="confidence">
          置信度 {{ (resolved.block.confidence * 100).toFixed(0) }}%
        </span>
      </div>
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

    <div
      v-if="resolved.block.children && resolved.block.children.length > 0"
      class="panel-block__children"
    >
      <DynamicBlockRenderer
        v-for="child in resolved.block.children"
        :key="child.id"
        :block="child"
        :data-blocks="dataBlocks"
      />
    </div>

    <footer v-if="resolved.warnings.length > 0" class="panel-block__footer">
      <p v-for="warning in resolved.warnings" :key="warning">{{ warning }}</p>
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed, withDefaults } from "vue";
import type { UIBlock, DataBlock } from "../../../shared/types/panel";
import { resolveBlock } from "../../../../utils/panelHelpers";
import { useDevModeStore } from "@/store/devModeStore";
import { storeToRefs } from "pinia";
import ListPanelBlock from "./ListPanelBlock.vue";
import LineChartBlock from "./LineChartBlock.vue";
import StatisticCardBlock from "./StatisticCardBlock.vue";
import FallbackBlock from "./FallbackRichTextBlock.vue";
import BarChartBlock from "./BarChartBlock.vue";
import PieChartBlock from "./PieChartBlock.vue";
import TableBlock from "./TableBlock.vue";
import ImageGalleryBlock from "./ImageGalleryBlock.vue";
import MediaCardGridBlock from "./MediaCardGridBlock.vue";

defineOptions({
  name: "DynamicBlockRenderer",
});

const props = withDefaults(
  defineProps<{
    blockId?: string;
    block?: UIBlock;
    blockMap?: Map<string, UIBlock>;
    dataBlocks?: Record<string, DataBlock>;
  }>(),
  {
    dataBlocks: () => ({} as Record<string, DataBlock>),
  }
);

const emit = defineEmits<{
  (event: 'inspect-component', payload: { block: UIBlock; dataBlock: DataBlock | null }): void;
}>();

// 开发者模式
const devModeStore = useDevModeStore();
const { enabled: devModeEnabled } = storeToRefs(devModeStore);

const targetBlock = computed<UIBlock | null>(() => {
  if (props.block) {
    return props.block;
  }
  if (props.blockId && props.blockMap) {
    return props.blockMap.get(props.blockId) ?? null;
  }
  return null;
});

const resolved = computed(() => {
  const block = targetBlock.value;
  if (!block) {
    const fallbackId = props.blockId ?? "unknown";
    return {
      ability: null,
      block: {
        id: fallbackId,
        component: "Unknown",
        props: {},
        options: {},
      } as UIBlock,
      data: null,
      dataBlock: null,
      interactions: [],
      warnings: [`无法找到 block: ${fallbackId}`],
    };
  }
  return resolveBlock(block, props.dataBlocks);
});

const COMPONENT_LABELS: Record<string, string> = {
  ListPanel: "洞察列表",
  LineChart: "趋势图",
  BarChart: "对比图",
  PieChart: "占比分析",
  Table: "数据表",
  StatisticCard: "指标卡片",
  ImageGallery: "图像画廊",
  MediaCardGrid: "媒体卡片",
};
const displayTitle = computed(() => {
  const block = resolved.value.block;
  if (block.title && block.title.trim().length > 0) {
    return block.title;
  }
  const componentName = block.component ?? "";
  return (COMPONENT_LABELS[componentName] ?? componentName) || "面板组件";
});

const resolvedComponent = computed(() => {
  switch (resolved.value.block.component) {
    case "ListPanel":
      return ListPanelBlock;
    case "LineChart":
      return LineChartBlock;
    case "StatisticCard":
      return StatisticCardBlock;
    case "BarChart":
      return BarChartBlock;
    case "PieChart":
      return PieChartBlock;
    case "Table":
      return TableBlock;
    case "ImageGallery":
      return ImageGalleryBlock;
    case "MediaCardGrid":
      return MediaCardGridBlock;
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

/**
 * 处理组件点击事件（开发者模式）
 */
function handleBlockClick(event: MouseEvent) {
  if (!devModeEnabled.value) return;

  // 只有点击在组件本身，不是子元素时才触发
  const target = event.target as HTMLElement;
  if (!target.closest('.panel-block__header')) return;

  event.stopPropagation();

  const block = resolved.value.block;
  const dataBlock = resolved.value.dataBlock;

  emit('inspect-component', { block, dataBlock });
}
</script>

<style scoped>
.panel-block {
  display: flex;
  flex-direction: column;
  border-radius: var(--panel-card-radius, 18px);
  background: color-mix(in srgb, var(--shell-surface) 25%, transparent);
  border: 1px solid color-mix(in srgb, var(--border) 60%, transparent);
  padding: var(--panel-card-padding, 16px);
  font-size: calc(1rem * var(--panel-font-scale, 1));
  min-height: 200px;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.panel-block:hover {
  border-color: color-mix(in srgb, var(--border) 85%, transparent);
  background: color-mix(in srgb, var(--shell-surface) 35%, transparent);
}

/* 开发者模式样式 */
.panel-block.dev-mode {
  cursor: pointer;
  border-color: color-mix(in srgb, var(--primary) 30%, transparent);
}

.panel-block.dev-mode:hover {
  border-color: color-mix(in srgb, var(--primary) 60%, transparent);
  background: color-mix(in srgb, var(--primary) 5%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 10%, transparent);
}

.panel-block.dev-mode .panel-block__header {
  cursor: pointer;
}

.dev-indicator {
  font-size: var(--panel-meta-size, 11px);
  color: var(--primary);
  background: color-mix(in srgb, var(--primary) 15%, transparent);
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
}

.panel-block__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: calc(12px * var(--panel-spacing-scale, 1));
}

.panel-block__header h3 {
  margin: 0;
  font-size: var(--panel-heading-size, 16px);
  color: var(--foreground);
  font-weight: 600;
}

.confidence {
  font-size: var(--panel-meta-size, 12px);
  color: var(--primary-500, #2563eb);
  background: color-mix(in srgb, var(--primary-500, #2563eb) 15%, transparent);
  padding: 2px 8px;
  border-radius: 999px;
}

.panel-block__body {
  flex: 1;
  overflow: hidden;
}

.panel-block__children {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
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
