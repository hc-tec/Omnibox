<!--
  面板条目组件 - Manus 风格
-->
<script setup lang="ts">
import { ref } from 'vue'
import { LayoutGrid, Pin, Check, X, ChevronDown, ChevronRight } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import PanelBoard from '@/features/panel/components/PanelBoard.vue'
import { useDashboardStore } from '@/features/dashboard/stores/dashboardStore'
import type { TimelineEntry } from '../../../types/workspace'
import type { LayoutTree, UIBlock, DataBlock } from '@/shared/types/panel'

const props = defineProps<{
  entry: TimelineEntry
}>()

const dashboardStore = useDashboardStore()

// 展开状态
const isExpanded = ref(true)

// Pin 状态
const pinStatus = ref<'idle' | 'success' | 'error'>('idle')
const pinMessage = ref('')

// Pin 到仪表盘
async function handlePin() {
  if (!props.entry.panel) return

  try {
    const result = await dashboardStore.pinPanel({
      title: props.entry.panel.title || '数据面板',
      layout: (props.entry.panel.layout || {}) as Record<string, unknown>,
      blocks: (props.entry.panel.blocks || []) as Array<Record<string, unknown>>,
      data_blocks: (props.entry.panel.dataBlocks || {}) as Record<string, unknown>,
    })

    if (result) {
      pinStatus.value = 'success'
      pinMessage.value = '已添加到仪表盘'
      setTimeout(() => {
        pinStatus.value = 'idle'
        pinMessage.value = ''
      }, 2000)
    }
  } catch (error) {
    pinStatus.value = 'error'
    pinMessage.value = error instanceof Error ? error.message : '未知错误'
    setTimeout(() => {
      pinStatus.value = 'idle'
      pinMessage.value = ''
    }, 3000)
  }
}
</script>

<template>
  <div class="rounded-lg border border-green-500/20 bg-green-500/5 overflow-hidden">
    <!-- 头部 -->
    <div class="flex items-center justify-between px-3 py-2 border-b border-green-500/10">
      <div
        class="flex items-center gap-2 cursor-pointer flex-1"
        @click="isExpanded = !isExpanded"
      >
        <component :is="isExpanded ? ChevronDown : ChevronRight" class="h-4 w-4 text-muted-foreground" />
        <LayoutGrid class="h-4 w-4 text-green-500" />
        <span class="text-sm font-medium text-foreground">{{ entry.panel?.title || '数据面板' }}</span>
      </div>
      <div class="flex items-center gap-2">
        <!-- Pin 状态提示 -->
        <span
          v-if="pinStatus !== 'idle'"
          class="text-[11px] flex items-center gap-1"
          :class="pinStatus === 'success' ? 'text-green-500' : 'text-red-500'"
        >
          <Check v-if="pinStatus === 'success'" class="h-3 w-3" />
          <X v-else class="h-3 w-3" />
          {{ pinMessage }}
        </span>
        <Button
          variant="ghost"
          size="sm"
          class="h-7 text-xs"
          @click.stop="handlePin"
          :disabled="pinStatus !== 'idle'"
        >
          <Pin class="h-3 w-3 mr-1" />
          Pin
        </Button>
      </div>
    </div>

    <!-- 面板内容 -->
    <div v-show="isExpanded" class="p-3">
      <div class="bg-background rounded-lg border border-border/40 max-h-[400px] overflow-y-auto">
        <PanelBoard
          v-if="entry.panel?.layout"
          :layout="(entry.panel.layout as LayoutTree)"
          :blocks="(entry.panel.blocks as UIBlock[])"
          :data-blocks="(entry.panel.dataBlocks as Record<string, DataBlock>)"
        />
        <div v-else class="p-4 text-center text-muted-foreground text-sm">
          面板数据加载中...
        </div>
      </div>
    </div>
  </div>
</template>
