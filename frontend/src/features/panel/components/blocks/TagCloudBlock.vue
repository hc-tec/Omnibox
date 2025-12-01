<template>
  <Card class="h-full">
    <CardHeader v-if="block.title">
      <CardTitle>{{ block.title }}</CardTitle>
    </CardHeader>
    <CardContent :class="{ 'pt-6': !block.title }">
      <div v-if="isEmpty" class="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
        暂无数据
      </div>
      <div v-else class="flex flex-wrap items-center justify-center gap-2 py-4" :style="{ minHeight: '180px' }">
        <span
          v-for="(tag, index) in displayTags"
          :key="tag.name"
          class="inline-flex cursor-default items-center rounded-full px-3 py-1 transition-all hover:scale-105"
          :class="getTagColorClass(index)"
          :style="{
            fontSize: getTagFontSize(tag.weight),
            opacity: getTagOpacity(tag.weight),
          }"
          :title="`${tag.name}: ${tag.count}`"
        >
          {{ tag.name }}
          <span v-if="showCount" class="ml-1 text-xs opacity-70">{{ tag.count }}</span>
        </span>
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
const items = computed(() => {
  return (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];
});

const isEmpty = computed(() => items.value.length === 0);

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

const nameField = getProp('name_field', 'name');
const countField = getProp('count_field', 'count');
const maxTags = getOption<number>('max_tags', 30);
const showCount = getOption<boolean>('show_count', false);

// 处理标签数据
interface TagItem {
  name: string;
  count: number;
  weight: number; // 0-1 范围的权重
}

const displayTags = computed<TagItem[]>(() => {
  const tags = items.value.slice(0, maxTags).map((item) => ({
    name: String(item[nameField] ?? ''),
    count: Number(item[countField] ?? 0),
  }));

  if (tags.length === 0) return [];

  // 计算权重（基于 count 的相对大小）
  const counts = tags.map((t) => t.count);
  const minCount = Math.min(...counts);
  const maxCount = Math.max(...counts);
  const range = maxCount - minCount || 1;

  return tags.map((tag) => ({
    ...tag,
    weight: (tag.count - minCount) / range,
  }));
});

// 颜色类（循环使用）
const TAG_COLORS = [
  'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
  'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300',
  'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300',
  'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
  'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
];

function getTagColorClass(index: number): string {
  return TAG_COLORS[index % TAG_COLORS.length];
}

// 根据权重计算字体大小
function getTagFontSize(weight: number): string {
  const minSize = sizePreset.value.metaSize * 0.9;
  const maxSize = sizePreset.value.headingSize * 1.3;
  const size = minSize + weight * (maxSize - minSize);
  return `${Math.round(size)}px`;
}

// 根据权重计算透明度
function getTagOpacity(weight: number): number {
  return 0.6 + weight * 0.4; // 0.6 - 1.0 范围
}
</script>
