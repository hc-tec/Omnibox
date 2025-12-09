<script setup lang="ts">
/**
 * 仪表盘网格布局
 *
 * 使用 CSS Grid 实现 12 列响应式布局
 * 支持编辑模式下的拖拽调整
 */
import { computed } from 'vue'
import type { DashboardCard } from '../types/dashboard'

interface Props {
  cards: DashboardCard[]
  editMode?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  editMode: false,
})

const emit = defineEmits<{
  'layout-change': [layouts: Array<{ card_id: string; x: number; y: number; width: number; height: number }>]
}>()

// 计算网格样式
function getCardStyle(card: DashboardCard) {
  return {
    gridColumn: `${card.position.x + 1} / span ${card.position.width}`,
    gridRow: `${card.position.y + 1} / span ${card.position.height}`,
  }
}

// 计算最大行数
const maxRow = computed(() => {
  if (props.cards.length === 0) return 1
  return Math.max(
    ...props.cards.map((c) => c.position.y + c.position.height)
  )
})
</script>

<template>
  <div
    class="dashboard-grid"
    :style="{
      gridTemplateRows: `repeat(${maxRow}, minmax(120px, auto))`,
    }"
  >
    <div
      v-for="card in cards"
      :key="card.card_id"
      class="grid-item"
      :class="{ 'edit-mode': editMode }"
      :style="getCardStyle(card)"
    >
      <slot name="card" :card="card" />
    </div>
  </div>
</template>

<style scoped>
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 16px;
  min-height: 100%;
}

.grid-item {
  min-height: 120px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.grid-item.edit-mode {
  cursor: move;
}

.grid-item.edit-mode:hover {
  transform: scale(1.01);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .dashboard-grid {
    grid-template-columns: repeat(6, 1fr);
  }
}

@media (max-width: 768px) {
  .dashboard-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (max-width: 480px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}
</style>
