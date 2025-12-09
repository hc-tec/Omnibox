<template>
  <div class="artifact-preview p-3">
    <!-- 基本信息 -->
    <div class="space-y-2">
      <h4 class="text-xs font-semibold text-foreground">
        {{ artifact.name }}
      </h4>

      <p
        v-if="artifact.description"
        class="text-[11px] text-muted-foreground line-clamp-2"
      >
        {{ artifact.description }}
      </p>
    </div>

    <!-- Schema 信息 -->
    <div v-if="artifact.schema_info" class="mt-3">
      <div class="mb-1.5 flex items-center justify-between">
        <span class="text-[10px] font-semibold text-muted-foreground">字段</span>
        <span class="text-[10px] text-muted-foreground">
          {{ artifact.schema_info.fields?.length || 0 }} 个
        </span>
      </div>

      <div class="space-y-1">
        <div
          v-for="field in displayFields"
          :key="field.name"
          class="flex items-center justify-between rounded-md border border-border/30 bg-background/50 px-2 py-1"
        >
          <span class="text-[11px] text-foreground">{{ field.name }}</span>
          <span class="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
            {{ field.type }}
          </span>
        </div>

        <div
          v-if="hasMoreFields"
          class="text-center text-[10px] text-muted-foreground"
        >
          还有 {{ artifact.schema_info.fields.length - maxDisplayFields }} 个字段
        </div>
      </div>
    </div>

    <!-- 统计信息 -->
    <div v-if="artifact.statistics" class="mt-3">
      <span class="text-[10px] font-semibold text-muted-foreground">统计</span>

      <div class="mt-1.5 grid grid-cols-2 gap-1.5">
        <div class="rounded-md border border-border/30 bg-background/50 px-2 py-1.5 text-center">
          <p class="text-sm font-semibold text-foreground">
            {{ artifact.schema_info?.total_count || 0 }}
          </p>
          <p class="text-[10px] text-muted-foreground">总条数</p>
        </div>

        <div class="rounded-md border border-border/30 bg-background/50 px-2 py-1.5 text-center">
          <p class="text-sm font-semibold text-foreground">
            {{ artifact.schema_info?.fields?.length || 0 }}
          </p>
          <p class="text-[10px] text-muted-foreground">字段数</p>
        </div>
      </div>
    </div>

    <!-- 可视化建议 -->
    <div v-if="artifact.suggested_views?.length" class="mt-3">
      <span class="text-[10px] font-semibold text-muted-foreground">推荐视图</span>

      <div class="mt-1.5 flex flex-wrap gap-1">
        <span
          v-for="view in artifact.suggested_views.slice(0, 3)"
          :key="view.component"
          class="inline-flex items-center gap-1 rounded-md border border-border/30 bg-background/50 px-2 py-1 text-[10px] text-muted-foreground"
        >
          <component :is="getViewIcon(view.component)" class="h-3 w-3" />
          {{ formatViewName(view.component) }}
        </span>
      </div>
    </div>

    <!-- 时间信息 -->
    <div class="mt-3 text-[10px] text-muted-foreground/70">
      创建于 {{ formatDate(artifact.created_at) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw } from 'vue'
import {
  BarChart3,
  LineChart,
  PieChart,
  Table2,
  List,
} from 'lucide-vue-next'
import type { Artifact } from '../../types/workspace'

// ========== Props ==========
const props = defineProps<{
  artifact: Artifact
}>()

// ========== Constants ==========
const maxDisplayFields = 5

// ========== Computed ==========

const displayFields = computed(() => {
  return props.artifact.schema_info?.fields?.slice(0, maxDisplayFields) || []
})

const hasMoreFields = computed(() => {
  return (props.artifact.schema_info?.fields?.length || 0) > maxDisplayFields
})

// ========== Methods ==========

function getViewIcon(component: string) {
  const icons: Record<string, unknown> = {
    BarChart: markRaw(BarChart3),
    LineChart: markRaw(LineChart),
    PieChart: markRaw(PieChart),
    Table: markRaw(Table2),
    ListPanel: markRaw(List),
  }
  return icons[component] || markRaw(BarChart3)
}

function formatViewName(component: string): string {
  const names: Record<string, string> = {
    BarChart: '柱状图',
    LineChart: '折线图',
    PieChart: '饼图',
    Table: '表格',
    ListPanel: '列表',
  }
  return names[component] || component
}

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}
</script>
