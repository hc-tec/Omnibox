<template>
  <Card class="h-full">
    <CardHeader v-if="block.title">
      <CardTitle>{{ block.title }}</CardTitle>
    </CardHeader>
    <CardContent class="flex h-full items-center justify-center" :class="{ 'pt-6': !block.title }">
      <div v-if="isEmpty" class="text-center text-sm text-muted-foreground">
        暂无数据
      </div>
      <div v-else class="flex w-full items-stretch gap-4">
        <!-- 左侧指标 -->
        <div class="flex flex-1 flex-col items-center justify-center rounded-lg bg-muted/30 p-4">
          <div class="mb-1 text-sm text-muted-foreground" :style="{ fontSize: labelSize }">
            {{ leftLabel }}
          </div>
          <div class="font-bold tabular-nums text-primary" :style="{ fontSize: valueSize }">
            {{ formattedLeftValue }}
          </div>
          <div v-if="leftUnit" class="mt-1 text-xs text-muted-foreground">
            {{ leftUnit }}
          </div>
        </div>

        <!-- VS 分隔符 -->
        <div class="flex flex-col items-center justify-center">
          <div
            class="rounded-full bg-muted px-3 py-1 text-xs font-semibold text-muted-foreground"
          >
            VS
          </div>
          <!-- 差值指示 -->
          <div
            v-if="showDiff"
            class="mt-2 text-xs font-medium"
            :class="diffClass"
          >
            {{ diffText }}
          </div>
        </div>

        <!-- 右侧指标 -->
        <div class="flex flex-1 flex-col items-center justify-center rounded-lg bg-muted/30 p-4">
          <div class="mb-1 text-sm text-muted-foreground" :style="{ fontSize: labelSize }">
            {{ rightLabel }}
          </div>
          <div class="font-bold tabular-nums" :class="rightColorClass" :style="{ fontSize: valueSize }">
            {{ formattedRightValue }}
          </div>
          <div v-if="rightUnit" class="mt-1 text-xs text-muted-foreground">
            {{ rightUnit }}
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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

const leftLabelField = getProp('left_label_field', 'left_label');
const leftValueField = getProp('left_value_field', 'left_value');
const leftUnitField = getProp('left_unit_field', 'left_unit');
const rightLabelField = getProp('right_label_field', 'right_label');
const rightValueField = getProp('right_value_field', 'right_value');
const rightUnitField = getProp('right_unit_field', 'right_unit');
const showDiff = getOption<boolean>('show_diff', true);

// 提取值
const leftLabel = computed(() => record.value ? String(record.value[leftLabelField] ?? '左侧') : '左侧');
const rightLabel = computed(() => record.value ? String(record.value[rightLabelField] ?? '右侧') : '右侧');
const leftUnit = computed(() => record.value ? String(record.value[leftUnitField] ?? '') : '');
const rightUnit = computed(() => record.value ? String(record.value[rightUnitField] ?? '') : '');

const leftValue = computed(() => {
  if (!record.value) return 0;
  const val = record.value[leftValueField];
  return typeof val === 'number' ? val : Number(val) || 0;
});

const rightValue = computed(() => {
  if (!record.value) return 0;
  const val = record.value[rightValueField];
  return typeof val === 'number' ? val : Number(val) || 0;
});

// 格式化数值
function formatNumber(val: number): string {
  if (val >= 100000000) return `${(val / 100000000).toFixed(1)}亿`;
  if (val >= 10000) return `${(val / 10000).toFixed(1)}万`;
  return val.toLocaleString();
}

const formattedLeftValue = computed(() => formatNumber(leftValue.value));
const formattedRightValue = computed(() => formatNumber(rightValue.value));

// 差值计算
const diff = computed(() => {
  if (leftValue.value === 0) return 0;
  return ((rightValue.value - leftValue.value) / leftValue.value) * 100;
});

const diffText = computed(() => {
  const d = diff.value;
  if (d > 0) return `+${d.toFixed(1)}%`;
  if (d < 0) return `${d.toFixed(1)}%`;
  return '持平';
});

const diffClass = computed(() => {
  const d = diff.value;
  if (d > 0) return 'text-green-500';
  if (d < 0) return 'text-red-500';
  return 'text-muted-foreground';
});

const rightColorClass = computed(() => {
  const d = diff.value;
  if (d > 0) return 'text-green-500';
  if (d < 0) return 'text-red-500';
  return 'text-foreground';
});

// 响应式尺寸
const labelSize = computed(() => `${sizePreset.value.metaSize}px`);
const valueSize = computed(() => `${Math.round(sizePreset.value.headingSize * 1.5)}px`);
</script>
