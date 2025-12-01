<template>
  <Card class="h-full">
    <CardContent class="flex h-full flex-col items-center justify-center p-6">
      <div v-if="isEmpty" class="text-sm text-muted-foreground">
        暂无数据
      </div>
      <template v-else>
        <!-- 标题 -->
        <div
          v-if="metricTitle"
          class="mb-2 text-sm font-medium text-muted-foreground"
          :style="{ fontSize: titleSize }"
        >
          {{ metricTitle }}
        </div>

        <!-- 主数值 -->
        <div
          class="font-bold tabular-nums"
          :class="colorClass"
          :style="{ fontSize: valueSize }"
        >
          {{ formattedValue }}
        </div>

        <!-- 单位 -->
        <div
          v-if="unit"
          class="mt-1 text-muted-foreground"
          :style="{ fontSize: unitSize }"
        >
          {{ unit }}
        </div>

        <!-- 描述 -->
        <div
          v-if="description"
          class="mt-2 text-center text-xs text-muted-foreground line-clamp-2"
        >
          {{ description }}
        </div>
      </template>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Card, CardContent } from '@/components/ui/card';
import type { UIBlock, DataBlock } from '@/shared/types/panel';
import type { ComponentAbility } from '@/shared/componentManifest';
import { usePanelSizePreset } from '@/composables/usePanelSizePreset';

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const sizePreset = usePanelSizePreset();

// 数据源
const record = computed(() => {
  const items = (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];
  return items[0] ?? null;
});

const isEmpty = computed(() => !record.value);

// 字段映射
function getProp(key: string, fallback: string): string {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[key] ?? fallback) as string;
}

function getOption<T>(key: string, fallback: T): T {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  const options = props.block.options ?? {};
  if (camel in options) return options[camel] as T;
  if (key in options) return options[key] as T;
  return fallback;
}

const titleField = getProp('title_field', 'metric_title');
const valueField = getProp('value_field', 'metric_value');
const unitField = getProp('unit_field', 'unit');
const descriptionField = getProp('description_field', 'description');
const colorTheme = getOption<string>('color', 'default');

// 提取值
const metricTitle = computed(() => {
  if (!record.value) return props.block.title ?? '';
  return String(record.value[titleField] ?? props.block.title ?? '');
});

const metricValue = computed(() => {
  if (!record.value) return 0;
  const val = record.value[valueField];
  return typeof val === 'number' ? val : Number(val) || 0;
});

const unit = computed(() => {
  if (!record.value) return '';
  return String(record.value[unitField] ?? '');
});

const description = computed(() => {
  if (!record.value) return '';
  return String(record.value[descriptionField] ?? '');
});

// 格式化数值
const formattedValue = computed(() => {
  const val = metricValue.value;
  if (val >= 100000000) {
    return `${(val / 100000000).toFixed(1)}亿`;
  }
  if (val >= 10000) {
    return `${(val / 10000).toFixed(1)}万`;
  }
  return val.toLocaleString();
});

// 颜色主题
const colorClass = computed(() => {
  const theme = colorTheme;
  switch (theme) {
    case 'primary':
      return 'text-primary';
    case 'success':
      return 'text-green-500';
    case 'warning':
      return 'text-yellow-500';
    case 'error':
      return 'text-red-500';
    case 'info':
      return 'text-blue-500';
    default:
      return 'text-foreground';
  }
});

// 响应式尺寸
const valueSize = computed(() => `${Math.round(sizePreset.value.headingSize * 2.5)}px`);
const titleSize = computed(() => `${sizePreset.value.metaSize}px`);
const unitSize = computed(() => `${sizePreset.value.metaSize}px`);
</script>
