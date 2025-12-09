<template>
  <div class="main-canvas flex h-full flex-col">
    <!-- 头部：视图切换 + 当前信息 -->
    <header class="flex items-center justify-between border-b border-border/20 bg-[var(--shell-surface)]/95 px-4 py-2 backdrop-blur">
      <!-- 视图切换标签 -->
      <div class="flex items-center gap-1 rounded-lg border border-border/40 bg-background/50 p-1">
        <button
          v-for="view in views"
          :key="view.value"
          class="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition"
          :class="viewButtonClass(view.value)"
          @click="setCanvasView(view.value)"
        >
          <component :is="view.icon" class="h-3.5 w-3.5" />
          {{ view.label }}
        </button>
      </div>

      <!-- 当前上下文信息 -->
      <div class="flex items-center gap-3">
        <!-- 当前步骤 -->
        <div
          v-if="currentStepOutput"
          class="flex items-center gap-2 rounded-lg border border-border/40 bg-background/50 px-3 py-1.5"
        >
          <span class="text-[10px] text-muted-foreground">当前:</span>
          <span class="text-xs font-medium text-foreground">
            {{ currentStepOutput.stepName }}
          </span>
        </div>

        <!-- 当前产物 -->
        <div
          v-if="selectedArtifact"
          class="flex items-center gap-2 rounded-lg border border-primary/40 bg-primary/5 px-3 py-1.5"
        >
          <Database class="h-3.5 w-3.5 text-primary" />
          <span class="text-xs font-medium text-primary">
            {{ selectedArtifact.name }}
          </span>
        </div>
      </div>
    </header>

    <!-- 主内容区域 -->
    <div class="canvas-viewport flex-1 overflow-auto bg-background p-4">
      <!-- 有数据时显示 PanelBoard -->
      <div v-if="hasContent" class="h-full">
        <!-- 图表视图 -->
        <div v-if="canvasView === 'chart'" class="h-full">
          <PanelBoard
            v-if="panelData.layout"
            :layout="panelData.layout"
            :blocks="panelData.blocks"
            :data-blocks="panelData.dataBlocks"
          />
          <CanvasEmptyState v-else message="暂无图表数据" />
        </div>

        <!-- 表格视图 -->
        <div v-else-if="canvasView === 'table'" class="h-full">
          <div class="rounded-lg border border-border/40 bg-background/50 p-4">
            <p class="text-sm text-muted-foreground">表格视图 - 待实现</p>
          </div>
        </div>

        <!-- 文本视图 -->
        <div v-else-if="canvasView === 'text'" class="h-full">
          <div class="rounded-lg border border-border/40 bg-background/50 p-4">
            <p class="text-sm text-muted-foreground">文本视图 - 待实现</p>
          </div>
        </div>

        <!-- 原始视图 -->
        <div v-else-if="canvasView === 'raw'" class="h-full">
          <div class="rounded-lg border border-border/40 bg-background/50 p-4">
            <pre class="overflow-auto text-xs text-muted-foreground">
{{ JSON.stringify(currentStepOutput?.data || selectedArtifact, null, 2) }}
            </pre>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <CanvasEmptyState v-else />
    </div>

    <!-- 底部：对话交互区 -->
    <div class="border-t border-border/20 bg-[var(--shell-surface)]/95 backdrop-blur">
      <ChatInteractionArea />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw } from 'vue'
import { storeToRefs } from 'pinia'
import {
  BarChart3,
  Table2,
  FileText,
  Code2,
  Database,
} from 'lucide-vue-next'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import PanelBoard from '@/features/panel/components/PanelBoard.vue'
import ChatInteractionArea from './ChatInteractionArea.vue'
import CanvasEmptyState from './CanvasEmptyState.vue'
import type { CanvasView } from '../../types/workspace'

// ========== Store ==========
const store = useWorkspaceStore()
const {
  canvasView,
  currentStepOutput,
  selectedArtifact,
} = storeToRefs(store)

const { setCanvasView } = store

// ========== 视图配置 ==========
const views = [
  { value: 'chart' as CanvasView, label: '图表', icon: markRaw(BarChart3) },
  { value: 'table' as CanvasView, label: '表格', icon: markRaw(Table2) },
  { value: 'text' as CanvasView, label: '文本', icon: markRaw(FileText) },
  { value: 'raw' as CanvasView, label: '原始', icon: markRaw(Code2) },
]

// ========== Computed ==========

const hasContent = computed(() => {
  return currentStepOutput.value || selectedArtifact.value
})

// 从产物或步骤输出构建面板数据
const panelData = computed(() => {
  // TODO: 根据 selectedArtifact 或 currentStepOutput 构建面板数据
  return {
    layout: null,
    blocks: [],
    dataBlocks: {},
  }
})

// ========== Methods ==========

function viewButtonClass(view: CanvasView) {
  return {
    'bg-primary text-primary-foreground': canvasView.value === view,
    'text-muted-foreground hover:text-foreground hover:bg-background/80': canvasView.value !== view,
  }
}
</script>

<style scoped>
.canvas-viewport {
  scrollbar-width: thin;
  scrollbar-color: rgba(100, 100, 100, 0.3) rgba(0, 0, 0, 0.1);
}

.canvas-viewport::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.canvas-viewport::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
}

.canvas-viewport::-webkit-scrollbar-thumb {
  background: rgba(100, 100, 100, 0.3);
  border-radius: 4px;
}

.canvas-viewport::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 100, 100, 0.5);
}
</style>
