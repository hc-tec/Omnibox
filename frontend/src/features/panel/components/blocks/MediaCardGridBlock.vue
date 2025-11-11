<template>
  <section
    class="grid overflow-y-auto pr-1"
    :class="columnClass"
    :style="{ maxHeight: maxHeightPx, gap: gridGap }"
  >
    <Card
      v-for="item in displayItems"
      :key="itemKey(item)"
      class="group flex cursor-pointer flex-col overflow-hidden rounded-xl border border-border/50 bg-background/70 shadow-none transition-colors hover:border-border hover:bg-[var(--shell-surface)]/40"
      :style="{ padding: 'var(--panel-card-padding, 16px)' }"
      role="button"
      tabindex="0"
      @click="handleCardClick(item)"
      @keyup.enter="handleCardClick(item)"
    >
      <div class="relative aspect-video w-full overflow-hidden bg-muted/40">
        <img
          v-if="coverField(item)"
          :src="coverField(item)!"
          alt=""
          referrerpolicy="no-referrer"
          crossorigin="anonymous"
          class="h-full w-full object-cover transition duration-500 group-hover:scale-[1.02]"
        />
        <div
          v-else
          class="flex h-full w-full items-center justify-center bg-muted text-3xl font-semibold text-foreground/70"
        >
          {{ titleInitial(item) }}
        </div>
        <span
          v-if="durationField(item)"
          class="pointer-events-none absolute bottom-2 right-2 rounded-sm bg-black/70 px-2 py-0.5 text-[11px] text-white"
        >
          {{ durationField(item) }}
        </span>
      </div>
      <CardContent class="flex flex-col gap-2 px-3 pb-3 pt-3">
        <p class="line-clamp-2 text-sm font-semibold text-foreground transition group-hover:text-primary">
          {{ titleField(item) }}
        </p>
        <div class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground/80">
          <span v-if="authorField(item)">UP {{ authorField(item) }}</span>
          <span v-if="authorField(item) && metaLine(item)" class="text-border">·</span>
          <span v-if="metaLine(item)">{{ metaLine(item) }}</span>
        </div>
        <p v-if="summaryField(item)" class="line-clamp-2 text-xs text-muted-foreground/90">
          {{ summaryField(item) }}
        </p>
        <div v-if="badgesField(item).length" class="flex flex-wrap gap-1 pt-1">
          <Badge v-for="badge in badgesField(item).slice(0, 3)" :key="badge" variant="outline" class="text-[11px]">
            {{ badge }}
          </Badge>
        </div>
      </CardContent>
    </Card>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ComponentAbility } from "@/shared/componentManifest";
import type { UIBlock, DataBlock } from "@/shared/types/panel";
import { usePanelSizePreset } from "@/composables/usePanelSizePreset";

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const items = (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];
const sizePreset = usePanelSizePreset();

function getOption<T>(key: string, fallback: T): T {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  const options = props.block.options ?? {};
  if (camel in options) return options[camel] as T;
  if (key in options) return options[key] as T;
  return fallback;
}

function getProp(key: string, fallback?: string): string | undefined {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[key] ?? (fallback ? props.block.props[fallback] : undefined)) as
    | string
    | undefined;
}

const columns = Math.min(Math.max(Number(getOption("columns", 4)) || 4, 1), 6);
const maxItems = Number(getOption("max_items", 12));
const rows = computed(() =>
  Math.max(Number(getOption("max_rows", sizePreset.value.mediaRows)) || sizePreset.value.mediaRows, 1)
);
const maxItemsLimit = computed(() => Math.min(maxItems, sizePreset.value.mediaMaxItems));
const displayItems = computed(() => items.slice(0, maxItemsLimit.value));
const columnClasses: Record<number, string> = {
  1: "grid-cols-1",
  2: "grid-cols-1 sm:grid-cols-2",
  3: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
  4: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4",
  5: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5",
  6: "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6",
};
const columnClass = computed(() => columnClasses[columns] ?? columnClasses[3]);
const maxHeightPx = computed(() => `${rows.value * sizePreset.value.mediaRowHeight}px`);
const gridGap = computed(() => `calc(var(--panel-grid-gap, 24px) * ${sizePreset.value.spacingScale})`);

function titleField(item: Record<string, unknown>): string {
  const key = getProp("title_field") ?? "title";
  return String(item[key] ?? "");
}

function titleInitial(item: Record<string, unknown>): string {
  const title = titleField(item).trim();
  return title ? title[0]?.toUpperCase() ?? "·" : "·";
}

function linkField(item: Record<string, unknown>): string | null {
  const key = getProp("link_field") ?? "link";
  const value = item[key];
  return value ? String(value) : null;
}

function coverField(item: Record<string, unknown>): string | null {
  const key = getProp("cover_field") ?? "cover_url";
  const value = item[key];
  return value ? String(value) : null;
}

function authorField(item: Record<string, unknown>): string | null {
  const key = getProp("author_field") ?? "author";
  const value = item[key];
  return value ? String(value) : null;
}

function summaryField(item: Record<string, unknown>): string | null {
  const key = getProp("summary_field") ?? "summary";
  const value = item[key];
  return value ? String(value) : null;
}

function durationField(item: Record<string, unknown>): string | null {
  const key = getProp("duration_field") ?? "duration";
  const value = item[key];
  return value ? String(value) : null;
}

function badgesField(item: Record<string, unknown>): string[] {
  const key = getProp("badges_field") ?? "badges";
  const badges = item[key];
  return Array.isArray(badges) ? badges.map((badge) => String(badge)) : [];
}

function metaLine(item: Record<string, unknown>): string | null {
  const viewKey = getProp("view_count_field") ?? "view_count";
  const likeKey = getProp("like_count_field") ?? "like_count";
  const views = formattedCount(item[viewKey]);
  const likes = formattedCount(item[likeKey]);
  if (views && likes) return `${views} 播放 · ${likes} 赞`;
  if (views) return `${views} 播放`;
  if (likes) return `${likes} 赞`;
  const published = item["published_at"];
  return published ? String(published) : null;
}

function formattedCount(value: unknown): string | null {
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) return null;
  return num >= 10000 ? `${(num / 10000).toFixed(1)}万` : `${num}`;
}

function handleCardClick(item: Record<string, unknown>): void {
  const link = linkField(item);
  if (link) {
    window.open(link, "_blank", "noopener,noreferrer");
  }
}

function itemKey(item: Record<string, unknown>): string {
  return String(item["id"] ?? item["link"] ?? item["title"] ?? Math.random());
}
</script>
