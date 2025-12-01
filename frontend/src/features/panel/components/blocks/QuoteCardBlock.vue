<template>
  <Card class="h-full">
    <CardContent class="flex h-full flex-col justify-center p-6">
      <div v-if="isEmpty" class="text-center text-sm text-muted-foreground">
        暂无内容
      </div>
      <template v-else>
        <!-- 引用符号 -->
        <div class="mb-2 text-4xl leading-none text-muted-foreground/30">"</div>

        <!-- 引用内容 -->
        <blockquote
          class="mb-4 text-base font-medium leading-relaxed"
          :class="[compact ? 'line-clamp-3' : 'line-clamp-5']"
          :style="{ fontSize: contentSize }"
        >
          {{ content }}
        </blockquote>

        <!-- 来源信息 -->
        <div class="flex items-center gap-2 text-muted-foreground" :style="{ fontSize: metaSize }">
          <span v-if="author" class="font-medium">— {{ author }}</span>
          <span v-if="author && source" class="text-muted-foreground/50">·</span>
          <span v-if="source" class="truncate">{{ source }}</span>
        </div>

        <!-- 时间 -->
        <div v-if="timestamp" class="mt-2 text-xs text-muted-foreground/70">
          {{ formattedTime }}
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

const contentField = getProp('content_field', 'content');
const authorField = getProp('author_field', 'author');
const sourceField = getProp('source_field', 'source');
const timestampField = getProp('timestamp_field', 'timestamp');
const compact = getOption<boolean>('compact', false);

// 提取值
const content = computed(() => {
  if (!record.value) return '';
  return String(record.value[contentField] ?? '');
});

const author = computed(() => {
  if (!record.value) return '';
  return String(record.value[authorField] ?? '');
});

const source = computed(() => {
  if (!record.value) return '';
  return String(record.value[sourceField] ?? '');
});

const timestamp = computed(() => {
  if (!record.value) return '';
  return String(record.value[timestampField] ?? '');
});

// 格式化时间
const formattedTime = computed(() => {
  if (!timestamp.value) return '';
  const date = new Date(timestamp.value);
  if (isNaN(date.getTime())) return timestamp.value;
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
});

// 响应式尺寸
const contentSize = computed(() => `${sizePreset.value.headingSize}px`);
const metaSize = computed(() => `${sizePreset.value.metaSize}px`);
</script>
