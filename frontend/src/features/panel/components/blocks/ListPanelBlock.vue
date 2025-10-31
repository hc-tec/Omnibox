<template>
  <div class="list-panel">
    <ol>
      <li v-for="item in displayItems" :key="itemKey(item)">
        <a :href="linkField(item)" target="_blank" rel="noreferrer">
          <span class="title">{{ titleField(item) }}</span>
        </a>
        <p v-if="descriptionField(item)" class="description">
          {{ descriptionField(item) }}
        </p>
        <time v-if="pubDateField(item)" class="time">
          {{ formatDate(pubDateField(item)) }}
        </time>
      </li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import type { ComponentAbility } from "../../../../shared/componentManifest";
import type { UIBlock, DataBlock } from "../../../../shared/types/panel";

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const items = (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];
const maxItems = Number(props.block.options?.maxItems ?? 20);
const displayItems = items.slice(0, maxItems);

function getProp(key: string): string | undefined {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[key]) as string | undefined;
}

function titleField(item: Record<string, unknown>): string {
  const key = getProp("title_field") ?? "title";
  return String(item[key] ?? "");
}

function linkField(item: Record<string, unknown>): string {
  const key = getProp("link_field") ?? "link";
  return String(item[key] ?? "#");
}

function descriptionField(item: Record<string, unknown>): string | null {
  if (props.block.options?.show_description === false) return null;
  const key = getProp("description_field") ?? "description";
  const value = item[key];
  return value ? String(value) : null;
}

function pubDateField(item: Record<string, unknown>): string | null {
  const key = getProp("pub_date_field") ?? "pubDate";
  const value = item[key];
  return value ? String(value) : null;
}

function itemKey(item: Record<string, unknown>): string {
  return String(item["guid"] ?? item["link"] ?? item["title"] ?? Math.random());
}

function formatDate(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN");
}
</script>

<style scoped>
.list-panel {
  height: 100%;
  overflow-y: auto;
}

ol {
  margin: 0;
  padding-left: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

li {
  list-style: decimal;
}

a {
  text-decoration: none;
  color: #1e293b;
}

.title {
  font-weight: 600;
}

.description {
  margin: 4px 0 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.45;
}

.time {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #94a3b8;
}
</style>
