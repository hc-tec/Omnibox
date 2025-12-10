<!--
  消息条目组件 - Manus 风格（支持结构化报告）
-->
<script setup lang="ts">
import { computed } from 'vue'
import { Info, AlertTriangle, CheckCircle2, Lightbulb, ArrowRight } from 'lucide-vue-next'
import type { TimelineEntry } from '../../../types/workspace'

interface StructuredReport {
  summary: string
  evidence?: Array<{ source: string; insight: string }>
  next_actions?: string[]
}

const props = defineProps<{
  entry: TimelineEntry
  /** 是否当前活跃步骤，用于运行态提示 */
  isActive?: boolean
}>()

// 尝试解析结构化报告
const parsedReport = computed<StructuredReport | null>(() => {
  const content = props.entry.message?.content
  if (!content) return null

  // 尝试解析 JSON
  try {
    const parsed = JSON.parse(content)
    if (parsed && typeof parsed.summary === 'string') {
      return parsed as StructuredReport
    }
  } catch {
    // 不是 JSON，返回 null
  }
  return null
})

// 是否为结构化报告
const isStructured = computed(() => parsedReport.value !== null)

// 图标
const icon = computed(() => {
  switch (props.entry.message?.level) {
    case 'warning':
      return AlertTriangle
    case 'success':
      return CheckCircle2
    default:
      return Info
  }
})

// 样式类
const containerClass = computed(() => {
  switch (props.entry.message?.level) {
    case 'warning':
      return 'border-l-yellow-500 bg-yellow-500/5'
    case 'success':
      return 'border-l-green-500 bg-green-500/5'
    default:
      return 'border-l-blue-500 bg-blue-500/5'
  }
})

const iconClass = computed(() => {
  switch (props.entry.message?.level) {
    case 'warning':
      return 'text-yellow-500'
    case 'success':
      return 'text-green-500'
    default:
      return 'text-blue-500'
  }
})

const textClass = computed(() => {
  switch (props.entry.message?.level) {
    case 'warning':
      return 'text-yellow-700 dark:text-yellow-400'
    case 'success':
      return 'text-green-700 dark:text-green-400'
    default:
      return 'text-blue-700 dark:text-blue-400'
  }
})
</script>

<template>
  <!-- 结构化报告展示 -->
  <div
    v-if="isStructured && parsedReport"
    class="rounded-lg p-3 border-l-[3px] space-y-2.5"
    :class="[containerClass, props.isActive ? 'shimmer-text' : '']"
  >
    <!-- 摘要 -->
    <div class="flex items-start gap-2">
      <component :is="icon" class="h-4 w-4 flex-shrink-0 mt-0.5" :class="iconClass" />
      <p class="text-sm font-medium" :class="textClass">{{ parsedReport.summary }}</p>
    </div>

    <!-- 证据/来源 -->
    <div v-if="parsedReport.evidence && parsedReport.evidence.length > 0" class="pl-6 space-y-1.5">
      <div
        v-for="(item, index) in parsedReport.evidence"
        :key="index"
        class="text-[11px] text-muted-foreground border-l-2 border-border/40 pl-2.5"
      >
        <span class="font-medium text-foreground/80">{{ item.source }}</span>
        <span class="mx-1">-</span>
        <span>{{ item.insight }}</span>
      </div>
    </div>

    <!-- 下一步操作建议 -->
    <div v-if="parsedReport.next_actions && parsedReport.next_actions.length > 0" class="pl-6">
      <div class="flex items-center gap-1 text-[11px] text-muted-foreground mb-1">
        <Lightbulb class="h-3 w-3" />
        <span>建议操作</span>
      </div>
      <div class="space-y-1">
        <div
          v-for="(action, index) in parsedReport.next_actions"
          :key="index"
          class="flex items-start gap-1.5 text-[11px] text-foreground/70"
        >
          <ArrowRight class="h-3 w-3 mt-0.5 flex-shrink-0 text-primary/60" />
          <span>{{ action }}</span>
        </div>
      </div>
    </div>
  </div>

  <!-- 普通文本消息 -->
  <div
    v-else
    class="rounded-lg p-2.5 border-l-[3px] flex items-center gap-2"
    :class="[containerClass, props.isActive ? 'shimmer-text' : '']"
  >
    <component :is="icon" class="h-4 w-4 flex-shrink-0" :class="iconClass" />
    <p class="text-sm" :class="textClass">{{ entry.message?.content }}</p>
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
    rgba(255, 255, 255, 0.35) 45%,
    rgba(255, 255, 255, 0.7) 50%,
    rgba(255, 255, 255, 0.35) 55%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.3s linear infinite;
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
