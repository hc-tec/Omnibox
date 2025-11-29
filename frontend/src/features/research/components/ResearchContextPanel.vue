<template>
  <div class="research-context-panel flex h-full flex-col">
    <!-- 顶部：研究计划 -->
    <div class="border-b border-border/20 p-4 space-y-3">
      <div class="flex items-center justify-between gap-2">
        <h3 class="text-sm font-semibold text-foreground">研究计划</h3>
        <span v-if="planItems.length" class="text-[11px] text-muted-foreground">
          {{ planItems.length }} 个任务
        </span>
      </div>

      <div v-if="store.state.plan" class="space-y-2 text-xs text-muted-foreground">
        <p>{{ store.state.plan.reasoning || "研究代理正在构建多阶段计划..." }}</p>
        <div class="flex flex-wrap items-center gap-2">
          <span>数据任务 {{ dataTaskCount }}</span>
          <span>分析任务 {{ analysisTaskCount }}</span>
          <span v-if="store.state.plan.estimated_time">预计 {{ store.state.plan.estimated_time }}s</span>
        </div>
      </div>

      <div v-else class="text-xs text-muted-foreground">
        <div class="animate-pulse">规划中...</div>
      </div>

      <!-- 研究计划列表 -->
      <div v-if="planItems.length" class="space-y-2 rounded-xl border border-border/30 bg-background/40 p-3">
        <div
          v-for="item in planItems"
          :key="item.stepId ?? item.query"
          class="flex items-start gap-3 rounded-lg border border-border/20 bg-background/70 px-3 py-2 text-xs transition"
          :class="planStatusClass(item.status)"
        >
          <div class="mt-0.5 flex-shrink-0">
            <span
              class="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase"
              :class="planTagClass(item.task_type)"
            >
              {{ planTaskTypeText(item.task_type) }}
            </span>
          </div>
          <div class="flex-1 min-w-0 space-y-1">
            <p class="font-medium text-foreground line-clamp-2">{{ item.query }}</p>
            <div class="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
              <span v-if="item.datasource">数据源：{{ item.datasource }}</span>
              <span>状态：{{ planStatusText(item.status) }}</span>
            </div>
          </div>
        </div>
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
                  :class="stepTypeClass(step.step_type)"
                >
                  {{ stepTypeText(step.step_type) }}
                </span>
                <span class="text-[10px] text-muted-foreground">
                  #{{ index + 1 }}
                </span>
                <span v-if="step.step_id?.startsWith('node-')" class="rounded bg-border/40 px-1 py-0.5 text-[10px] text-muted-foreground">
                  Agent 节点
                </span>
              </div>

              <p class="mt-1 text-xs font-medium text-foreground">
                {{ step.action }}
              </p>

              <!-- 详情 -->
              <div v-if="hasDetails(step)" class="mt-2 space-y-1.5 text-[11px] text-muted-foreground">
                <div v-if="step.details?.item_count" class="flex items-center gap-1">
                  <Database class="h-3 w-3" />
                  {{ step.details.item_count }} 条数据
                </div>
                <div v-if="step.details?.feed_title">
                  来源：{{ step.details.feed_title }}
                </div>
                <div v-if="step.details?.error" class="text-red-400">
                  错误：{{ step.details.error }}
                </div>
                <div v-if="step.details?.summary" class="rounded border border-border/30 bg-background/60 p-2">
                  <p class="text-[10px] font-semibold text-muted-foreground/80 mb-1">摘要</p>
                  <pre class="whitespace-pre-wrap break-words text-[11px] text-muted-foreground/90">{{ formatSummary(step.details.summary) }}</pre>
                </div>
                <div v-for="detail in otherDetailEntries(step.details)" :key="detail.label" class="flex items-start gap-1">
                  <span class="text-muted-foreground/70">{{ detail.label }}：</span>
                  <span class="text-foreground/80">{{ detail.value }}</span>
                </div>
              </div>

              <!-- 时间戳 -->
              <p class="mt-2 text-[10px] text-muted-foreground">
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
import { computed } from "vue";
import { useResearchViewStore } from "@/store/researchViewStore";
import type { ResearchStep, ResearchStepType } from "@/store/researchViewStore";
import { CheckCircle2, XCircle, Circle, Loader2, Database } from "lucide-vue-next";

