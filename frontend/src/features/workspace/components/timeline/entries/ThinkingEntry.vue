<!--
  思考条目组件 - Manus 风格（简洁版）
  支持基于 status 的 UI 状态切换：processing 显示动画，success/error 显示最终状态
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { Brain, ChevronDown, ChevronRight, Lightbulb } from 'lucide-vue-next'
import type { TimelineEntry } from '../../../types/workspace'

const { entry, isActive = false } = defineProps<{
  entry: TimelineEntry
  /** 是否当前正在执行的思考步骤，用于控制炫光 */
  isActive?: boolean
}>()

// 折叠状态（默认展开）
const isExpanded = ref(true)

// 基于 status 判断是否正在处理中
const isProcessing = computed(() => entry.thinking?.status === 'processing')

// 炫光开关：isActive 或 processing 状态时启用
const shimmerClass = computed(() => (isActive || isProcessing.value ? 'shimmer-text' : ''))

// 状态文本
const statusText = computed(() => {
  if (isProcessing.value) return '思考中'
  return '思考完成'
})
</script>

<template>
  <div class="bg-muted/30 rounded-lg overflow-hidden">
    <!-- 标题行 -->
    <div
      class="flex items-center gap-1.5 px-3 py-2 cursor-pointer hover:bg-muted/50 transition-colors"
      @click="isExpanded = !isExpanded"
    >
      <Brain class="h-3.5 w-3.5 text-muted-foreground" />
      <span class="text-xs font-medium text-muted-foreground" :class="shimmerClass">{{ statusText }}</span>
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

<style scoped>
.shimmer-text {
  position: relative;
  color: var(--foreground);
}

.shimmer-text::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(
    120deg,
    transparent 0%,
    rgba(255, 255, 255, 0.45) 45%,
    rgba(255, 255, 255, 0.9) 50%,
    rgba(255, 255, 255, 0.45) 55%,
    transparent 100%
  );
  background-size: 220% 100%;
  animation: shimmer 1.2s linear infinite;
  mix-blend-mode: screen;
  pointer-events: none;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
