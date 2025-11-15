<template>
  <div
    class="query-card group relative overflow-hidden rounded-2xl border backdrop-blur-sm transition-all duration-300"
    :class="cardClass"
  >
    <!-- 顶部状态条 -->
    <div class="absolute top-0 left-0 right-0 h-1 transition-all duration-500" :class="statusBarClass" />

    <!-- 状态背景渐变 -->
    <div
      class="absolute inset-0 opacity-0 transition-opacity duration-300"
      :class="backgroundGradient"
    />

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
              <Badge variant="secondary" class="text-[10px]">
                {{ modeText }}
              </Badge>
              <span class="text-[10px] text-muted-foreground">
                {{ relativeTime }}
              </span>
            </div>
            <h3 class="text-sm font-semibold leading-snug text-foreground line-clamp-2">
              {{ card.query }}
            </h3>
          </div>
        </div>

        <!-- 删除按钮（悬停时显示） -->
        <Button
          variant="ghost"
          size="icon"
          class="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity -mr-2 -mt-1 hover:bg-destructive/10 hover:text-destructive"
          @click.stop="$emit('delete', card.id)"
        >
          <X class="h-4 w-4" />
        </Button>
      </div>

      <!-- Body -->
      <div class="px-5 pb-5">
        <!-- Pending 状态：骨架屏 -->
        <div v-if="card.status === 'pending'" class="skeleton-container space-y-3">
          <div class="h-5 w-3/4 animate-pulse rounded-lg bg-muted/50" />
          <div class="space-y-2">
            <div class="h-4 w-full animate-pulse rounded bg-muted/30" />
            <div class="h-4 w-5/6 animate-pulse rounded bg-muted/30" />
            <div class="h-4 w-4/6 animate-pulse rounded bg-muted/30" />
          </div>
        </div>

        <!-- Processing 状态：进度显示 -->
        <div v-else-if="card.status === 'processing'" class="space-y-3">
          <div class="flex items-center gap-2 text-sm">
            <Loader class="h-4 w-4 animate-spin text-blue-500" />
            <span class="text-muted-foreground">{{ card.current_step || '正在处理...' }}</span>
          </div>

          <!-- 进度条 -->
          <div v-if="card.progress !== undefined" class="space-y-1.5">
            <div class="flex items-center justify-between text-xs">
              <span class="text-muted-foreground">进度</span>
              <span class="font-mono text-foreground">{{ card.progress }}%</span>
            </div>
            <div class="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                class="h-full bg-gradient-to-r from-blue-500 to-cyan-500 transition-all duration-500 ease-out"
                :style="{ width: `${card.progress}%` }"
              />
            </div>
          </div>
        </div>

        <!-- Completed 状态：显示结果预览 -->
        <div v-else-if="card.status === 'completed'" class="space-y-3">
          <div class="rounded-xl border border-border/40 bg-muted/20 p-3">
            <p class="text-xs text-muted-foreground">
              查询已完成，生成了 {{ card.panels?.length || 0 }} 个数据面板
            </p>
          </div>
        </div>

        <!-- Error 状态：显示错误 -->
        <div v-else-if="card.status === 'error'">
          <div class="rounded-xl border border-red-500/30 bg-red-500/5 p-3.5 backdrop-blur-sm">
            <div class="flex items-start gap-3">
              <AlertCircle class="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
              <div class="flex-1 space-y-1.5">
                <p class="text-xs font-semibold text-foreground">执行出错</p>
                <p class="text-xs leading-relaxed text-muted-foreground">
                  {{ card.error_message || '未知错误' }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer（仅 completed 状态显示） -->
      <div
        v-if="card.status === 'completed'"
        class="border-t border-border/40 bg-muted/10 px-5 py-3 backdrop-blur-sm"
      >
        <div class="flex items-center justify-between gap-3">
          <span class="text-xs text-muted-foreground">
            点击查看完整结果
          </span>
          <div class="flex gap-2">
            <Button
              v-if="card.refresh_metadata"
              variant="ghost"
              size="sm"
              class="h-8 rounded-lg text-xs"
              @click.stop="$emit('refresh', card.id)"
            >
              <RefreshCw class="h-3.5 w-3.5 mr-1.5" />
              刷新
            </Button>
            <Button
              variant="ghost"
              size="sm"
              class="h-8 rounded-lg text-xs"
              @click.stop="$emit('open', card.id)"
            >
              查看详情
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Loader,
  CheckCircle,
  AlertCircle,
  Sparkles,
  X,
  RefreshCw,
} from 'lucide-vue-next';
import type { QueryCard } from '@/types/queryCard';