// ========== Store ==========
const store = useResearchViewStore();

type PlanItem = {
  query: string;
  task_type: string;
  datasource?: string | null;
  stepId: string | null;
  status: ResearchStep["status"] | "pending";
};

const planItems = computed<PlanItem[]>(() => {
  const plan = store.state.plan;
  if (!plan || !plan.sub_queries?.length) {
    return [];
  }

  const stepStatusMap = new Map(store.state.steps.map(step => [step.step_id, step.status]));
  let dataIdx = 0;
  let analysisIdx = 0;

  return plan.sub_queries.map(sub => {
    let stepId: string | null = null;
    if (sub.task_type === "data_fetch") {
      stepId = `data_fetch_${dataIdx++}`;
    } else if (sub.task_type === "analysis" || sub.task_type === "report") {
      stepId = `analysis_${analysisIdx++}`;
    }
    const status = (stepId && stepStatusMap.get(stepId)) || "pending";
    return {
      query: sub.query,
      task_type: sub.task_type,
      datasource: sub.datasource,
      stepId,
      status,
    };
  });
});

const dataTaskCount = computed(() => planItems.value.filter(item => item.task_type === "data_fetch").length);
const analysisTaskCount = computed(() =>
  planItems.value.filter(item => item.task_type === "analysis" || item.task_type === "report").length
);

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

function stepTypeClass(type: ResearchStepType) {
  return {
    "bg-purple-500/10 text-purple-500": type === "planning",
    "bg-blue-500/10 text-blue-500": type === "data_fetch",
    "bg-amber-500/10 text-amber-500": type === "analysis",
  };
}

function hasDetails(step: ResearchStep): boolean {
  if (!step.details) return false;
  const keys = Object.keys(step.details);
  return keys.some((key) => step.details && step.details[key] !== undefined && step.details[key] !== null);
}

function formatSummary(summary: unknown): string {
  if (typeof summary === "string") {
    return summary;
  }
  try {
    return JSON.stringify(summary, null, 2);
  } catch {
    return String(summary);
  }
}

function otherDetailEntries(details?: Record<string, any>) {
  if (!details) return [];
  const skip = new Set(["item_count", "feed_title", "error", "summary"]);
  return Object.entries(details)
    .filter(([key, value]) => !skip.has(key) && value !== undefined && value !== null)
    .map(([key, value]) => ({
      label: formatDetailLabel(key),
      value: formatDetailValue(value),
    }));
}

function formatDetailLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDetailValue(value: unknown): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
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

function planTaskTypeText(type: string): string {
  if (type === "data_fetch") return "获取数据";
  if (type === "analysis" || type === "report") return "分析/总结";
  return "其他";
}

function planTagClass(type: string) {
  if (type === "data_fetch") {
    return "bg-blue-500/10 text-blue-500";
  }
  if (type === "analysis" || type === "report") {
    return "bg-amber-500/10 text-amber-500";
  }
  return "bg-muted text-muted-foreground";
}

function planStatusText(status: ResearchStep["status"] | "pending"): string {
  switch (status) {
    case "processing":
      return "执行中";
    case "success":
      return "已完成";
    case "error":
      return "失败";
    default:
      return "待开始";
  }
}

function planStatusClass(status: ResearchStep["status"] | "pending") {
  switch (status) {
    case "success":
      return "border-emerald-500/40 bg-emerald-500/5";
    case "processing":
      return "border-blue-500/40 bg-blue-500/5";
    case "error":
      return "border-red-500/40 bg-red-500/5";
    default:
      return "border-border/20 bg-background/60";
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
