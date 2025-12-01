<template>
  <Card class="h-full">
    <CardContent class="flex h-full flex-col justify-center p-6">
      <div v-if="isEmpty" class="text-center text-sm text-muted-foreground">
        暂无数据
      </div>
      <template v-else>
        <!-- 标题行 -->
        <div class="mb-3 flex items-center justify-between">
          <span class="text-sm font-medium" :style="{ fontSize: titleSize }">
            {{ label }}
          </span>
          <span class="font-semibold tabular-nums" :class="colorClass" :style="{ fontSize: valueSize }">
            {{ displayValue }}
          </span>
        </div>

        <!-- 进度条 -->
        <div class="relative h-3 w-full overflow-hidden rounded-full bg-muted">
          <div
            class="absolute left-0 top-0 h-full rounded-full transition-all duration-500"
            :class="barColorClass"
            :style="{ width: `${percentage}%` }"
          />
        </div>

        <!-- 描述 -->
        <div
          v-if="description"
          class="mt-2 text-xs text-muted-foreground"
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

const labelField = getProp('label_field', 'label');
const valueField = getProp('value_field', 'value');
const maxField = getProp('max_field', 'max');
const descriptionField = getProp('description_field', 'description');
const colorTheme = getOption<string>('color', 'primary');
const showPercentage = getOption<boolean>('show_percentage', true);

// 提取值
const label = computed(() => {
  if (!record.value) return props.block.title ?? '';
  return String(record.value[labelField] ?? props.block.title ?? '');
});

const value = computed(() => {
  if (!record.value) return 0;
  const val = record.value[valueField];
  return typeof val === 'number' ? val : Number(val) || 0;
});

const max = computed(() => {
  if (!record.value) return 100;
  const val = record.value[maxField];
  return typeof val === 'number' && val > 0 ? val : 100;
});

const description = computed(() => {
  if (!record.value) return '';
  return String(record.value[descriptionField] ?? '');
});

// 计算百分比
const percentage = computed(() => {
  const p = (value.value / max.value) * 100;
  return Math.min(Math.max(p, 0), 100);
});

// 显示值
const displayValue = computed(() => {
  if (showPercentage) {
    return `${percentage.value.toFixed(1)}%`;
  }
  return `${value.value} / ${max.value}`;
});

// 颜色主题
const colorClass = computed(() => {
  switch (colorTheme) {
    case 'success': return 'text-green-500';
    case 'warning': return 'text-yellow-500';
    case 'error': return 'text-red-500';
    case 'info': return 'text-blue-500';
    default: return 'text-primary';
  }
});

const barColorClass = computed(() => {
  switch (colorTheme) {
    case 'success': return 'bg-green-500';
    case 'warning': return 'bg-yellow-500';
    case 'error': return 'bg-red-500';
    case 'info': return 'bg-blue-500';
    default: return 'bg-primary';
  }
});

// 响应式尺寸
const titleSize = computed(() => `${sizePreset.value.metaSize}px`);
const valueSize = computed(() => `${sizePreset.value.headingSize}px`);
</script>
