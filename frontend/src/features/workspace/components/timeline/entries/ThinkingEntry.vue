<!--
  思考条目组件 - Manus 风格（简洁版）
-->
<script setup lang="ts">
import { ref } from 'vue'
import { Brain, ChevronDown, ChevronRight, Lightbulb } from 'lucide-vue-next'
import type { TimelineEntry } from '../../../types/workspace'

defineProps<{
  entry: TimelineEntry
}>()

// 折叠状态（默认展开）
const isExpanded = ref(true)
</script>

<template>
  <div class="bg-muted/30 rounded-lg overflow-hidden">
    <!-- 标题行 -->
    <div
      class="flex items-center gap-1.5 px-3 py-2 cursor-pointer hover:bg-muted/50 transition-colors"
      @click="isExpanded = !isExpanded"
    >
      <Brain class="h-3.5 w-3.5 text-muted-foreground" />
      <span class="text-xs font-medium text-muted-foreground">思考中</span>
      <component
        :is="isExpanded ? ChevronDown : ChevronRight"
        class="h-3.5 w-3.5 text-muted-foreground/60 ml-auto"
      />
    </div>

    <!-- 内容 -->
    <div v-show="isExpanded" class="px-3 pb-2.5">
      <!-- 主要内容 -->
      <div class="text-[13px] leading-relaxed text-foreground/80 whitespace-pre-wrap">
        {{ entry.thinking?.content }}
      </div>

      <!-- 详细推理（如果有） -->
      <div v-if="entry.thinking?.reasoning" class="mt-2 pt-2 border-t border-border/50">
        <div class="flex items-center gap-1.5 mb-1.5">
          <Lightbulb class="h-3 w-3 text-yellow-500/80" />
          <span class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
            详细推理
          </span>
        </div>
        <div class="text-[13px] leading-relaxed text-foreground/70 whitespace-pre-wrap bg-muted/20 rounded px-2 py-1.5">
          {{ entry.thinking.reasoning }}
        </div>
      </div>
    </div>
  </div>
</template>
