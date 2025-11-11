<template>
  <Card>
    <template v-if="!hasChildren">
      <CardHeader v-if="block.title">
        <CardTitle>{{ block.title }}</CardTitle>
        <CardDescription v-if="dataBlock?.stats?.description">
          {{ dataBlock.stats.description }}
        </CardDescription>
      </CardHeader>

      <CardContent>
        <div
          v-if="isEmpty"
          class="flex h-[180px] items-center justify-center text-sm text-muted-foreground"
        >
          暂无内容
        </div>
        <template v-else>
          <div
            v-if="horizontalScroll"
            class="list-scroll-horizontal flex overflow-x-auto pb-1"
            :style="{ gap: horizontalGap }"
          >
            <div
              v-for="item in displayItems"
              :key="itemKey(item)"
              :style="[horizontalWidthStyle, itemContainerStyle(true)]"
              :class="itemContainerClasses(linkField(item), true)"
              @click="handleItemClick(item)"
            >
              <ListPanelItem
                :item="item"
                :compact="compact"
                :show-description="showDescription"
                :show-metadata="showMetadata"
                :show-categories="showCategories"
                :title-key="titleKey"
                :description-key="descriptionKey"
                :author-key="authorKey"
                :pub-date-key="pubDateKey"
                :categories-key="categoriesKey"
              />
            </div>
          </div>

          <div
            v-else
            class="list-scroll flex flex-col overflow-auto pr-1"
            :style="verticalListStyle"
          >
            <div
              v-for="item in displayItems"
              :key="itemKey(item)"
              :class="itemContainerClasses(linkField(item))"
              :style="itemContainerStyle()"
              @click="handleItemClick(item)"
            >
              <ListPanelItem
                :item="item"
                :compact="compact"
                :show-description="showDescription"
                :show-metadata="showMetadata"
                :show-categories="showCategories"
                :title-key="titleKey"
                :description-key="descriptionKey"
                :author-key="authorKey"
                :pub-date-key="pubDateKey"
                :categories-key="categoriesKey"
              />
            </div>
          </div>
        </template>
      </CardContent>
    </template>
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
import type { UIBlock, DataBlock } from '@/shared/types/panel';
import type { ComponentAbility } from '@/shared/componentManifest';
import ListPanelItem from './ListPanelItem.vue';
import { usePanelSizePreset } from '@/composables/usePanelSizePreset';

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const items = (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];
const sizePreset = usePanelSizePreset();

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

const compact = getOption('compact', false);
const maxItems = Number(getOption('max_items', compact ? 6 : 8));
const showDescription = getOption('show_description', getOption('showDescription', true));
const showMetadata = getOption('show_metadata', getOption('showMetadata', true));
const showCategories = getOption('show_categories', getOption('showCategories', true));
const horizontalScroll = getOption('horizontal_scroll', getOption('horizontalScroll', false));
const horizontalItemWidthOption = Number(getOption('item_min_width', getOption('itemMinWidth', 0)));

const titleKey = getProp('title_field', 'title');
const linkKey = getProp('link_field', 'link');
const descriptionKey = getProp('description_field', 'summary');
const pubDateKey = getProp('pub_date_field', 'published_at');
const authorKey = getProp('author_field', 'author');
const categoriesKey = getProp('categories_field', 'categories');

const maxItemsLimit = computed(() => Math.min(maxItems, sizePreset.value.listMaxItems));
const displayItems = computed(() => items.slice(0, maxItemsLimit.value));
const hasChildren = computed(() => (props.block.children?.length ?? 0) > 0);
const isEmpty = computed(() => items.length === 0);
const verticalMaxHeight = computed(
  () => `${sizePreset.value.listRowHeight * sizePreset.value.listVisibleRows}px`
);
const resolvedHorizontalWidth = computed(() =>
  horizontalItemWidthOption > 0 ? horizontalItemWidthOption : sizePreset.value.horizontalItemMinWidth
);
const horizontalWidthStyle = computed(() => ({
  minWidth: `${resolvedHorizontalWidth.value}px`,
}));
const horizontalGap = computed(() => `${0.5 * sizePreset.value.spacingScale}rem`);
const verticalListStyle = computed(() => ({
  maxHeight: verticalMaxHeight.value,
  gap: `${(compact ? 0.18 : 0.4) * sizePreset.value.spacingScale}rem`,
  paddingBottom: compact ? "0.25rem" : "0.4rem",
}));
const itemPadding = computed(() => `${Math.max(6, Math.round(sizePreset.value.cardPadding * (compact ? 0.45 : 0.65)))}px`);
const itemRadius = computed(() => `${Math.max(8, sizePreset.value.cardRadius - (compact ? 6 : 2))}px`);
const itemMinHeight = computed(() => `${Math.round(sizePreset.value.listRowHeight * (compact ? 0.7 : 0.9))}px`);

function linkField(item: Record<string, unknown>): string | null {
  const value = item[linkKey];
  return value ? String(value) : null;
}

function itemKey(item: Record<string, unknown>): string {
  return String(item['id'] ?? item['link'] ?? item['title'] ?? Math.random());
}

function handleItemClick(item: Record<string, unknown>) {
  const link = linkField(item);
  if (link) window.open(link, '_blank', 'noopener,noreferrer');
}

function itemContainerClasses(hasLink: string | null, horizontal = false) {
  return [
    'group border border-border/50 bg-background/60 transition-colors flex flex-col justify-center',
    horizontal ? 'flex-shrink-0' : '',
    hasLink ? 'cursor-pointer hover:border-border hover:bg-accent/15' : '',
  ];
}

function itemContainerStyle(horizontal = false) {
  return {
    padding: itemPadding.value,
    borderRadius: itemRadius.value,
    minHeight: horizontal ? `calc(${itemMinHeight.value} * 0.9)` : itemMinHeight.value,
  };
}
</script>

<style scoped>
.list-scroll::-webkit-scrollbar {
  width: 4px;
}

.list-scroll::-webkit-scrollbar-thumb,
.list-scroll-horizontal::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.4);
}

.list-scroll-horizontal::-webkit-scrollbar {
  height: 4px;
}
</style>
