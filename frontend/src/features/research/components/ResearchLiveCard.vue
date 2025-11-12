<template>
  <Card class="research-live-card" :class="statusClass">
    <CardHeader>
      <div class="flex items-center justify-between">
        <CardTitle class="text-sm flex items-center gap-2">
          <component :is="statusIcon" :class="iconClass" />
          {{ task.query }}
        </CardTitle>
        <Badge :variant="badgeVariant">{{ statusText }}</Badge>
      </div>
    </CardHeader>

    <CardContent>
      <!-- 处理中：显示执行步骤 -->
      <div v-if="task.status === 'processing'" class="space-y-2">
        <div
          v-for="step in task.execution_steps"
          :key="step.step_id"
          class="flex items-center gap-2 text-sm"
        >
          <CheckCircle v-if="step.status === 'success'" class="h-4 w-4 text-green-500 flex-shrink-0" />
          <Loader v-else class="h-4 w-4 animate-spin text-blue-500 flex-shrink-0" />
          <span class="text-muted-foreground">{{ step.action }}</span>
        </div>
        <div v-if="task.execution_steps.length === 0" class="flex items-center gap-2 text-sm">
          <Loader class="h-4 w-4 animate-spin text-blue-500" />
          <span class="text-muted-foreground">初始化中...</span>
        </div>
      </div>

      <!-- 等待人工输入：显示提示 -->
      <div v-else-if="task.status === 'human_in_loop'" class="space-y-3">
        <Alert>
          <AlertCircle class="h-4 w-4" />
          <AlertTitle>需要您的输入</AlertTitle>
          <AlertDescription>
            {{ task.human_request?.message || '等待响应...' }}
          </AlertDescription>
        </Alert>
        <p class="text-xs text-muted-foreground">
          请在右下角的 "行动收件箱" 中回复
        </p>
      </div>

      <!-- 完成：显示最终报告 -->
      <div v-else-if="task.status === 'completed'" class="prose prose-sm max-w-none dark:prose-invert">
        <p class="text-sm">{{ task.final_report }}</p>
      </div>

      <!-- 错误：显示错误信息 -->
      <div v-else-if="task.status === 'error'">
        <Alert variant="destructive">
          <AlertCircle class="h-4 w-4" />
          <AlertTitle>错误</AlertTitle>
          <AlertDescription>
            {{ task.error }}
          </AlertDescription>
        </Alert>
      </div>

      <div v-if="task.previews && task.previews.length" class="mt-4 space-y-3">
        <div
          v-for="preview in task.previews"
          :key="preview.preview_id"
          class="rounded-xl border border-border/60 bg-muted/20 p-3"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-semibold">{{ preview.title }}</p>
            <Badge variant="outline">实时</Badge>
          </div>
          <ul class="mt-2 space-y-1 text-xs text-muted-foreground">
            <li
              v-for="(item, idx) in preview.items"
              :key="`${preview.preview_id}-${idx}`"
              class="truncate"
            >
              {{ formatPreviewItem(item) }}
            </li>
            <li v-if="preview.items.length === 0" class="text-muted-foreground/70">暂无数据</li>
          </ul>
        </div>
      </div>

      <div
        v-if="task.metadata"
        class="mt-4 border-t border-border/60 pt-3 text-[12px] text-muted-foreground space-y-1"
      >
        <div v-if="task.metadata.task_id"><span class="font-semibold">任务ID：</span><code>{{ task.metadata.task_id }}</code></div>
        <div v-if="task.metadata.thread_id"><span class="font-semibold">线程：</span><code>{{ task.metadata.thread_id }}</code></div>
        <div v-if="task.metadata.total_steps"><span class="font-semibold">总步骤：</span>{{ task.metadata.total_steps }}</div>
        <div v-if="task.metadata.data_stash_count !== undefined"><span class="font-semibold">缓存片段：</span>{{ task.metadata.data_stash_count }}</div>
      </div>
    </CardContent>

    <CardFooter v-if="task.status === 'completed' || task.status === 'error'" class="justify-between">
      <span class="text-xs text-muted-foreground">
        {{ task.execution_steps.length }} 步骤完成
      </span>
      <Button variant="ghost" size="sm" @click="$emit('delete', task.task_id)">
        删除
      </Button>
    </CardFooter>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { CheckCircle, Loader, AlertCircle, Brain, Sparkles } from 'lucide-vue-next';
import type { ResearchTask } from '../types/researchTypes';

interface Props {
  task: ResearchTask;
}

const props = defineProps<Props>();

defineEmits<{
  delete: [taskId: string];
}>();

const statusIcon = computed(() => {
  switch (props.task.status) {
    case 'processing':
      return Loader;
    case 'human_in_loop':
      return Brain;
    case 'completed':
      return CheckCircle;
    case 'error':
      return AlertCircle;
    default:
      return Sparkles;
  }
});

const iconClass = computed(() => ({
  'h-4 w-4': true,
  'animate-spin text-blue-500': props.task.status === 'processing',
  'text-yellow-500': props.task.status === 'human_in_loop',
  'text-green-500': props.task.status === 'completed',
  'text-red-500': props.task.status === 'error',
}));

const statusText = computed(() => {
  switch (props.task.status) {
    case 'processing':
      return '处理中';
    case 'human_in_loop':
      return '等待回复';
    case 'completed':
      return '已完成';
    case 'error':
      return '错误';
    default:
      return '空闲';
  }
});

const badgeVariant = computed((): 'default' | 'secondary' | 'outline' | 'destructive' => {
  switch (props.task.status) {
    case 'processing':
      return 'default';
    case 'human_in_loop':
      return 'secondary';
    case 'completed':
      return 'outline';
    case 'error':
      return 'destructive';
    default:
      return 'outline';
  }
});

const statusClass = computed(() => ({
  'border-2 transition-colors': true,
  'border-blue-500': props.task.status === 'processing',
  'border-yellow-500': props.task.status === 'human_in_loop',
  'border-green-500': props.task.status === 'completed',
  'border-red-500': props.task.status === 'error',
}));

const formatPreviewItem = (item: Record<string, unknown> | undefined) => {
  if (!item || typeof item !== 'object') {
    return String(item ?? '');
  }
  return Object.entries(item)
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${String(value ?? '')}`)
    .join(' · ');
};
</script>
