<template>
  <div class="llm-call-timeline">
    <!-- 统计摘要 -->
    <div
      v-if="stats.total > 0"
      class="flex items-center justify-between gap-4 mb-4 p-3 rounded-lg bg-muted/30 border border-border/40"
    >
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <Activity class="h-4 w-4 text-primary" />
          <span class="text-sm font-medium">LLM 调用</span>
        </div>
        <div class="flex items-center gap-3 text-xs text-muted-foreground">
          <span>
            <span class="font-mono text-foreground">{{ stats.completed }}</span>
            /{{ stats.total }} 完成
          </span>
          <span v-if="stats.failed > 0" class="text-red-500">
            {{ stats.failed }} 失败
          </span>
          <span v-if="stats.totalTokens > 0">
            <Coins class="h-3 w-3 inline mr-1" />
            {{ formatTokens(stats.totalTokens) }} tokens
          </span>
          <span v-if="stats.totalDuration > 0">
            <Clock class="h-3 w-3 inline mr-1" />
            {{ formatDuration(stats.totalDuration) }}
          </span>
        </div>
      </div>
      <!-- 操作按钮 -->
      <div class="flex items-center gap-2">
        <button
          class="flex items-center gap-1 px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded transition"
          title="导出为 JSON"
          @click.stop="handleExport"
        >
          <Download class="h-3 w-3" />
          导出
        </button>
        <button
          class="flex items-center gap-1 px-2 py-1 text-xs text-muted-foreground hover:text-red-500 hover:bg-red-500/10 rounded transition"
          title="清除所有记录"
          @click.stop="handleClear"
        >
          <Trash2 class="h-3 w-3" />
          清除
        </button>
      </div>
    </div>

    <!-- 无调用时显示占位 -->
    <div
      v-if="calls.length === 0"
      class="text-center py-8 text-muted-foreground text-sm"
    >
      <Cpu class="h-8 w-8 mx-auto mb-2 opacity-50" />
      <p>暂无 LLM 调用记录</p>
    </div>

    <!-- 调用时间线 -->
    <div v-else class="space-y-2">
      <div
        v-for="call in calls"
        :key="call.call_id"
        class="call-item group relative flex items-start gap-3 p-3 rounded-lg border transition-all duration-200 cursor-pointer"
        :class="callItemClass(call)"
        @click="toggleExpand(call.call_id)"
      >
        <!-- 状态指示器 -->
        <div class="flex-shrink-0 mt-0.5">
          <div
            class="h-8 w-8 rounded-lg flex items-center justify-center"
            :class="statusIconClass(call)"
          >
            <Loader
              v-if="call.status === 'started'"
              class="h-4 w-4 animate-spin"
            />
            <CheckCircle v-else-if="call.status === 'completed'" class="h-4 w-4" />
            <AlertCircle v-else class="h-4 w-4" />
          </div>
        </div>

        <!-- 调用信息 -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <Badge :variant="roleBadgeVariant(call.role)" class="text-[10px] uppercase">
              {{ call.role }}
            </Badge>
            <span class="text-xs text-muted-foreground">
              {{ formatTimestamp(call.timestamp) }}
            </span>
            <span
              v-if="call.duration_ms"
              class="text-xs text-muted-foreground font-mono"
            >
              {{ call.duration_ms }}ms
            </span>
          </div>

          <!-- Token 信息 -->
          <div
            v-if="call.total_tokens"
            class="flex items-center gap-3 text-xs text-muted-foreground mb-2"
          >
            <span v-if="call.prompt_tokens">
              输入: <span class="font-mono text-foreground">{{ call.prompt_tokens }}</span>
            </span>
            <span v-if="call.completion_tokens">
              输出: <span class="font-mono text-foreground">{{ call.completion_tokens }}</span>
            </span>
            <span v-if="call.total_tokens">
              总计: <span class="font-mono text-foreground">{{ call.total_tokens }}</span>
            </span>
          </div>

          <!-- 预览（可展开） -->
          <div v-if="expandedCalls.has(call.call_id)" class="mt-3 space-y-3">
            <!-- Prompt 完整内容 -->
            <div v-if="call.prompt_preview" class="rounded-lg bg-muted/50 p-3">
              <div class="text-[10px] uppercase text-muted-foreground mb-1">Prompt</div>
              <pre class="text-xs text-foreground whitespace-pre-wrap font-mono overflow-x-auto">{{ call.prompt_preview }}</pre>
            </div>

            <!-- Response 完整内容 -->
            <div v-if="call.response_preview" class="rounded-lg bg-muted/50 p-3">
              <div class="text-[10px] uppercase text-muted-foreground mb-1">Response</div>
              <pre class="text-xs text-foreground whitespace-pre-wrap font-mono overflow-x-auto">{{ call.response_preview }}</pre>
            </div>

            <!-- 错误信息 -->
            <div v-if="call.error_message" class="rounded-lg bg-red-500/10 border border-red-500/30 p-3">
              <div class="text-[10px] uppercase text-red-500 mb-1">Error</div>
              <pre class="text-xs text-red-400 whitespace-pre-wrap font-mono">{{ call.error_message }}</pre>
            </div>

            <!-- 模型信息 -->
            <div v-if="call.model" class="text-xs text-muted-foreground">
              模型: <span class="font-mono text-foreground">{{ call.model }}</span>
              <span v-if="call.temperature !== null && call.temperature !== undefined">
                (temp: {{ call.temperature }})
              </span>
            </div>
          </div>

          <!-- 展开提示 -->
          <div
            v-else-if="call.prompt_preview || call.response_preview"
            class="text-[10px] text-muted-foreground mt-1"
          >
            点击查看详情
          </div>
        </div>

        <!-- 展开图标 -->
        <ChevronDown
          v-if="call.prompt_preview || call.response_preview"
          class="h-4 w-4 text-muted-foreground transition-transform duration-200 flex-shrink-0"
          :class="{ 'rotate-180': expandedCalls.has(call.call_id) }"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { Badge } from '@/components/ui/badge';
