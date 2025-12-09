<template>
  <div class="workspace-layout flex h-screen bg-background text-foreground">
    <!-- 左侧：工作流面板 -->
    <aside
      class="workflow-panel-container flex-shrink-0 border-r border-border/20 bg-background/50 transition-all duration-200"
      :style="{ width: leftPanelCollapsed ? '48px' : `${leftPanelWidth}px` }"
    >
      <!-- 折叠状态：只显示图标按钮 -->
      <div
        v-if="leftPanelCollapsed"
        class="flex h-full flex-col items-center gap-2 py-4"
      >
        <button
          class="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-background hover:text-foreground"
          title="展开工作流面板"
          @click="toggleLeftPanel"
        >
          <PanelLeftOpen class="h-4 w-4" />
        </button>
        <button
          class="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-background hover:text-foreground"
          title="工作流列表"
        >
          <Workflow class="h-4 w-4" />
        </button>
      </div>

      <!-- 展开状态：完整面板 -->
      <div v-else class="flex h-full flex-col">
        <WorkflowPanel @collapse="toggleLeftPanel" />
      </div>
    </aside>

    <!-- 中间：主画布 -->
    <main class="main-canvas-container flex flex-1 flex-col min-w-0 overflow-hidden">
      <MainCanvas />
    </main>

    <!-- 右侧：数据产物面板 -->
    <aside
      class="artifact-panel-container flex-shrink-0 border-l border-border/20 bg-background/50 transition-all duration-200"
      :style="{ width: rightPanelCollapsed ? '48px' : `${rightPanelWidth}px` }"
    >
      <!-- 折叠状态：只显示图标按钮 -->
      <div
        v-if="rightPanelCollapsed"
        class="flex h-full flex-col items-center gap-2 py-4"
      >
        <button
          class="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-background hover:text-foreground"
          title="展开数据面板"
          @click="toggleRightPanel"
        >
          <PanelRightOpen class="h-4 w-4" />
        </button>
        <button
          class="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-background hover:text-foreground"
          title="数据产物"
        >
          <Database class="h-4 w-4" />
        </button>
      </div>

      <!-- 展开状态：完整面板 -->
      <div v-else class="flex h-full flex-col">
        <ArtifactPanel @collapse="toggleRightPanel" />
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import {
  PanelLeftOpen,
  PanelRightOpen,
  Workflow,
  Database,
} from 'lucide-vue-next'
import { useWorkspaceStore } from './stores/workspaceStore'
import WorkflowPanel from './components/workflow/WorkflowPanel.vue'
import MainCanvas from './components/canvas/MainCanvas.vue'
import ArtifactPanel from './components/artifact/ArtifactPanel.vue'

// ========== Store ==========
const store = useWorkspaceStore()
const {
  leftPanelCollapsed,
  rightPanelCollapsed,
  leftPanelWidth,
  rightPanelWidth,
} = storeToRefs(store)

const { toggleLeftPanel, toggleRightPanel } = store
</script>

<style scoped>
.workspace-layout {
  /* 自定义滚动条样式 */
  --scrollbar-width: 6px;
  --scrollbar-track: rgba(0, 0, 0, 0.1);
  --scrollbar-thumb: rgba(100, 100, 100, 0.3);
  --scrollbar-thumb-hover: rgba(100, 100, 100, 0.5);
}

/* 面板可调整大小的手柄（未来可添加） */
.workflow-panel-container,
.artifact-panel-container {
  position: relative;
}
</style>
