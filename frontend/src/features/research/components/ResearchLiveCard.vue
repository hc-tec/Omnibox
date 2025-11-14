<template>
  <div
    class="research-live-card group relative overflow-hidden rounded-2xl border backdrop-blur-sm transition-all duration-300"
    :class="[cardClass, clickableClass]"
    @click="handleCardClick"
  >
    <!-- 状态指示渐变背景 -->
    <div class="absolute inset-0 opacity-0 transition-opacity duration-300" :class="backgroundGradient" />

    <!-- 顶部状态条 -->
    <div class="absolute top-0 left-0 right-0 h-1 transition-all duration-500" :class="statusBarClass" />

    <!-- 卡片内容 -->
    <div class="relative">
      <!-- Header -->
      <div class="flex items-start justify-between gap-3 p-5 pb-4">
        <div class="flex items-start gap-3 flex-1 min-w-0">
          <!-- 状态图标 -->
          <div class="flex-shrink-0 mt-0.5">
            <div
              class="flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-300"
              :class="iconContainerClass"
            >
              <component :is="statusIcon" :class="iconClass" />
            </div>
          </div>

          <!-- 标题和查询 -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <Badge :variant="badgeVariant" class="text-[10px] uppercase tracking-wider">
                {{ statusText }}
              </Badge>
              <span v-if="task.execution_steps.length > 0" class="text-[10px] text-muted-foreground">
                {{ task.execution_steps.length }} 步骤
              </span>
            </div>
            <h3 class="text-sm font-semibold leading-snug text-foreground line-clamp-2">
              {{ task.query }}
            </h3>
          </div>
        </div>

        <!-- 删除按钮（悬停时显示） -->
        <Button
          v-if="!isSuggested"
          variant="ghost"
          size="icon"
          class="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity -mr-2 -mt-1 hover:bg-destructive/10 hover:text-destructive"
          @click.stop="$emit('delete', task.task_id)"
        >
          <X class="h-4 w-4" />
        </Button>
      </div>

      <!-- Content -->
      <div class="px-5 pb-5 space-y-4">
        <!-- 自动提示：建议进入研究视图 -->
        <div v-if="isSuggested" class="space-y-3">
          <div class="rounded-xl border border-primary/30 bg-primary/5 p-3.5 backdrop-blur-sm">
            <div class="flex items-start gap-3">
              <Brain class="h-4 w-4 text-primary flex-shrink-0 mt-0.5" />
              <div class="flex-1 space-y-2">
                <p class="text-xs font-semibold text-foreground">AI 检测到复杂研究需求</p>
                <p class="text-xs leading-relaxed text-muted-foreground">
                  建议启用研究模式，保留子查询、面板推理和实时日志。
                </p>
              </div>
            </div>
          </div>

          <div
            v-if="topSubQueries.length"
            class="space-y-1.5 rounded-xl border border-border/40 bg-muted/20 p-3"
          >
            <p class="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
              子查询预览
            </p>
            <div
              v-for="(item, idx) in topSubQueries"
              :key="idx"
              class="flex items-center gap-2 text-xs text-muted-foreground"
            >
              <div class="h-1 w-1 rounded-full bg-primary flex-shrink-0" />
              <span class="truncate">{{ item.query }}</span>
            </div>
            <p v-if="extraSubQueryCount > 0" class="text-xs text-muted-foreground/60 pt-1">
              + {{ extraSubQueryCount }} 条额外子查询
            </p>
          </div>
        </div>

        <!-- 处理中：显示进度 -->
        <div v-else-if="task.status === 'processing'" class="space-y-2">
          <div
            v-for="step in displaySteps"
            :key="step.step_id"
            class="flex items-center gap-2.5 text-xs group/step"
          >
            <div class="flex-shrink-0">
              <CheckCircle
                v-if="step.status === 'success'"
                class="h-3.5 w-3.5 text-emerald-500"
              />
              <div
                v-else
                class="h-3.5 w-3.5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin"
              />
            </div>
            <span class="text-muted-foreground group-hover/step:text-foreground transition-colors">
              {{ step.action }}
            </span>
          </div>
          <div v-if="task.execution_steps.length === 0" class="flex items-center gap-2.5 text-xs">
            <div class="h-3.5 w-3.5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin flex-shrink-0" />
            <span class="text-muted-foreground">初始化研究任务…</span>
          </div>
          <div v-if="task.execution_steps.length > 3" class="text-xs text-muted-foreground/60 pl-6">
            + {{ task.execution_steps.length - 3 }} 个额外步骤
          </div>
        </div>

        <!-- 等待人类输入 -->
        <div v-else-if="task.status === 'human_in_loop'" class="space-y-2.5">
          <div class="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3.5 backdrop-blur-sm">
            <div class="flex items-start gap-3">
              <AlertCircle class="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
              <div class="flex-1 space-y-1.5">
                <p class="text-xs font-semibold text-foreground">需要你的回复</p>
                <p class="text-xs leading-relaxed text-muted-foreground">
                  {{ task.human_request?.message || "等待响应…" }}
                </p>
              </div>
            </div>
          </div>
          <p class="text-xs text-muted-foreground flex items-center gap-1.5">
            <Inbox class="h-3 w-3" />
            请在右下角 "行动收件箱" 中回复
          </p>
        </div>

        <!-- 已完成 -->
        <div v-else-if="task.status === 'completed'" class="space-y-3">
          <div class="rounded-xl border border-border/40 bg-muted/20 p-3.5">
            <p class="text-xs leading-relaxed text-muted-foreground line-clamp-3">
              {{ task.final_report || "研究已完成，点击查看详情" }}
            </p>
          </div>
        </div>

        <!-- 错误 -->
        <div v-else-if="task.status === 'error'">
          <div class="rounded-xl border border-red-500/30 bg-red-500/5 p-3.5 backdrop-blur-sm">
            <div class="flex items-start gap-3">
              <AlertCircle class="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
              <div class="flex-1 space-y-1.5">
                <p class="text-xs font-semibold text-foreground">执行出错</p>
                <p class="text-xs leading-relaxed text-muted-foreground">
                  {{ task.error }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- 预览数据 -->
        <div v-if="task.previews && task.previews.length" class="space-y-2.5">
          <p class="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
            实时数据预览
          </p>
          <div
            v-for="preview in task.previews.slice(0, 2)"
            :key="preview.preview_id"
            class="rounded-xl border border-border/40 bg-gradient-to-br from-muted/10 to-muted/5 p-3 backdrop-blur-sm"
          >
            <div class="flex items-center justify-between gap-2 mb-2">
              <p class="text-xs font-semibold text-foreground">{{ preview.title }}</p>
              <div class="flex h-5 w-5 items-center justify-center rounded-md bg-primary/10">
                <Zap class="h-3 w-3 text-primary" />
              </div>
            </div>
            <ul class="space-y-1">
              <li
                v-for="(item, idx) in preview.items.slice(0, 2)"
                :key="`${preview.preview_id}-${idx}`"
                class="text-xs text-muted-foreground truncate"
              >
                {{ formatPreviewItem(item) }}
              </li>
              <li v-if="preview.items.length === 0" class="text-xs text-muted-foreground/50">
                暂无数据
              </li>
              <li v-if="preview.items.length > 2" class="text-xs text-muted-foreground/60">
                + {{ preview.items.length - 2 }} 项
              </li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div
        v-if="showFooter"
        class="border-t border-border/40 bg-muted/10 px-5 py-3 backdrop-blur-sm"
      >
        <div class="flex items-center justify-between gap-3">
          <span class="text-xs text-muted-foreground">
            {{ footerText }}
          </span>
          <div class="flex gap-2">
            <Button
              v-if="isSuggested"
              size="sm"
              class="h-8 rounded-lg text-xs"
              @click.stop="$emit('open', task.task_id)"
            >
              <Sparkles class="mr-1.5 h-3.5 w-3.5" />
              启动研究
            </Button>
            <Button
              v-else
              variant="ghost"
              size="sm"
              class="h-8 rounded-lg text-xs hover:text-destructive hover:bg-destructive/10"
              @click.stop="$emit('delete', task.task_id)"
            >
              删除
            </Button>
          </div>
        </div>
      </div>
    </div>

    <!-- 悬停光效 -->
    <div
      class="pointer-events-none absolute -inset-px rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
      :class="hoverGlowClass"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  CheckCircle,
  Loader,
  AlertCircle,
  Brain,
  Sparkles,
  X,
  Inbox,
  Zap,
} from "lucide-vue-next";
import type { ResearchTask } from "../types/researchTypes";

