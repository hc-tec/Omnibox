<script setup lang="ts">
/**
 * 开发者日志面板
 *
 * 显示调试日志，支持按级别过滤、自动滚动、展开详情
 */
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { Trash2, ChevronDown, ChevronRight, Terminal } from 'lucide-vue-next';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { devLogger, type LogEntry, type LogLevel } from '../mockDataGenerator';

const logLevels: { value: LogLevel; label: string; color: string }[] = [
  { value: 'debug', label: 'DEBUG', color: 'bg-slate-500/20 text-slate-500 border-slate-500/30' },
  { value: 'info', label: 'INFO', color: 'bg-blue-500/20 text-blue-500 border-blue-500/30' },
  { value: 'warn', label: 'WARN', color: 'bg-amber-500/20 text-amber-500 border-amber-500/30' },
  { value: 'error', label: 'ERROR', color: 'bg-red-500/20 text-red-500 border-red-500/30' },
];

const logs = ref<LogEntry[]>([]);
const visibleLevels = ref<LogLevel[]>(['info', 'warn', 'error']);
const expandedLogs = ref<Set<string>>(new Set());
const autoScroll = ref(true);
const logContainer = ref<HTMLElement | null>(null);

const filteredLogs = computed(() => {
  return logs.value.filter((log) => visibleLevels.value.includes(log.level));
});

function toggleLevel(level: LogLevel) {
  const index = visibleLevels.value.indexOf(level);
  if (index === -1) {
    visibleLevels.value.push(level);
  } else {
    visibleLevels.value.splice(index, 1);
  }
}

function toggleLogData(logId: string) {
  if (expandedLogs.value.has(logId)) {
    expandedLogs.value.delete(logId);
  } else {
    expandedLogs.value.add(logId);
  }
}

function clearLogs() {
  devLogger.clear();
}

function toggleAutoScroll() {
  autoScroll.value = !autoScroll.value;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatData(data: unknown): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

function getLevelConfig(level: LogLevel) {
  return logLevels.find((l) => l.value === level) || logLevels[1];
}

function scrollToBottom() {
  if (autoScroll.value && logContainer.value) {
    nextTick(() => {
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight;
      }
    });
  }
}

// 订阅日志更新
let unsubscribe: (() => void) | null = null;

onMounted(() => {
  logs.value = devLogger.getLogs();
  unsubscribe = devLogger.subscribe((newLogs) => {
    logs.value = newLogs;
    scrollToBottom();
  });
});

onUnmounted(() => {
  if (unsubscribe) {
    unsubscribe();
  }
});

watch(filteredLogs, () => {
  scrollToBottom();
});
</script>

<template>
  <div class="flex h-full flex-col">
    <!-- 头部 -->
    <div class="flex items-center justify-between border-b border-border/20 px-4 py-3">
      <div class="flex items-center gap-2">
        <Terminal class="h-4 w-4 text-primary" />
        <span class="text-sm font-semibold">调试日志</span>
      </div>
      <div class="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          class="h-7 rounded-lg px-2 text-xs hover:bg-destructive/10 hover:text-destructive"
          @click="clearLogs"
        >
          <Trash2 class="mr-1 h-3 w-3" />
          清空
        </Button>
        <Button
          variant="ghost"
          size="sm"
          :class="[
            'h-7 rounded-lg px-2 text-xs',
            autoScroll ? 'bg-primary/10 text-primary' : ''
          ]"
          @click="toggleAutoScroll"
        >
          {{ autoScroll ? '自动滚动' : '手动滚动' }}
        </Button>
      </div>
    </div>

    <!-- 过滤器 -->
    <div class="flex flex-wrap gap-1.5 border-b border-border/20 px-4 py-2">
      <button
        v-for="level in logLevels"
        :key="level.value"
        :class="[
          'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-medium transition-all',
          visibleLevels.includes(level.value)
            ? level.color
            : 'border-border/40 bg-transparent text-muted-foreground opacity-50'
        ]"
        @click="toggleLevel(level.value)"
      >
        {{ level.label }}
      </button>
    </div>

    <!-- 日志列表 -->
    <div ref="logContainer" class="flex-1 overflow-y-auto">
      <div class="space-y-0.5 p-2">
        <div
          v-if="filteredLogs.length === 0"
          class="flex flex-col items-center justify-center py-10 text-muted-foreground"
        >
          <Terminal class="mb-2 h-8 w-8 opacity-30" />
          <span class="text-xs">暂无日志</span>
        </div>

        <div
          v-for="log in filteredLogs"
          :key="log.id"
          class="group rounded-lg px-2 py-1.5 transition-colors hover:bg-muted/30"
        >
          <div class="flex items-start gap-2">
            <!-- 展开按钮 -->
            <button
              v-if="log.data !== undefined"
              class="mt-0.5 flex-shrink-0 rounded p-0.5 transition-colors hover:bg-muted"
              @click="toggleLogData(log.id)"
            >
              <ChevronRight
                v-if="!expandedLogs.has(log.id)"
                class="h-3 w-3 text-muted-foreground"
              />
              <ChevronDown
                v-else
                class="h-3 w-3 text-muted-foreground"
              />
            </button>
            <div v-else class="w-4 flex-shrink-0" />

            <!-- 时间 -->
            <span class="flex-shrink-0 text-[10px] text-muted-foreground">
              {{ formatTime(log.timestamp) }}
            </span>

            <!-- 级别标签 -->
            <Badge
              variant="outline"
              :class="['flex-shrink-0 px-1.5 py-0 text-[9px]', getLevelConfig(log.level).color]"
            >
              {{ log.level.toUpperCase() }}
            </Badge>

            <!-- 组件名称 -->
            <span class="flex-shrink-0 text-[10px] font-medium text-purple-500">
              [{{ log.component }}]
            </span>

            <!-- 消息 -->
            <span class="min-w-0 flex-1 text-[11px] text-foreground">
              {{ log.message }}
            </span>
          </div>

          <!-- 展开的数据 -->
          <div
            v-if="log.data !== undefined && expandedLogs.has(log.id)"
            class="ml-6 mt-1.5"
          >
            <pre class="overflow-x-auto rounded-lg border border-border/30 bg-muted/30 p-2 text-[10px] font-mono text-muted-foreground">{{ formatData(log.data) }}</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部统计 -->
    <div class="flex items-center justify-between border-t border-border/20 px-4 py-2 text-[10px] text-muted-foreground">
      <span>共 {{ logs.length }} 条日志</span>
      <span v-if="filteredLogs.length !== logs.length">
        显示 {{ filteredLogs.length }} 条
      </span>
    </div>
  </div>
</template>
