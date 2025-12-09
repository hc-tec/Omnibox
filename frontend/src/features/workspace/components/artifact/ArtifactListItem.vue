<template>
  <div
    class="artifact-list-item group rounded-lg border p-2.5 transition cursor-pointer"
    :class="itemClass"
    @click="$emit('click')"
  >
    <div class="flex items-start gap-2">
      <!-- 类型图标 -->
      <div
        class="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg"
        :class="iconClass"
      >
        <component :is="typeIcon" class="h-3.5 w-3.5" />
      </div>

      <!-- 信息 -->
      <div class="min-w-0 flex-1">
        <p class="truncate text-xs font-medium text-foreground">
          {{ artifact.name }}
        </p>

        <div class="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
          <span
            class="rounded px-1.5 py-0.5 font-medium"
            :class="typeClass"
          >
            {{ typeText }}
          </span>
          <span v-if="artifact.schema_info?.total_count">
            {{ artifact.schema_info.total_count }} 条
          </span>
        </div>

        <!-- 来源信息 -->
        <div
          v-if="artifact.source?.tool_name"
          class="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground/70"
        >
          <Wrench class="h-3 w-3" />
          <span class="truncate">{{ artifact.source.tool_name }}</span>
        </div>
      </div>

      <!-- 预览按钮 -->
      <button
        class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-0 transition group-hover:opacity-100 hover:bg-background hover:text-foreground"
        title="在画布中预览"
        @click.stop="$emit('preview')"
      >
        <Eye class="h-3.5 w-3.5" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw } from 'vue'
import {
  Database,
  BarChart3,
  Lightbulb,
  FileText,
  Wrench,
  Eye,
} from 'lucide-vue-next'
import type { Artifact } from '../../types/workspace'

// ========== Props ==========
const props = defineProps<{
  artifact: Artifact
  selected?: boolean
}>()

// ========== Emits ==========
defineEmits<{
  click: []
  preview: []
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

const typeIcon = computed(() => {
  switch (props.artifact.artifact_type) {
    case 'dataset':
      return markRaw(Database)
    case 'analysis':
      return markRaw(BarChart3)
    case 'insight':
      return markRaw(Lightbulb)
    case 'document':
      return markRaw(FileText)
    default:
      return markRaw(Database)
  }
})

const typeText = computed(() => {
  switch (props.artifact.artifact_type) {
    case 'dataset':
      return '数据集'
    case 'analysis':
      return '分析'
    case 'insight':
      return '洞察'
    case 'document':
      return '文档'
    default:
      return props.artifact.artifact_type
  }
})

const typeClass = computed(() => {
  switch (props.artifact.artifact_type) {
    case 'dataset':
      return 'bg-blue-500/10 text-blue-500'
    case 'analysis':
      return 'bg-purple-500/10 text-purple-500'
    case 'insight':
      return 'bg-amber-500/10 text-amber-500'
    case 'document':
      return 'bg-green-500/10 text-green-500'
    default:
      return 'bg-muted text-muted-foreground'
  }
})
</script>