interface Props {
  task: ResearchTask;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  delete: [taskId: string];
  open: [taskId: string];
}>();

const isSuggested = computed(() => props.task.status === "idle" && props.task.auto_detected);

const topSubQueries = computed(() => {
  const subQueries = props.task.metadata?.sub_queries;
  if (!subQueries || !Array.isArray(subQueries)) return [];
  return subQueries.slice(0, 3);
});

const extraSubQueryCount = computed(() => {
  const subQueries = props.task.metadata?.sub_queries;
  if (!subQueries || !Array.isArray(subQueries)) return 0;
  return Math.max(subQueries.length - 3, 0);
});

// 只显示前3个步骤
const displaySteps = computed(() => props.task.execution_steps.slice(0, 3));

const statusIcon = computed(() => {
  switch (props.task.status) {
    case "processing":
      return Loader;
    case "human_in_loop":
      return Brain;
    case "completed":
      return CheckCircle;
    case "error":
      return AlertCircle;
    case "idle":
    default:
      return Sparkles;
  }
});

const iconClass = computed(() => ({
  "h-5 w-5 transition-all duration-300": true,
  "animate-spin text-blue-500": props.task.status === "processing",
  "text-amber-500": props.task.status === "human_in_loop",
  "text-emerald-500": props.task.status === "completed",
  "text-red-500": props.task.status === "error",
  "text-primary": props.task.status === "idle",
}));

