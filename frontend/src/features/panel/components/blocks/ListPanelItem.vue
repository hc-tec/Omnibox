<template>
  <!-- 极简模式：热榜/排行榜样式 -->
  <div v-if="variant === 'minimal'" class="flex items-center gap-3">
    <span
      v-if="showRank"
      class="flex-shrink-0 w-5 text-center font-semibold"
      :class="rankClass"
      :style="{ fontSize: rankSize }"
    >
      {{ rank }}
    </span>
    <span
      class="flex-1 min-w-0 truncate"
      :style="{ fontSize: minimalTitleSize }"
    >
      {{ title }}
    </span>
    <span
      v-if="hotValue"
      class="flex-shrink-0 text-muted-foreground"
      :style="{ fontSize: metaSize }"
    >
      {{ hotValue }}
    </span>
  </div>

  <!-- 标准模式：完整信息展示 -->
  <div v-else class="space-y-1">
    <div :class="compact ? 'mb-0.5' : 'mb-1.5'">
      <h3
        :class="[titleClampClass, compact ? 'font-semibold leading-tight' : 'font-semibold leading-snug']"
        :style="{ fontSize: titleSize }"
      >
        {{ title }}
      </h3>
    </div>

    <p
      v-if="summary && showDescription"
      :class="[summaryClampClass, 'text-muted-foreground']"
      :style="{ fontSize: summarySize }"
    >
      {{ summary }}
    </p>

    <div
      v-if="showMetadata && (author || publishedAt)"
      class="flex flex-wrap items-center text-muted-foreground"
      :class="metaGapClass"
      :style="{ fontSize: metaSize }"
    >
      <span v-if="author" class="flex items-center gap-1.5">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5">
          <path
            d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM12.735 14c.618 0 1.093-.561.872-1.139a6.002 6.002 0 0 0-11.215 0c-.22.578.254 1.139.872 1.139h9.47Z"
          />
        </svg>
        {{ author }}
      </span>

      <Separator v-if="author && publishedAt" orientation="vertical" class="h-3" />

      <span v-if="publishedAt" class="flex items-center gap-1.5">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5">
          <path
            fill-rule="evenodd"
            d="M4 1.75a.75.75 0 0 1 1.5 0V3h5V1.75a.75.75 0 0 1 1.5 0V3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2V1.75ZM4.5 6a1 1 0 0 0-1 1v4.5a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1h-7Z"
            clip-rule="evenodd"
          />
        </svg>
        {{ publishedAt }}
      </span>
    </div>

    <div v-if="showCategories && categories.length" class="flex flex-wrap gap-1 text-muted-foreground">
      <Badge
        v-for="(category, idx) in visibleCategories"
        :key="idx"
        variant="secondary"
        class="text-[10px]"
        :style="{ fontSize: badgeFontSize }"
      >
        {{ category }}
      </Badge>
      <Badge
        v-if="categories.length > visibleCategories.length"
        variant="outline"
        class="text-[10px]"
        :style="{ fontSize: badgeFontSize }"
      >
        +{{ categories.length - visibleCategories.length }}
      </Badge>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';

export type ListVariant = 'minimal' | 'standard';

const props = withDefaults(defineProps<{
  item: Record<string, unknown>;
  compact: boolean;
  showDescription: boolean;
  showMetadata: boolean;
  showCategories: boolean;
  titleKey: string;
  descriptionKey: string;
  authorKey: string;
  pubDateKey: string;
  categoriesKey: string;
  variant?: ListVariant;
  index?: number;
  showRank?: boolean;
  hotKey?: string;
}>(), {
  variant: 'standard',
  index: 0,
  showRank: false,
  hotKey: 'hot',
});

const title = computed(() => getString(props.titleKey) ?? '');
const summary = computed(() => getString(props.descriptionKey));
const author = computed(() => getString(props.authorKey));
const publishedAt = computed(() => formatDate(getString(props.pubDateKey)));
const categories = computed(() => {
  const raw = props.item[props.categoriesKey];
  return Array.isArray(raw) ? raw.map(String) : [];
});

// 排名相关
const rank = computed(() => props.index + 1);
const rankClass = computed(() => {
  if (rank.value <= 3) return 'text-orange-500';
  return 'text-muted-foreground';
});
const rankSize = computed(() => `calc(var(--panel-heading-size, 16px) * 0.9)`);

// 热度值（可选）
const hotValue = computed(() => {
  const value = props.item[props.hotKey];
  if (value == null) return null;
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  if (num >= 10000) return `${(num / 10000).toFixed(1)}万`;
  return String(num);
});

// 标准模式样式
const titleSize = computed(() =>
  props.compact ? `calc(var(--panel-heading-size, 16px) * 0.82)` : `var(--panel-heading-size, 16px)`
);
const summarySize = computed(() => `calc(0.9rem * var(--panel-font-scale, 1))`);
const metaSize = computed(() => `calc(var(--panel-meta-size, 12px) * 0.95)`);
const badgeFontSize = computed(() => `calc(0.8 * var(--panel-meta-size, 12px))`);
const titleClampClass = computed(() => (props.compact ? 'line-clamp-1' : 'line-clamp-2'));
const summaryClampClass = computed(() => (props.compact ? 'line-clamp-1' : 'line-clamp-2'));
const metaGapClass = computed(() => (props.compact ? 'gap-1' : 'gap-2'));
const visibleCategories = computed(() => categories.value.slice(0, props.compact ? 2 : 3));

// 极简模式样式
const minimalTitleSize = computed(() => `calc(var(--panel-heading-size, 16px) * 0.88)`);

function getString(key: string): string | null {
  const value = props.item[key];
  return value != null ? String(value) : null;
}

function formatDate(value: string | null): string | null {
  if (!value) return null;
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return value;
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return '刚刚';
  if (diffMins < 60) return `${diffMins} 分钟前`;
  if (diffHours < 24) return `${diffHours} 小时前`;
  if (diffDays < 7) return `${diffDays} 天前`;

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const currentYear = now.getFullYear();
  return year === currentYear ? `${month}-${day}` : `${year}-${month}-${day}`;
}
</script>
