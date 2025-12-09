<template>
  <div
    class="workflow-list-item group rounded-lg border p-3 transition cursor-pointer"
    :class="itemClass"
    @click="$emit('click')"
  >
    <div class="flex items-start gap-2">
      <!-- 图标 -->
      <div
        class="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg"
        :class="iconClass"
      >
        <Workflow class="h-3.5 w-3.5" />
      </div>

      <!-- 信息 -->
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <span class="truncate text-sm font-medium text-foreground">
            {{ workflow.name }}
          </span>
          <span
            v-if="workflow.is_template"
            class="flex-shrink-0 rounded bg-purple-500/10 px-1.5 py-0.5 text-[10px] font-medium text-purple-500"
          >
            模板
          </span>
        </div>

        <p
          v-if="workflow.description"
          class="mt-0.5 truncate text-xs text-muted-foreground"
        >
          {{ workflow.description }}
        </p>

        <div class="mt-1.5 flex items-center gap-3 text-[10px] text-muted-foreground">
          <span class="flex items-center gap-1">
            <ListOrdered class="h-3 w-3" />
            {{ workflow.steps?.length || 0 }} 步骤
          </span>
          <span>{{ formatDate(workflow.updated_at) }}</span>
        </div>
      </div>

      <!-- 状态标识 -->
      <div class="flex-shrink-0">
        <span
          class="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium"
          :class="statusClass"
        >
          {{ statusText }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Workflow, ListOrdered } from 'lucide-vue-next'
import type { Workflow as WorkflowType } from '../../types/workspace'

// ========== Props ==========
const props = defineProps<{
  workflow: WorkflowType
  selected?: boolean
}>()

// ========== Emits ==========
defineEmits<{
  click: []
}>()

// ========== Computed ==========

const itemClass = computed(() => ({
  'border-primary/40 bg-primary/5': props.selected,
  'border-border/40 bg-background/50 hover:border-border/60 hover:bg-background/80': !props.selected,
}))

const iconClass = computed(() => ({
  'bg-primary/10 text-primary': props.selected,
  'bg-border/30 text-muted-foreground group-hover:bg-border/50': !props.selected,
}))

const statusText = computed(() => {
  switch (props.workflow.status) {
    case 'draft':
      return '草稿'
    case 'ready':
      return '就绪'
    case 'template':
      return '模板'
    default:
      return props.workflow.status
  }
})

const statusClass = computed(() => {
  switch (props.workflow.status) {
    case 'draft':
      return 'bg-yellow-500/10 text-yellow-500'
    case 'ready':
      return 'bg-green-500/10 text-green-500'
    case 'template':
      return 'bg-purple-500/10 text-purple-500'
    default:
      return 'bg-muted text-muted-foreground'
  }
})

// ========== Methods ==========

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))

    if (days === 0) return '今天'
    if (days === 1) return '昨天'
    if (days < 7) return `${days}天前`

    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return dateStr
  }
}
</script>
