<!--
  思考条目组件 - Manus 风格（简洁版）
-->
<script setup lang="ts">
import { ref } from 'vue'
import { Brain, ChevronDown, ChevronRight } from 'lucide-vue-next'
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
    <div v-show="isExpanded" class="px-3 pb-2.5 text-[13px] leading-relaxed text-foreground/80 whitespace-pre-wrap">
      {{ entry.thinking?.content }}
    </div>
  </div>
</template>
