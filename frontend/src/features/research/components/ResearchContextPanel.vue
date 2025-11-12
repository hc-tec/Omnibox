<template>
  <div class="research-context-panel flex h-full flex-col">
    <!-- 顶部：研究计划 -->
    <div class="border-b border-border/20 p-4">
      <h3 class="mb-2 text-sm font-semibold text-foreground">研究计划</h3>

      <div v-if="store.state.plan" class="space-y-2">
        <p class="text-xs text-muted-foreground">
          {{ store.state.plan.reasoning }}
        </p>

        <div class="flex items-center gap-2 text-xs text-muted-foreground">
          <span>
            {{ store.state.plan.sub_queries.length }} 个子任务
          </span>
          <span v-if="store.state.plan.estimated_time">
            · 预计 {{ store.state.plan.estimated_time }}s
          </span>
        </div>
      </div>

      <div v-else class="text-xs text-muted-foreground">
        <div class="animate-pulse">规划中...</div>
      </div>
    </div>

    <!-- 进度条 -->
    <div v-if="store.isActive || store.isCompleted" class="border-b border-border/20 p-4">
      <div class="mb-1 flex items-center justify-between text-xs">
        <span class="text-muted-foreground">整体进度</span>
        <span class="font-semibold text-foreground">{{ store.progressPercentage }}%</span>
      </div>

      <div class="h-2 w-full overflow-hidden rounded-full bg-border/20">
        <div
          class="h-full rounded-full transition-all duration-300"
          :class="{
            'bg-blue-500': store.isActive,
            'bg-green-500': store.state.status === 'completed',
            'bg-red-500': store.state.status === 'error',
          }"
          :style="{ width: `${store.progressPercentage}%` }"
        />
      </div>

      <div class="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
        <span class="flex items-center gap-1">
          <CheckCircle2 class="h-3 w-3 text-green-500" />
          成功 {{ store.successStepsCount }}
        </span>
        <span v-if="store.errorStepsCount > 0" class="flex items-center gap-1">
          <XCircle class="h-3 w-3 text-red-500" />
          失败 {{ store.errorStepsCount }}
        </span>
      </div>
    </div>

    <!-- 步骤列表 -->
    <div class="flex-1 overflow-auto p-4">
      <h3 class="mb-3 text-sm font-semibold text-foreground">执行步骤</h3>

      <div v-if="store.state.steps.length > 0" class="space-y-2">
        <div
          v-for="(step, index) in store.state.steps"
          :key="step.step_id"
          class="group rounded-lg border border-border/40 bg-background/50 p-3 transition hover:border-border/60 hover:bg-background/80"
        >
          <div class="flex items-start gap-2">
            <!-- 状态图标 -->
            <div class="mt-0.5 flex-shrink-0">
              <Loader2
                v-if="step.status === 'processing'"
                class="h-4 w-4 animate-spin text-blue-500"
              />
              <CheckCircle2
                v-else-if="step.status === 'success'"
                class="h-4 w-4 text-green-500"
              />
              <XCircle
                v-else-if="step.status === 'error'"
                class="h-4 w-4 text-red-500"
              />
              <Circle
                v-else
                class="h-4 w-4 text-muted-foreground"
              />
            </div>

            <!-- 步骤信息 -->
            <div class="flex-1">
              <div class="flex items-center gap-2">
                <span
                  class="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase"
                  :class="{
                    'bg-purple-500/10 text-purple-500': step.step_type === 'planning',
                    'bg-blue-500/10 text-blue-500': step.step_type === 'data_fetch',
                    'bg-amber-500/10 text-amber-500': step.step_type === 'analysis',
                  }"
                >
                  {{ stepTypeText(step.step_type) }}
                </span>
                <span class="text-[10px] text-muted-foreground">
                  #{{ index + 1 }}
                </span>
              </div>

              <p class="mt-1 text-xs text-foreground">
                {{ step.action }}
              </p>

              <!-- 详情 -->
              <div v-if="step.details" class="mt-2 text-[10px] text-muted-foreground">
                <div v-if="step.details.item_count" class="flex items-center gap-1">
                  <Database class="h-3 w-3" />
                  {{ step.details.item_count }} 条数据
                </div>
                <div v-if="step.details.feed_title">
                  来源：{{ step.details.feed_title }}
                </div>
                <div v-if="step.details.error" class="text-red-400">
                  错误：{{ step.details.error }}
                </div>
              </div>

              <!-- 时间戳 -->
              <p class="mt-1 text-[10px] text-muted-foreground">
                {{ formatTimestamp(step.timestamp) }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="text-xs text-muted-foreground">
        <div class="flex items-center gap-2">
          <Loader2 class="h-4 w-4 animate-spin" />
          等待步骤执行...
        </div>
      </div>
    </div>

    <!-- 底部：统计信息 -->
    <div v-if="store.isCompleted" class="border-t border-border/20 p-4">
      <div class="space-y-1 text-xs">
        <div class="flex items-center justify-between">
          <span class="text-muted-foreground">总耗时</span>
          <span class="font-semibold text-foreground">
            {{ store.state.total_time ? `${store.state.total_time.toFixed(2)}s` : "N/A" }}
          </span>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-muted-foreground">数据面板</span>
          <span class="font-semibold text-foreground">
            {{ store.state.panels.length }}
          </span>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-muted-foreground">分析结果</span>
          <span class="font-semibold text-foreground">
            {{ store.state.analyses.length }}
          </span>
        </div>
      </div>

      <!-- 错误信息 -->
      <div v-if="store.hasError && store.state.error_message" class="mt-3 rounded-lg bg-red-500/10 p-3">
        <p class="text-xs text-red-500">{{ store.state.error_message }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useResearchViewStore } from "@/store/researchViewStore";
import type { ResearchStepType } from "@/store/researchViewStore";
import {
  CheckCircle2,
  XCircle,
  Circle,
  Loader2,
  Database,
} from "lucide-vue-next";

// ========== Store ==========
const store = useResearchViewStore();

// ========== 方法 ==========

/**
 * 步骤类型文本
 */
function stepTypeText(type: ResearchStepType): string {
  switch (type) {
    case "planning":
      return "规划";
    case "data_fetch":
      return "数据";
    case "analysis":
      return "分析";
    default:
      return "未知";
  }
}

/**
 * 格式化时间戳
 */
function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return timestamp;
  }
}
</script>

<style scoped>
.research-context-panel {
  /* 自定义滚动条样式 */
  scrollbar-width: thin;
  scrollbar-color: rgba(100, 100, 100, 0.3) rgba(0, 0, 0, 0.1);
}

.research-context-panel::-webkit-scrollbar {
  width: 6px;
}

.research-context-panel::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
}

.research-context-panel::-webkit-scrollbar-thumb {
  background: rgba(100, 100, 100, 0.3);
  border-radius: 3px;
}

.research-context-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 100, 100, 0.5);
}
</style>
