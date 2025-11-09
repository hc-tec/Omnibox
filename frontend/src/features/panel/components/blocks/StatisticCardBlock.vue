<template>
  <Card>
    <CardHeader class="pb-2">
      <CardDescription>{{ metricTitle }}</CardDescription>
    </CardHeader>

    <CardContent>
      <div v-if="isEmpty" class="flex h-[80px] items-center justify-center text-muted-foreground text-sm">
        暂无数据
      </div>

      <div v-else>
        <!-- 主数值 -->
        <div class="flex items-baseline gap-2">
          <div class="text-3xl font-bold tracking-tight">
            {{ formattedValue }}
          </div>
          <div v-if="metricUnit" class="text-sm text-muted-foreground">
            {{ metricUnit }}
          </div>
        </div>

        <!-- 趋势指示 -->
        <div v-if="metricTrend || metricDeltaText" class="mt-2 flex items-center gap-2 text-sm">
          <!-- 趋势图标 -->
          <div
            v-if="trendIcon"
            :class="['flex items-center gap-1', trendColor]"
            v-html="trendIcon"
          ></div>

          <!-- 变化文本 -->
          <span v-if="metricDeltaText" class="text-muted-foreground">
            {{ metricDeltaText }}
          </span>
        </div>

        <!-- 补充说明 -->
        <p v-if="description" class="mt-2 text-xs text-muted-foreground line-clamp-2">
          {{ description }}
        </p>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from '@/components/ui/card';
import type { ComponentAbility } from '@/shared/componentManifest';
import type { UIBlock, DataBlock } from '@/shared/types/panel';

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const record = (props.data ?? props.dataBlock?.records?.[0]) as Record<string, unknown> | null | undefined;

const isEmpty = computed(() => {
  return !record;
});

function resolveField(propName: string, fallback: string): string {
  const camel = propName.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[propName] ?? fallback) as string;
}

const metricTitle = computed(() => {
  if (!record) return '';
  const titleField = resolveField('title_field', 'metric_title');
  return String((record as Record<string, unknown>)[titleField] ?? props.block.title ?? '指标');
});

const metricValue = computed(() => {
  if (!record) return 0;
  const valueField = resolveField('value_field', 'metric_value');
  return Number((record as Record<string, unknown>)[valueField] ?? 0);
});

const metricUnit = computed(() => {
  return record?.['metric_unit'] as string | null ?? null;
});

const metricDeltaText = computed(() => {
  return record?.['metric_delta_text'] as string | null ?? null;
});

const metricTrend = computed(() => {
  if (!record) return null;
  const trendField = resolveField('trend_field', 'metric_trend');
  return (record as Record<string, unknown>)[trendField] as 'up' | 'down' | 'flat' | null ?? null;
});

const description = computed(() => {
  return record?.['description'] as string | null ?? null;
});

const formattedValue = computed(() => {
  return formatNumber(metricValue.value);
});

const trendIcon = computed(() => {
  return getTrendIcon(metricTrend.value);
});

const trendColor = computed(() => {
  return getTrendColor(metricTrend.value);
});

function formatNumber(value: number): string {
  if (value === 0) return '0';

  const absValue = Math.abs(value);

  // 万、亿单位
  if (absValue >= 100000000) {
    return (value / 100000000).toFixed(2) + '亿';
  }
  if (absValue >= 10000) {
    return (value / 10000).toFixed(2) + '万';
  }

  // 千分位分隔
  return value.toLocaleString('zh-CN');
}

function getTrendIcon(trend: 'up' | 'down' | 'flat' | null): string | null {
  if (!trend) return null;

  const icons = {
    up: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4">
      <path fill-rule="evenodd" d="M8 14a.75.75 0 0 1-.75-.75V4.56L4.03 7.78a.75.75 0 0 1-1.06-1.06l4.5-4.5a.75.75 0 0 1 1.06 0l4.5 4.5a.75.75 0 0 1-1.06 1.06L8.75 4.56v8.69A.75.75 0 0 1 8 14Z" clip-rule="evenodd" />
    </svg>`,
    down: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4">
      <path fill-rule="evenodd" d="M8 2a.75.75 0 0 1 .75.75v8.69l3.22-3.22a.75.75 0 1 1 1.06 1.06l-4.5 4.5a.75.75 0 0 1-1.06 0l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.22 3.22V2.75A.75.75 0 0 1 8 2Z" clip-rule="evenodd" />
    </svg>`,
    flat: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4">
      <path d="M2 8a.75.75 0 0 1 .75-.75h10.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 8Z" />
    </svg>`,
  };

  return icons[trend] || null;
}

function getTrendColor(trend: 'up' | 'down' | 'flat' | null): string {
  if (!trend) return 'text-muted-foreground';

  const colors = {
    up: 'text-green-600 dark:text-green-500',
    down: 'text-red-600 dark:text-red-500',
    flat: 'text-gray-500 dark:text-gray-400',
  };

  return colors[trend] || 'text-muted-foreground';
}
</script>
