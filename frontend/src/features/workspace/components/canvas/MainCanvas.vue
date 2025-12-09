<template>
  <div class="main-canvas flex h-full flex-col">
    <!-- 头部状态栏 -->
    <header class="flex items-center justify-between border-b border-border/20 bg-[var(--shell-surface)]/95 px-4 py-2 backdrop-blur">
      <div class="flex items-center gap-2">
        <Sparkles class="h-4 w-4 text-primary" />
        <span class="text-sm font-medium text-foreground">执行流程</span>
        <span class="text-xs text-muted-foreground">
          ({{ timelineCount }} 条记录)
        </span>
      </div>

      <!-- 清空按钮 -->
      <Button
        v-if="timelineCount > 0"
        variant="ghost"
        size="sm"
        class="h-7 text-xs text-muted-foreground hover:text-foreground"
        @click="handleClearTimeline"
      >
        <Trash2 class="h-3.5 w-3.5 mr-1" />
        清空
      </Button>
    </header>

    <!-- 主内容区域：时间线 -->
    <div class="timeline-container flex-1 overflow-hidden">
      <ExecutionTimeline />
    </div>

    <!-- 底部：对话交互区 -->
    <div class="border-t border-border/20 bg-[var(--shell-surface)]/95 backdrop-blur">
      <ChatInteractionArea />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Sparkles, Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { usePanelStore } from '@/store/panelStore'
import ExecutionTimeline from '../timeline/ExecutionTimeline.vue'
import ChatInteractionArea from './ChatInteractionArea.vue'

// ========== Store ==========
const store = useWorkspaceStore()
const panelStore = usePanelStore()

// ========== 初始化：workspace 使用紧凑模式 ==========
onMounted(() => {
  panelStore.state.sizePreset = 'compact'
})

// ========== Computed ==========
const timelineCount = computed(() => store.timelineEntries.length)

// ========== Methods ==========
function handleClearTimeline() {
  store.clearTimeline()
  store.clearPanelPreviews()
  store.clearArtifacts()
}
</script>

<style scoped>
.main-canvas {
  background: var(--background);
}

.timeline-container {
  display: flex;
  flex-direction: column;
}
</style>