const iconContainerClass = computed(() => ({
  "transition-all duration-300": true,
  "bg-blue-500/10 shadow-lg shadow-blue-500/20": props.task.status === "processing",
  "bg-amber-500/10 shadow-lg shadow-amber-500/20": props.task.status === "human_in_loop",
  "bg-emerald-500/10 shadow-lg shadow-emerald-500/20": props.task.status === "completed",
  "bg-red-500/10 shadow-lg shadow-red-500/20": props.task.status === "error",
  "bg-primary/10 shadow-lg shadow-primary/20": props.task.status === "idle",
}));

const statusText = computed(() => {
  switch (props.task.status) {
    case "processing":
      return "处理中";
    case "human_in_loop":
      return "等待回复";
    case "completed":
      return "已完成";
    case "error":
      return "出错";
    case "idle":
      return "待启动";
    default:
      return "未知";
  }
});

const badgeVariant = computed((): "default" | "secondary" | "outline" | "destructive" => {
  switch (props.task.status) {
    case "processing":
      return "default";
    case "human_in_loop":
    case "idle":
      return "secondary";
    case "completed":
      return "outline";
    case "error":
      return "destructive";
    default:
      return "outline";
  }
});

const cardClass = computed(() => ({
  "border-border/30 bg-background/60": true,
  "hover:border-blue-500/40 hover:bg-background/80": props.task.status === "processing" && isClickable.value,
  "hover:border-amber-500/40 hover:bg-background/80": props.task.status === "human_in_loop",
  "hover:border-emerald-500/40 hover:bg-background/80": props.task.status === "completed" && isClickable.value,
  "hover:border-red-500/40 hover:bg-background/80": props.task.status === "error",
  "hover:border-primary/40 hover:bg-background/80": props.task.status === "idle",
}));

const statusBarClass = computed(() => {
  switch (props.task.status) {
    case "processing":
      return "bg-gradient-to-r from-blue-500 via-cyan-500 to-blue-500 animate-pulse";
    case "human_in_loop":
      return "bg-gradient-to-r from-amber-500 to-orange-500";
    case "completed":
      return "bg-gradient-to-r from-emerald-500 to-green-500";
    case "error":
      return "bg-gradient-to-r from-red-500 to-rose-500";
    case "idle":
      return "bg-gradient-to-r from-primary to-purple-500";
    default:
      return "bg-muted";
  }
});

const backgroundGradient = computed(() => {
  if (!isClickable.value) return "";

  switch (props.task.status) {
    case "processing":
      return "group-hover:opacity-5 bg-gradient-to-br from-blue-500/20 to-cyan-500/20";
    case "completed":
      return "group-hover:opacity-5 bg-gradient-to-br from-emerald-500/20 to-green-500/20";
    default:
      return "";
  }
});

const hoverGlowClass = computed(() => {
  if (!isClickable.value) return "";

  switch (props.task.status) {
    case "processing":
      return "shadow-2xl shadow-blue-500/20";
    case "completed":
      return "shadow-2xl shadow-emerald-500/20";
    default:
      return "";
  }
});

const showFooter = computed(
  () => props.task.status === "completed" || props.task.status === "error" || isSuggested.value
);

const footerText = computed(() => {
  if (isSuggested.value) {
    if (props.task.metadata?.query_plan?.sub_query_count) {
      return `推测包含 ${props.task.metadata.query_plan.sub_query_count} 条子查询`;
    }
    return "AI 建议转入研究模式";
  }

  const stepCount = props.task.execution_steps.length;
  if (stepCount === 0) return "暂无执行步骤";

  const completedSteps = props.task.execution_steps.filter(s => s.status === "success").length;
  return `${completedSteps}/${stepCount} 步骤完成`;
});

const formatPreviewItem = (item: Record<string, unknown> | undefined) => {
  if (!item || typeof item !== "object") {
    return String(item ?? "");
  }
  return Object.entries(item)
    .slice(0, 2)
    .map(([key, value]) => `${key}: ${String(value ?? "")}`)
    .join(" · ");
};

// 可点击状态：completed 和 processing 状态的卡片可以点击进入研究页面
const isClickable = computed(() =>
  props.task.status === "completed" || props.task.status === "processing"
);

const clickableClass = computed(() => ({
  "cursor-pointer hover:scale-[1.02] hover:shadow-2xl": isClickable.value,
}));

// 处理卡片点击事件
const handleCardClick = () => {
  if (isClickable.value) {
    emit("open", props.task.task_id);
  }
};
</script>

<style scoped>
.research-live-card {
  /* 确保变换原点在中心 */
  transform-origin: center;
}

/* 自定义动画 */
@keyframes shimmer {
  0% {
    background-position: -1000px 0;
  }
  100% {
    background-position: 1000px 0;
  }
}

.research-live-card:hover {
  /* 添加微妙的提升效果 */
  transform: translateY(-2px);
}
</style>
