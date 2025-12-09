<template>
  <div class="step-tree space-y-1.5">
    <div
      v-for="(step, index) in steps"
      :key="step.step_id"
      class="step-item group"
    >
      <!-- 连接线 -->
      <div
        v-if="index > 0"
        class="relative ml-[11px] h-2"
      >
        <div class="absolute left-0 top-0 h-full w-px bg-border/40" />
      </div>

      <!-- 步骤内容 -->
      <div
        class="flex items-start gap-2 rounded-lg border p-2 transition cursor-pointer"
        :class="stepItemClass(step)"
        @click="$emit('step-click', step)"
      >
        <!-- 状态图标 -->
        <div class="mt-0.5 flex-shrink-0">
          <Loader2
            v-if="stepStatuses[step.step_id] === 'running' || step.step_id === currentStepId"
            class="h-4 w-4 animate-spin text-blue-500"
          />
          <CheckCircle2
            v-else-if="stepStatuses[step.step_id] === 'completed'"
            class="h-4 w-4 text-green-500"
          />
          <XCircle
            v-else-if="stepStatuses[step.step_id] === 'failed'"
            class="h-4 w-4 text-red-500"
          />
          <Circle
            v-else
            class="h-4 w-4 text-muted-foreground"
          />
        </div>

        <!-- 步骤信息 -->
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <span
              class="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase"
              :class="stepTypeClass(step.step_type)"
            >
              {{ stepTypeText(step.step_type) }}
            </span>
            <span class="text-[10px] text-muted-foreground">
              #{{ index + 1 }}
            </span>
          </div>

          <p class="mt-0.5 truncate text-xs font-medium text-foreground">
            {{ step.name }}
          </p>

          <p
            v-if="step.description"
            class="mt-0.5 truncate text-[10px] text-muted-foreground"
          >
            {{ step.description }}
          </p>

          <!-- 依赖信息 -->
          <div
            v-if="step.depends_on?.length"
            class="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground"
          >
            <GitBranch class="h-3 w-3" />
            <span>依赖步骤 {{ step.depends_on.join(', ') }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div
      v-if="steps.length === 0"
      class="py-4 text-center text-xs text-muted-foreground"
    >
      暂无步骤
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  Circle,
  CheckCircle2,
  XCircle,
  Loader2,
  GitBranch,
} from 'lucide-vue-next'
import type { WorkflowStep, StepStatusMap, StepType } from '../../types/workspace'

// ========== Props ==========
const props = defineProps<{
  steps: WorkflowStep[]
  stepStatuses: StepStatusMap
  currentStepId?: number | null
}>()

// ========== Emits ==========
defineEmits<{
  'step-click': [step: WorkflowStep]
}>()

// ========== Methods ==========

function stepItemClass(step: WorkflowStep) {
  const status = props.stepStatuses[step.step_id] || 'pending'
  return {
    'border-blue-500/40 bg-blue-500/5': status === 'running',
    'border-green-500/40 bg-green-500/5': status === 'completed',
    'border-red-500/40 bg-red-500/5': status === 'failed',
    'border-border/40 bg-background/50 hover:border-border/60 hover:bg-background/80': !['running', 'completed', 'failed'].includes(status),
  }
}

function stepTypeText(type: StepType): string {
  switch (type) {
    case 'fetch':
      return '采集'
    case 'process':
      return '处理'
    case 'analyze':
      return '分析'
    case 'output':
      return '输出'
    default:
      return type
  }
}

function stepTypeClass(type: StepType) {
  switch (type) {
    case 'fetch':
      return 'bg-blue-500/10 text-blue-500'
    case 'process':
      return 'bg-amber-500/10 text-amber-500'
    case 'analyze':
      return 'bg-purple-500/10 text-purple-500'
    case 'output':
      return 'bg-green-500/10 text-green-500'
    default:
      return 'bg-muted text-muted-foreground'
  }
}
</script>
