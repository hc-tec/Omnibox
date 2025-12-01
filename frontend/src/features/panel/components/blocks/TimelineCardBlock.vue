<template>
  <Card class="h-full">
    <CardHeader v-if="block.title">
      <CardTitle>{{ block.title }}</CardTitle>
    </CardHeader>
    <CardContent :class="{ 'pt-6': !block.title }">
      <div v-if="isEmpty" class="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
        暂无数据
      </div>
      <div v-else class="timeline-container overflow-auto pr-2" :style="{ maxHeight: maxHeight }">
        <div class="relative pl-6">
          <!-- 时间线轴 -->
          <div class="absolute left-2 top-2 bottom-2 w-0.5 bg-border" />

          <!-- 时间线项目 -->
          <div
            v-for="(item, index) in displayItems"
            :key="item.id"
            class="relative pb-6 last:pb-0"
          >
            <!-- 节点圆点 -->
            <div
              class="absolute -left-4 top-1 h-3 w-3 rounded-full border-2 border-background"
              :class="getStatusClass(item.status)"
            />

            <!-- 内容区 -->
            <div
              class="rounded-lg border border-border/50 bg-muted/20 p-3 transition-colors hover:bg-muted/40"
              :class="{ 'cursor-pointer': item.link }"
              @click="handleItemClick(item)"
            >
              <!-- 时间戳 -->
              <div class="mb-1 text-xs text-muted-foreground">
                {{ formatTime(item.timestamp) }}
              </div>

              <!-- 标题 -->
              <h4 class="font-medium line-clamp-2" :style="{ fontSize: titleSize }">
                {{ item.title }}
              </h4>

              <!-- 描述 -->
              <p
                v-if="item.description && showDescription"
                class="mt-1 text-muted-foreground line-clamp-2"
                :style="{ fontSize: descSize }"
              >
                {{ item.description }}
              </p>

              <!-- 元数据标签 -->
              <div v-if="item.type" class="mt-2">
                <span
                  class="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary"
                >
                  {{ item.type }}
                </span>
              </div>
            </div>
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

const titleField = getProp('title_field', 'title');
const timestampField = getProp('timestamp_field', 'timestamp');
const descriptionField = getProp('description_field', 'description');
const statusField = getProp('status_field', 'status');
const typeField = getProp('type_field', 'type');
const linkField = getProp('link_field', 'link');
const maxItems = getOption<number>('max_items', 10);
const showDescription = getOption<boolean>('show_description', true);

// 处理数据
interface TimelineItem {
  id: string;
  title: string;
  timestamp: string;
  description: string;
  status: string;
  type: string;
  link: string;
}

const displayItems = computed<TimelineItem[]>(() => {
  return items.value.slice(0, maxItems).map((item, index) => ({
    id: String(item['id'] ?? index),
    title: String(item[titleField] ?? ''),
    timestamp: String(item[timestampField] ?? ''),
    description: String(item[descriptionField] ?? ''),
    status: String(item[statusField] ?? 'default'),
    type: String(item[typeField] ?? ''),
    link: String(item[linkField] ?? ''),
  }));
});

// 状态颜色
function getStatusClass(status: string): string {
  switch (status) {
    case 'completed':
    case 'success':
      return 'bg-green-500';
    case 'pending':
    case 'warning':
      return 'bg-yellow-500';
    case 'error':
    case 'failed':
      return 'bg-red-500';
    case 'active':
    case 'processing':
      return 'bg-blue-500';
    default:
      return 'bg-muted-foreground';
  }
}

// 格式化时间
function formatTime(timestamp: string): string {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return timestamp;

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return '刚刚';
  if (diffMins < 60) return `${diffMins} 分钟前`;
  if (diffHours < 24) return `${diffHours} 小时前`;
  if (diffDays < 7) return `${diffDays} 天前`;

  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// 点击处理
function handleItemClick(item: TimelineItem) {
  if (item.link) {
    window.open(item.link, '_blank', 'noopener,noreferrer');
  }
}

// 响应式尺寸
const maxHeight = computed(() => `${sizePreset.value.listRowHeight * sizePreset.value.listVisibleRows}px`);
const titleSize = computed(() => `${sizePreset.value.headingSize * 0.9}px`);
const descSize = computed(() => `${sizePreset.value.metaSize}px`);
</script>

<style scoped>
.timeline-container::-webkit-scrollbar {
  width: 4px;
}

.timeline-container::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.4);
}
</style>
