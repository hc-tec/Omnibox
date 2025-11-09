<template>
  <Card>
    <CardHeader v-if="block.title">
      <CardTitle>{{ block.title }}</CardTitle>
      <CardDescription v-if="dataBlock?.stats?.description">
        {{ dataBlock.stats.description }}
      </CardDescription>
    </CardHeader>

    <CardContent>
      <div v-if="isEmpty" class="flex h-[200px] items-center justify-center text-muted-foreground">
        暂无数据
      </div>

      <div :class="compact ? 'space-y-1' : 'space-y-4'">
        <div
          v-for="item in displayItems"
          :key="itemKey(item)"
          :class="[
            'group rounded-lg border transition-colors',
            compact ? 'p-2' : 'p-4',
            linkField(item) ? 'cursor-pointer hover:bg-accent' : '',
          ]"
          @click="handleItemClick(item)"
        >
          <!-- 标题行 -->
          <div :class="compact ? 'mb-0' : 'mb-2'">
            <h3
              :class="[
                compact ? 'text-sm font-medium' : 'text-base font-semibold',
                'leading-tight',
                linkField(item) ? 'group-hover:text-primary' : '',
              ]"
            >
              {{ titleField(item) }}
            </h3>
          </div>

          <!-- 摘要 -->
          <p
            v-if="descriptionField(item)"
            :class="[
              'line-clamp-2 text-sm text-muted-foreground',
              compact ? 'mb-0 mt-1' : 'mb-2',
            ]"
          >
            {{ descriptionField(item) }}
          </p>

          <!-- 元数据 -->
          <div
            v-if="showMetadata && (authorField(item) || pubDateField(item))"
            class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
          >
            <span v-if="authorField(item)" class="flex items-center gap-1">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 16 16"
                fill="currentColor"
                class="h-3 w-3"
              >
                <path
                  d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM12.735 14c.618 0 1.093-.561.872-1.139a6.002 6.002 0 0 0-11.215 0c-.22.578.254 1.139.872 1.139h9.47Z"
                />
              </svg>
              {{ authorField(item) }}
            </span>

            <Separator
              v-if="authorField(item) && pubDateField(item)"
              orientation="vertical"
              class="h-3"
            />

            <span v-if="pubDateField(item)" class="flex items-center gap-1">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 16 16"
                fill="currentColor"
                class="h-3 w-3"
              >
                <path
                  fill-rule="evenodd"
                  d="M4 1.75a.75.75 0 0 1 1.5 0V3h5V1.75a.75.75 0 0 1 1.5 0V3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2V1.75ZM4.5 6a1 1 0 0 0-1 1v4.5a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1h-7Z"
                  clip-rule="evenodd"
                />
              </svg>
              {{ formatDate(pubDateField(item)) }}
            </span>
          </div>

          <div
            v-if="showCategories && categoriesField(item).length > 0"
            class="mt-1 flex flex-wrap gap-1 text-xs text-muted-foreground"
          >
            <Badge
              v-for="(category, index) in categoriesField(item).slice(0, 3)"
              :key="index"
              variant="secondary"
              class="text-xs"
            >
              {{ category }}
            </Badge>
            <Badge
              v-if="categoriesField(item).length > 3"
              variant="outline"
              class="text-xs"
            >
              +{{ categoriesField(item).length - 3 }}
            </Badge>
          </div>
        </div>
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
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import type { ComponentAbility } from '@/shared/componentManifest';
import type { UIBlock, DataBlock } from '@/shared/types/panel';

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const items = (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];

function getOption<T>(key: string, fallback: T): T {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  const options = props.block.options ?? {};
  if (camel in options) {
    return options[camel] as T;
  }
  if (key in options) {
    return options[key] as T;
  }
  return fallback;
}

// 配置项
const maxItems = Number(getOption('max_items', 20));
const showDescription = getOption('show_description', getOption('showDescription', true));
const showMetadata = getOption('show_metadata', getOption('showMetadata', true));
const showCategories = getOption('show_categories', getOption('showCategories', true));
const compact = getOption('compact', false);

const displayItems = items.slice(0, maxItems);

const isEmpty = computed(() => {
  return items.length === 0;
});

function getProp(key: string): string | undefined {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[key]) as string | undefined;
}

function titleField(item: Record<string, unknown>): string {
  const key = getProp('title_field') ?? 'title';
  return String(item[key] ?? '');
}

function linkField(item: Record<string, unknown>): string | null {
  const key = getProp('link_field') ?? 'link';
  const value = item[key];
  return value ? String(value) : null;
}

function descriptionField(item: Record<string, unknown>): string | null {
  if (!showDescription) return null;
  const key = getProp('description_field') ?? 'summary';
  const value = item[key];
  return value ? String(value) : null;
}

function authorField(item: Record<string, unknown>): string | null {
  const value = item['author'];
  return value ? String(value) : null;
}

function pubDateField(item: Record<string, unknown>): string | null {
  const key = getProp('pub_date_field') ?? 'published_at';
  const value = item[key];
  return value ? String(value) : null;
}

function categoriesField(item: Record<string, unknown>): string[] {
  const value = item['categories'];
  if (Array.isArray(value)) {
    return value.map(String);
  }
  return [];
}

function itemKey(item: Record<string, unknown>): string {
  return String(item['id'] ?? item['link'] ?? item['title'] ?? Math.random());
}

function formatDate(value: string | null): string {
  if (!value) return '';

  try {
    const date = new Date(value);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    // 相对时间
    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins} 分钟前`;
    if (diffHours < 24) return `${diffHours} 小时前`;
    if (diffDays < 7) return `${diffDays} 天前`;

    // 绝对时间
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const currentYear = now.getFullYear();

    if (year === currentYear) {
      return `${month}-${day}`;
    }
    return `${year}-${month}-${day}`;
  } catch {
    return value;
  }
}

function handleItemClick(item: Record<string, unknown>) {
  const link = linkField(item);
  if (link) {
    window.open(link, '_blank');
  }
}
</script>