import {
  Activity,
  Loader,
  CheckCircle,
  AlertCircle,
  ChevronDown,
  Coins,
  Clock,
  Cpu,
  Download,
  Trash2,
} from 'lucide-vue-next';
import type { LLMCallEvent } from '@/shared/types/panel';

interface Props {
  calls: LLMCallEvent[];
  stats?: {
    total: number;
    completed: number;
    failed: number;
    totalTokens: number;
    totalDuration: number;
  };
}

const props = withDefaults(defineProps<Props>(), {
  stats: () => ({
    total: 0,
    completed: 0,
    failed: 0,
    totalTokens: 0,
    totalDuration: 0,
  }),
});

const emit = defineEmits<{
  (e: 'clear'): void;
}>();

// 导出为 JSON 文件
function handleExport() {
  const exportData = {
    exportedAt: new Date().toISOString(),
    stats: props.stats,
    calls: props.calls,
  };
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `llm-calls-${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// 清除所有调用
function handleClear() {
  emit('clear');
}

// 展开状态
const expandedCalls = ref<Set<string>>(new Set());

function toggleExpand(callId: string) {
  if (expandedCalls.value.has(callId)) {
    expandedCalls.value.delete(callId);
  } else {
    expandedCalls.value.add(callId);
  }
}

// 格式化工具
function formatTokens(tokens: number): string {
  if (tokens >= 1000) {
    return `${(tokens / 1000).toFixed(1)}k`;
  }
  return tokens.toString();
}

function formatDuration(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${ms}ms`;
}

function formatTimestamp(timestamp: string | null | undefined): string {
  if (!timestamp) return '';
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return timestamp;
  }
}

// 样式计算
function callItemClass(call: LLMCallEvent) {
  return {
    'border-border/40 bg-background/60': call.status === 'completed',
    'border-blue-500/40 bg-blue-500/5': call.status === 'started',
    'border-red-500/40 bg-red-500/5': call.status === 'failed',
    'hover:bg-muted/50': true,
  };
}

function statusIconClass(call: LLMCallEvent) {
  return {
    'bg-emerald-500/10 text-emerald-500': call.status === 'completed',
    'bg-blue-500/10 text-blue-500': call.status === 'started',
    'bg-red-500/10 text-red-500': call.status === 'failed',
  };
}

function roleBadgeVariant(role: string): 'default' | 'secondary' | 'outline' | 'destructive' {
  switch (role) {
    case 'planner':
      return 'default';
    case 'reflector':
      return 'secondary';
    case 'synthesizer':
      return 'outline';
    case 'router':
      return 'outline';
    default:
      return 'secondary';
  }
}
</script>

<style scoped>
.call-item {
  transform-origin: center;
}

.call-item:hover {
  transform: translateY(-1px);
}
</style>
