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
                {{ formatStepAction(step) }}
              </p>

              <!-- 详情 -->
              <div v-if="hasDetails(step)" class="mt-2 space-y-1.5 text-[11px] text-muted-foreground">
                <div
                  v-for="detail in stepDetailEntries(step)"
                  :key="`${detail.label}-${detail.value}`"
                  class="flex items-start gap-1"
                >
                  <span class="text-muted-foreground/70">{{ detail.label }}：</span>
                  <span class="text-foreground/80">{{ detail.value }}</span>
                </div>
                <div v-if="summaryText(step)" class="rounded border border-border/30 bg-background/60 p-2">
                  <p class="text-[10px] font-semibold text-muted-foreground/80 mb-1">摘要</p>
                  <pre class="whitespace-pre-wrap break-words text-[11px] text-muted-foreground/90">{{ summaryText(step) }}</pre>
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
import { CheckCircle2, XCircle, Circle, Loader2 } from "lucide-vue-next";

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

type StepDetailEntry = {
  label: string;
  value: string;
};

function isStageStep(step: ResearchStep): boolean {
  return Boolean(step.step_id?.startsWith("stage-"));
}

function formatIntentType(intent?: unknown): string | null {
  if (typeof intent !== "string" || !intent) return null;
  if (intent === "data_query") return "需要数据分析";
  if (intent === "chitchat") return "闲聊问答";
  return intent;
}

function parseRouterPreview(preview: unknown): { route?: string; reasoning?: string } | null {
  if (typeof preview !== "string" || !preview.trim()) {
    return null;
  }
  const trimmed = preview.trim();
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (parsed && typeof parsed === "object") {
        return {
          route: typeof (parsed as Record<string, unknown>).route === "string" ? (parsed as Record<string, unknown>).route : undefined,
          reasoning: typeof (parsed as Record<string, unknown>).reasoning === "string" ? (parsed as Record<string, unknown>).reasoning : undefined,
        };
      }
    } catch {
      return { reasoning: trimmed };
    }
  }
  return { reasoning: trimmed };
}

const CACHE_LABELS: Record<string, string> = {
  rss_cache: "RSS 缓存命中",
  rag_cache: "RAG 缓存命中",
  none: "未命中",
};

function formatCacheLabel(flag: unknown): string | null {
  if (typeof flag !== "string" || !flag) return null;
  return CACHE_LABELS[flag] ?? flag;
}

function formatStepAction(step: ResearchStep): string {
  const details = step.details || {};
  if (isStageStep(step) && step.step_id) {
    const stage = step.step_id.replace("stage-", "");
    if (stage === "intent") {
      const intent = formatIntentType(details.intent_type);
      return intent ? `识别查询意图：${intent}` : "识别查询意图";
    }
    if (stage === "rag") {
      return typeof details.message === "string" && details.message ? details.message : "检索候选数据源";
    }
    if (stage === "fetch") {
      const target = details.feed_title || details.route || details.generated_path || details.source;
      if (step.status === "success") {
        return target ? `已获取 ${target} 的数据` : "数据获取完成";
      }
      return target ? `正在获取 ${target} 的数据` : "正在获取数据";
    }
    if (stage === "summary") {
      return typeof details.message === "string" && details.message ? details.message : "生成总结与洞察";
    }
  }

  if (step.step_id?.startsWith("llm-") && details.role === "router") {
    const routerDecision = parseRouterPreview(details.response_preview);
    if (routerDecision?.reasoning) {
      return `Router 决策：${routerDecision.reasoning}`;
    }
  }

  if (step.step_type === "data_fetch") {
    const target = details.feed_title || details.route || details.datasource;
    if (target) {
      if (step.status === "success") {
        return `数据准备完成：${target}`;
      }
      if (step.status === "processing") {
        return `正在获取 ${target} 的数据`;
      }
    }
  }

  return step.action;
}

function summaryText(step: ResearchStep): string | null {
  const summary = step.details?.summary;
  if (!summary) return null;
  if (typeof summary === "string") {
    return truncateText(summary);
  }
  if (typeof summary === "object" && summary !== null) {
    const summaryObj = summary as Record<string, unknown>;
    const candidate = summaryObj.preview || summaryObj.description || summaryObj.text;
    if (typeof candidate === "string" && candidate.trim()) {
      return truncateText(candidate);
    }
  }
  return null;
}

function truncateText(value: string, maxLength = 160): string {
  if (!value) return value;
  return value.length > maxLength ? `${value.slice(0, maxLength)}…` : value;
}

function stepDetailEntries(step: ResearchStep): StepDetailEntry[] {
  const details = step.details || {};
  const entries: StepDetailEntry[] = [];
  const used = new Set<string>();

  const pushEntry = (label: string, value?: unknown) => {
    if (value === undefined || value === null) return;
    const text = String(value).trim();
    if (!text) return;
    const key = `${label}-${text}`;
    if (used.has(key)) return;
    used.add(key);
    entries.push({ label, value: text });
  };

  if (isStageStep(step) && step.step_id) {
    const stage = step.step_id.replace("stage-", "");
    if (stage === "intent") {
      if (typeof details.reasoning === "string") {
        pushEntry("判定理由", details.reasoning);
      }
      return entries;
    }
    if (stage === "rag") {
      if (typeof details.message === "string") {
        pushEntry("检索说明", details.message);
      }
      return entries;
    }
    if (stage === "fetch") {
      pushEntry("数据源", details.feed_title || details.route || details.generated_path);
      if (typeof details.items_count === "number") {
        pushEntry("返回条数", details.items_count);
      }
      const cache = formatCacheLabel(details.cache_hit);
      if (cache) {
        pushEntry("缓存", cache);
      }
      return entries;
    }
    if (stage === "summary") {
      if (typeof details.message === "string") {
        pushEntry("说明", details.message);
      }
      if (typeof details.block_count === "number") {
        pushEntry("面板数量", details.block_count);
      }
      return entries;
    }
  }

  if (step.step_id?.startsWith("llm-") && details.role === "router") {
    const routerDecision = parseRouterPreview(details.response_preview);
    if (routerDecision?.route) {
      pushEntry("路由", routerDecision.route);
    }
    if (routerDecision?.reasoning) {
      pushEntry("决策理由", routerDecision.reasoning);
    }
    return entries;
  }

  pushEntry("数据源", details.feed_title || details.route || details.datasource);
  if (typeof details.item_count === "number") {
    pushEntry("数据条数", details.item_count);
  }
  if (typeof details.cache_hit === "string") {
    const cache = formatCacheLabel(details.cache_hit);
    if (cache) {
      pushEntry("缓存", cache);
    }
  }
  if (typeof details.reasoning === "string") {
    pushEntry("说明", details.reasoning);
  }
  if (typeof details.error === "string") {
    pushEntry("错误", details.error);
  }
  if (details.summary && typeof details.summary === "object" && details.summary !== null) {
    const summaryObj = details.summary as Record<string, unknown>;
    if (typeof summaryObj.dataset_count === "number") {
      pushEntry("数据集数量", summaryObj.dataset_count);
    }
    if (typeof summaryObj.item_count === "number") {
      pushEntry("记录数", summaryObj.item_count);
    }
  }

  return entries;
}

function hasDetails(step: ResearchStep): boolean {
  return stepDetailEntries(step).length > 0 || Boolean(summaryText(step));
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