interface Props {
  card: QueryCard;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  delete: [cardId: string];
  open: [cardId: string];
  refresh: [cardId: string];
}>();

// ========== 状态图标 ==========
const statusIcon = computed(() => {
  switch (props.card.status) {
    case 'processing':
      return Loader;
    case 'completed':
      return CheckCircle;
    case 'error':
      return AlertCircle;
    case 'pending':
    default:
      return Sparkles;
  }
});

const iconClass = computed(() => ({
  'h-5 w-5 transition-all duration-300': true,
  'animate-spin text-blue-500': props.card.status === 'processing',
  'text-emerald-500': props.card.status === 'completed',
  'text-red-500': props.card.status === 'error',
  'text-primary': props.card.status === 'pending',
}));

const iconContainerClass = computed(() => ({
  'transition-all duration-300': true,
  'bg-blue-500/10 shadow-lg shadow-blue-500/20': props.card.status === 'processing',
  'bg-emerald-500/10 shadow-lg shadow-emerald-500/20': props.card.status === 'completed',
  'bg-red-500/10 shadow-lg shadow-red-500/20': props.card.status === 'error',
  'bg-primary/10 shadow-lg shadow-primary/20': props.card.status === 'pending',
}));

// ========== 状态文本 ==========
const statusText = computed(() => {
  switch (props.card.status) {
    case 'processing':
      return '处理中';
    case 'completed':
      return '已完成';
    case 'error':
      return '出错';
    case 'pending':
      return '等待中';
    default:
      return '未知';
  }
});

const badgeVariant = computed((): 'default' | 'secondary' | 'outline' | 'destructive' => {
  switch (props.card.status) {
    case 'processing':
      return 'default';
    case 'pending':
      return 'secondary';
    case 'completed':
      return 'outline';
    case 'error':
      return 'destructive';
    default:
      return 'outline';
  }
});

// ========== 模式文本 ==========
const modeText = computed(() => {
  return props.card.mode === 'research' ? '研究模式' : '普通查询';
});

// ========== 相对时间 ==========
const relativeTime = ref('');

function updateRelativeTime() {
  const now = Date.now();
  const past = new Date(props.card.created_at).getTime();
  const diffMs = now - past;

  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) {
    relativeTime.value = '刚刚';
  } else if (minutes < 60) {
    relativeTime.value = `${minutes} 分钟前`;
  } else if (hours < 24) {
    relativeTime.value = `${hours} 小时前`;
  } else if (days < 7) {
    relativeTime.value = `${days} 天前`;
  } else {
    // 超过 7 天显示绝对时间
    relativeTime.value = new Date(props.card.created_at).toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
}

// 每分钟更新一次相对时间
let timer: number | null = null;

onMounted(() => {
  updateRelativeTime();
  timer = window.setInterval(updateRelativeTime, 60000);
});

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer);
  }
});

// ========== 样式 ==========
const cardClass = computed(() => ({
  'border-border/30 bg-background/60': true,
  'hover:border-blue-500/40 hover:bg-background/80': props.card.status === 'processing',
  'hover:border-emerald-500/40 hover:bg-background/80': props.card.status === 'completed',
  'hover:border-red-500/40 hover:bg-background/80': props.card.status === 'error',
  'hover:border-primary/40 hover:bg-background/80': props.card.status === 'pending',
  'cursor-pointer': props.card.status === 'completed',
}));

const statusBarClass = computed(() => {
  switch (props.card.status) {
    case 'processing':
      return 'bg-gradient-to-r from-blue-500 via-cyan-500 to-blue-500 animate-pulse';
    case 'completed':
      return 'bg-gradient-to-r from-emerald-500 to-green-500';
    case 'error':
      return 'bg-gradient-to-r from-red-500 to-rose-500';
    case 'pending':
      return 'bg-gradient-to-r from-primary to-purple-500';
    default:
      return 'bg-muted';
  }
});

const backgroundGradient = computed(() => {
  if (props.card.status === 'processing') {
    return 'group-hover:opacity-5 bg-gradient-to-br from-blue-500/20 to-cyan-500/20';
  } else if (props.card.status === 'completed') {
    return 'group-hover:opacity-5 bg-gradient-to-br from-emerald-500/20 to-green-500/20';
  }
  return '';
});
</script>

<style scoped>
.query-card {
  /* 确保变换原点在中心 */
  transform-origin: center;
}

.query-card:hover {
  /* 添加微妙的提升效果 */
  transform: translateY(-2px);
}
</style>
